#!/usr/bin/env bash
#
# Usage:
#   ./run_postprocess.sh [INPUT_CSV] [OUTPUT_IMAGE]
#
# If INPUT_CSV is omitted, the newest dooloutput/dool_profiling_*.csv is used.
# If OUTPUT_IMAGE is omitted, the plot is shown interactively (matplotlib).
#

set -x
# Directory this script lives in (used to locate the post-processor).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# --- 1. Resolve the input CSV --------------------------------------------
INPUT_CSV="${1:-}"
if [ -z "$INPUT_CSV" ]; then
    INPUT_CSV="$(ls -1t "$SCRIPT_DIR"/dooloutput/dool_profiling_*.csv 2>/dev/null | head -n1 || true)"
fi
if [ -z "$INPUT_CSV" ] || [ ! -f "$INPUT_CSV" ]; then
    echo "Error: no input CSV found. Pass one as the first argument." >&2
    exit 1
fi
echo "Input CSV: $INPUT_CSV"


# --- 2. Run the plotting script ------------------------------------------
PLOTTER="$SCRIPT_DIR/dool_postprocess.py"
if [ -n "${2:-}" ]; then
    python "$PLOTTER" "$INPUT_CSV" -o "$2"
else
    python "$PLOTTER" "$INPUT_CSV"
fi
