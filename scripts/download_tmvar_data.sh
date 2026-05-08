#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
TMVAR_DIR="$REPO_DIR/tmvar"
TMP_DIR="$(mktemp -d)"
ARCHIVE="$TMP_DIR/tmVar3.tar.gz"
EXTRACT_DIR="$TMP_DIR/tmVar3"

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

echo "Cleaning up ..."
rm -rf "$TMP_DIR"

echo "Done."
