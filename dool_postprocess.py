#!/usr/bin/env python3
"""
Post-processing script for dool CSV output files.
Generates multi-panel matplotlib plots with shared time axis.
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


def plot_cpu_usage(df, ax):
    """Plot CPU usage metrics."""
    cpu_cols = ['usr', 'sys', 'idl', 'wai', 'stl']
    available_cols = [col for col in cpu_cols if col in df.columns]
    
    if not available_cols:
        return False
    
    colors = {'usr': '#2196F3', 'sys': '#F44336', 'idl': '#4CAF50', 
              'wai': '#FF9800', 'stl': '#9C27B0'}
    
    for col in available_cols:
        ax.plot(df['time'], df[col], label=col.upper(), 
                color=colors.get(col, 'gray'), linewidth=1.5)
    
    ax.set_ylabel('CPU Usage (%)')
    ax.set_title('CPU Usage')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    
    return True


def plot_disk_usage(df, ax):
    """Plot disk I/O metrics."""
    disk_cols = [col for col in df.columns if col.startswith('dsk/')]
    
    if not disk_cols:
        return False
    
    for col in disk_cols:
        ax.plot(df['time'], df[col], label=col, linewidth=1.5)
    
    ax.set_ylabel('Disk I/O (kB/s)')
    ax.set_title('Disk I/O')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    return True


def plot_network_usage(df, ax):
    """Plot network metrics."""
    net_cols = [col for col in df.columns if col.startswith('net/')]
    
    if not net_cols:
        return False
    
    for col in net_cols:
        ax.plot(df['time'], df[col], label=col, linewidth=1.5)
    
    ax.set_ylabel('Network (kB/s)')
    ax.set_title('Network I/O')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    return True


def plot_paging(df, ax):
    """Plot paging metrics."""
    paging_cols = ['in', 'out']
    available_cols = [col for col in paging_cols if col in df.columns]
    
    if not available_cols:
        return False
    
    for col in available_cols:
        ax.plot(df['time'], df[col], label=f'Paging {col}', linewidth=1.5)
    
    ax.set_ylabel('Paging (kB/s)')
    ax.set_title('Paging')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    return True


def plot_system_metrics(df, ax):
    """Plot system metrics (interrupts, context switches)."""
    sys_cols = ['int', 'csw']
    available_cols = [col for col in sys_cols if col in df.columns]
    
    if not available_cols:
        return False
    
    for col in available_cols:
        ax.plot(df['time'], df[col], label=col.upper(), linewidth=1.5)
    
    ax.set_ylabel('Count/s')
    ax.set_title('System Metrics')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    return True


def plot_memory_usage(df, ax):
    """Plot memory usage metrics."""
    mem_cols = ['used', 'free', 'cach', 'avai']
    available_cols = [col for col in mem_cols if col in df.columns]
    
    if not available_cols:
        return False
    
    colors = {'used': '#F44336', 'free': '#4CAF50', 'cach': '#2196F3', 'avai': '#FF9800'}
    
    for col in available_cols:
        # Convert bytes to GB for readability
        ax.plot(df['time'], df[col] / (1024**3), label=col.upper(), 
                color=colors.get(col, 'gray'), linewidth=1.5)
    
    ax.set_ylabel('Memory (GB)')
    ax.set_title('Memory Usage')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    return True


def plot_gpu_usage(df, ax):
    """Plot GPU usage metrics."""
    gpu_cols = [col for col in df.columns if col.startswith('gpu') and not col.startswith('gpu') or col in ['gpu0', 'gpu1', 'gpu2', 'gpu3']]
    gpu_usage_cols = [col for col in ['gpu0', 'gpu1', 'gpu2', 'gpu3'] if col in df.columns]
    
    if not gpu_usage_cols:
        return False
    
    for col in gpu_usage_cols:
        ax.plot(df['time'], df[col], label=col.upper(), linewidth=1.5)
    
    ax.set_ylabel('GPU Usage (%)')
    ax.set_title('GPU Usage')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_ylim(0, 100)
    
    return True


def plot_gpu_memory(df, ax):
    """Plot GPU memory usage metrics."""
    # Look for nv-gpu memory columns
    mem_cols = [col for col in df.columns if 'gpu' in col.lower() and 'mem' in col.lower()]
    
    if not mem_cols:
        # Try alternative column names
        mem_cols = [col for col in df.columns if col.startswith('gpu') and 'total' not in col.lower()]
        # Filter to only memory-related columns (typically have larger values)
        if mem_cols:
            # Check if these look like memory values (typically in GB range)
            sample_val = df[mem_cols[0]].dropna().iloc[0] if not df[mem_cols[0]].dropna().empty else 0
            if sample_val > 100:  # Likely memory in bytes
                pass
            else:
                mem_cols = []
    
    if not mem_cols:
        return False
    
    for col in mem_cols:
        # Convert to GB if values are large (likely in bytes)
        if df[col].dropna().iloc[0] > 1e9 if not df[col].dropna().empty else False:
            ax.plot(df['time'], df[col] / (1024**3), label=col, linewidth=1.5)
        else:
            ax.plot(df['time'], df[col], label=col, linewidth=1.5)
    
    ax.set_ylabel('GPU Memory (GB)')
    ax.set_title('GPU Memory Usage')
    ax.legend(loc='upper right', fontsize=8)
    ax.grid(True, alpha=0.3)
    
    return True


def create_plots(df, output_path=None, figsize=(14, 10)):
    """Create multi-panel plot with all metrics."""
    # Determine which plots to create based on available data
    plot_functions = [
        ('CPU', plot_cpu_usage),
        ('Disk', plot_disk_usage),
        ('Network', plot_network_usage),
        ('Paging', plot_paging),
        ('System', plot_system_metrics),
        ('Memory', plot_memory_usage),
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
    
    # Create figure with subplots
    n_plots = len(active_plots)
    fig, axes = plt.subplots(n_plots, 1, figsize=figsize, sharex=True)
    
    if n_plots == 1:
        axes = [axes]
    
    # Create each plot
    for idx, (name, func) in enumerate(active_plots):
        func(df, axes[idx])
    
    # Format x-axis
    axes[-1].xaxis.set_major_formatter(mdates.DateFormatter('%H:%M:%S'))
    axes[-1].xaxis.set_major_locator(mdates.AutoDateLocator())
    plt.xticks(rotation=45)
    
    # Set common x-label
    axes[-1].set_xlabel('Time')
    
    # Add main title
    fig.suptitle('Dool System Monitoring', fontsize=16, fontweight='bold', y=0.98)
    
    # Adjust layout
    plt.tight_layout()
    plt.subplots_adjust(top=0.95)
    
    # Save or show
    if output_path:
        plt.savefig(output_path, dpi=150, bbox_inches='tight')
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