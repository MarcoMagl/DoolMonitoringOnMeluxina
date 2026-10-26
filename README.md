# Dool Monitoring on Slurm HPC (Meluxina)

Track system and **GPU** resource usage during a Slurm job with the [dool](https://github.com/scottchiefbaker/dool) tool, then plot the results.

Although tailored for Meluxina, the scripts work on any Slurm HPC with `dool` and NVIDIA GPU monitoring.

## Setup

```bash
source setup_dool_and_venv.sh
```

This installs [`uv`](https://docs.astral.sh/uv/), creates a `.venv` with `matplotlib`, `pandas` and `pynvml`, clones `dool`, and copies the NVIDIA GPU plugins from `dool_plugins/`.

## Run an example job

```bash
sbatch dcgmi-monitoring/run_dool_dgcmi_example.sh
```

The job records CPU, disk, network, memory, system and NVIDIA GPU (usage + memory) metrics every second into `dooloutput/dool_profiling_<JOBID>.csv`.

## Plot the results

```bash
./run_postprocess.sh                      # newest CSV, show interactively
./run_postprocess.sh <csv> <output.pdf>   # specific input and output
```

`run_postprocess.sh` wraps `dool_postprocess.py`, which turns a `dool` CSV into a multi-panel plot.

## Example output for the simple `nvidia-dcgmi` test

![Dool monitoring plot](dooloutput/dool_result_profiling_5378308.pdf)

## Example output for the Sarek workflow

![Dool monitoring plot](example_with_sarek/dool-plots/run-4433692/dool_monitoring.pdf)

## Files

| Path | What it does |
| ------ | -------------- |
| `setup_dool_and_venv.sh` | Set up `dool`, the venv and the GPU plugins |
| `run_postprocess.sh` | Post-process a `dool` CSV into a plot |
| `dool_postprocess.py` | Plotting script (CPU, disk, network, paging, system, memory, GPU) |
| `dool_plugins/` | `dool` plugins for NVIDIA GPU usage and memory |
| `dcgmi-monitoring/` | Example Slurm job based on `dcgmi` |
| `example_with_sarek/` | Example Slurm job based on Sarek |
