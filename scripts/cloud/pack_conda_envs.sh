#!/usr/bin/env bash
# pack_conda_envs.sh — pack civic-pubtator conda envs and upload to GCS.
#
# Run this manually on the VM after creating or updating conda environments.
# gcp_server_startup.py downloads these tarballs on fresh VMs to avoid
# re-resolving from live package servers, which may prune old packages.
#
# Usage:
#   bash scripts/cloud/pack_conda_envs.sh              # pack all envs
#   bash scripts/cloud/pack_conda_envs.sh aioner-tf23-gpu  # pack one env

set -euo pipefail

BUCKET="gs://civic-pubtator-tool-data"
GCS_ENVS="${BUCKET}/conda-envs"

ALL_ENVS=(gnorm2-tf215 aioner-tf23 aioner-tf23-gpu nlmchem-py39)

# ── find conda ─────────────────────────────────────────────────────────────────

CONDA=""
for candidate in \
    "$(which conda 2>/dev/null || true)" \
    /opt/conda/bin/conda \
    /usr/local/conda/bin/conda \
    "$HOME/miniforge3/bin/conda" \
    "$HOME/miniconda3/bin/conda"; do
    if [[ -n "$candidate" && -f "$candidate" ]]; then
        CONDA="$candidate"
        break
    fi
done

if [[ -z "$CONDA" ]]; then
    echo "ERROR: conda not found" >&2
    exit 1
fi
echo "Using conda: $CONDA"

# ── ensure conda-pack is installed in base ────────────────────────────────────

if ! "$CONDA" run -n base python -c "import conda_pack" 2>/dev/null; then
    echo "Installing conda-pack into base env..."
    "$CONDA" install -y -n base -c conda-forge conda-pack
fi

# ── select envs ───────────────────────────────────────────────────────────────

if [[ $# -gt 0 ]]; then
    ENVS=("$@")
else
    ENVS=("${ALL_ENVS[@]}")
fi

# ── pack and upload ───────────────────────────────────────────────────────────

for env in "${ENVS[@]}"; do
    if ! "$CONDA" env list | grep -q "^${env} "; then
        echo "WARNING: conda env '${env}' not found — skipping"
        continue
    fi

    out="/tmp/${env}.tar.gz"

    echo ""
    echo "=== Packing ${env} → ${out} ==="
    "$CONDA" pack -n "$env" -o "$out" --ignore-missing-files

    size=$(du -sh "$out" | cut -f1)
    echo "=== Uploading ${size} → ${GCS_ENVS}/${env}.tar.gz ==="
    gcloud storage cp "$out" "${GCS_ENVS}/${env}.tar.gz"

    rm -f "$out"
    echo "=== Done: ${env} ==="
done

echo ""
echo "All done. Tarballs at ${GCS_ENVS}/"
echo "Run gcp_server_startup.py on a fresh VM to verify restore works."
