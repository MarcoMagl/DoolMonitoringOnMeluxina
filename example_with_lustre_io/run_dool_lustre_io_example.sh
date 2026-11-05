#!/bin/bash -l
# Copyright (c) 2026 Marco Magliulo, Xavier Besseron - LuxProvide
#
# Example Slurm job: record system + NVIDIA GPU metrics with the containerized
# `dool` while a Lustre IO + GPU batch-loading workload runs.
#
# Build the image once first (from the repository root):
#     apptainer build dool.sif dool-monitoring.def

#SBATCH --job-name="lustre-io-monitoring"
#SBATCH --qos default
#SBATCH --partition gpu
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --output=%x.out
#SBATCH --error=%x.out
#SBATCH --time=00:20:00

# CUDA for the workload (PyTorch). The workload itself is optional-CUDA: it falls
# back to NumPy on CPU if torch is unavailable.
ml CUDA
ml Apptainer
ml Python

# set -euo pipefail

# Repository root (this script lives in example_with_lustre_io/) and image.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIF="${SIF:-$REPO_ROOT/dool.sif}"
if [ ! -f "$SIF" ]; then
    echo "Error: $SIF not found. Build it first:" >&2
    echo "    apptainer build $SIF $REPO_ROOT/dool-monitoring.def" >&2
    exit 1
fi

export DOOL_OUTPUT_DIR=$REPO_ROOT/example_with_lustre_io/dooloutput
export DOOL_OUTPUT_CSV=$DOOL_OUTPUT_DIR/dool_profiling_${SLURM_JOBID}.csv
export DOOL_OUTPUT_PLOTS="$DOOL_OUTPUT_DIR/dool_result_profiling_${SLURM_JOBID}.pdf"

mkdir -p $DOOL_OUTPUT_DIR 


apptainer exec --nv     docker://pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime     python -c "import torch; print(torch.__version__); print(torch.cuda.is_available())"
# Record metrics with the container (GPU via --nv), in the background, every
# second. The workload's [STEP] timestamps use the same clock, so they line up
# with the dsk/net/paging panels afterwards.
set -m
apptainer exec -B $DOOL_OUTPUT_DIR --nv "$SIF" \
    dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output="$DOOL_OUTPUT_CSV" &
DOOL_PID=$!


apptainer exec --nv  -B $DOOL_OUTPUT_DIR -B $REPO_ROOT -B $PWD docker://pytorch/pytorch:2.15.0-cuda13.2-cudnn9-runtime \
    python $REPO_ROOT/example_with_lustre_io/lustre_io_workload.py \
        --data-dir "$PWD/lustre_data" \
        --num-files 32 \
        --file-size-mb 128 \
        --features 256 \
        --num-steps 100 \
        --files-per-step 4 \
        --batch-size 1048576 \
        --keep-data

# Stop the whole process group (apptainer + dool), not just the wrapper PID.
kill -TERM -- -"$DOOL_PID" 2>/dev/null || true
wait "$DOOL_PID" 2>/dev/null || true

# Plot the recorded CSV with the container's post-processor.
# Plot the recorded CSV with the container's post-processor.
echo "Starting post-processing of dool output ! "
apptainer exec -B $DOOL_OUTPUT_DIR --nv "$SIF" bash /opt/dool-monitoring/run_postprocess.sh "$DOOL_OUTPUT_CSV" "$DOOL_OUTPUT_PLOTS"

# The workload venv is local to this example; drop it.
# deactivate 2>/dev/null || true
