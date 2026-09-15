#!/usr/bin/env bash
# Figure-extraction test: runs only the GROBID step (pdf_to_bioc.py) on each
# publication's main PDF(s) into /data/figure_test/<id>/02_grobid, leaving the
# publication directories themselves untouched.
#
# Usage: bash src/testing/test_figures_vm.sh <pub_dir> [<pub_dir> ...]
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT=/data/figure_test

curl -sf http://localhost:8070/api/isalive >/dev/null \
  || { echo "GROBID is not running — start it with: sudo systemctl start grobid"; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT"
for pub in "$@"; do
  pub=${pub%/}
  id=$(basename "$pub")
  dest="$OUT/$id/02_grobid"
  mkdir -p "$dest"
  echo "=== $id"
  python3 "$REPO/src/pipeline_steps/pdf_to_bioc.py" "$pub/01_source" "$dest"

  # teiCoordinates should only add attributes, never change extracted text
  for xml in "$dest"/*.xml; do
    [ -f "$xml" ] || continue
    old="$pub/02_grobid/$(basename "$xml")"
    if [ ! -f "$old" ]; then
      echo "  text check: no existing $(basename "$xml") to compare against"
    elif cmp -s "$xml" "$old"; then
      echo "  text check: $(basename "$xml") identical to existing 02_grobid output"
    else
      n=$(diff <(tr '>' '\n' < "$old") <(tr '>' '\n' < "$xml") | grep -c '^[<>]')
      echo "  text check: $(basename "$xml") DIFFERS from existing output ($n changed chunks)"
      diff <(tr '>' '\n' < "$old") <(tr '>' '\n' < "$xml") | head -8
    fi
  done
done

python3 - "$OUT" <<'EOF'
import glob, json, os, sys
root = sys.argv[1]
print(f"\n{'pub':<14}{'pdf':<42}{'figs':>5}{'graphic':>8}{'figure':>7}{'none':>5}{'pngs':>5}")
for fj in sorted(glob.glob(os.path.join(root, "*", "02_grobid", "figures", "*", "figures.json"))):
    parts = fj.split(os.sep)
    figs = json.load(open(fj))["figures"]
    cnt = lambda s: sum(f["source"] == s for f in figs)
    pngs = sum(len(f["images"]) for f in figs)
    print(f"{parts[-5]:<14}{parts[-2][:40]:<42}{len(figs):>5}{cnt('graphic'):>8}{cnt('figure'):>7}{cnt('none'):>5}{pngs:>5}")
EOF

tar -czf /data/figure_test.tar.gz -C /data figure_test
echo -e "\nWrote /data/figure_test.tar.gz ($(du -h /data/figure_test.tar.gz | cut -f1))"
