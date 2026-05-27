#!/usr/bin/env python3
import argparse
import collections
import gzip
import html
import os
import re
import sys

ENTITY_STYLE = {
    'ProteinMutation': {'bg': '#fed7aa', 'border': '#ea580c', 'label': 'Protein Mutation'},
    'ProteinAllele':   {'bg': '#fef9c3', 'border': '#ca8a04', 'label': 'Protein Allele'},
    'DNAMutation':     {'bg': '#fecaca', 'border': '#dc2626', 'label': 'DNA Mutation'},
    'SNP':             {'bg': '#e9d5ff', 'border': '#9333ea', 'label': 'SNP'},
    'Gene':            {'bg': '#bfdbfe', 'border': '#2563eb', 'label': 'Gene'},
    'Species':         {'bg': '#bbf7d0', 'border': '#16a34a', 'label': 'Species'},
}
DEFAULT_STYLE = {'bg': '#e2e8f0', 'border': '#64748b', 'label': 'Other'}


def entity_style(etype):
    return ENTITY_STYLE.get(etype, DEFAULT_STYLE)


def parse_details(details_str):
    result = {}
    for part in details_str.split(';'):
        if ':' in part:
            k, v = part.split(':', 1)
            result[k.strip()] = v.strip()
    return result


def parse_pubtator(path):
    passages = []
    annotations = []
    with open(path, encoding='utf-8') as f:
        for line in f:
            line = line.rstrip('\n')
            if not line:
                continue
            pipe_parts = line.split('|', 2)
            if len(pipe_parts) == 3 and pipe_parts[1] in ('title', 'abstract', 'body', 't', 'a', 'fig_caption', 'table'):
                passages.append({'pmid': pipe_parts[0], 'ptype': pipe_parts[1], 'text': pipe_parts[2]})
            else:
                tab_parts = line.split('\t')
                if len(tab_parts) >= 5:
                    try:
                        start = int(tab_parts[1])
                        end = int(tab_parts[2])
                    except ValueError:
                        continue
                    mention = tab_parts[3]
                    etype = tab_parts[4]
                    details_str = tab_parts[5] if len(tab_parts) > 5 else ''
                    details = parse_details(details_str)
                    annotations.append({
                        'start': start,
                        'end': end,
                        'mention': mention,
                        'type': etype,
                        'hgvs': details.get('HGVS', ''),
                        'rs': details.get('RS#', ''),
                        'gene': details.get('CorrespondingGene', ''),
                        'details': details,
                    })
    return passages, annotations


def classify_pubtator_path(rel_path):
    parts = rel_path.replace('\\', '/').split('/')
    if len(parts) == 1:
        stem = re.sub(r'\.xml\.PubTator$', '', parts[0])
        return 'Main Publication', stem
    if len(parts) == 3 and parts[0] == 's':
        stem = parts[1]
        return 'Supplementary PDF', stem
    if len(parts) == 4 and parts[0] == 's':
        stem = parts[1]
        tab = parts[2]
        return 'Supplementary Spreadsheet', f'{stem} / {tab}'
    stem = re.sub(r'\.xml\.PubTator$', '', parts[-1])
    return 'Other', stem


def collect_pubtator_files(tmvar3_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(tmvar3_dir):
        dirnames[:] = [d for d in dirnames if d != 'tmp']
        for fname in filenames:
            if not fname.endswith('.PubTator'):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, tmvar3_dir)
            category, label = classify_pubtator_path(rel)
            files.append({'path': full, 'rel': rel, 'category': category, 'label': label})
    files.sort(key=lambda x: (0 if x['category'] == 'Main Publication' else 1, x['rel']))
    return files


def parse_manifest(path):
    result = {
        'tool_version': '',
        'run_timestamp': '',
        'input_directory': '',
        'source_pdfs': [],
        'supplementary_files': [],
    }
    if not os.path.isfile(path):
        return result
    with open(path, encoding='utf-8') as f:
        content = f.read()
    m = re.search(r'Tool version:\s+(.+)', content)
    if m:
        result['tool_version'] = m.group(1).strip()
    m = re.search(r'Run timestamp:\s+(.+)', content)
    if m:
        result['run_timestamp'] = m.group(1).strip()
    m = re.search(r'Input directory:\s+(.+)', content)
    if m:
        result['input_directory'] = m.group(1).strip()

    file_re = re.compile(r'^(\S+)\s+([\d,]+)\s+(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})$')

    def parse_file_lines(block_text):
        entries = []
        for line in block_text.splitlines():
            line = line.strip()
            if not line or line.startswith('-') or line.startswith('File') or line.startswith('Size'):
                continue
            m = file_re.match(line)
            if m:
                entries.append({
                    'name': m.group(1),
                    'size_bytes': int(m.group(2).replace(',', '')),
                    'modified': m.group(3),
                })
            else:
                entries.append({'name': line, 'size_bytes': None, 'modified': None})
        return entries

    source_block = re.search(r'Source PDFs.*?---+\n(.*?)(?:={6}|$)', content, re.DOTALL)
    if source_block:
        result['source_pdfs'] = parse_file_lines(source_block.group(1))

    supp_block = re.search(r'Supplementary files.*?---+\n(.*?)(?:={6}|$)', content, re.DOTALL)
    if supp_block:
        result['supplementary_files'] = parse_file_lines(supp_block.group(1))

    return result


def parse_pipeline_stats(path):
    rows = []
    if not os.path.isfile(path):
        return rows
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()
    if not lines:
        return rows
    header = lines[0].rstrip('\n').split('\t')
    for line in lines[1:]:
        parts = line.rstrip('\n').split('\t')
        if len(parts) < len(header):
            parts += [''] * (len(header) - len(parts))
        rows.append(dict(zip(header, parts)))
    return rows


def human_chars(s):
    try:
        n = int(s.replace(',', ''))
    except (ValueError, AttributeError):
        return s
    if n < 1_000:
        return str(n)
    if n < 10_000:
        return f'{n/1_000:.1f}k'
    if n < 1_000_000:
        return f'{round(n/1_000)}k'
    if n < 10_000_000:
        return f'{n/1_000_000:.1f}m'
    return f'{round(n/1_000_000)}m'


def build_pipeline_stats_table(stats_rows):
    by_label = collections.OrderedDict()
    for row in stats_rows:
        label = row.get('label', '')
        if label not in by_label:
            by_label[label] = {}
        step_name = row.get('step_name', '')
        by_label[label][step_name] = row

    rows_html = []
    for label, steps in by_label.items():
        grobid_time = steps.get('GROBID', {}).get('runtime', '')
        gnorm_time = steps.get('GNorm2', {}).get('runtime', '')
        tmvar_time = steps.get('tmVar3', {}).get('runtime', '')
        chars = steps.get('tmVar3', steps.get('GNorm2', steps.get('GROBID', {}))).get('chars', '')
        chars_display = human_chars(chars)
        chars_cell = (f'<td title="{html.escape(chars)} chars">{html.escape(chars_display)}</td>'
                      if chars_display != chars else f'<td>{html.escape(chars)}</td>')
        rows_html.append(
            f'<tr><td>{html.escape(label)}</td>'
            f'<td>{html.escape(grobid_time)}</td>'
            f'<td>{html.escape(gnorm_time)}</td>'
            f'<td>{html.escape(tmvar_time)}</td>'
            f'{chars_cell}</tr>'
        )
    return '\n'.join(rows_html)


def load_gene_symbols(gene_ids):
    """Return {gene_id_str: symbol} for each ID in gene_ids, using ref_files/gene_info.gz."""
    if not gene_ids:
        return {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gz_path = os.path.join(script_dir, '..', 'ref_files', 'gene_info_select.gz')
    if not os.path.isfile(gz_path):
        print('warning: ref_files/gene_info_select.gz not found — gene IDs will not be converted to symbols',
              file=sys.stderr)
        return {}
    remaining = set(gene_ids)
    result = {}
    try:
        with gzip.open(gz_path, 'rt', encoding='utf-8') as f:
            next(f)  # skip header
            for line in f:
                if not remaining:
                    break
                tab1 = line.index('\t')
                tab2 = line.index('\t', tab1 + 1)
                tab3 = line.index('\t', tab2 + 1)
                gid = line[tab1 + 1:tab2]
                if gid in remaining:
                    symbol = line[tab2 + 1:tab3]
                    if symbol not in ('NEWENTRY', '-'):
                        result[gid] = symbol
                    remaining.discard(gid)
    except Exception as e:
        print(f'warning: could not read gene_info.gz: {e}', file=sys.stderr)
    return result


def _doc_key_sort(k):
    return (0 if k.startswith('m') else 1, int(k[1:]))


def build_variant_summary(doc_data, gene_map=None):
    if gene_map is None:
        gene_map = {}
    key_to_label = {doc['key']: doc['label'] for doc in doc_data}
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            skey = (ann['mention'], ann['type'], ann['hgvs'], ann['gene'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])

    rows = []
    for (mention, etype, hgvs, gene), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        style = entity_style(etype)
        chip = (f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
                f'border-radius:4px;padding:1px 6px;font-size:0.85em">'
                f'{html.escape(style["label"])}</span>')
        sorted_doc_keys = sorted(info['docs'], key=_doc_key_sort)
        keys_display = html.escape(', '.join(sorted_doc_keys))
        labels_tip = html.escape(', '.join(key_to_label.get(k, k) for k in sorted_doc_keys))
        if gene and gene in gene_map:
            gene_cell = (f'<span title="Gene ID: {html.escape(gene)}">'
                         f'{html.escape(gene_map[gene])}</span>')
        else:
            gene_cell = html.escape(gene)
        rows.append(
            f'<tr data-type="{html.escape(etype)}">'
            f'<td>{html.escape(mention)}</td>'
            f'<td>{chip}</td>'
            f'<td>{gene_cell}</td>'
            f'<td>{html.escape(hgvs)}</td>'
            f'<td>{info["count"]}</td>'
            f'<td title="{labels_tip}">{keys_display}</td>'
            f'</tr>'
        )
    return '\n'.join(rows)


def highlight_text(full_text, annotations):
    sorted_anns = sorted(annotations, key=lambda a: a['start'])
    parts = []
    pos = 0
    for ann in sorted_anns:
        start, end = ann['start'], ann['end']
        mention = ann['mention']
        mention_len = len(mention)
        # tmVar3 mixes byte offsets (within-passage) with character offsets (passage start),
        # which shifts annotations by +1 for each non-ASCII character preceding them in the
        # same passage.  Search a small window to find the true position.
        if full_text[start:start + mention_len] != mention:
            for delta in range(1, 8):
                if full_text[start - delta:start - delta + mention_len] == mention:
                    start -= delta
                    break
                if full_text[start + delta:start + delta + mention_len] == mention:
                    start += delta
                    break
        end = start + mention_len
        if start < pos:
            continue
        if start > pos:
            segment = html.escape(full_text[pos:start])
            segment = segment.replace('\n', '<br>\n')
            parts.append(segment)
        style = entity_style(ann['type'])
        tip_parts = [f"Type: {ann['type']}"]
        if ann['hgvs']:
            tip_parts.append(f"HGVS: {ann['hgvs']}")
        if ann['rs']:
            tip_parts.append(f"RS#: {ann['rs']}")
        if ann['gene']:
            tip_parts.append(f"Gene: {ann['gene']}")
        tooltip = html.escape(' | '.join(tip_parts))
        span_text = html.escape(full_text[start:end])
        parts.append(
            f'<mark style="background:{style["bg"]};border-bottom:2px solid {style["border"]};'
            f'border-radius:2px;padding:0 2px;cursor:default" title="{tooltip}">'
            f'{span_text}</mark>'
        )
        pos = end
    if pos < len(full_text):
        segment = html.escape(full_text[pos:])
        segment = segment.replace('\n', '<br>\n')
        parts.append(segment)
    return ''.join(parts)


def build_doc_section(doc, doc_id, gene_map=None):
    if gene_map is None:
        gene_map = {}
    label = doc['label']
    category = doc['category']
    annotations = doc['annotations']
    passages = doc['passages']

    full_text = '\n'.join(p['text'] for p in passages)

    types_present = sorted(set(a['type'] for a in annotations))
    legend_chips = []
    for etype in types_present:
        style = entity_style(etype)
        legend_chips.append(
            f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
            f'border-radius:4px;padding:2px 8px;margin:2px;font-size:0.85em;display:inline-block">'
            f'{html.escape(style["label"])}</span>'
        )
    legend_html = ' '.join(legend_chips)

    ann_counts = collections.Counter()
    ann_hgvs = {}
    ann_gene = {}
    for a in annotations:
        key = (a['mention'], a['type'])
        ann_counts[key] += 1
        ann_hgvs[key] = a['hgvs']
        ann_gene[key] = a['gene']

    ann_rows = []
    for (mention, etype), count in sorted(ann_counts.items(), key=lambda x: -x[1]):
        style = entity_style(etype)
        chip = (f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
                f'border-radius:4px;padding:1px 6px;font-size:0.85em">'
                f'{html.escape(style["label"])}</span>')
        gene = ann_gene.get((mention, etype), '')
        if gene and gene in gene_map:
            gene_cell = (f'<span title="Gene ID: {html.escape(gene)}">'
                         f'{html.escape(gene_map[gene])}</span>')
        else:
            gene_cell = html.escape(gene)
        ann_rows.append(
            f'<tr><td>{html.escape(mention)}</td><td>{chip}</td>'
            f'<td>{gene_cell}</td>'
            f'<td>{html.escape(ann_hgvs.get((mention, etype), ""))}</td>'
            f'<td>{count}</td></tr>'
        )
    ann_table = '\n'.join(ann_rows)

    tbl_id = f'ann-table-{doc_id}'
    sel_id = f'ann-limit-{doc_id}'
    disp_id = f'ann-count-{doc_id}'

    highlighted = highlight_text(full_text, annotations)

    return f'''
<div id="{doc_id}" class="doc-section" style="display:none">
  <div style="margin-bottom:1rem">
    <button onclick="showMain()" style="padding:6px 14px;cursor:pointer;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc">&#8592; Back to summary</button>
  </div>
  <h2 style="margin:0 0 0.25rem">{html.escape(label)}</h2>
  <div style="color:#64748b;margin-bottom:1rem;font-size:0.9em">{html.escape(category)}</div>
  <div style="margin-bottom:1rem">{legend_html}</div>
  <h3 style="margin:1rem 0 0.5rem">Annotation Summary</h3>
  <div style="display:flex;align-items:center;gap:6px;margin-bottom:0.5rem;font-size:0.9rem">
    Show: <select id="{sel_id}" class="ann-limit-select"
      data-table="{tbl_id}" data-display="{disp_id}"
      onchange="applyTableRowLimit('{tbl_id}','{sel_id}','{disp_id}')"
      style="padding:2px 6px;border:1px solid #cbd5e1;border-radius:4px;font-size:0.9em">
      <option value="50">Top 50</option>
      <option value="100">Top 100</option>
      <option value="500">Top 500</option>
      <option value="all">All</option>
    </select>
    <span id="{disp_id}" style="color:#64748b;font-size:0.85em"></span>
  </div>
  <div style="overflow-x:auto;margin-bottom:1.5rem">
    <table id="{tbl_id}" class="data-table"
      data-limit-select="{sel_id}" data-limit-display="{disp_id}">
      <thead><tr><th>Mention</th><th>Type</th><th>Gene</th><th>HGVS</th><th>Count</th></tr></thead>
      <tbody>{ann_table}</tbody>
    </table>
  </div>
  <h3 style="margin:1rem 0 0.5rem">Document Text</h3>
  <div style="font-family:monospace;font-size:0.88em;line-height:1.7;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1.25rem;white-space:pre-wrap;word-break:break-word">
{highlighted}
  </div>
</div>
'''


def build_document_index(doc_data):
    rows = []
    for doc in doc_data:
        doc_id = doc['doc_id']
        n = len(doc['annotations'])
        rows.append(
            f'<tr>'
            f'<td style="font-family:monospace;white-space:nowrap">{html.escape(doc["key"])}</td>'
            f'<td><a href="#" onclick="show(\'{doc_id}\');return false">'
            f'{html.escape(doc["label"])}</a></td>'
            f'<td>{html.escape(doc["category"])}</td>'
            f'<td>{n}</td></tr>'
        )
    return '\n'.join(rows)


def human_size(n):
    for unit in ('B', 'KB', 'MB', 'GB', 'TB'):
        if n < 1024 or unit == 'TB':
            return f'{n:,.1f} {unit}' if unit != 'B' else f'{n} B'
        n /= 1024


def build_source_files_html(manifest):
    pdfs = manifest['source_pdfs']
    supps = manifest['supplementary_files']

    def make_table(items, title):
        if not items:
            return ''
        rows = []
        for item in items:
            name_cell = f'<td style="font-family:monospace">{html.escape(item["name"])}</td>'
            if item['size_bytes'] is not None:
                size_cell = (f'<td style="text-align:right" title="{item["size_bytes"]:,} bytes">'
                             f'{html.escape(human_size(item["size_bytes"]))}</td>')
                date_cell = f'<td>{html.escape(item["modified"])}</td>'
            else:
                size_cell = '<td></td>'
                date_cell = '<td></td>'
            rows.append(f'<tr>{name_cell}{size_cell}{date_cell}</tr>')
        header = '<thead><tr><th>File</th><th style="text-align:right">Size</th><th>Date modified</th></tr></thead>'
        tbody = '<tbody>' + ''.join(rows) + '</tbody>'
        return (f'<h3 style="margin:1rem 0 0.5rem">{title} ({len(items)} file{"s" if len(items)!=1 else ""})</h3>'
                f'<div style="overflow-x:auto"><table class="data-table">{header}{tbody}</table></div>')

    return make_table(pdfs, 'Source PDFs') + make_table(supps, 'Supplementary Files')


CSS = '''
* { box-sizing: border-box; }
body { margin: 0; font-family: system-ui, sans-serif; background: #f1f5f9; color: #1e293b; }
#topbar { background: #1e293b; color: #f8fafc; padding: 0.75rem 1.5rem; font-size: 1.1rem; font-weight: 600; }
#main-content { max-width: 1200px; margin: 0 auto; padding: 1.5rem; }
.card { background: #fff; border: 1px solid #e2e8f0; border-radius: 10px; padding: 1.25rem 1.5rem; margin-bottom: 1.5rem; }
.card h2 { margin: 0 0 1rem; font-size: 1.1rem; color: #334155; border-bottom: 1px solid #e2e8f0; padding-bottom: 0.5rem; }
.data-table { border-collapse: collapse; width: 100%; font-size: 0.9rem; }
.data-table th { background: #f1f5f9; text-align: left; padding: 8px 12px; border: 1px solid #e2e8f0; cursor: pointer; white-space: nowrap; user-select: none; }
.data-table th:hover { background: #e2e8f0; }
.data-table td { padding: 6px 12px; border: 1px solid #e2e8f0; vertical-align: top; }
.data-table tbody tr:hover { background: #f8fafc; }
.run-info { display: grid; grid-template-columns: max-content 1fr; gap: 4px 16px; font-size: 0.9rem; }
.run-info dt { color: #64748b; font-weight: 500; }
.run-info dd { margin: 0; }
.filter-bar { margin-bottom: 0.75rem; display: flex; flex-wrap: wrap; gap: 8px; align-items: center; font-size: 0.9rem; }
.filter-bar label { display: flex; align-items: center; gap: 4px; cursor: pointer; }
'''

JS = '''
function show(id) {
  document.getElementById('main-view').style.display = 'none';
  document.querySelectorAll('.doc-section').forEach(el => el.style.display = 'none');
  var el = document.getElementById(id);
  if (el) { el.style.display = 'block'; }
  window.scrollTo(0, 0);
}
function showMain() {
  document.querySelectorAll('.doc-section').forEach(el => el.style.display = 'none');
  document.getElementById('main-view').style.display = 'block';
  window.scrollTo(0, 0);
}
function sortTable(table, col) {
  var tbody = table.querySelector('tbody');
  var rows = Array.from(tbody.querySelectorAll('tr'));
  var asc = table.dataset.sortCol == col && table.dataset.sortDir != 'asc';
  table.dataset.sortCol = col;
  table.dataset.sortDir = asc ? 'asc' : 'desc';
  rows.sort(function(a, b) {
    var va = a.cells[col] ? a.cells[col].textContent.trim() : '';
    var vb = b.cells[col] ? b.cells[col].textContent.trim() : '';
    var na = parseFloat(va.replace(/,/g, ''));
    var nb = parseFloat(vb.replace(/,/g, ''));
    if (!isNaN(na) && !isNaN(nb)) return asc ? na - nb : nb - na;
    return asc ? va.localeCompare(vb) : vb.localeCompare(va);
  });
  rows.forEach(r => tbody.appendChild(r));
  if (table.id === 'variant-table') {
    applyVariantFilters();
  } else if (table.dataset.limitSelect) {
    applyTableRowLimit(table.id, table.dataset.limitSelect, table.dataset.limitDisplay);
  }
}
function applyTableRowLimit(tableId, selectId, displayId) {
  var limit = document.getElementById(selectId).value;
  var rows = Array.from(document.querySelectorAll('#' + tableId + ' tbody tr'));
  var shown = 0, total = rows.length;
  rows.forEach(function(row) {
    var maxShow = limit === 'all' ? Infinity : parseInt(limit);
    if (shown < maxShow) { row.style.display = ''; shown++; }
    else { row.style.display = 'none'; }
  });
  var d = document.getElementById(displayId);
  if (d) {
    d.textContent = (shown === total)
      ? 'Showing all ' + total + ' entries'
      : 'Showing top ' + shown + ' of ' + total + ' entries';
  }
}
function applyVariantFilters() {
  var limitSelect = document.getElementById('row-limit-select');
  var limit = limitSelect ? limitSelect.value : 'all';
  var filterInput = document.querySelector('input[name="vfilter"]:checked');
  var filterType = filterInput ? filterInput.value : 'all';
  var rows = Array.from(document.querySelectorAll('#variant-table tbody tr'));
  var shown = 0, total = 0;
  rows.forEach(function(row) {
    var matchesType = (filterType === 'all' || row.dataset.type === filterType);
    if (!matchesType) { row.style.display = 'none'; return; }
    total++;
    var maxShow = (limit === 'all') ? Infinity : parseInt(limit);
    if (shown < maxShow) { row.style.display = ''; shown++; }
    else { row.style.display = 'none'; }
  });
  var display = document.getElementById('variant-count-display');
  if (display) {
    display.textContent = (limit === 'all' || shown === total)
      ? 'Showing all ' + total + ' entries'
      : 'Showing top ' + shown + ' of ' + total + ' entries';
  }
}
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.data-table').forEach(function(table) {
    var ths = table.querySelectorAll('th');
    ths.forEach(function(th, i) {
      th.addEventListener('click', function() { sortTable(table, i); });
    });
  });
  applyVariantFilters();
  document.querySelectorAll('.ann-limit-select').forEach(function(sel) {
    applyTableRowLimit(sel.dataset.table, sel.id, sel.dataset.display);
  });
});
'''


def build_filter_bar(doc_data):
    types = set()
    for doc in doc_data:
        for ann in doc['annotations']:
            types.add(ann['type'])
    types = sorted(types)
    buttons = ['<label><input type="radio" name="vfilter" value="all" checked onchange="applyVariantFilters()"> All</label>']
    for etype in types:
        style = entity_style(etype)
        chip_style = (f'background:{style["bg"]};border:1px solid {style["border"]};'
                      f'border-radius:4px;padding:1px 6px;font-size:0.85em')
        label_escaped = html.escape(style['label'])
        etype_escaped = html.escape(etype)
        buttons.append(
            f'<label><input type="radio" name="vfilter" value="{etype_escaped}" '
            f'onchange="applyVariantFilters()"> '
            f'<span style="{chip_style}">{label_escaped}</span></label>'
        )
    limit_select = (
        '<span style="margin-left:auto;display:flex;align-items:center;gap:6px">'
        'Show: <select id="row-limit-select" onchange="applyVariantFilters()" '
        'style="padding:2px 6px;border:1px solid #cbd5e1;border-radius:4px;font-size:0.9em">'
        '<option value="50">Top 50</option>'
        '<option value="100">Top 100</option>'
        '<option value="500">Top 500</option>'
        '<option value="all">All</option>'
        '</select>'
        '<span id="variant-count-display" style="color:#64748b;font-size:0.85em"></span>'
        '</span>'
    )
    return '<div class="filter-bar">' + '\n'.join(buttons) + '\n' + limit_select + '</div>'


def get_paper_title(doc_data):
    for doc in doc_data:
        if doc['category'] == 'Main Publication':
            for p in doc['passages']:
                if p['ptype'] in ('t', 'title'):
                    return p['text']
    return ''


def generate_html(run_dir, manifest, stats_rows, doc_data, gene_map=None):
    run_title = os.path.basename(os.path.abspath(run_dir))

    paper_title = get_paper_title(doc_data)
    paper_title_html = (
        f'<div style="font-size:1.35rem;font-weight:700;color:#1e293b;line-height:1.4;'
        f'margin-bottom:1.5rem;padding:1rem 1.25rem;background:#fff;border:1px solid #e2e8f0;'
        f'border-radius:10px">{html.escape(paper_title)}</div>'
        if paper_title else ''
    )

    run_info_html = f'''
<dl class="run-info">
  <dt>Tool version</dt><dd>{html.escape(manifest.get("tool_version",""))}</dd>
  <dt>Run timestamp</dt><dd>{html.escape(manifest.get("run_timestamp",""))}</dd>
  <dt>Input directory</dt><dd>{html.escape(manifest.get("input_directory",""))}</dd>
</dl>'''

    source_files_html = build_source_files_html(manifest)

    stats_table_html = ''
    if stats_rows:
        stats_table_html = f'''
<div class="card">
  <h2>Pipeline Statistics</h2>
  <div style="overflow-x:auto">
    <table class="data-table">
      <thead><tr><th>Document</th><th>GROBID time</th><th>GNorm2 time</th><th>tmVar3 time</th><th>Total chars</th></tr></thead>
      <tbody>{build_pipeline_stats_table(stats_rows)}</tbody>
    </table>
  </div>
</div>'''

    filter_bar = build_filter_bar(doc_data)
    variant_rows = build_variant_summary(doc_data, gene_map)
    variant_section = f'''
<div class="card">
  <h2>Variant Summary</h2>
  {filter_bar}
  <div style="overflow-x:auto">
    <table class="data-table" id="variant-table">
      <thead><tr><th>Mention</th><th>Type</th><th>Gene</th><th>HGVS</th><th>Count</th><th>Docs</th></tr></thead>
      <tbody>{variant_rows}</tbody>
    </table>
  </div>
</div>'''

    doc_index_rows = build_document_index(doc_data)
    doc_index = f'''
<div class="card">
  <h2>Documents</h2>
  <div style="overflow-x:auto">
    <table class="data-table">
      <thead><tr><th>Key</th><th>Label</th><th>Category</th><th>Annotations</th></tr></thead>
      <tbody>{doc_index_rows}</tbody>
    </table>
  </div>
</div>'''

    doc_sections = '\n'.join(build_doc_section(doc, doc['doc_id'], gene_map) for doc in doc_data)

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>civic-pubtator report — {html.escape(run_title)}</title>
<style>{CSS}</style>
</head>
<body>
<div id="topbar">civic-pubtator report &mdash; {html.escape(run_title)}</div>
<div id="main-content">
  <div id="main-view">
    {paper_title_html}
    <div class="card">
      <h2>Run Information</h2>
      {run_info_html}
    </div>
    {"" if not source_files_html else f'<div class="card"><h2>Source Files</h2>{source_files_html}</div>'}
    {stats_table_html}
    {doc_index}
    {variant_section}
  </div>
  {doc_sections}
</div>
<script>{JS}</script>
</body>
</html>
'''


def main():
    parser = argparse.ArgumentParser(description='Generate HTML report from civic-pubtator tmVar3 results.')
    parser.add_argument('run_dir', help='Run directory containing 04_tmvar3/, MANIFEST.txt, pipeline_stats.tsv')
    parser.add_argument('-o', '--output', default=None, help='Output HTML path (default: <run_dir>/report.html)')
    args = parser.parse_args()

    run_dir = os.path.abspath(args.run_dir)
    if not os.path.isdir(run_dir):
        print(f'error: run_dir not found: {run_dir}', file=sys.stderr)
        sys.exit(1)

    run_title = os.path.basename(run_dir)
    output_path = args.output or os.path.join(run_dir, f'report_{run_title}.html')

    manifest = parse_manifest(os.path.join(run_dir, 'MANIFEST.txt'))
    stats_rows = parse_pipeline_stats(os.path.join(run_dir, 'pipeline_stats.tsv'))

    tmvar3_dir = os.path.join(run_dir, '04_tmvar3')
    if not os.path.isdir(tmvar3_dir):
        print(f'error: 04_tmvar3/ not found in {run_dir}', file=sys.stderr)
        sys.exit(1)

    pubtator_files = collect_pubtator_files(tmvar3_dir)
    if not pubtator_files:
        print('warning: no .PubTator files found', file=sys.stderr)

    doc_data = []
    main_count = supp_count = 0
    for i, pf in enumerate(pubtator_files):
        if pf['category'] == 'Main Publication':
            main_count += 1
            key = f'm{main_count}'
        else:
            supp_count += 1
            key = f's{supp_count}'
        passages, annotations = parse_pubtator(pf['path'])
        doc_data.append({
            'doc_id': f'doc-{i}',
            'key': key,
            'label': pf['label'],
            'category': pf['category'],
            'rel': pf['rel'],
            'passages': passages,
            'annotations': annotations,
        })

    gene_ids = {ann['gene'] for doc in doc_data for ann in doc['annotations'] if ann['gene']}
    gene_map = load_gene_symbols(gene_ids)

    html_content = generate_html(run_dir, manifest, stats_rows, doc_data, gene_map)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(output_path)


if __name__ == '__main__':
    main()
