#!/usr/bin/env bash
# sync_tool_data.sh — sync tool model files between VM and GCS
#
# GCS layout:   gs://civic-pubtator/tool-data/{GNorm2,AIONER,tmvar,NLMChem}/
# VM layout:
#   GNorm2, AIONER, NLMChem  →  /data/tool-data/<tool>/
#                                (symlinked into /opt/civic-pubtator/ by startup script)
#   tmvar                    →  /opt/civic-pubtator/tmvar/  (already in git repo;
#                                startup script leaves the real dir in place)
#
# Usage:
#   bash sync_tool_data.sh down [TOOL...]     # GCS → VM  (default: all tools)
#   bash sync_tool_data.sh up   [TOOL...]     # VM  → GCS (default: all tools)
#
# Examples:
#   bash sync_tool_data.sh down               # sync all tools from GCS
#   bash sync_tool_data.sh down GNorm2 AIONER # sync only GNorm2 and AIONER
#   bash sync_tool_data.sh up tmvar           # upload updated tmvar data to GCS

set -euo pipefail

BUCKET="gs://civic-pubtator/tool-data"
LOCAL="/data/tool-data"
REPO_DIR="/opt/civic-pubtator"
ALL_TOOLS=(GNorm2 AIONER tmvar NLMChem)

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[sync_tool_data] $*"; }

DIRECTION=${1:-}
shift || true

if [[ -z "$DIRECTION" || ( "$DIRECTION" != "up" && "$DIRECTION" != "down" ) ]]; then
    echo "Usage: $0 <up|down> [TOOL...]"
    echo "Tools: ${ALL_TOOLS[*]}"
    exit 1
fi

# If specific tools were listed use those, otherwise sync all
if [[ $# -gt 0 ]]; then
    TOOLS=("$@")
else
    TOOLS=("${ALL_TOOLS[@]}")
fi

for tool in "${TOOLS[@]}"; do
    gcs_path="${BUCKET}/${tool}/"

    # tmvar lives directly in the git repo (not under /data/tool-data) because
    # the repo already contains its source and small config files.  Only the
    # large Database/ and CRF/ subdirectories come from GCS.
    if [[ "$tool" == "tmvar" ]]; then
        local_dir="${REPO_DIR}/tmvar"
    else
        local_dir="${LOCAL}/${tool}"
    fi

    mkdir -p "$local_dir"

    if [[ "$DIRECTION" == "down" ]]; then
        info "Downloading ${tool}: ${gcs_path} → ${local_dir}/"
        gcloud storage rsync -r "$gcs_path" "${local_dir}/"
    else
        info "Uploading ${tool}: ${local_dir}/ → ${gcs_path}"
        gcloud storage rsync -r "${local_dir}/" "$gcs_path"
    fi
done

info "Done."
