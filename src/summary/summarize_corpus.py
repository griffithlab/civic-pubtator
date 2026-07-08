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
import sys
import tempfile
from collections import defaultdict

log = logging.getLogger(__name__)

# Preferred display order for entity-category columns.
PREFERRED_CATEGORIES = ["Variant", "Gene", "Chemical", "Disease", "Organism", "NER_AIONER"]

# Override display labels for entity-category table columns.
CAT_DISPLAY_NAMES = {"Chemical": "Drug"}


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


def fmt_seconds(s):
    """Format integer seconds as 'Xh Ym', 'Xm Ys', or 'Xs'."""
    if s is None:
        return "N/A"
    s = int(round(s))
    h, rem = divmod(s, 3600)
    m, sec = divmod(rem, 60)
    if h > 0:
        return f"{h}h {m}m" if m else f"{h}h"
    if m > 0:
        return f"{m}m {sec}s"
    return f"{sec}s"


def _median(values):
    """Median of a sorted list; returns None for empty input."""
    if not values:
        return None
    n = len(values)
    mid = n // 2
    return values[mid] if n % 2 else (values[mid - 1] + values[mid]) // 2


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


# ── Report regeneration ───────────────────────────────────────────────────────

def check_report_inputs(pub_dir):
    """
    Return True if report_civic_pubtator.py has the minimum required inputs.
    Requires at least one of 03_gnorm2/ or 04_tmvar3/ as a non-empty directory.
    """
    for step_dir in ('03_gnorm2', '04_tmvar3'):
        d = os.path.join(pub_dir, step_dir)
        if os.path.isdir(d):
            try:
                next(iter(os.scandir(d)))
                return True
            except StopIteration:
                pass
    return False


def regenerate_report(pub_dir, report_script):
    """Run report_civic_pubtator.py for pub_dir. Returns True on success."""
    try:
        result = subprocess.run(
            [sys.executable, report_script, pub_dir],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            log.warning(
                "Report regeneration failed for %s:\n%s",
                os.path.basename(pub_dir), result.stderr.strip(),
            )
            return False
        log.info("Regenerated report for %s", os.path.basename(pub_dir))
        return True
    except Exception as exc:
        log.warning("Could not regenerate report for %s: %s", os.path.basename(pub_dir), exc)
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
    Step-1 rows are GROBID runs; label 'main' = main article, 's/…' = supplementary.

    Returns:
      doc_count        int  (main + supplementary)
      main_doc_count   int
      supp_doc_count   int
      has_supplements  bool
      total_chars      int or None
      total_words      int or None
      total_runtime_s  int or None   (seconds)
      total_runtime_str str
    """
    main_doc_count = 0
    supp_doc_count = 0
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
                    label = (row.get("label") or "").strip()
                    if label.startswith("s/"):
                        supp_doc_count += 1
                    else:
                        main_doc_count += 1
                elif step == "TOTAL":
                    total_chars = _int_or_na(row.get("chars", ""))
                    total_words = _int_or_na(row.get("words", ""))
                    rt = (row.get("runtime") or "").strip()
                    total_runtime_str = rt or "N/A"
                    total_runtime_s = parse_runtime_to_seconds(rt)
    except OSError as exc:
        log.warning("Could not read %s: %s", path, exc)

    return {
        "doc_count":       main_doc_count + supp_doc_count,
        "main_doc_count":  main_doc_count,
        "supp_doc_count":  supp_doc_count,
        "has_supplements": supp_doc_count > 0,
        "total_chars":     total_chars,
        "total_words":     total_words,
        "total_runtime_s":   total_runtime_s,
        "total_runtime_str": total_runtime_str,
    }


def parse_manifest(path):
    """
    Parse MANIFEST.txt for original supplementary file extensions.

    Returns {'supp_ext_counts': {ext_lowercase: count}}.
    Only files listed under the 'Supplementary files' section are counted.
    """
    supp_ext_counts = defaultdict(int)
    in_supp = False
    if path is None:
        return {"supp_ext_counts": {}}
    try:
        with open(path, encoding="utf-8") as fh:
            for line in fh:
                stripped = line.strip()
                if stripped.startswith("Supplementary files"):
                    in_supp = True
                elif stripped.startswith("===") and in_supp:
                    break
                elif in_supp and stripped.startswith("s/"):
                    fname = stripped.split()[0]   # e.g. "s/Table1.docx"
                    ext = os.path.splitext(fname)[1].lstrip(".").lower()
                    if ext:
                        supp_ext_counts[ext] += 1
    except OSError:
        pass
    return {"supp_ext_counts": dict(supp_ext_counts)}


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
        for _ln in ('civicpy', 'civicpy.civic'):
            logging.getLogger(_ln).setLevel(logging.WARNING)
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
        log.info("Loaded CIViC metadata: %d total sources, %d PUBMED (%d with PMID, %d with PMCID).",
                 len(sources), len(pubmed), len(pmid_map), len(pmcid_map))
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
    Copy report_<pubid>.html to output_dir/pub-reports/.  Returns True on success.
    """
    filename = f"report_{pubid}.html"
    dst = os.path.join(output_dir, "pub-reports", filename)
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
.wrapper { overflow-x: auto; overflow-y: auto; max-height: 80vh;
           margin: 0 1rem 1rem; background: white;
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
  margin: 0.5rem 1.5rem 1rem;
  font-size: 11px; color: #666; line-height: 2;
}
.footer a { color: #1a3a5c; }
/* ── Corpus stats panel ─────────────────────────────────── */
.stats-panel { margin: 0 1rem 2rem; }
.stats-panel > h2 {
  font-size: 1rem; color: #1a3a5c; font-weight: 600;
  border-top: 2px solid #1a3a5c;
  padding-top: 0.75rem; margin-bottom: 0.75rem;
}
.stats-grid {
  display: grid;
  grid-template-columns: repeat(auto-fit, minmax(190px, 1fr));
  gap: 0.65rem; margin-bottom: 0.65rem;
}
.stat-card {
  background: #fff; border-radius: 6px;
  box-shadow: 0 1px 4px rgba(0,0,0,.12);
  padding: 0.55rem 0.8rem;
}
.stat-card h3 {
  font-size: 0.68rem; color: #1a3a5c; text-transform: uppercase;
  letter-spacing: 0.06em; border-bottom: 1px solid #d0d7e0;
  padding-bottom: 0.3rem; margin-bottom: 0.3rem;
}
.stat-tbl { border-collapse: collapse; width: 100%; font-size: 12px; }
.stat-tbl td { padding: 2px 0; }
.stat-tbl td.sn {
  text-align: right; font-weight: 600; padding-left: 0.5rem;
  font-variant-numeric: tabular-nums; color: #1a3a5c;
}
.entity-bar { display: flex; flex-wrap: wrap; gap: 0.55rem; margin-top: 0.35rem; }
.e-chip {
  background: #f0f4f9; border: 1px solid #c8d4e3;
  border-radius: 5px; padding: 0.25rem 0.55rem; min-width: 90px;
}
.e-chip .ec-lbl {
  font-size: 9px; text-transform: uppercase; letter-spacing: 0.05em;
  color: #666; display: block;
}
.e-chip .ec-n {
  font-size: 1.25rem; font-weight: 700; color: #1a3a5c;
  line-height: 1.2; display: block;
}
.e-chip.e-total { background: #1a3a5c; border-color: #1a3a5c; }
.e-chip.e-total .ec-lbl { color: #90afc8; }
.e-chip.e-total .ec-n  { color: #fff; }
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


def render_stats_panel(corpus_stats, all_categories):
    """Return the corpus statistics HTML section as a string."""

    def _s(n):
        return f"{n:,}" if isinstance(n, int) else str(n)

    def srow(label, val):
        return f'<tr><td>{_esc(label)}</td><td class="sn">{_esc(_s(val))}</td></tr>'

    n_pubs          = corpus_stats.get("n_pubs", 0)
    pubs_with_supp  = corpus_stats.get("pubs_with_supp", 0)
    pubs_main_only  = corpus_stats.get("pubs_main_only", 0)
    total_main_docs = corpus_stats.get("total_main_docs", 0)
    total_supp_docs = corpus_stats.get("total_supp_docs", 0)
    total_docs      = total_main_docs + total_supp_docs
    entity_totals   = corpus_stats.get("entity_totals", {})
    supp_exts       = corpus_stats.get("supp_ext_counts", {})

    pub_card = (
        '<div class="stat-card">'
        '<h3>Publications</h3>'
        '<table class="stat-tbl">'
        + srow("Total processed", n_pubs)
        + srow("Main article only", pubs_main_only)
        + srow("With supplementary", pubs_with_supp)
        + '</table></div>'
    )

    doc_card = (
        '<div class="stat-card">'
        '<h3>Documents</h3>'
        '<table class="stat-tbl">'
        + srow("Total documents", total_docs)
        + srow("Main articles", total_main_docs)
        + srow("Supplementary", total_supp_docs)
        + '</table></div>'
    )

    rt_card = (
        '<div class="stat-card">'
        '<h3>Pipeline Runtime</h3>'
        '<table class="stat-tbl">'
        + srow("Median", fmt_seconds(corpus_stats.get("median_runtime")))
        + srow("Mean",   fmt_seconds(corpus_stats.get("mean_runtime")))
        + srow("Total compute", fmt_seconds(corpus_stats.get("total_runtime")))
        + srow("Fastest", fmt_seconds(corpus_stats.get("min_runtime")))
        + srow("Slowest", fmt_seconds(corpus_stats.get("max_runtime")))
        + '</table></div>'
    )

    if supp_exts:
        ext_rows = "".join(
            srow(ext.upper(), cnt)
            for ext, cnt in sorted(supp_exts.items(), key=lambda x: -x[1])
        )
        supp_card = (
            '<div class="stat-card">'
            '<h3>Supplementary File Types</h3>'
            '<table class="stat-tbl">' + ext_rows + '</table></div>'
        )
    else:
        supp_card = (
            '<div class="stat-card">'
            '<h3>Supplementary File Types</h3>'
            '<p style="font-size:11px;color:#888;margin-top:0.3rem">None</p>'
            '</div>'
        )

    display_cats = [c for c in all_categories if c in entity_totals]
    display_cats += sorted(c for c in entity_totals if c not in all_categories)
    total_entities = sum(entity_totals.values())
    chips = "".join(
        f'<div class="e-chip">'
        f'<span class="ec-lbl">{_esc(cat)}</span>'
        f'<span class="ec-n">{entity_totals[cat]:,}</span>'
        f'</div>'
        for cat in display_cats
    )
    chips += (
        f'<div class="e-chip e-total">'
        f'<span class="ec-lbl">Total</span>'
        f'<span class="ec-n">{total_entities:,}</span>'
        f'</div>'
    )
    entity_card = (
        '<div class="stat-card" style="margin-top:0.65rem">'
        '<h3>Entity Annotations — all publications combined</h3>'
        '<div class="entity-bar">' + chips + '</div>'
        '</div>'
    )

    return (
        '<section class="stats-panel">'
        '<h2>Corpus Statistics</h2>'
        '<div class="stats-grid">'
        + pub_card + doc_card + rt_card + supp_card
        + '</div>'
        + entity_card
        + '</section>'
    )


def render_html(rows, all_categories, input_dir, output_dir, generated_at, corpus_stats=None):
    """
    Build corpus_summary.html as a string.

    rows: list of dicts — pubid, title, date, doc_count, total_runtime_s,
          total_runtime_str, total_words, total_chars, total_entities,
          entity_counts {category: int}
    all_categories: ordered list of entity_category column names to include
    """
    # Column definitions: (key, header_label, is_text_searchable)
    # Layout: ID/Date/Title/Docs | entity counts | Total Entities | Runtime/Words/Chars
    head_cols = [
        ("pubid",          "Publication ID", True),
        ("date",           "Date",           False),
        ("title",          "Title",          True),
        ("doc_count",      "Documents",      False),
    ]
    tail_cols = [
        ("total_entities",  "Total Entities", False),
        ("total_runtime_s", "Run Time (s)",   False),
        ("total_words",     "Total Words",    False),
        ("total_chars",     "Total Chars",    False),
    ]

    cat_cols = [(cat, f"N {CAT_DISPLAY_NAMES.get(cat, cat)}", False) for cat in all_categories]
    columns = head_cols + cat_cols + tail_cols

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
                cells.append(f'<td><a href="pub-reports/report_{pid}.html">{pid}</a></td>')

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

    stats_html = render_stats_panel(corpus_stats, all_categories) if corpus_stats else ""

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
        + stats_html + "\n"
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
    parser.add_argument(
        "--regen-reports", action="store_true",
        help=(
            "Regenerate per-publication HTML/TSV reports using report_civic_pubtator.py "
            "before building the corpus summary. Each publication is checked for the "
            "required input directories (03_gnorm2/ or 04_tmvar3/) and skipped if absent. "
            "Not supported for GCS --input-dir."
        ),
    )
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

    os.makedirs(args.output_dir, exist_ok=True)
    os.makedirs(os.path.join(args.output_dir, "pub-reports"), exist_ok=True)
    tmp_dir = tempfile.mkdtemp(prefix="summarize_corpus_")

    try:
        pubids = discover_publications(args.input_dir)
        log.info("Found %d publication directories.", len(pubids))

        # Resolve reporter script path once (src/pipeline_steps/ relative to this file)
        report_script = os.path.join(
            os.path.dirname(os.path.abspath(__file__)),
            '..', 'pipeline_steps', 'report_civic_pubtator.py',
        )

        if args.regen_reports:
            if is_gcs(args.input_dir):
                log.warning(
                    "--regen-reports is not supported for GCS inputs; "
                    "report regeneration will be skipped."
                )
                args.regen_reports = False
            elif not os.path.isfile(report_script):
                log.warning(
                    "report_civic_pubtator.py not found at %s; "
                    "--regen-reports will be skipped.", report_script,
                )
                args.regen_reports = False

        # Load CIViC metadata once for all publications
        pmid_map, pmcid_map = ({}, {})
        if not args.no_civic:
            log.info("Loading CIViC source metadata…")
            pmid_map, pmcid_map = load_civic_metadata_map()

        all_categories_seen = set()
        pub_rows = []

        for pubid in pubids:
            log.info("Processing %s", pubid)

            if args.regen_reports:
                pub_dir = os.path.join(args.input_dir, pubid)
                if check_report_inputs(pub_dir):
                    regenerate_report(pub_dir, report_script)
                else:
                    log.warning(
                        "Skipping report regeneration for %s — "
                        "neither 03_gnorm2/ nor 04_tmvar3/ found or non-empty.", pubid,
                    )

            report_path = get_local_file(
                args.input_dir, pubid, f"report_{pubid}.tsv", tmp_dir
            )
            stats_path = get_local_file(
                args.input_dir, pubid, "pipeline_stats.tsv", tmp_dir
            )
            manifest_path = get_local_file(
                args.input_dir, pubid, "MANIFEST.txt", tmp_dir
            )

            if report_path is None:
                log.warning("Skipping %s — report_%s.tsv not found", pubid, pubid)
                continue
            if stats_path is None:
                log.warning("Skipping %s — pipeline_stats.tsv not found", pubid)
                continue

            report_data   = parse_report_tsv(report_path)
            stats_data    = parse_pipeline_stats(stats_path)
            manifest_data = parse_manifest(manifest_path)
            all_categories_seen.update(report_data["entity_counts"].keys())

            title, date = lookup_civic_metadata(pubid, pmid_map, pmcid_map)

            pub_rows.append({
                "pubid":             pubid,
                "title":             title,
                "date":              date,
                "doc_count":         stats_data["doc_count"],
                "main_doc_count":    stats_data["main_doc_count"],
                "supp_doc_count":    stats_data["supp_doc_count"],
                "has_supplements":   stats_data["has_supplements"],
                "supp_ext_counts":   manifest_data["supp_ext_counts"],
                "total_runtime_s":   stats_data["total_runtime_s"],
                "total_runtime_str": stats_data["total_runtime_str"],
                "total_words":       stats_data["total_words"],
                "total_chars":       stats_data["total_chars"],
                "total_entities":    sum(report_data["entity_counts"].values()),
                "entity_counts":     report_data["entity_counts"],
            })

            copy_html_report(args.input_dir, pubid, args.output_dir, tmp_dir)

        # Ordered category columns: preferred first, then any others alphabetically
        all_categories = [c for c in PREFERRED_CATEGORIES if c in all_categories_seen]
        all_categories += sorted(
            c for c in all_categories_seen if c not in PREFERRED_CATEGORIES
        )

        # Corpus-level aggregate statistics
        runtimes = sorted(
            r["total_runtime_s"] for r in pub_rows
            if isinstance(r.get("total_runtime_s"), int)
        )
        all_ext_counts: dict = defaultdict(int)
        for r in pub_rows:
            for ext, cnt in r.get("supp_ext_counts", {}).items():
                all_ext_counts[ext] += cnt
        entity_totals: dict = defaultdict(int)
        for r in pub_rows:
            for cat, cnt in r["entity_counts"].items():
                entity_totals[cat] += cnt
        n_rt = len(runtimes)
        corpus_stats = {
            "n_pubs":          len(pub_rows),
            "pubs_with_supp":  sum(1 for r in pub_rows if r.get("has_supplements")),
            "pubs_main_only":  sum(1 for r in pub_rows if not r.get("has_supplements")),
            "total_main_docs": sum(r.get("main_doc_count", 0) for r in pub_rows),
            "total_supp_docs": sum(r.get("supp_doc_count", 0) for r in pub_rows),
            "median_runtime":  _median(runtimes),
            "mean_runtime":    (sum(runtimes) // n_rt) if n_rt else None,
            "total_runtime":   sum(runtimes) if runtimes else None,
            "min_runtime":     runtimes[0]    if runtimes else None,
            "max_runtime":     runtimes[-1]   if runtimes else None,
            "entity_totals":   dict(entity_totals),
            "supp_ext_counts": dict(all_ext_counts),
        }

        generated_at = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        html = render_html(
            pub_rows, all_categories, args.input_dir, args.output_dir, generated_at,
            corpus_stats=corpus_stats,
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
