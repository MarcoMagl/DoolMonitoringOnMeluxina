#!/bin/bash -l
# Copyright (c) 2026 Marco Magliulo, Xavier Besseron - LuxProvide
#SBATCH --job-name="lustre-io-monitoring"
#SBATCH --qos default
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --partition gpu
#SBATCH --gpus-per-node=1
#SBATCH --output=%x.out
#SBATCH --error=%x.out
#SBATCH --time=00:20:00

set -e

mkdir -p dooloutput
export DOOL_OUTPUT=$PWD/dooloutput/dool_profiling_${SLURM_JOBID}.csv

module purge
ml CUDA

cd ..
source setup_dool_and_venv.sh
cd -

# The workload uses PyTorch (CUDA) to load batches onto the GPU and pynvml
# (already installed by setup_dool_and_venv.sh) to report GPU memory.
uv pip install --quiet torch >/dev/null 2>&1 || echo "Warning: torch install failed, continuing CPU-only"

# ---------------------------------------------------------------------------
# The workload prints a wall-clock timestamp for every step (see the [STEP]
# log lines). dool records in parallel, so those timestamps line up with the
# dsk/net/paging panels of the dool output and let you correlate the two.
# ---------------------------------------------------------------------------
dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output=$DOOL_OUTPUT &
DOOL_PID=$!

python lustre_io_workload.py \
    --data-dir "$PWD/lustre_data" \
    --num-files 32 \
    --file-size-mb 128 \
    --features 256 \
    --num-steps 100 \
    --files-per-step 4 \
    --batch-size 1048576 \
    --keep-data

kill $DOOL_PID 2>/dev/null
wait $DOOL_PID 2>/dev/null

echo "Starting post-processing of dool output ! "

export DOOL_PLOTS=$PWD/dooloutput/dool_result_profiling_${SLURM_JOBID}
bash ../run_postprocess.sh $DOOL_OUTPUT $DOOL_PLOTS.pdf
