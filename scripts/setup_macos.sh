#!/usr/bin/env bash
set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
CRF_DIR="$REPO_DIR/tmvar/CRF"

# ── 1. Require macOS ─────────────────────────────────────────────────────────
if [[ "$(uname)" != "Darwin" ]]; then
    echo "This script is for macOS only." >&2
    exit 1
fi

# ── 2. Require Homebrew ──────────────────────────────────────────────────────
if ! command -v brew &>/dev/null; then
    echo "ERROR: Homebrew is not installed. Install it from https://brew.sh then re-run this script." >&2
    exit 1
fi

# ── 3. Install CRF++ ─────────────────────────────────────────────────────────
if ! command -v crf_test &>/dev/null; then
    echo "Installing CRF++ via Homebrew ..."
    brew install crf++
else
    echo "CRF++ already installed: $(which crf_test)"
fi

# ── 4. Write shims into tmvar/CRF/ ───────────────────────────────────────────
if [[ ! -d "$CRF_DIR" ]]; then
    echo "ERROR: $CRF_DIR does not exist. Run scripts/download_tmvar_data.sh first." >&2
    exit 1
fi

echo "Writing CRF shims into $CRF_DIR ..."

cat > "$CRF_DIR/crf_test" <<'EOF'
#!/usr/bin/env bash
# Shim: delegates to system crf_test (installed via Homebrew on macOS)
exec crf_test "$@"
EOF
chmod +x "$CRF_DIR/crf_test"

cat > "$CRF_DIR/crf_learn" <<'EOF'
#!/usr/bin/env bash
# Shim: delegates to system crf_learn (installed via Homebrew on macOS)
exec crf_learn "$@"
EOF
chmod +x "$CRF_DIR/crf_learn"

echo "Done. tmVar is ready to run on macOS."
