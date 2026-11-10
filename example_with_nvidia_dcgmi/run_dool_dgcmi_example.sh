#!/bin/bash -l
# Copyright (c) 2026 Marco Magliulo, Xavier Besseron - LuxProvide
#
# Example Slurm job: record system + NVIDIA GPU metrics with the containerized
# `dool`, while `dcgmi` runs on the node as the (GPU-loading) workload.
#
# Build the image once first (from the repository root):
#     apptainer build dool.sif dool-monitoring.def

#SBATCH --job-name="dcgmi-monitoring"
#SBATCH --qos default
#SBATCH --partition gpu
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --gpus-per-node=1
#SBATCH --output=%x.out
#SBATCH --error=%x.err
#SBATCH --time=00:15:00

set -euo pipefail
# dcgmi is provided by the CUDA/DCGM environment on the compute node.
ml CUDA
ml Apptainer

# Repository root (this script lives in example_with_nvidia_dcgmi/) and image.
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SIF="${SIF:-$REPO_ROOT/dool.sif}"
if [ ! -f "$SIF" ]; then
    echo "Error: $SIF not found. Build it first:" >&2
    echo "    apptainer build $SIF $REPO_ROOT/dool-monitoring.def" >&2
    exit 1
fi

export DOOL_OUTPUT_DIR=$REPO_ROOT/example_with_nvidia_dcgmi/dooloutput
mkdir -p $DOOL_OUTPUT_DIR
export DOOL_OUTPUT_CSV=$DOOL_OUTPUT_DIR/dool_profiling_${SLURM_JOBID}.csv
export DOOL_OUTPUT_PLOTS="$DOOL_OUTPUT_DIR/dool_result_profiling_${SLURM_JOBID}.png"


# Record metrics with the container (GPU libraries injected via --nv), in the
# background, every second. `set -m` (monitor mode) puts the recording in its
# own process group: `apptainer exec` spawns dool as a child, so killing the
# wrapper PID alone would leave dool running.
set -m
apptainer exec \
    -B $DOOL_OUTPUT_DIR \
    --nv "$SIF" \
    dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output="$DOOL_OUTPUT_CSV" &
DOOL_PID=$!

# Workload being monitored (runs on the node, not in the container).
dcgmi diag -r 2

# Stop the whole process group (apptainer + dool), not just the wrapper PID.
kill -TERM -- -"$DOOL_PID" 2>/dev/null || true
wait "$DOOL_PID" 2>/dev/null || true

# Plot the recorded CSV with the container's post-processor.
echo "Starting post-processing of dool output ! "
apptainer exec --nv -B $DOOL_OUTPUT_DIR "$SIF" bash /opt/dool-monitoring/run_postprocess.sh "$DOOL_OUTPUT_CSV" "$DOOL_OUTPUT_PLOTS"
