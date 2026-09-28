#!/usr/bin/env bash
# TEI + table-crop test. For each publication:
#   1. pdf_to_bioc.py on the main PDF(s) into /data/tei_test/<id>/02_grobid
#      (publication dirs untouched); BioC text must match the existing output.
#   2. backfill_figures.py on a copy of 01_source + 02_grobid in
#      /data/tei_test/backfill/<id>, run twice: the second pass must skip.
#
# Usage: bash src/testing/test_tei_tables_vm.sh <pub_dir> [<pub_dir> ...]
set -uo pipefail
REPO="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
OUT=/data/tei_test

curl -sf http://localhost:8070/api/isalive >/dev/null \
  || { echo "GROBID is not running — start it with: sudo systemctl start grobid"; exit 1; }

rm -rf "$OUT"
mkdir -p "$OUT/backfill"
for pub in "$@"; do
  pub=${pub%/}
  id=$(basename "$pub")
  dest="$OUT/$id/02_grobid"
  mkdir -p "$dest"
  echo "=== $id"
  python3 "$REPO/src/pipeline_steps/pdf_to_bioc.py" "$pub/01_source" "$dest"

  # The GROBID request is unchanged, so the BioC text must be too
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
    fi
  done

  # Backfill on a copy: first pass fills TEI + tables, second pass must skip
  bf="$OUT/backfill/$id"
  mkdir -p "$bf"
  cp -r "$pub/01_source" "$pub/02_grobid" "$bf/"
  echo "  backfill pass 1:"
  python3 "$REPO/src/pipeline_steps/backfill_figures.py" "$bf" 2>&1 | grep -E "Docs|images|WARNING|SKIP" | sed 's/^/    /'
  echo "  backfill pass 2 (expect 0 backfilled):"
  python3 "$REPO/src/pipeline_steps/backfill_figures.py" "$bf" 2>&1 | grep -E "Docs (backfilled|already)" | sed 's/^/    /'
done

python3 - "$OUT" <<'EOF'
import glob, gzip, json, os, sys
import xml.etree.ElementTree as ET
root = sys.argv[1]
T = "{http://www.tei-c.org/ns/1.0}"
print(f"\n{'pub':<14}{'doc':<34}{'heads':>6}{'paras':>6}{'refs':>5}{'figs':>5}{'tabs':>5}"
      f"{'tabPNG':>7}{'figPNG':>7}{'nonASCII':>9}")
for tei in sorted(glob.glob(os.path.join(root, "**", "*.tei.xml.gz"), recursive=True)):
    rel = os.path.relpath(tei, root)
    pub = rel.split(os.sep)[0] if not rel.startswith("backfill") else "bf/" + rel.split(os.sep)[1]
    stem = os.path.basename(tei)[: -len(".tei.xml.gz")]
    text = gzip.open(tei, "rt", encoding="utf-8").read()
    body = ET.fromstring(text).find(f".//{T}body")
    n = lambda tag: len(body.findall(f".//{T}{tag}")) if body is not None else 0
    refs = len([r for r in body.iter(f"{T}ref") if r.get("type") in ("figure", "table")]) if body is not None else 0
    fj = os.path.join(os.path.dirname(tei), "figures", stem, "figures.json")
    figs = tabs = []
    if os.path.exists(fj):
        d = json.load(open(fj)); figs, tabs = d.get("figures", []), d.get("tables")
    tabs_s = "MISSING" if tabs is None else str(len(tabs))
    pngs = lambda recs: sum(len(r["images"]) for r in (recs or []))
    print(f"{pub:<14}{stem[:32]:<34}{n('head'):>6}{n('p'):>6}{refs:>5}{len(figs):>5}{tabs_s:>5}"
          f"{pngs(tabs):>7}{pngs(figs):>7}{sum(ord(c) > 127 for c in text):>9}")

# Every TEI must be invisible to the annotation steps (they glob *.xml)
leaks = [p for p in glob.glob(os.path.join(root, "**", "*.xml"), recursive=True) if ".tei." in p]
print("\nTEI files named *.xml (must be none):", leaks or "none")
EOF

tar -czf /data/tei_test.tar.gz -C /data tei_test
echo -e "\nWrote /data/tei_test.tar.gz ($(du -h /data/tei_test.tar.gz | cut -f1))"
