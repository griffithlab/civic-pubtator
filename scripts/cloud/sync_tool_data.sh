#!/usr/bin/env bash
# sync_tool_data.sh — download tool model files from GCS into the repo
#
# GCS layout:   gs://civic-pubtator-tool-data/{GNorm2,AIONER,tmvar,NLMChem}/
#               Each tool directory contains one or more tarballs (.tar.gz);
#               NLMChem also includes non-archive files (.docx, .zip).
# VM layout:    /opt/civic-pubtator/{GNorm2,AIONER,tmvar,NLMChem}/
#               (large data files gitignored; small config/code tracked in git)
#
# Usage:
#   bash sync_tool_data.sh [TOOL...]     # default: all tools
#
# Examples:
#   bash sync_tool_data.sh               # sync all tools from GCS
#   bash sync_tool_data.sh GNorm2 AIONER # sync only GNorm2 and AIONER
#
# Behaviour:
#   Each tool's archives are downloaded to a temp directory, extracted there,
#   then merged into the tool's repo directory.  Files already present in the
#   repo are never overwritten, even if the tarball contains a different version.
#   Non-archive files (.docx, .zip, etc.) are copied as-is only if absent.

set -euo pipefail

BUCKET="gs://civic-pubtator-tool-data"
REPO_DIR="/opt/civic-pubtator"
ALL_TOOLS=(GNorm2 AIONER tmvar NLMChem)

info() { echo "[sync_tool_data] $*"; }

# If specific tools were listed use those, otherwise sync all
if [[ $# -gt 0 ]]; then
    TOOLS=("$@")
else
    TOOLS=("${ALL_TOOLS[@]}")
fi

for tool in "${TOOLS[@]}"; do
    gcs_path="${BUCKET}/${tool}/"
    tool_dir="${REPO_DIR}/${tool}"

    mkdir -p "$tool_dir"

    tmp_dir=$(mktemp -d)
    info "Downloading ${tool} archives: ${gcs_path} → ${tmp_dir}/"
    # Non-recursive: only files directly in the tool's GCS directory
    gcloud storage rsync "${gcs_path}" "${tmp_dir}/"

    for f in "${tmp_dir}"/*; do
        [[ -e "$f" ]] || continue
        fname=$(basename "$f")

        if [[ "$fname" == *.tar.gz ]]; then
            extract_dir="${tmp_dir}/${fname%.tar.gz}"
            mkdir -p "$extract_dir"
            info "  Extracting ${fname}..."
            tar xzf "$f" -C "$extract_dir"

            # Strip a top-level directory only if its name matches the tool name
            # (i.e. the tarball was packed from outside the tool dir).  If the
            # top-level dir has a different name it is a component subdirectory
            # that should be preserved (e.g. NLMChemTaggerNormalizer inside NLMChem).
            mapfile -t top_entries < <(ls -1 "$extract_dir")
            if [[ ${#top_entries[@]} -eq 1 && -d "${extract_dir}/${top_entries[0]}" && "${top_entries[0]}" == "$tool" ]]; then
                src="${extract_dir}/${top_entries[0]}/"
            else
                src="${extract_dir}/"
            fi

            info "  Merging into ${tool_dir}/ (skipping files already present)..."
            rsync -a --ignore-existing "$src" "${tool_dir}/"
        else
            # Non-archive file: copy only if not already present in the repo
            dest="${tool_dir}/${fname}"
            if [[ ! -e "$dest" ]]; then
                info "  Copying ${fname} → ${tool_dir}/"
                cp "$f" "$dest"
            else
                info "  Skipping ${fname} (already present in repo)"
            fi
        fi
    done

    rm -rf "$tmp_dir"
    info "Done: ${tool}"
done

info "Done."
