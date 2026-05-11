#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMVAR_DIR="$REPO_DIR/tmvar"
TMP_DIR="$(mktemp -d)"
ARCHIVE="$TMP_DIR/tmVar3.tar.gz"
EXTRACT_DIR="$TMP_DIR/tmVar3"

if [[ -d "$TMVAR_DIR/Database" && -d "$TMVAR_DIR/CRF" ]]; then
    echo "tmVar3 data already present, skipping download."
else
    echo "Downloading tmVar3 archive to $TMP_DIR ..."
    curl -fL --progress-bar \
        "https://ftp.ncbi.nlm.nih.gov/pub/lu/tmVar3/tmVar3.tar.gz" \
        -o "$ARCHIVE"

    echo "Unpacking ..."
    mkdir -p "$EXTRACT_DIR"
    tar -xzf "$ARCHIVE" -C "$EXTRACT_DIR" --strip-components=1

    echo "Moving Database and CRF into $TMVAR_DIR ..."
    mv "$EXTRACT_DIR/Database" "$TMVAR_DIR/Database"
    mv "$EXTRACT_DIR/CRF"      "$TMVAR_DIR/CRF"

    echo "Cleaning up tmVar tmp ..."
    rm -rf "$TMP_DIR"
fi

# --- GNorm2 ---
GNORM2_DIR="$REPO_DIR"
GNORM2_TMP="$(mktemp -d)"
GNORM2_ARCHIVE="$GNORM2_TMP/GNorm2.tar.gz"

if [[ -d "$GNORM2_DIR/GNorm2" ]]; then
    echo "GNorm2 data already present, skipping download."
else
    echo "Downloading GNorm2 archive to $GNORM2_TMP ..."
    curl -fL --progress-bar \
        "https://ftp.ncbi.nlm.nih.gov/pub/lu/GNorm2/GNorm2.tar.gz" \
        -o "$GNORM2_ARCHIVE"

    echo "Unpacking GNorm2 ..."
    tar -xzf "$GNORM2_ARCHIVE" -C "$GNORM2_DIR"

    echo "Cleaning up GNorm2 tmp ..."
    rm -rf "$GNORM2_TMP"
fi

# --- GNorm2 examples ---
GNORM2_EXAMPLES_DIR="$REPO_DIR/GNorm2/examples"
GNORM2_EXAMPLES_TMP="$(mktemp -d)"
GNORM2_EXAMPLES_ARCHIVE="$GNORM2_EXAMPLES_TMP/examples.tar.gz"

if [[ -d "$GNORM2_EXAMPLES_DIR" ]]; then
    echo "GNorm2 examples already present, skipping download."
else
    if [[ ! -d "$REPO_DIR/GNorm2" ]]; then
        echo "ERROR: $REPO_DIR/GNorm2 does not exist. Download GNorm2 data first." >&2
        exit 1
    fi

    echo "Downloading GNorm2 examples ..."
    curl -fL --progress-bar \
        "https://www.ncbi.nlm.nih.gov/CBBresearch/Lu/Demo/tmTools/download/GNorm2/examples.tar.gz" \
        -o "$GNORM2_EXAMPLES_ARCHIVE"

    echo "Unpacking GNorm2 examples ..."
    tar -xzf "$GNORM2_EXAMPLES_ARCHIVE" -C "$REPO_DIR/GNorm2"
    cp "$GNORM2_EXAMPLES_DIR"/* "$REPO_DIR/GNorm2/input/"

    echo "Cleaning up examples tmp ..."
    rm -rf "$GNORM2_EXAMPLES_TMP"
fi

echo "Done."
