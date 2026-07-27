
#!/bin/bash -l
#SBATCH --job-name="TestJobMonitoringWithDool""
#SBATCH -N 1
#SBATCH --ntasks=1
#SBATCH --output=slurm-ReFrameCheck-%x-%j.out
#SBATCH --error=slurm-ReFrameCheck-%x-%j.out
#SBATCH --time=00:01:00

module purge 


python3.11 -m venv PostProcessEnv 
source PostProcessEnv/bin/activate
python -m pip install matplotlib pandas pynvml 


ml CUDA 

source setup_dool.sh

mkdir -p dooloutput
export DOOL_OUTPUT=$PWD/dooloutput/dool_profiling_${SLURM_JOBID}.csv

# we record the different metrics we chose via the flags we give to the command every 1 second 
dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output=$DOOL_OUTPUT &
DOOL_PID=$!


cat << 'EOF' > /tmp/gpu_stress.cu
#include <stdio.h>
#include <cuda_runtime.h>

__global__ void stress() {
    volatile float x = 1.0f;
    for (int i = 0; i < 1000000; i++) x = x * 1.0001f + 0.0001f;
}

int main() {
    printf("GPU stressor started\n");
    time_t start = time(NULL);
    while (difftime(time(NULL), start) < 10) {
        stress<<<256, 256>>>();
        cudaDeviceSynchronize();
    }
    printf("GPU stressor finished after 10 seconds\n");
    return 0;
}
EOF

nvcc -o /tmp/gpu_stress /tmp/gpu_stress.cu && echo "Small CUDA sample compiled" 

SRUN_PIDS=()

for i in {0..3}
do
    CUDA_VISIBLE_DEVICES=$i
    srun --exact --export=ALL,CUDA_VISIBLE_DEVICES --gres=gpu:1 --ntasks=1 --nodes 1 /tmp/gpu_stress  &
    SRUN_PIDS+=($!)
done

# Wait only for the srun processes
for pid in "${SRUN_PIDS[@]}"; do
    wait "$pid"
done


kill $DOOL_PID 2>/dev/null
wait $DOOL_PID 2>/dev/null

echo "Starting post-processing of dool output ! "




export DOOL_PLOTS=$PWD/dooloutput/dool_result_profiling_${SLURM_JOBID}
python dool_postprocess.py $DOOL_OUTPUT -o $DOOL_PLOTS.pdf



