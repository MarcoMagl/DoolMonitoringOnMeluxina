#!/usr/bin/env python3
"""
Post-processing script for dool CSV output files.
Generates multi-panel matplotlib plots with shared time axis.
Copyright (c) 2026 Marco Magliulo, Xavier Besseron - LuxProvide
"""

import pandas as pd
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
from datetime import datetime
import sys
import os
import argparse


def parse_dool_csv(filepath):
    """Parse dool CSV file, handling the multi-line header structure."""
    with open(filepath, 'r') as f:
        lines = f.readlines()
    
    print(f"Total lines in file: {len(lines)}")
    
    # Find the column header line - it must contain BOTH "time" and "epoch" as quoted fields
    # In dool CSV, the header is a single quoted CSV line
    col_header_idx = None
    for i, line in enumerate(lines):
        stripped = line.strip()
        if not stripped:
            continue
        # The definitive header line contains both "time" and "epoch" as column names
        if '"time"' in stripped and '"epoch"' in stripped:
            col_header_idx = i
            print(f"Found header at line {i}: {stripped[:100]}...")
            break
    
    if col_header_idx is None:
        print("DEBUG: First 10 non-empty lines:")
        count = 0
        for i, line in enumerate(lines):
            if line.strip() and count < 10:
                print(f"  Line {i}: {line.strip()[:120]}")
                count += 1
        raise ValueError("Could not find column header line containing both 'time' and 'epoch'")
    
    # Parse column names
    col_names = [col.strip().strip('"') for col in lines[col_header_idx].split(',')]
    print(f"Column names ({len(col_names)}): {col_names[:10]}...")
    
    # Parse data rows (everything after the header)
    data_lines = lines[col_header_idx + 1:]
    data = []
    for line in data_lines:
        if line.strip():
            values = [val.strip().strip('"') for val in line.split(',')]
            # dool appends a trailing comma to every data row, which split()
            # turns into one extra empty field; drop it so the row aligns
            # with the header. (No real data column is left empty here.)
            if len(values) == len(col_names) + 1 and values[-1] == '':
                values = values[:-1]
            if len(values) == len(col_names):
                data.append(values)
    
    print(f"Parsed {len(data)} data rows")
    
    # Create DataFrame
    df = pd.DataFrame(data, columns=col_names)
    
    # Handle duplicate column names (e.g. total, gpu0-3 appear twice: usage + memory)
    seen = {}
    new_cols = []
    for col in df.columns:
        if col in seen:
            seen[col] += 1
            new_cols.append(f"{col}_{seen[col]}")
        else:
            seen[col] = 0
            new_cols.append(col)
    df.columns = new_cols
    print(f"Columns after dedup: {list(df.columns)}")
    
    # Convert numeric columns
    for col in df.columns:
        if col not in ['time', 'epoch']:
            df[col] = pd.to_numeric(df[col], errors='coerce')
    
    # Parse time column (use errors='coerce' to handle label rows like 'system')
    df['time'] = pd.to_datetime(df['time'], format='%b-%d %H:%M:%S', errors='coerce')
    
    # Drop rows where time parsing failed (e.g., category label rows)
    df = df.dropna(subset=['time'])
    df = df.reset_index(drop=True)
    
    return df


# --- Plot styling -----------------------------------------------------------

# Colorblind-friendly categorical palette (Tableau 10) used across all panels.
PALETTE = [
    '#4e79a7', '#f28e2b', '#e15759', '#76b7b2', '#59a14f',
    '#edc948', '#b07aa1', '#ff9da7', '#9c755f', '#bab0ac',
]


def _colors(n):
    """Return ``n`` colors, cycling through the palette."""
    return [PALETTE[i % len(PALETTE)] for i in range(n)]


def setup_plot_style():
    """Apply a clean, modern matplotlib style to the current session."""
    plt.rcParams.update({
        'figure.facecolor': 'white',
        'axes.facecolor': 'white',
        'savefig.facecolor': 'white',
        'figure.dpi': 150,
        'font.size': 11,
        'axes.titlesize': 13,
        'axes.labelsize': 11,
        'xtick.labelsize': 9,
        'ytick.labelsize': 9,
        'legend.fontsize': 8.5,
        'lines.linewidth': 1.8,
        'axes.grid': True,
        'grid.color': '#e6e6e6',
        'grid.linewidth': 0.9,
        'axes.edgecolor': '#cbcbcb',
        'axes.linewidth': 0.8,
        'xtick.color': '#888888',
        'ytick.color': '#888888',
        'axes.spines.top': False,
        'axes.spines.right': False,
    })


def _configure_axes(ax, ylabel, title):
    """Style a single subplot consistently."""
    ax.set_title(title, fontsize=12, fontweight='bold', pad=8, color='#2b2b2b')
    ax.set_ylabel(ylabel, fontsize=10, fontweight='bold', color='#2b2b2b')
    ax.grid(True, axis='y', alpha=0.35)
    ax.set_axisbelow(True)  # keep the grid behind the lines
    ax.tick_params(colors='#666666', labelsize=9, length=0)
    for spine in ax.spines.values():
        spine.set_color('#cbcbcb')
        spine.set_linewidth(0.8)


def _plot_columns(ax, cols, df, ylabel, title, colors=None):
    """Plot ``cols`` against time and style the panel consistently."""
    colors = colors or _colors(len(cols))
    for col, color in zip(cols, colors):
        ax.plot(df['time'], df[col], label=col.upper(), color=color, linewidth=1.8)
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, ncol=2)
    _configure_axes(ax, ylabel, title)
    return True


def plot_cpu_usage(df, ax):
    """Plot CPU usage metrics."""
    cpu_cols = ['usr', 'sys', 'idl', 'wai', 'stl']
    cols = [c for c in cpu_cols if c in df.columns]
    if not cols:
        return False

    # Intuitive per-metric colors.
    colors = {
        'usr': PALETTE[0], 'sys': PALETTE[2], 'idl': PALETTE[4],
        'wai': PALETTE[1], 'stl': PALETTE[6],
    }
    for col in cols:
        ax.plot(df['time'], df[col], label=col.upper(),
                color=colors.get(col, PALETTE[0]), linewidth=1.8)

    ncol = min(3, len(cols))
    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, ncol=ncol)
    _configure_axes(ax, 'CPU Usage (%)', 'CPU Usage')
    ax.set_ylim(0, 100)
    return True


def plot_disk_usage(df, ax):
    """Plot disk I/O metrics."""
    cols = [col for col in df.columns if col.startswith('dsk/')]
    if not cols:
        return False
    return _plot_columns(ax, cols, df, 'Disk I/O (kB/s)', 'Disk I/O')


def plot_network_usage(df, ax):
    """Plot network metrics."""
    cols = [col for col in df.columns if col.startswith('net/')]
    if not cols:
        return False
    return _plot_columns(ax, cols, df, 'Network (kB/s)', 'Network I/O')


def plot_paging(df, ax):
    """Plot paging metrics."""
    cols = [col for col in ['in', 'out'] if col in df.columns]
    if not cols:
        return False
    return _plot_columns(ax, cols, df, 'Paging (kB/s)', 'Paging')


def plot_system_metrics(df, ax):
    """Plot system metrics (interrupts, context switches)."""
    cols = [col for col in ['int', 'csw'] if col in df.columns]
    if not cols:
        return False
    return _plot_columns(ax, cols, df, 'Count/s', 'System')


def plot_memory_usage(df, ax):
    """Plot memory usage metrics."""
    mem_cols = ['used', 'free', 'cach', 'avai']
    cols = [c for c in mem_cols if c in df.columns]
    if not cols:
        return False

    colors = {'used': PALETTE[2], 'free': PALETTE[4],
              'cach': PALETTE[0], 'avai': PALETTE[1]}
    for col in cols:
        # Convert bytes to GB for readability
        ax.plot(df['time'], df[col] / (1024**3), label=col.upper(),
                color=colors.get(col, PALETTE[0]), linewidth=1.8)

    ax.legend(loc='upper left', fontsize=8, framealpha=0.9, ncol=2)
    _configure_axes(ax, 'Memory (GB)', 'Memory Usage')
    return True


def plot_gpu_usage(df, ax):
    """Plot GPU usage metrics."""
    cols = [col for col in ['gpu0', 'gpu1', 'gpu2', 'gpu3'] if col in df.columns]
    if not cols:
        return False
    return _plot_columns(ax, cols, df, 'GPU Usage (%)', 'GPU Usage')


def plot_gpu_memory(df, ax):
    """Plot GPU memory usage metrics.

    dool --nvidia-gpu-mem reports used memory per GPU (in bytes). Because
    --nvidia-gpu already occupies gpu0..gpu3, these appear as the _1-suffixed
    columns (gpu0_1..gpu3_1) after de-duplication.
    """
    cols = [col for col in ['gpu0_1', 'gpu1_1', 'gpu2_1', 'gpu3_1'] if col in df.columns]
    if not cols:
        return False
    return _plot_columns(ax, cols, df, 'GPU Memory (GB)', 'GPU Memory Usage')


def create_plots(df, output_path=None, figsize=(14, 10), subtitle=None):
    """Create multi-panel plot with all metrics."""
    setup_plot_style()

    # Determine which plots to create based on available data
    plot_functions = [
        ('CPU Usage', plot_cpu_usage),
        ('Disk I/O', plot_disk_usage),
        ('Network I/O', plot_network_usage),
        ('Paging', plot_paging),
        ('System', plot_system_metrics),
        ('Memory Usage', plot_memory_usage),
        ('GPU Usage', plot_gpu_usage),
        ('GPU Memory', plot_gpu_memory),
    ]

    # Filter to only include plots with data
    active_plots = []
    for name, func in plot_functions:
        # Create a dummy axis to test if data exists
        fig_test = plt.figure()
        ax_test = fig_test.add_subplot(111)
        if func(df, ax_test):
            active_plots.append((name, func))
        plt.close(fig_test)

    if not active_plots:
        print("No data available to plot")
        return

    # Create figure with subplots (taller when there are more panels)
    n_plots = len(active_plots)
    fig_height = max(figsize[1], n_plots * 1.8)
    fig, axes = plt.subplots(n_plots, 1, figsize=(figsize[0], fig_height), sharex=True)

    if n_plots == 1:
        axes = [axes]

    # Create each plot
    for idx, (name, func) in enumerate(active_plots):
        func(df, axes[idx])

    # Format shared x-axis. Use time-only labels for single-day runs, but
    # include the date when the run spans more than one calendar day so the
    # axis stays unambiguous across midnight.
    spans_days = df['time'].dt.normalize().nunique() > 1
    time_fmt = '%H:%M:%S' if not spans_days else '%m-%d %H:%M'
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter(time_fmt))
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
    axes[-1].tick_params(axis='x', rotation=0 if spans_days else 45,
                         colors='#666666', labelsize=9)
    axes[-1].set_xlabel('Time', fontsize=10, fontweight='bold', color='#2b2b2b')

    # Title (and optional subtitle, e.g. the source CSV)
    if subtitle:
        fig.suptitle('Dool System Monitoring', fontsize=16, fontweight='bold',
                     color='#222222', y=0.99)
        fig.text(0.5, 0.935, subtitle, ha='center', fontsize=9.5, color='#777777')
        plt.tight_layout(rect=[0, 0, 1, 0.92])
    else:
        fig.suptitle('Dool System Monitoring', fontsize=16, fontweight='bold',
                     color='#222222', y=0.99)
        plt.tight_layout(rect=[0, 0, 1, 0.96])

    # Save or show
    if output_path:
        plt.savefig(output_path, facecolor=fig.get_facecolor())
        print(f"Plot saved to: {output_path}")
    else:
        plt.show()

    plt.close()


def main():
    parser = argparse.ArgumentParser(description='Post-process dool CSV output files')
    parser.add_argument('input_file', help='Path to dool CSV file')
    parser.add_argument('-o', '--output', help='Output image file path (PNG, PDF, etc.)')
    parser.add_argument('--figsize', nargs=2, type=float, default=[14, 10],
                        help='Figure size (width height) in inches')
    
    args = parser.parse_args()
    
    # Check if input file exists
    if not os.path.exists(args.input_file):
        print(f"Error: File '{args.input_file}' not found")
        sys.exit(1)
    
    # Parse CSV
    print(f"Parsing {args.input_file}...")
    df = parse_dool_csv(args.input_file)
    print(f"Loaded {len(df)} data points")
    
    # Create plots
    create_plots(df, output_path=args.output, figsize=tuple(args.figsize))


if __name__ == '__main__':
    main()
