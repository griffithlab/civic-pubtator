#!/usr/bin/env python3
"""
summarize_corpus.py — Generate an interactive HTML corpus summary report.

Reads per-publication results from a parent directory (local or GCS), extracts
entity counts from report_<pubid>.tsv and pipeline metrics from
pipeline_stats.tsv, and writes a single self-contained HTML file with a
sortable, searchable summary table (one row per publication) to --output-dir.
Per-publication HTML reports are also copied so their hyperlinks work.

Inputs:
  <input-dir>/<pubid>/report_<pubid>.tsv   — entity annotations (entity_category, count, …)
  <input-dir>/<pubid>/pipeline_stats.tsv   — per-step runtime stats (TOTAL row used)
  <input-dir>/<pubid>/report_<pubid>.html  — copied to output-dir for hyperlinking

Outputs:
  <output-dir>/corpus_summary.html
  <output-dir>/report_<pubid>.html  (one per publication)

No third-party dependencies — stdlib only.
"""

import argparse
import csv
import datetime
import logging
import os
import re
import shutil
import subprocess
import tempfile
from collections import defaultdict

log = logging.getLogger(__name__)

# Preferred display order for entity-category columns.
PREFERRED_CATEGORIES = ["Gene", "Disease", "Chemical", "Variant", "Organism", "NER_AIONER"]


# ── Helpers ───────────────────────────────────────────────────────────────────

def is_gcs(path):
    return path.startswith("gs://")


def parse_runtime_to_seconds(s):
    """Convert '10m 39s', '3s', '1m 42s' → integer seconds."""
    s = (s or "").strip()
    m = re.match(r'^(?:(\d+)m\s*)?(\d+)s?$', s)
    if m:
        return int(m.group(1) or 0) * 60 + int(m.group(2) or 0)
    return None


def _int_or_na(s):
    try:
        return int(s)
    except (ValueError, TypeError):
        return None


def _fmt(n):
    """Format integer with commas, or return 'N/A'."""
    return f"{n:,}" if isinstance(n, int) else "N/A"


def _esc(s):
    """Minimal HTML escape."""
    return (s or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


# ── GCS helpers ───────────────────────────────────────────────────────────────

def gcs_list_dirs(gcs_path):
    """Return sorted list of immediate subdirectory names under a GCS path."""
    prefix = gcs_path.rstrip("/") + "/"
    try:
        result = subprocess.run(
            ["gcloud", "storage", "ls", prefix],
            capture_output=True, text=True, check=True,
        )
    except subprocess.CalledProcessError as exc:
        log.error("gcloud storage ls failed for %s: %s", gcs_path, exc.stderr.strip())
        return []
    dirs = []
    for line in result.stdout.splitlines():
        line = line.strip()
        if line.startswith(prefix) and line.endswith("/"):
            name = line[len(prefix):].rstrip("/")
            if name:
                dirs.append(name)
    return sorted(dirs)


def gcs_cp(src, dst):
    """Copy a single GCS object to a local path. Returns True on success."""
    os.makedirs(os.path.dirname(dst), exist_ok=True)
    try:
        subprocess.run(
            ["gcloud", "storage", "cp", src, dst],
            capture_output=True, text=True, check=True,
        )
        return True
    except subprocess.CalledProcessError as exc:
        log.warning("gcloud storage cp failed (%s → %s): %s", src, dst, exc.stderr.strip())
        return False


# ── Publication discovery ─────────────────────────────────────────────────────

def discover_publications(input_dir):
    """Return sorted list of pubids found as immediate subdirectories of input_dir."""
    if is_gcs(input_dir):
        return gcs_list_dirs(input_dir)
    if not os.path.isdir(input_dir):
        log.error("Input directory does not exist: %s", input_dir)
        return []
    return sorted(
        e for e in os.listdir(input_dir)
        if os.path.isdir(os.path.join(input_dir, e))
    )


def get_local_file(input_dir, pubid, filename, tmp_dir):
    """
    Return a local path for input_dir/<pubid>/<filename>.
    For GCS sources, downloads to tmp_dir/<pubid>/<filename> (cached on reuse).
    Returns None if the file is not found or download fails.
    """
    if is_gcs(input_dir):
        local = os.path.join(tmp_dir, pubid, filename)
        if os.path.isfile(local):
            return local
        src = f"{input_dir.rstrip('/')}/{pubid}/{filename}"
        return local if gcs_cp(src, local) else None
    local = os.path.join(input_dir, pubid, filename)
    return local if os.path.isfile(local) else None


# ── File parsers ──────────────────────────────────────────────────────────────

def parse_report_tsv(path):
    """
    Parse report_<pubid>.tsv.

    Actual columns: entity_category, entity_type, mention, identifier,
                    identifier_name, hgvs, count, doc_keys, source

    Returns {'entity_counts': {category: total_mention_count}}.
    """
    counts = defaultdict(int)
    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            fields = reader.fieldnames or []
            if "entity_category" not in fields:
                log.warning("'entity_category' column missing in %s", path)
                return {"entity_counts": {}}
            has_count = "count" in fields
            for row in reader:
                cat = (row.get("entity_category") or "").strip()
                if not cat:
                    continue
                try:
                    n = int(row["count"]) if has_count else 1
                except (ValueError, TypeError):
                    n = 1
                counts[cat] += n
    except OSError as exc:
        log.warning("Could not read %s: %s", path, exc)
    return {"entity_counts": dict(counts)}


def parse_pipeline_stats(path):
    """
    Parse pipeline_stats.tsv.

    Columns: step, step_name, label, chars, words, runtime, input_name, output_file
    The TOTAL row (step == 'TOTAL') contains aggregate chars/words/runtime.
    Document count = number of rows with step == '1' (GROBID, one row per document).

    Returns:
      doc_count        int
      total_chars      int or None
      total_words      int or None
      total_runtime_s  int or None   (seconds)
      total_runtime_str str
    """
    doc_count = 0
    total_chars = None
    total_words = None
    total_runtime_s = None
    total_runtime_str = "N/A"

    try:
        with open(path, newline="", encoding="utf-8") as fh:
            reader = csv.DictReader(fh, delimiter="\t")
            for row in reader:
                step = (row.get("step") or "").strip()
                if step == "1":
                    doc_count += 1
                elif step == "TOTAL":
                    total_chars = _int_or_na(row.get("chars", ""))
                    total_words = _int_or_na(row.get("words", ""))
                    rt = (row.get("runtime") or "").strip()
                    total_runtime_str = rt or "N/A"
                    total_runtime_s = parse_runtime_to_seconds(rt)
    except OSError as exc:
        log.warning("Could not read %s: %s", path, exc)

    return {
        "doc_count": doc_count,
        "total_chars": total_chars,
        "total_words": total_words,
        "total_runtime_s": total_runtime_s,
        "total_runtime_str": total_runtime_str,
    }


# ── CIViC metadata ────────────────────────────────────────────────────────────

def load_civic_metadata_map():
    """
    Fetch all PUBMED sources from CIViC via civicpy and build lookup maps.

    Returns two dicts (pmid_map, pmcid_map) each mapping ID strings to:
      {'title': str, 'date': str, 'civic_sid': int}
    Returns ({}, {}) on any failure (civicpy absent, network error, etc.).
    """
    try:
        from civicpy import civic  # optional dependency
        sources = civic.get_all_sources()
        pubmed = [s for s in sources if s.source_type == "PUBMED"]
        pmid_map, pmcid_map = {}, {}
        for s in pubmed:
            entry = {
                "title":     s.title or None,
                "date":      s.publication_date or None,
                "civic_sid": s.id,
            }
            if s.citation_id:
                pmid_map[str(s.citation_id)] = entry
            if s.pmc_id:
                pmcid_map[str(s.pmc_id)] = entry
        log.info("Loaded CIViC metadata for %d PUBMED sources.", len(pmid_map))
        return pmid_map, pmcid_map
    except Exception as exc:
        log.warning("Could not load CIViC metadata: %s", exc)
        return {}, {}


def lookup_civic_metadata(pubid, pmid_map, pmcid_map):
    """
    Return (title, date) for pubid using pre-built CIViC maps.
    Handles both numeric PMIDs and PMC-prefixed IDs.
    """
    pid = str(pubid)
    if pid.upper().startswith("PMC"):
        entry = pmcid_map.get(pid) or pmcid_map.get(pid.upper())
    else:
        entry = pmid_map.get(pid)
    if entry:
        return entry.get("title"), entry.get("date")
    return None, None


# ── HTML report copy ──────────────────────────────────────────────────────────

def copy_html_report(input_dir, pubid, output_dir, tmp_dir):
    """
    Copy report_<pubid>.html to output_dir.  Returns True on success.
    """
    filename = f"report_{pubid}.html"
    dst = os.path.join(output_dir, filename)
    if is_gcs(input_dir):
        src = get_local_file(input_dir, pubid, filename, tmp_dir)
        if src is None:
            log.warning("HTML report not found in GCS for %s", pubid)
            return False
        shutil.copy2(src, dst)
    else:
        src = os.path.join(input_dir, pubid, filename)
        if not os.path.isfile(src):
            log.warning("HTML report not found: %s", src)
            return False
        shutil.copy2(src, dst)
    return True


# ── HTML rendering ────────────────────────────────────────────────────────────

_CSS = """
<style>
* { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  font-size: 13px; background: #f0f2f5; color: #222;
}
h1 { padding: 1.2rem 1.5rem 0.6rem; font-size: 1.35rem; color: #1a3a5c; }
.wrapper { overflow-x: auto; margin: 0 1rem 1rem; background: white;
           border-radius: 6px; box-shadow: 0 1px 4px rgba(0,0,0,.15); }
#summary-table { border-collapse: collapse; width: 100%; }
#summary-table th, #summary-table td {
  border: 1px solid #d0d7e0; padding: 5px 8px; white-space: nowrap;
}
#summary-table thead th {
  background: #1a3a5c; color: #fff; cursor: pointer;
  position: sticky; top: 0; z-index: 2; vertical-align: top;
  user-select: none;
}
#summary-table thead th:hover { background: #25527a; }
#summary-table tbody tr:nth-child(even) { background: #f6f8fb; }
#summary-table tbody tr:hover { background: #deeaf8; }
#summary-table td { vertical-align: middle; }
.title-cell {
  max-width: 320px; overflow: hidden;
  text-overflow: ellipsis; white-space: nowrap;
}
.col-search {
  display: block; margin-top: 4px; width: 100%;
  font-size: 11px; padding: 2px 5px;
  background: rgba(255,255,255,.15); border: 1px solid rgba(255,255,255,.4);
  color: #fff; border-radius: 3px;
}
.col-search::placeholder { color: rgba(255,255,255,.55); }
.sort-ind { margin-left: 4px; font-size: 10px; }
.footer {
  margin: 0.5rem 1.5rem 2rem;
  font-size: 11px; color: #666; line-height: 2;
}
.footer a { color: #1a3a5c; }
</style>
"""

_JS = """
<script>
(function () {
  var sortCol = -1, sortAsc = true;

  function numVal(td) {
    var ds = td ? td.getAttribute('data-sort') : null;
    return ds !== null ? parseFloat(ds) : NaN;
  }

  function textVal(td) {
    return td ? td.innerText.trim().toLowerCase() : '';
  }

  function sortTable(col) {
    var tbl = document.getElementById('summary-table');
    var tbody = tbl.tBodies[0];
    var rows = Array.from(tbody.rows);
    sortAsc = (sortCol === col) ? !sortAsc : true;
    sortCol = col;

    rows.sort(function (a, b) {
      var va = numVal(a.cells[col]), vb = numVal(b.cells[col]);
      if (!isNaN(va) && !isNaN(vb)) return sortAsc ? va - vb : vb - va;
      var sa = textVal(a.cells[col]), sb = textVal(b.cells[col]);
      return sortAsc ? sa.localeCompare(sb) : sb.localeCompare(sa);
    });
    rows.forEach(function (r) { tbody.appendChild(r); });

    document.querySelectorAll('.sort-ind').forEach(function (el, i) {
      el.textContent = (i === col) ? (sortAsc ? ' ▲' : ' ▼') : '';
    });
  }

  function filterTable() {
    var filters = Array.from(document.querySelectorAll('.col-search'))
      .map(function (inp) {
        return { col: parseInt(inp.getAttribute('data-col')), val: inp.value.toLowerCase() };
      })
      .filter(function (f) { return f.val.length > 0; });

    Array.from(document.getElementById('summary-table').tBodies[0].rows)
      .forEach(function (row) {
        var hide = filters.some(function (f) {
          var td = row.cells[f.col];
          return td && !td.innerText.toLowerCase().includes(f.val);
        });
        row.style.display = hide ? 'none' : '';
      });
  }

  window.sortTable = sortTable;
  window.filterTable = filterTable;
})();
</script>
"""


def render_html(rows, all_categories, input_dir, output_dir, generated_at):
    """
    Build corpus_summary.html as a string.

    rows: list of dicts — pubid, title, date, doc_count, total_runtime_s,
          total_runtime_str, total_words, total_chars, total_entities,
          entity_counts {category: int}
    all_categories: ordered list of entity_category column names to include
    """
    # Column definitions: (key, header_label, is_text_searchable)
    fixed_cols = [
        ("pubid",            "Publication ID", True),
        ("date",             "Date",           False),
        ("title",            "Title",          True),
        ("doc_count",        "Documents",      False),
        ("total_runtime_s",  "Run Time (s)",   False),
        ("total_words",      "Total Words",    False),
        ("total_chars",      "Total Chars",    False),
        ("total_entities",   "Total Entities", False),
    ]
    cat_cols = [(cat, f"N {cat}", False) for cat in all_categories]
    columns = fixed_cols + cat_cols

    # --- thead ---
    th_cells = []
    for i, (key, label, searchable) in enumerate(columns):
        search = (
            f'<input type="text" class="col-search" data-col="{i}" '
            f'placeholder="filter…" oninput="filterTable()">'
        ) if searchable else ""
        th_cells.append(
            f'<th onclick="sortTable({i})">'
            f'{_esc(label)}<span class="sort-ind"></span>'
            + (f'<br>{search}' if search else "")
            + "</th>"
        )
    thead = "<thead><tr>" + "".join(th_cells) + "</tr></thead>"

    # --- tbody ---
    tbody_rows = []
    for row in rows:
        cells = []
        for i, (key, label, _) in enumerate(columns):
            if key == "pubid":
                pid = _esc(row["pubid"])
                cells.append(f'<td><a href="report_{pid}.html">{pid}</a></td>')

            elif key == "date":
                cells.append(f'<td>{_esc(row.get("date") or "N/A")}</td>')

            elif key == "title":
                t = _esc(row.get("title") or "N/A")
                cells.append(f'<td class="title-cell" title="{t}">{t}</td>')

            elif key == "total_runtime_s":
                s = row.get("total_runtime_s")
                disp = _esc(row.get("total_runtime_str") or "N/A")
                sort = s if isinstance(s, int) else -1
                cells.append(f'<td data-sort="{sort}">{disp}</td>')

            elif key in ("doc_count", "total_words", "total_chars", "total_entities"):
                v = row.get(key)
                sort = v if isinstance(v, int) else -1
                cells.append(f'<td data-sort="{sort}">{_fmt(v)}</td>')

            else:
                # entity category column
                v = row["entity_counts"].get(key, 0)
                cells.append(f'<td data-sort="{v}">{v:,}</td>')

        tbody_rows.append("<tr>" + "".join(cells) + "</tr>")

    tbody = "<tbody>" + "\n".join(tbody_rows) + "</tbody>"
    table = f'<table id="summary-table">{thead}{tbody}</table>'

    footer = (
        f'<div class="footer">'
        f'Report generated: {_esc(generated_at)}<br>'
        f'Data source: {_esc(input_dir)}<br>'
        f'Publications summarized: {len(rows)}<br>'
        f'<a href="https://github.com/griffithlab/civic-pubtator">'
        f'civic-pubtator on GitHub</a>'
        f'</div>'
    )

    return (
        "<!DOCTYPE html>\n"
        '<html lang="en">\n'
        "<head>\n"
        '<meta charset="UTF-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1">\n'
        "<title>civic-pubtator corpus summary</title>\n"
        + _CSS
        + "</head>\n<body>\n"
        "<h1>civic-pubtator — corpus summary</h1>\n"
        '<div class="wrapper">\n' + table + "\n</div>\n"
        + footer + "\n"
        + _JS
        + "\n</body>\n</html>\n"
    )


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description=(
            "Generate an interactive HTML corpus summary across all "
            "civic-pubtator publications processed to date."
        )
    )
    parser.add_argument(
        "--input-dir", required=True,
        help="Local path or GCS path (gs://…) containing per-publication subdirs",
    )
    parser.add_argument(
        "--output-dir", required=True,
        help="Local directory to write corpus_summary.html and per-pub HTML reports",
    )
    parser.add_argument(
        "--no-civic", action="store_true",
        help="Skip CIViC metadata lookups; title and date will appear as N/A",
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    os.makedirs(args.output_dir, exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="summarize_corpus_")

    try:
        pubids = discover_publications(args.input_dir)
        log.info("Found %d publication directories.", len(pubids))

        # Load CIViC metadata once for all publications
        pmid_map, pmcid_map = ({}, {})
        if not args.no_civic:
            log.info("Loading CIViC source metadata…")
            pmid_map, pmcid_map = load_civic_metadata_map()

        all_categories_seen = set()
        pub_rows = []

        for pubid in pubids:
            log.info("Processing %s", pubid)

            report_path = get_local_file(
                args.input_dir, pubid, f"report_{pubid}.tsv", tmp_dir
            )
            stats_path = get_local_file(
                args.input_dir, pubid, "pipeline_stats.tsv", tmp_dir
            )

            if report_path is None:
                log.warning("Skipping %s — report_%s.tsv not found", pubid, pubid)
                continue
            if stats_path is None:
                log.warning("Skipping %s — pipeline_stats.tsv not found", pubid)
                continue

            report_data = parse_report_tsv(report_path)
            stats_data  = parse_pipeline_stats(stats_path)
            all_categories_seen.update(report_data["entity_counts"].keys())

            title, date = lookup_civic_metadata(pubid, pmid_map, pmcid_map)

            pub_rows.append({
                "pubid":            pubid,
                "title":            title,
                "date":             date,
                "doc_count":        stats_data["doc_count"],
                "total_runtime_s":  stats_data["total_runtime_s"],
                "total_runtime_str": stats_data["total_runtime_str"],
                "total_words":      stats_data["total_words"],
                "total_chars":      stats_data["total_chars"],
                "total_entities":   sum(report_data["entity_counts"].values()),
                "entity_counts":    report_data["entity_counts"],
            })

            copy_html_report(args.input_dir, pubid, args.output_dir, tmp_dir)

        # Ordered category columns: preferred first, then any others alphabetically
        all_categories = [c for c in PREFERRED_CATEGORIES if c in all_categories_seen]
        all_categories += sorted(
            c for c in all_categories_seen if c not in PREFERRED_CATEGORIES
        )

        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html = render_html(
            pub_rows, all_categories, args.input_dir, args.output_dir, generated_at
        )

        out_path = os.path.join(args.output_dir, "corpus_summary.html")
        with open(out_path, "w", encoding="utf-8") as fh:
            fh.write(html)

        print(
            f"Done. {len(pub_rows)} publications summarized. "
            f"Report written to {out_path}"
        )

    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


if __name__ == "__main__":
    main()
