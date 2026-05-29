#!/usr/bin/env bash
# setup_aioner_conda.sh
#
# Creates an isolated conda environment (Python 3.9) for the AIONER NER step.
#
# Background
# ----------
# AIONER originally required tensorflow==2.3.0, which has no ARM64 macOS wheels.
# This script installs TF 2.13.0 + tensorflow-addons 0.21.0, the lowest
# ARM64-native pair that satisfies AIONER's CRF-layer dependency.  No Metal GPU
# acceleration is available for this version of TF; AIONER runs CPU-only.
#
# Usage
# -----
#   bash scripts/setup_aioner_conda.sh        # first-time setup
#
# Running AIONER with this environment
# -------------------------------------
# The script prints the exact --aioner-python path to use at the end.
# Example:
#
#   python3 scripts/run_civic_pubtator.py <input_dir> \
#       --aioner-python /path/to/conda/envs/aioner-tf213/bin/python3
#
# To run AIONER directly (must run from the AIONER/ directory):
#
#   cd AIONER
#   /path/to/conda/envs/aioner-tf213/bin/python3 AIONER_Run.py \
#       -i input/ \
#       -m AIONER_trained_models/AIONER/Bioformer-Softmax-BEST-AIO_tmvar3.20230415.h5 \
#       -e Chemical \
#       -o output/

set -euo pipefail

ENV_NAME="aioner-tf213"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
AIONER_DIR="${REPO_DIR}/AIONER"
REQUIREMENTS="${REPO_DIR}/scripts/requirements_aioner.txt"

# ── helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[setup] $*"; }
error() { echo "[setup] ERROR: $*" >&2; exit 1; }

# ── 1. Pre-flight checks ─────────────────────────────────────────────────────
[[ -f "$REQUIREMENTS" ]] || error "Requirements file not found: ${REQUIREMENTS}"
[[ -d "$AIONER_DIR" ]]   || error "AIONER directory not found: ${AIONER_DIR}. Run scripts/download_data_files.sh first."
[[ -f "${AIONER_DIR}/AIONER_Run.py" ]] || error "AIONER_Run.py not found in ${AIONER_DIR}."

# ── 2. Homebrew ──────────────────────────────────────────────────────────────
command -v brew &>/dev/null || \
    error "Homebrew not found. Install it from https://brew.sh then re-run."

# ── 3. Locate / install Miniforge ────────────────────────────────────────────
find_conda() {
    command -v conda 2>/dev/null && return
    local cask_conda="/opt/homebrew/Caskroom/miniforge/base/condabin/conda"
    [[ -x "$cask_conda" ]] && echo "$cask_conda" && return
    [[ -x "${HOME}/miniforge3/bin/conda" ]] && echo "${HOME}/miniforge3/bin/conda" && return
    echo ""
}

CONDA="$(find_conda)"

if [[ -z "$CONDA" ]]; then
    info "Installing Miniforge via Homebrew ..."
    brew install miniforge
    CONDA="$(find_conda)"
    [[ -n "$CONDA" ]] || error "conda not found after installing miniforge. Try opening a new shell and re-running."
else
    info "Miniforge already installed: $CONDA"
fi

# Always ensure conda shell integration is present for zsh
if ! grep -q "conda initialize" "${HOME}/.zshrc" 2>/dev/null; then
    info "Initialising conda for zsh (you will need to restart your shell or run: source ~/.zshrc)."
    "$CONDA" init zsh || true
else
    info "conda zsh integration already present in ~/.zshrc"
fi

info "Using $("$CONDA" --version)"

# ── 4. Create / recreate the conda environment ───────────────────────────────
if "$CONDA" env list | grep -q "^${ENV_NAME} "; then
    info "Conda env '${ENV_NAME}' already exists — skipping creation."
    info "To rebuild from scratch: conda env remove -n ${ENV_NAME}"
else
    info "Creating conda env '${ENV_NAME}' with Python 3.9 ..."
    "$CONDA" create -y -n "$ENV_NAME" python=3.9
fi

# ── 5. Install Python dependencies ───────────────────────────────────────────
# Install via pip first (some packages may pull in a newer tokenizers as a
# transitive dep), then force-install tokenizers==0.12.1 from conda-forge
# afterwards so conda's ARM64 pre-built wheel is the final version.
# requirements_aioner.txt pins tokenizers==0.12.1 so subsequent pip runs
# treat it as already satisfied and leave the conda build in place.
info "Installing Python packages from ${REQUIREMENTS} ..."
"$CONDA" run -n "$ENV_NAME" pip install --upgrade pip
"$CONDA" run -n "$ENV_NAME" pip install -r "$REQUIREMENTS"

info "Force-installing tokenizers==0.12.1 from conda-forge (ARM64 pre-built, overrides pip) ..."
"$CONDA" install -y -n "$ENV_NAME" -c conda-forge "tokenizers=0.12.1"

# Remove any stale tokenizers dist-info folders left by pip at other versions.
# When multiple .dist-info directories coexist, importlib.metadata may report
# the wrong version, causing transformers' version gate to raise ImportError.
CONDA_BASE="$("$CONDA" info --base)"
SP="${CONDA_BASE}/envs/${ENV_NAME}/lib/python3.9/site-packages"
for stale in "$SP"/tokenizers-*.dist-info; do
    ver="$(basename "$stale" | sed 's/tokenizers-//;s/\.dist-info//')"
    if [[ "$ver" != "0.12.1" ]]; then
        info "Removing stale dist-info: $(basename "$stale")"
        rm -rf "$stale"
    fi
done

# ── 6. Download spaCy English model (required by stanza tokenizer) ────────────
info "Downloading spaCy English model (en_core_web_sm) ..."
"$CONDA" run -n "$ENV_NAME" python -m spacy download en_core_web_sm

# ── 7. Locate the env's Python interpreter ───────────────────────────────────
CONDA_BASE="$("$CONDA" info --base)"
CONDA_PYTHON="${CONDA_BASE}/envs/${ENV_NAME}/bin/python3"
[[ -x "$CONDA_PYTHON" ]] || error "Could not find python3 at expected path: ${CONDA_PYTHON}"

# ── 8. Verify ────────────────────────────────────────────────────────────────
info "Verifying AIONER dependencies ..."
"$CONDA_PYTHON" - <<'PYEOF'
import sys
import importlib.metadata

def ver(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "NOT FOUND"

import tensorflow as tf
import tensorflow_addons
import transformers
import stanza
import bioc
import spacy

print(f"  Python              : {sys.version}")
print(f"  tensorflow          : {tf.__version__}")
print(f"  tensorflow-addons   : {ver('tensorflow-addons')}")
print(f"  transformers        : {ver('transformers')}")
print(f"  stanza              : {ver('stanza')}")
print(f"  bioc                : {ver('bioc')}")
print(f"  spacy               : {ver('spacy')}")

gpus = tf.config.list_physical_devices('GPU')
print(f"  GPU devices         : {gpus or 'none (CPU-only mode)'}")
print("  All key packages imported successfully.")
PYEOF

# ── 9. Smoke-test AIONER imports (must run from AIONER dir) ──────────────────
info "Smoke-testing AIONER source imports ..."
"$CONDA_PYTHON" - <<PYEOF
import sys, os
os.chdir("${AIONER_DIR}")
sys.path.insert(0, "${AIONER_DIR}")
from src_python.AIONER.model_ner import HUGFACE_NER
from src_python.AIONER.processing_data import ml_intext_fn
from src_python.AIONER.restore_index import NN_restore_index_fn
from src_python.AIONER.postprocessing import postprocess_abbr, entity_consistency
print("  AIONER source modules imported successfully.")
PYEOF

# ── 10. Usage reminder ───────────────────────────────────────────────────────
cat <<EOF

Setup complete.

Python interpreter : ${CONDA_PYTHON}
AIONER directory   : ${AIONER_DIR}
Default model      : AIONER_trained_models/AIONER/Bioformer-Softmax-BEST-AIO_tmvar3.20230415.h5

To run chemical NER (from the AIONER/ directory):

  cd ${AIONER_DIR}
  ${CONDA_PYTHON} AIONER_Run.py \\
      -i input/ \\
      -m AIONER_trained_models/AIONER/Bioformer-Softmax-BEST-AIO_tmvar3.20230415.h5 \\
      -e Chemical \\
      -o output/

To use this environment with the pipeline:

  python3 scripts/run_civic_pubtator.py <input_dir> \\
      --aioner-python ${CONDA_PYTHON}

To activate the environment interactively:

  conda activate ${ENV_NAME}

EOF
