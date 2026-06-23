#!/usr/bin/env bash
# sync_pub_data.sh — sync publication data between VM and GCS
#
# GCS layout:   gs://<bucket>/{pmid}/
# VM layout:    /data/pub-data/{pmid}/
#
# Usage:
#   bash sync_pub_data.sh --bucket <bucket> down [PMID...]     # GCS → VM  (default: all papers)
#   bash sync_pub_data.sh --bucket <bucket> up   [PMID...]     # VM  → GCS (default: all papers)
#
# Examples:
#   bash sync_pub_data.sh --bucket civic-pubtator-pub-data down               # sync all pub-data from GCS
#   bash sync_pub_data.sh --bucket civic-pubtator-pub-data down 36922589      # sync one paper from GCS
#   bash sync_pub_data.sh --bucket civic-pubtator-pub-data up 36922589        # upload results for one paper
#   bash sync_pub_data.sh --bucket civic-pubtator-pub-data up                 # upload all local results

set -euo pipefail

LOCAL="/data/pub-data"

die()  { echo "ERROR: $*" >&2; exit 1; }
info() { echo "[sync_pub_data] $*"; }

usage() {
    echo "Usage: $0 --bucket <bucket-name> <up|down> [PMID...]"
    echo ""
    echo "Arguments:"
    echo "  --bucket <name>   GCS bucket name (e.g. civic-pubtator-pub-data)"
    echo "  up|down           Direction: upload VM→GCS or download GCS→VM"
    echo "  [PMID...]         Optional list of PMIDs; omit to sync all"
    echo ""
    echo "Examples:"
    echo "  $0 --bucket civic-pubtator-pub-data down               # sync all pub-data from GCS"
    echo "  $0 --bucket civic-pubtator-pub-data down 36922589      # sync one paper from GCS"
    echo "  $0 --bucket civic-pubtator-pub-data up 36922589        # upload results for one paper"
    echo "  $0 --bucket civic-pubtator-pub-data up                 # upload all local results"
}

BUCKET_NAME=""

while [[ $# -gt 0 ]]; do
    case "$1" in
        -h|--help)
            usage
            exit 0
            ;;
        --bucket)
            [[ -n "${2:-}" ]] || die '"--bucket" requires a non-empty argument.'
            BUCKET_NAME="$2"
            shift 2
            ;;
        --local-dir)
            [[ -n "${2:-}" ]] || die '"--local-dir" requires a non-empty argument.'
            LOCAL="$2"
            shift 2
            ;;
        *)
            break
            ;;
    esac
done

if [[ -z "$BUCKET_NAME" ]]; then
    usage >&2
    die '"--bucket" is required.'
fi

BUCKET="gs://${BUCKET_NAME}"

DIRECTION=${1:-}
shift || true

if [[ -z "$DIRECTION" || ( "$DIRECTION" != "up" && "$DIRECTION" != "down" ) ]]; then
    usage >&2
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
            gcloud storage rsync -r "$gcs_path" "${local_dir}/"
        else
            info "Uploading ${pmid}: ${local_dir}/ → ${gcs_path}"
            gcloud storage rsync -r "${local_dir}/" "$gcs_path"
        fi
    done
else
    # Sync entire pub-data directory
    if [[ "$DIRECTION" == "down" ]]; then
        info "Downloading all pub-data: ${BUCKET}/ → ${LOCAL}/"
        gcloud storage rsync -r "${BUCKET}/" "${LOCAL}/"
    else
        info "Uploading all pub-data: ${LOCAL}/ → ${BUCKET}/"
        gcloud storage rsync -r "${LOCAL}/" "${BUCKET}/"
    fi
fi

info "Done."
