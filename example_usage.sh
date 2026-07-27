#!/bin/bash
# Example usage of dool_postprocess.py

# Basic usage - display plot
python dool_postprocess.py dooloutput/dool_profiling_4900869.csv

# Save to PNG file
python dool_postprocess.py dooloutput/dool_profiling_4900869.csv -o output.png

# Save to PDF file (better for reports)
python dool_postprocess.py dooloutput/dool_profiling_4900869.csv -o output.pdf

# Custom figure size
python dool_postprocess.py dooloutput/dool_profiling_4900869.csv -o output.png --figsize 16 12

# Process multiple files
for file in dooloutput/dool_profiling_*.csv; do
    output_name=$(basename "$file" .csv).png
    python dool_postprocess.py "$file" -o "plots/$output_name"
done