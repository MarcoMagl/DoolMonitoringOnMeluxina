# Dool Monitoring on Slurm HPC (Meluxina)

## Authors

- **Marco Eduardo Paolo Magliulo**
- **Xavier Besseron**

## Purpose

This repository demonstrates how to use the **dool** monitoring tool to track the usage of different system resources — in particular **GPU usage** — during the execution of a **Slurm job** on the **Meluxina** HPC platform.

Although the scripts are tailored for Meluxina, they can be adapted and used on **any Slurm-based HPC platform** that supports `dool` and NVIDIA GPU monitoring.

## Repository Structure

| File | Description |
|------|-------------|
| `setup_dool.sh` | Sets up the `dool` environment and dependencies |
| `run_dool_example.sh` | Example Slurm job script that runs `dool` alongside a GPU workload |
| `dool_postprocess.py` | Python script to post-process and visualize `dool` output data |
| `dooloutput/` | Directory containing example `dool` profiling output (CSV) |

## Quick Start

1. Clone this repository on the HPC platform.
2. Source the setup script to prepare the environment:
   ```bash
   source setup_dool.sh
   ```
3. Submit the example Slurm job:
   ```bash
   sbatch run_dool_example.sh
   ```
4. After the job completes, post-process the output:
   ```bash
   python dool_postprocess.py dooloutput/dool_profiling_<JOBID>.csv -o output.png
   ```

## Monitoring with Dool

The `dool` command is configured to collect the following metrics every second:

- CPU usage
- Disk I/O
- Network activity
- Memory usage
- System load
- **NVIDIA GPU utilization and memory** (`--nvidia-gpu --nvidia-gpu-mem`)

Example command used in the Slurm script:

```bash
dool -tTcdngym 1 --nvidia-gpu --nvidia-gpu-mem --full --output=<output.csv> &
```

## Post-processing

The `dool_postprocess.py` script generates publication-ready plots from the raw `dool` CSV output.


## Adapting to Other HPC Platforms

To use these scripts on a different Slurm HPC:

1. Ensure `dool` is installed and available in your environment.
2. Ensure NVIDIA GPU support is available (`nvidia-smi`, CUDA toolkit).
3. Adjust the Slurm directives in `run_dool_example.sh` (partition, time, nodes, etc.) to match your cluster's configuration.
4. Modify the module loads as needed for your environment.

## License

This project is provided as-is for educational and research purposes.

</parameter>