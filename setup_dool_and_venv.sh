#!/bin/bash
# Copyright (c) 2026 Marco Magliulo, Xavier Besseron - LuxProvide
# All rights reserved.

set -euo pipefail


# "Present directory" = wherever the script is invoked from.
CACHE_DIR="$PWD/.uv-cache"
VENV_DIR="$PWD/.venv"

REQUIREMENTS=(matplotlib pandas pynvml)


# --- 1. Install uv if it is not installed --------------------------------
if ! command -v uv >/dev/null 2>&1; then
    echo "uv not found: installing..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
fi

# --- 2. Make uv available on PATH ----------------------------------------
if [ -f "$PWD/.local/bin/env" ]; then
    # shellcheck disable=SC1091
    source "$PWD/.local/bin/env"
fi
export PATH="$PWD/.local/bin:$PATH"

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


REPO_ROOT="$(git rev-parse --show-toplevel)"
DOOL_DIR=${DOOL_DIR:-"$REPO_ROOT/dool_installation"}
mkdir -p $DOOL_DIR
mkdir -p $DOOL_DIR/plugins

# ── Check if dool is present, executable, and working ────────────────────────
if [ -x "$DOOL_DIR/dool/dool" ] && "$DOOL_DIR/dool/dool" --version > /dev/null 2>&1; then
    echo "dool executable already present and working at $DOOL_DIR/dool"
else
    echo "📥 Cloning dool from https://github.com/scottchiefbaker/dool.git..."
    cd "$DOOL_DIR"
    git clone https://github.com/scottchiefbaker/dool.git
    cd -
    echo "dool cloned successfully"
fi

cp -rp dool_plugins/* "$DOOL_DIR/plugins/"

# ── Add dool to PATH ─────────────────────────────────────────────────────────
export PATH="$DOOL_DIR/dool:$PATH"
echo "Added dool to PATH: $DOOL_DIR/dool"

echo
echo "To make dool permanently available, run:"
echo "echo 'export PATH=\"${DOOL_DIR}/dool:\$PATH\"' >> ~/.bashrc"
echo "source ~/.bashrc"

# ── Verify dool is working ───────────────────────────────────────────────────
if dool --version > /dev/null 2>&1; then
    which dool
    echo "dool is working:"
    dool --list
else
    echo "ERROR: dool --version failed. dool is not working correctly." >&2
fi
