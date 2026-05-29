#!/usr/bin/env bash
# sync_pub_data.sh — sync publication data between VM and GCS
#
# GCS layout:   gs://civic-pubtator/pub-data/{pmid}/
# VM layout:    /data/pub-data/{pmid}/
#
# Usage:
#   bash sync_pub_data.sh down [PMID...]     # GCS → VM  (default: all papers)
#   bash sync_pub_data.sh up   [PMID...]     # VM  → GCS (default: all papers)
#
# Examples:
#   bash sync_pub_data.sh down               # sync all pub-data from GCS
#   bash sync_pub_data.sh down 36922589      # sync one paper from GCS
#   bash sync_pub_data.sh up 36922589        # upload results for one paper
#   bash sync_pub_data.sh up                 # upload all local results

set -euo pipefail

BUCKET="gs://civic-pubtator/pub-data"
LOCAL="/data/pub-data"

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[sync_pub_data] $*"; }

DIRECTION=${1:-}
shift || true

if [[ -z "$DIRECTION" || ( "$DIRECTION" != "up" && "$DIRECTION" != "down" ) ]]; then
    echo "Usage: $0 <up|down> [PMID...]"
    exit 1
fi

mkdir -p "$LOCAL"

if [[ $# -gt 0 ]]; then
    # Sync specific PMIDs
    for pmid in "$@"; do
        local_dir="${LOCAL}/${pmid}"
        gcs_path="${BUCKET}/${pmid}/"
        mkdir -p "$local_dir"

        if [[ "$DIRECTION" == "down" ]]; then
            info "Downloading ${pmid}: ${gcs_path} → ${local_dir}/"
            gsutil -m rsync -r "$gcs_path" "${local_dir}/"
        else
            info "Uploading ${pmid}: ${local_dir}/ → ${gcs_path}"
            gsutil -m rsync -r "${local_dir}/" "$gcs_path"
        fi
    done
else
    # Sync entire pub-data directory
    if [[ "$DIRECTION" == "down" ]]; then
        info "Downloading all pub-data: ${BUCKET}/ → ${LOCAL}/"
        gsutil -m rsync -r "${BUCKET}/" "${LOCAL}/"
    else
        info "Uploading all pub-data: ${LOCAL}/ → ${BUCKET}/"
        gsutil -m rsync -r "${LOCAL}/" "${BUCKET}/"
    fi
fi

info "Done."
