#!/bin/bash

set -e

DOOL_DIR="$HOME/dool"

# ── Check if dool directory exists ───────────────────────────────────────────
if [ -d "$DOOL_DIR" ]; then
    echo "dool directory already exists at $DOOL_DIR"
else
    echo "📥 Cloning dool from https://github.com/besserox/dool.git (branch: nvidia-gpu)..."
    cd "$HOME"
    git clone https://github.com/besserox/dool.git -b nvidia-gpu
    cd -
    echo "dool cloned successfully"
fi

# ── Add dool to PATH ─────────────────────────────────────────────────────────
export PATH="$PWD/dool:$PATH"
echo "Added dool to PATH: $PWD/dool"

# ── Verify dool is working ───────────────────────────────────────────────────
if dool --version > /dev/null 2>&1; then
    echo "dool is working:"
    dool --version
else
    echo "ERROR: dool --version failed. dool is not working correctly." >&2
    exit 1
fi