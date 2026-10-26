#!/bin/bash -l
# Copyright (c) 2026 Marco Magliulo, Xavier Besseron - LuxProvide
#SBATCH --job-name="dcgmi-monitoring""
#SBATCH --qos default 
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --output=%j/%x.out
#SBATCH --error=%j/%x.out
#SBATCH --time=00:15:00

export ROOT_OUTPUT="$PWD/dcgmi-monitoring"
mkdir -p $ROOT_OUTPUT 

module purge 
ml CUDA 

source setup_dool_and_venv.sh

mkdir -p dooloutput
export DOOL_OUTPUT=$ROOT_OUTPUT/dooloutput/dool_profiling_${SLURM_JOBID}.csv

# we record the different metrics we chose via the flags we give to the command every 1 second 
dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output=$DOOL_OUTPUT &
DOOL_PID=$!

dcgmi diag -r 2

kill $DOOL_PID 2>/dev/null
wait $DOOL_PID 2>/dev/null

echo "Starting post-processing of dool output ! "

export DOOL_PLOTS=$PWD/dooloutput/dool_result_profiling_${SLURM_JOBID}
bash run_postprocess.sh $DOOL_OUTPUT $DOOL_PLOTS.pdf



