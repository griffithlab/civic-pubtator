#!/usr/bin/env bash
# setup_nlmchem_conda.sh
#
# Creates an isolated conda environment (Python 3.9.18) for the NLMChem
# tagger/normalizer step with all dependencies from
# NLMChem/NLMChemTaggerNormalizer/requirements.txt.
#
# Usage
# -----
#   bash scripts/setup_nlmchem_conda.sh        # first-time setup
#
# Running NLMChem with this environment
# --------------------------------------
# The script prints the exact --nlmchem-python path to use at the end.
# Example:
#
#   python3 scripts/run_civic_pubtator.py <input_dir> \
#       --nlmchem-python /path/to/conda/envs/nlmchem-py39/bin/python3

set -euo pipefail

ENV_NAME="nlmchem-py39"
REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
REQUIREMENTS="${REPO_DIR}/NLMChem/NLMChemTaggerNormalizer/requirements.txt"

# ── helpers ──────────────────────────────────────────────────────────────────
info()  { echo "[setup] $*"; }
error() { echo "[setup] ERROR: $*" >&2; exit 1; }

# ── 1. Requirements file check ───────────────────────────────────────────────
[[ -f "$REQUIREMENTS" ]] || error "Requirements file not found: ${REQUIREMENTS}"

# ── 2. Homebrew ──────────────────────────────────────────────────────────────
command -v brew &>/dev/null || \
    error "Homebrew not found. Install it from https://brew.sh then re-run."

# ── 3. Install Miniforge (conda for Apple Silicon) ───────────────────────────
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
    info "Creating conda env '${ENV_NAME}' with Python 3.9.18 ..."
    "$CONDA" create -y -n "$ENV_NAME" python=3.9.18
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
info "Verifying key NLMChem dependencies ..."
"$CONDA_PYTHON" - <<'PYEOF'
import sys
import importlib.metadata
import bioc
import lxml
import tqdm
import intervaltree

def pkg_version(name):
    try:
        return importlib.metadata.version(name)
    except importlib.metadata.PackageNotFoundError:
        return "unknown"

print(f"  Python      : {sys.version}")
print(f"  bioc        : {pkg_version('bioc')}")
print(f"  lxml        : {pkg_version('lxml')}")
print(f"  tqdm        : {pkg_version('tqdm')}")
print(f"  intervaltree: {pkg_version('intervaltree')}")
print("  All key packages imported successfully.")
PYEOF

# ── 8. Patch run_Chemical_PubTator.sh to resolve CHEM_NORM relative to script ─
# The upstream script uses BASE_DIR=$(pwd), so CHEM_NORM must exist in whatever
# directory the caller runs from.  We patch it once to use the script's own
# directory instead, making it callable from anywhere.
for RUN_SCRIPT in \
    "${REPO_DIR}/NLMChem/NLMChemTaggerNormalizer/run_Chemical_PubTator.sh" \
    "${REPO_DIR}/NLMChem/NLMChemTaggerNormalizer/run_Chemical_BioCXML.sh"; do
    SCRIPT_NAME="$(basename "$RUN_SCRIPT")"
    if grep -qF 'BASE_DIR=$(cd "$(dirname "$0")" && pwd)' "$RUN_SCRIPT"; then
        info "${SCRIPT_NAME} already patched — skipping."
    else
        info "Patching ${SCRIPT_NAME} to use script-relative CHEM_NORM path ..."
        sed -i.bak 's|BASE_DIR=$(pwd)|BASE_DIR=$(cd "$(dirname "$0")" \&\& pwd)|' "$RUN_SCRIPT"
        info "Backup saved as ${RUN_SCRIPT}.bak"
    fi
done

# ── 9. Usage reminder ────────────────────────────────────────────────────────
cat <<EOF

Setup complete.

Python interpreter: ${CONDA_PYTHON}

To use this environment with the pipeline:

  python3 scripts/run_civic_pubtator.py <input_dir> \\
      --nlmchem-python ${CONDA_PYTHON}

To activate the environment interactively:

  conda activate ${ENV_NAME}
  python NLMChem/NLMChemTaggerNormalizer/src/tagger_and_normalizer.py ...

EOF
