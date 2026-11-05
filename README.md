# Dool Monitoring on Slurm HPC (Meluxina)

Track system resource usage on a compute node during a Slurm job with [dool](https://github.com/scottchiefbaker/dool), then plot the results.
We also include here the possibility to monitor GPU activity.

Everything is packaged into an [Apptainer](https://apptainer.org/) image, so it runs the same way on
any node with no per-user Python setup. GPU access is a **run-time** concern only:
`pynvml` picks up `libnvidia-ml.so` from the host driver via `apptainer exec --nv`, so the image
builds even on a machine without a GPU.

## Build

On Meluxina (or any host with Apptainer) — no registry account and no image push required:

```bash
apptainer build dool.sif dool-monitoring.def
```

The recipe ([dool-monitoring.def](dool-monitoring.def)) bootstraps from the public `python:3.11-slim`
base and runs [setup_dool_and_venv.sh](setup_dool_and_venv.sh) used to set up `dool` by hand:
it installs `dool`, the NVIDIA GPU plugins from [dool_plugins/](dool_plugins/) and the plotting
dependencies (`matplotlib`, `pandas`, `nvidia-ml-py`).

## Record metrics for a node with NVIDIA GPU

On a GPU node, grant GPU access with `--nv` and record the metrics you want:

```bash
apptainer exec --nv dool.sif \
    dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output=metrics.csv
```

Run it in the background while your workload runs, then stop it:

```bash
apptainer exec --nv dool.sif dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output=metrics.csv &
# ... run your workload ...
# stop the recording once you are done
```

## Record metrics for a node without GPU

On a machine without an NVIDIA GPU (or if you omit `--nv`), drop the `--nvidia-gpu*` flags and `dool`
records its CPU / disk / network / paging / system / memory panels instead:

```bash
apptainer exec dool.sif dool -tTcdngym 1 --output=metrics.csv
```

## Plot the recorded CSV

The image also ships [run_postprocess.sh](run_postprocess.sh) / [dool_postprocess.py](dool_postprocess.py),
which turn a `dool` CSV into a multi-panel plot:

```bash
apptainer exec dool.sif bash /opt/dool-monitoring/run_postprocess.sh metrics.csv metrics.pdf
```

## Examples

We provided a couple of examples ready to be run on the compute node of Meluxina.
The goal is to see how `dool` can be used to monitor the hardware acivity of different workloads.

### `nvidia-dcgmi` example

`nvidia-dcgmi` is a binary readibly available on Meluxina GPU compute nodes.
It can be used to make a quick check on the performances of a GPU card

to launch it:

```bash
sbatch example_with_nvidia_dcgmi/run_dool_dgcmi_example.sh
```

This slurm job will run `dcgmi`, monitor the activity of the node in the background and plot he metrics collected at the end.
The result is written to `dooloutput/dool_result_profiling_<JOBID>.pdf`:

An example of output can be found below

![Dool monitoring plot](example_with_nvidia_dcgmi/dooloutput/dool_result_profiling_5387572.png)

### Lustre-io intensive example

`lustre_io_workload.py` is an I/O-intensive workload that stresses the Lustre filesystem backing the
compute node while loading data batches onto the GPU. Unlike `dcgmi`, it ships its own script and
installs its dependencies (`torch`, `nvidia-ml-py`) on the node via `uv`, falling back to NumPy on CPU
if CUDA is unavailable.

to launch it:

```bash
sbatch example_with_lustre_io/run_dool_lustre_io_example.sh
```

This Slurm job runs the workload in the foreground and `dool` in the background, then plots the metrics collected at the end. The result is written to `dooloutput/dool_result_profiling_<JOBID>.pdf`:

It has two phases, both of which hit Lustre: a **dataset-creation** phase that writes 32×128 MB files (`lustre_data/shard_*.bin`), stressing Lustre *writes*, followed by a **batch-loading** phase that reads random files back and copies them onto the GPU, stressing Lustre *reads* and the host → device transfer.

Every phase and step is logged with a wall-clock timestamp (and the used GPU memory in the `[STEP]` lines). Because the timestamps share the same clock as the Slurm log and the `dool` CSV, a spike in the `dsk/...` / `net/...` panels lines up with the `[STEP]` read lines, so the Lustre activity can be correlated with what the workload was doing at that moment.

An example of output can be found below

![Dool monitoring plot](example_with_lustre_io/dooloutput/dool_result_profiling_5387572.png)
