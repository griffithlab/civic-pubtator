#!/usr/bin/env bash
# setup_gnorm2_conda.sh
#
# Creates an isolated conda environment (Python 3.11) for the GNorm2 ML step
# with TensorFlow 2.15 + tensorflow-metal 1.2.0 for Apple Silicon GPU acceleration.
#
# Background
# ----------
# The standard system Python (3.12) ships with TensorFlow 2.21, but
# tensorflow-metal 1.2.0 (the only available Metal plugin on PyPI) only supports
# TF 2.15.  TF 2.15 has no Python 3.12 wheels, so a separate Python 3.11
# environment is required.
#
# This script installs Miniforge (if absent), creates the env, and installs all
# GNorm2 Python dependencies.  The rest of the pipeline (GROBID, tmVar3) continues
# to use the system Python and is unaffected.
#
# Usage
# -----
#   bash scripts/setup_gnorm2_conda.sh        # first-time setup
#
# Running the pipeline with Metal GPU
# ------------------------------------
# The script prints the exact --gnorm2-python path to use at the end.
# Example:
#
#   python3 scripts/run_civic_pubtator.py <input_dir> \
#       --gnorm2-python /path/to/conda/envs/gnorm2-tf215/bin/python3

set -euo pipefail

ENV_NAME="gnorm2-tf215"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REQUIREMENTS="${REPO_DIR}/GNorm2/requirements_gnorm2.txt"

# ── helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[setup] $*"; }
error() { echo "[setup] ERROR: $*" >&2; exit 1; }

# ── 1. Platform check ────────────────────────────────────────────────────────
[[ "$(uname)" == "Darwin" ]] || error "This script is for macOS only."
[[ "$(uname -m)" == "arm64" ]] || error "tensorflow-metal requires Apple Silicon (arm64)."

# ── 2. Homebrew ──────────────────────────────────────────────────────────────
command -v brew &>/dev/null || \
    error "Homebrew not found. Install it from https://brew.sh then re-run."

# ── 3. Install Miniforge (conda for Apple Silicon) ───────────────────────────
# Homebrew's miniforge cask installs conda to a path inside Caskroom, not
# ~/miniforge3, so we locate it dynamically after installation.
find_conda() {
    # 1. already on PATH
    command -v conda 2>/dev/null && return
    # 2. Homebrew cask location (Apple Silicon)
    local cask_conda="/opt/homebrew/Caskroom/miniforge/base/condabin/conda"
    [[ -x "$cask_conda" ]] && echo "$cask_conda" && return
    # 3. traditional ~/miniforge3 location
    [[ -x "${HOME}/miniforge3/bin/conda" ]] && echo "${HOME}/miniforge3/bin/conda" && return
    echo ""
}

CONDA="$(find_conda)"

if [[ -z "$CONDA" ]]; then
    info "Installing Miniforge via Homebrew ..."
    brew install miniforge
    CONDA="$(find_conda)"
    [[ -n "$CONDA" ]] || error "conda not found after installing miniforge. Try opening a new shell and re-running."
    info "Initialising conda for zsh (you may need to restart your shell)."
    "$CONDA" init zsh || true
else
    info "Miniforge already installed: $CONDA"
fi

info "Using $("$CONDA" --version)"

# ── 4. Create / recreate the conda environment ───────────────────────────────
if "$CONDA" env list | grep -q "^${ENV_NAME} "; then
    info "Conda env '${ENV_NAME}' already exists — skipping creation."
    info "To rebuild from scratch: conda env remove -n ${ENV_NAME}"
else
    info "Creating conda env '${ENV_NAME}' with Python 3.11 ..."
    "$CONDA" create -y -n "$ENV_NAME" python=3.11
fi

# ── 5. Install Python dependencies ───────────────────────────────────────────
info "Installing Python packages from ${REQUIREMENTS} ..."
"$CONDA" run -n "$ENV_NAME" pip install --upgrade pip
"$CONDA" run -n "$ENV_NAME" pip install -r "$REQUIREMENTS"

# ── 6. Locate the env's Python interpreter ───────────────────────────────────
CONDA_BASE="$("$CONDA" info --base)"
CONDA_PYTHON="${CONDA_BASE}/envs/${ENV_NAME}/bin/python3"
[[ -x "$CONDA_PYTHON" ]] || error "Could not find python3 at expected path: ${CONDA_PYTHON}"

# ── 7. Verify ────────────────────────────────────────────────────────────────
info "Verifying TensorFlow and Metal GPU ..."
"$CONDA_PYTHON" - <<'PYEOF'
import tensorflow as tf
gpus = tf.config.list_physical_devices('GPU')
print(f"  TensorFlow : {tf.__version__}")
print(f"  GPU devices: {gpus}")
if not gpus:
    print("  WARNING: No Metal GPU detected — check tensorflow-metal install.")
else:
    print("  Metal GPU acceleration is active.")
PYEOF

# ── 8. Usage reminder ────────────────────────────────────────────────────────
cat <<EOF

Setup complete.

Python interpreter: ${CONDA_PYTHON}

To use Metal GPU acceleration with the pipeline:

  python3 scripts/run_civic_pubtator.py <input_dir> \\
      --gnorm2-python ${CONDA_PYTHON}

Or for run_gnorm2.py directly:

  python3 scripts/run_gnorm2.py <input> <output> \\
      --ml-python ${CONDA_PYTHON}

To activate the environment interactively:

  conda activate ${ENV_NAME}
  python GNorm2/GeneNER_SpeAss_run.py ...

EOF
