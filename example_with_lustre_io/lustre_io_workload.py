#!/usr/bin/env python3
"""
Lustre IO-intensive workload with GPU batch loading.

The workload has two phases, both of which stress the Lustre filesystem that
backs the current working directory:

1. Dataset creation - write a number of random dataset files to disk. This
   stresses Lustre *writes*.
2. Batch loading   - repeatedly pick random dataset files, read them back from
   Lustre, assemble a batch and copy it onto the GPU. This stresses Lustre
   *reads* and the host -> device transfer.

Every phase and every training step is logged with a wall-clock timestamp (and,
when available, the GPU memory usage). Because the timestamps use the same clock
as the Slurm log and the `dool` CSV recorded in parallel, the two can be
correlated afterwards: a spike in `dsk/...` or `net/...` in the dool output
lines up with the "[STEP ...]" read lines below.

Copyright (c) 2026 Marco Magliulo, Xavier Besseron - LuxProvide
"""

import argparse
import os
import sys
import time
from datetime import datetime

import numpy as np

# --- Optional GPU back-ends (the workload also runs CPU-only) ---------------
try:
    import torch
except Exception:  # torch is optional; fall back to NumPy on CPU
    torch = None

try:
    import pynvml

    PYNVML_OK = True
except Exception:
    pynvml = None
    PYNVML_OK = False

BYTES_PER_RECORD_FEATURE = 4  # float32


def timestamp():
    """Local wall-clock timestamp, ISO-8601, e.g. 2026-10-27T13:31:04.

    Local time (not UTC) is used on purpose so the log lines line up with the
    Slurm log and the dool CSV, which both use the node's local time.
    """
    return datetime.now().strftime("%Y-%m-%dT%H:%M:%S")


def log(msg):
    """Emit a single, greppable, timestamped log line and flush immediately."""
    print(f"{timestamp()} {msg}", flush=True)


# --- GPU helpers ------------------------------------------------------------

def init_gpu(use_cuda):
    """Return (device, gpu_handle). ``gpu_handle`` is a pynvml handle or None."""
    device = "cpu"
    gpu_handle = None

    if use_cuda and torch is not None and torch.cuda.is_available():
        device = "cuda"
        log(f"[GPU] CUDA is available: {torch.cuda.get_device_name(0)} "
            f"({torch.cuda.get_device_properties(0).total_memory / 1024**3:.1f} GiB)")
    else:
        log("[GPU] CUDA unavailable - running on CPU (install a CUDA build of "
            "PyTorch and request a GPU to exercise the device transfer).")

    if device == "cuda" and PYNVML_OK:
        try:
            pynvml.nvmlInit()
            gpu_handle = pynvml.nvmlDeviceGetHandleByIndex(0)
        except Exception as exc:  # pragma: no cover
            log(f"[GPU] pynvml init failed ({exc}); GPU memory will not be reported.")
            gpu_handle = None

    return device, gpu_handle


def gpu_memory_used_gb(gpu_handle):
    """Used GPU memory in GiB, or None if it cannot be read."""
    if gpu_handle is None:
        return None
    try:
        info = pynvml.nvmlDeviceGetMemoryInfo(gpu_handle)
        return info.used / 1024**3
    except Exception:  # pragma: no cover
        return None


# --- Phase 1: dataset creation ----------------------------------------------

def create_datasets(data_dir, num_files, file_size_mb, features):
    """Write ``num_files`` random float32 files of ~``file_size_mb`` each.

    Returns the per-file record count so phase 2 can reshape raw reads.
    """
    os.makedirs(data_dir, exist_ok=True)
    record_bytes = BYTES_PER_RECORD_FEATURE * features
    n_records = (file_size_mb * 1024 * 1024) // record_bytes
    n_bytes = n_records * record_bytes

    log(f"[CREATE] start data_dir={data_dir} num_files={num_files} "
        f"file_size_mb={file_size_mb} features={features} "
        f"records_per_file={n_records} "
        f"total_mb={num_files * file_size_mb}")

    t_phase = time.time()
    rng = np.random.default_rng(0)
    for i in range(num_files):
        path = os.path.join(data_dir, f"shard_{i:05d}.bin")
        t0 = time.time()
        # Write in one shot so the full size hits Lustre at once.
        rng.standard_normal(n_records * features, dtype=np.float32).tofile(path)
        written_mb = os.path.getsize(path) / (1024 * 1024)
        log(f"[CREATE] file {i:04d}/{num_files - 1:04d} {os.path.basename(path)} "
            f"size_mb={written_mb:.1f} write_s={time.time() - t0:.3f}")
    log(f"[CREATE] done total_s={time.time() - t_phase:.3f}")

    return n_records


# --- Phase 2: random batch loading ------------------------------------------

def load_batch(paths, batch_size, features, n_records, device, tensor):
    """Read random rows from ``paths`` into a batch on ``device``.

    When ``tensor`` (a reusable GPU tensor) is provided the numpy batch is
    copied into it in place, avoiding repeated allocations on the device.
    Returns the number of bytes read from disk.
    """
    rows_per_file = max(1, batch_size // len(paths))
    chunks = []
    bytes_read = 0
    for path in paths:
        size = os.path.getsize(path)
        record_bytes = BYTES_PER_RECORD_FEATURE * features
        count = min(rows_per_file, size // record_bytes)
        with open(path, "rb") as fh:
            # Random seek to a record boundary -> true random access on Lustre.
            max_off = (size // record_bytes - count) * record_bytes
            if max_off > 0:
                fh.seek(int(np.random.randint(0, max_off)))
            arr = np.fromfile(fh, dtype=np.float32, count=count * features)
        bytes_read += arr.nbytes
        chunks.append(arr)

    batch = np.concatenate(chunks)
    batch = batch[: rows_per_file * len(paths) * features]
    batch = batch.reshape(-1, features)

    if device == "cuda" and torch is not None:
        if tensor is None:
            tensor = torch.empty(batch.shape, dtype=torch.float32, device=device)
        tensor.copy_(torch.from_numpy(batch))
    else:
        tensor = batch

    return tensor, bytes_read


def run_batch_loading(data_dir, num_files, num_steps, files_per_step,
                      batch_size, features, n_records, device, gpu_handle):
    paths = [os.path.join(data_dir, f"shard_{i:05d}.bin")
             for i in range(num_files)
             if os.path.exists(os.path.join(data_dir, f"shard_{i:05d}.bin"))]
    if not paths:
        log("[LOAD] ERROR: no dataset files found - run phase 1 first.")
        return

    log(f"[LOAD] start num_steps={num_steps} files_per_step={files_per_step} "
        f"batch_size={batch_size} num_files_on_disk={len(paths)}")

    tensor = None
    t_phase = time.time()
    for step in range(num_steps):
        step_files = list(np.random.choice(paths, size=min(files_per_step, len(paths)),
                                            replace=False))
        t_step = time.time()

        t_read = time.time()
        tensor, bytes_read = load_batch(step_files, batch_size, features,
                                        n_records, device, tensor)
        read_s = time.time() - t_read

        gpu_mem = gpu_memory_used_gb(gpu_handle)
        mem_str = f" gpu_mem_used_gb={gpu_mem:.2f}" if gpu_mem is not None else ""

        log(f"[STEP] {step:04d}/{num_steps - 1:04d} "
            f"files=[{','.join(os.path.basename(p) for p in step_files)}] "
            f"read_mb={bytes_read / (1024 * 1024):.1f} read_s={read_s:.3f} "
            f"throughput_mbps={bytes_read / (1024 * 1024) / read_s if read_s else 0:.0f}"
            f"{mem_str} step_s={time.time() - t_step:.3f}")

    log(f"[LOAD] done total_s={time.time() - t_phase:.3f}")


# --- Entry point ------------------------------------------------------------

def parse_args():
    p = argparse.ArgumentParser(description=__doc__,
                                formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--data-dir", default="lustre_data",
                   help="Directory (on Lustre) where datasets are created "
                        "(default: ./lustre_data)")
    p.add_argument("--num-files", type=int, default=32,
                   help="Number of dataset files to create (default: 32)")
    p.add_argument("--file-size-mb", type=int, default=128,
                   help="Size of each dataset file in MB (default: 128)")
    p.add_argument("--features", type=int, default=256,
                   help="Feature dimension of each record (default: 256)")
    p.add_argument("--num-steps", type=int, default=100,
                   help="Number of random-batch loading steps (default: 100)")
    p.add_argument("--files-per-step", type=int, default=4,
                   help="Dataset files read per step (default: 4)")
    p.add_argument("--batch-size", type=int, default=1048576,
                   help="Records per batch (default: 1048576)")
    p.add_argument("--cpu", action="store_true",
                   help="Force CPU even if a GPU is available")
    p.add_argument("--keep-data", action="store_true",
                   help="Do not remove the dataset directory at the end")
    return p.parse_args()


def main():
    args = parse_args()
    use_cuda = not args.cpu

    log("[INFO] workload start " + " ".join(f"{k}={v}" for k, v in vars(args).items()))

    device, gpu_handle = init_gpu(use_cuda)

    # Phase 1: create the datasets on the current (Lustre) directory.
    n_records = create_datasets(args.data_dir, args.num_files,
                                args.file_size_mb, args.features)

    # Phase 2: import random batches from Lustre onto the GPU.
    run_batch_loading(args.data_dir, args.num_files, args.num_steps,
                      args.files_per_step, args.batch_size, args.features,
                      n_records, device, gpu_handle)

    if gpu_handle is not None:
        try:
            pynvml.nvmlShutdown()
        except Exception:  # pragma: no cover
            pass

    if not args.keep_data:
        log(f"[INFO] cleaning up dataset directory {args.data_dir}")
        import shutil

        shutil.rmtree(args.data_dir, ignore_errors=True)

    log("[INFO] workload done")


if __name__ == "__main__":
    main()
