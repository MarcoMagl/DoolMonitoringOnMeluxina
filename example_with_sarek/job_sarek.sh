#!/bin/bash -l
#SBATCH --job-name sarek
#SBATCH --time 48:00:00
#SBATCH --nodes 3
#SBATCH --ntasks-per-node 1
#SBATCH --hint nomultithread
#SBATCH --output run-%j-slurm.log
#SBATCH --account p20XXXX
#SBATCH --partition gpu
#SBATCH --qos default

module load env/release/2025.1
module load Apptainer/1.4.2-GCCcore-14.2.0
module load Nextflow/25.10.4
module load HyperQueue/0.25.1

RUN_DIR="${PWD}/run-${SLURM_JOB_ID}"
mkdir -p "${RUN_DIR}"



#####################
# Setup HyperQueue
#####################

# Directories and files
HYPERQUEUE_JOURNAL="${RUN_DIR}/hyperqueue-journal.log"
HYPERQUEUE_SERVER_LOG="${RUN_DIR}/hyperqueue-server.out"
HYPERQUEUE_WORKER_LOG="${RUN_DIR}/hyperqueue-worker-%n.out"

# Set the directory which hyperqueue will use 
export HQ_SERVER_DIR="${RUN_DIR}/hyperqueue-server-dir"
mkdir -p "${HQ_SERVER_DIR}"

# Define HyperQueue journal file
HQ_JOURNAL="hyperqueue-journal.log"

# Start the server in the background (&) and wait until it has started
hq server start --journal "${HYPERQUEUE_JOURNAL}" &> "${HYPERQUEUE_SERVER_LOG}" &
until hq job list &>/dev/null ; do sleep 1 ; done

# Start the workers in the background and wait for them to start
srun --overlap --cpu-bind=none --mpi=none --output="${HYPERQUEUE_WORKER_LOG}" hq worker start --no-hyper-threading --resource gpus=[0,1,2,3] &
hq worker wait "${SLURM_NTASKS}"



#####################
# Use Dool monitoring
#####################

# Start dool to monitor node usage
DOOL_EXEC="dool"
DOOL_OUTPUT="${RUN_DIR}/dool-%n.out"
DOOL_CSV="${RUN_DIR}"'/dool-${SLURM_NODEID}.csv'
srun --overlap --cpu-bind=none --mpi=none --output="${DOOL_OUTPUT}" \
    bash -c "${DOOL_EXEC} -tTcdngym 10 --nvidia-gpu --nvidia-gpu-mem --full --color --noupdate --display --output \"${DOOL_CSV}\"" &


#####################
# Sarek settings
#####################

# Sarek version
SAREK_VERSION="3.8.1"
# Config file
SAREK_CONFIG="${PWD}/nextflow_sarek_GE.config"
# Path to input files and directories
SAREK_INPUT_DIR="/project/home/p20XXXX/sarek-input"
SAREK_EXTRA_INPUT="/project/home/p20XXXX/sarek-input-extra"
SAREK_INPUT_FILE="${SAREK_EXTRA_INPUT}/paired_fastq_table.csv"
SAREK_INTERVALS="${SAREK_INPUT_DIR}/wgs_calling_regions_noseconds.hg38.chrM.bed"
SAREK_IGENOMES="${SAREK_INPUT_DIR}/igenomes"
# Output directory
SAREK_OUTPUT="${RUN_DIR}/sarek-output"
# Sarek options
SAREK_TOOLS="haplotypecaller"
SAREK_ALIGNER="parabricks"

#####################
# Run Nextflow
#####################

# Nextflow options
NEXTFLOW_PROFILE="apptainer,gpu"
# Use local directory to store NextFlow data and pipeline
export NXF_HOME="${RUN_DIR}/nextflow"
export NXF_LOG_FILE="${RUN_DIR}/nextflow.log"
export NXF_CACHE_DIR="${RUN_DIR}/nextflow-cache"
export NXF_APPTAINER_CACHEDIR="/project/home/p20XXXX/nextflow-apptainer-cache"
export NXF_ANSI_LOG=true
export NXF_ANSI_SUMMARY=true
export TERMINAL_WIDTH=200

# Set working directory
cd "${RUN_DIR}"

# Run Sarek to produce per-sample GVCFs
nextflow run nf-core/sarek \
  -revision "${SAREK_VERSION}" \
  -config "${SAREK_CONFIG}" \
  -profile "${NEXTFLOW_PROFILE}" \
  -work-dir      "${RUN_DIR}/nextflow-workdir"        \
  -with-report   "${RUN_DIR}/nextflow-report.html"    \
  -with-timeline "${RUN_DIR}/nextflow-timeline.html"  \
  -with-dag      "${RUN_DIR}/nextflow-flowchart.html" \
  -with-trace \
  --input  "${SAREK_INPUT_FILE}" \
  --outdir "${SAREK_OUTPUT}" \
  --aligner "${SAREK_ALIGNER}" \
  --genome GATK.GRCh38 \
  --trim_fastq \
  --three_prime_clip_r1 2 \
  --three_prime_clip_r2 2 \
  --clip_r1 2 \
  --clip_r2 2 \
  --intervals "${SAREK_INTERVALS}" \
  --tools "${SAREK_TOOLS}" \
  --save_output_as_bam \
  --joint_germline \
  --igenomes_base "${SAREK_IGENOMES}" \
  --igenomes_ignore false \
  --msisensorpro_scan "${SAREK_EXTRA_INPUT}/Homo_sapiens_assembly38.msisensor_scan.list" \
  --msisensor2_models "${SAREK_EXTRA_INPUT}/msisensor2/models_hg38/"



#####################
# Shutdown HyperQueue
#####################

# Wait for all jobs to finish, then shut down the workers and server
hq job wait all
hq worker stop all
hq server stop

