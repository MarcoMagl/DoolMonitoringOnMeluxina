#!/usr/bin/env bash
#
# Bootstrap uv + a virtualenv and run the dool post-processor.
#
#   - installs uv if it is not already available
#   - sources ~/.local/bin/env so uv lands on PATH
#   - keeps the uv cache inside the current ("present") directory
#   - creates the .venv only if it does not exist yet
#   - activates it and runs dool_postprocess.py
#
# Usage:
#   ./run_postprocess.sh [INPUT_CSV] [OUTPUT_IMAGE]
#
# If INPUT_CSV is omitted, the newest dooloutput/dool_profiling_*.csv is used.
# If OUTPUT_IMAGE is omitted, the plot is shown interactively (matplotlib).
#
set -euo pipefail

# Directory this script lives in (used to locate the post-processor).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# "Present directory" = wherever the script is invoked from.
CACHE_DIR="$PWD/.uv-cache"
VENV_DIR="$PWD/.venv"

REQUIREMENTS=(matplotlib pandas)
PLOTTER="$SCRIPT_DIR/dool_postprocess.py"

# --- 1. Install uv if it is not installed --------------------------------
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found: installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# --- 2. Make uv available on PATH ----------------------------------------
if [ -f "$HOME/.local/bin/env" ]; then
    # shellcheck disable=SC1091
    source "$HOME/.local/bin/env"
fi
export PATH="$HOME/.local/bin:$PATH"

if ! command -v uv >/dev/null 2>&1; then
    echo "Error: uv is still not on PATH after install." >&2
    exit 1
fi

# --- 3. Keep the uv cache in the present directory -----------------------
export UV_CACHE_DIR="$CACHE_DIR"
echo "uv cache directory: $UV_CACHE_DIR"

# --- 4. Create the virtual environment if it does not exist --------------
if [ ! -x "$VENV_DIR/bin/python" ]; then
    echo "Creating virtual environment at $VENV_DIR ..."
    uv venv "$VENV_DIR"
else
    echo "Virtual environment already present at $VENV_DIR"
fi

# --- 5. Activate it ------------------------------------------------------
# shellcheck disable=SC1091
source "$VENV_DIR/bin/activate"

# Dependencies (idempotent: fast when already installed).
uv pip install "${REQUIREMENTS[@]}"

# --- 6. Resolve the input CSV --------------------------------------------
INPUT_CSV="${1:-}"
if [ -z "$INPUT_CSV" ]; then
    INPUT_CSV="$(ls -1t "$SCRIPT_DIR"/dooloutput/dool_profiling_*.csv 2>/dev/null | head -n1 || true)"
fi
if [ -z "$INPUT_CSV" ] || [ ! -f "$INPUT_CSV" ]; then
    echo "Error: no input CSV found. Pass one as the first argument." >&2
    exit 1
fi
echo "Input CSV: $INPUT_CSV"

# --- 7. Run the plotting script ------------------------------------------
if [ -n "${2:-}" ]; then
    python "$PLOTTER" "$INPUT_CSV" -o "$2"
else
    python "$PLOTTER" "$INPUT_CSV"
fi
