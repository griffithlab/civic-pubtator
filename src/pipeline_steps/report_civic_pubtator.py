#!/usr/bin/env python3
import argparse
import collections
import gzip
import html
import os
import re
import sys
import xml.etree.ElementTree as ET

ENTITY_STYLE = {
    'ProteinMutation': {'bg': '#fed7aa', 'border': '#ea580c', 'label': 'Protein Mutation'},
    'ProteinAllele':   {'bg': '#fef9c3', 'border': '#ca8a04', 'label': 'AA Position'},
    'DNAMutation':     {'bg': '#fecaca', 'border': '#dc2626', 'label': 'DNA Mutation'},
    'SNP':             {'bg': '#e9d5ff', 'border': '#9333ea', 'label': 'SNP'},
    'Gene':            {'bg': '#bfdbfe', 'border': '#2563eb', 'label': 'Gene'},
    'FamilyName':      {'bg': '#bfdbfe', 'border': '#2563eb', 'label': 'Gene Family'},
    'GENERIF':         {'bg': '#bfdbfe', 'border': '#2563eb', 'label': 'Gene (RIF)'},
    'Domain':          {'bg': '#bfdbfe', 'border': '#2563eb', 'label': 'Gene Domain'},
    'Species':         {'bg': '#bbf7d0', 'border': '#16a34a', 'label': 'Species'},
    'Genus':           {'bg': '#bbf7d0', 'border': '#16a34a', 'label': 'Genus'},
    'Strain':          {'bg': '#bbf7d0', 'border': '#16a34a', 'label': 'Strain'},
    'CellLine':        {'bg': '#ccfbf1', 'border': '#0d9488', 'label': 'Cell Line'},
    'Mutation':        {'bg': '#fed7aa', 'border': '#ea580c', 'label': 'Mutation (NER)'},
    'Chemical':        {'bg': '#fae8ff', 'border': '#a21caf', 'label': 'Drug'},
    'Disease':         {'bg': '#ffe4e6', 'border': '#e11d48', 'label': 'Disease'},
}
DEFAULT_STYLE        = {'bg': '#e2e8f0', 'border': '#64748b', 'label': 'Other'}
VARIANT_DEFAULT_STYLE = {'bg': '#e2e8f0', 'border': '#64748b', 'label': 'Sequence ID'}

GENE_TYPES     = frozenset({'Gene', 'FamilyName', 'GENERIF', 'Domain'})
ORGANISM_TYPES = frozenset({'Species', 'CellLine', 'Genus', 'Strain'})
CHEMICAL_TYPES = frozenset({'Chemical'})
DISEASE_TYPES  = frozenset({'Disease'})
# All types produced by GNorm2 — used to filter out pass-throughs from tmVar3 PubTator
GNORM2_TYPES   = frozenset({'Gene', 'FamilyName', 'GENERIF', 'Domain',
                             'Species', 'Genus', 'Strain', 'CellLine'})


def entity_style(etype):
    return ENTITY_STYLE.get(etype, VARIANT_DEFAULT_STYLE)


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
                        'identifier': details_str,
                        'hgvs': details.get('HGVS', ''),
                        'rs': details.get('RS#', ''),
                        'gene': details.get('CorrespondingGene', ''),
                        'details': details,
                    })
    return passages, annotations


def parse_bioc_chemicals(path):
    """Parse NLMChem BioC XML; return list of Chemical annotation dicts."""
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8') as fh:
        content = fh.read()
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        print(f'warning: could not parse {path}: {exc}', file=sys.stderr)
        return []
    annotations = []
    for doc in root.findall('document'):
        for passage in doc.findall('passage'):
            for ann in passage.findall('annotation'):
                infons = {i.get('key'): (i.text or '') for i in ann.findall('infon')}
                if infons.get('type') != 'Chemical':
                    continue
                loc = ann.find('location')
                if loc is None:
                    continue
                start = int(loc.get('offset', 0))
                length = int(loc.get('length', 0))
                mention = ann.findtext('text', '')
                identifier = infons.get('identifier', '')
                annotations.append({
                    'start': start,
                    'end': start + length,
                    'mention': mention,
                    'type': 'Chemical',
                    'identifier': identifier,
                    'hgvs': '',
                    'rs': '',
                    'gene': '',
                    'details': {},
                    'mesh': identifier,
                })
    return annotations


def parse_bioc_diseases(path):
    """Parse TaggerOne BioC XML; return list of Disease annotation dicts."""
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8') as fh:
        content = fh.read()
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        print(f'warning: could not parse {path}: {exc}', file=sys.stderr)
        return []
    annotations = []
    for doc in root.findall('document'):
        for passage in doc.findall('passage'):
            for ann in passage.findall('annotation'):
                infons = {i.get('key'): (i.text or '') for i in ann.findall('infon')}
                if infons.get('type') != 'Disease':
                    continue
                loc = ann.find('location')
                if loc is None:
                    continue
                start = int(loc.get('offset', 0))
                length = int(loc.get('length', 0))
                mention = ann.findtext('text', '')
                identifier = infons.get('identifier', '')
                annotations.append({
                    'start': start,
                    'end': start + length,
                    'mention': mention,
                    'type': 'Disease',
                    'identifier': identifier,
                    'hgvs': '',
                    'rs': '',
                    'gene': '',
                    'details': {},
                })
    return annotations


_GNORM2_GENE_IDENTIFIER_KEY = {'Gene', 'FamilyName', 'GENERIF', 'Domain'}
_GNORM2_TAXON_IDENTIFIER_KEY = {'Species', 'Genus', 'Strain', 'CellLine'}


def parse_gnorm2_bioc(path):
    """Parse GNorm2 BioC XML; return (passages, annotations) in same format as parse_pubtator()."""
    if not os.path.isfile(path):
        return [], []
    with open(path, encoding='utf-8') as fh:
        content = fh.read()
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        print(f'warning: could not parse {path}: {exc}', file=sys.stderr)
        return [], []
    passages = []
    annotations = []
    for doc in root.findall('document'):
        pmid = doc.findtext('id', '')
        for passage in doc.findall('passage'):
            infons = {i.get('key'): (i.text or '') for i in passage.findall('infon')}
            ptype = infons.get('type', '')
            text = passage.findtext('text', '')
            if ptype and text:
                passages.append({'pmid': pmid, 'ptype': ptype, 'text': text})
            for ann in passage.findall('annotation'):
                ainfons = {i.get('key'): (i.text or '') for i in ann.findall('infon')}
                ann_type = ainfons.get('type', '')
                if ann_type not in GNORM2_TYPES:
                    continue
                loc = ann.find('location')
                if loc is None:
                    continue
                start = int(loc.get('offset', 0))
                length = int(loc.get('length', 0))
                mention = ann.findtext('text', '')
                if ann_type in _GNORM2_GENE_IDENTIFIER_KEY:
                    identifier = ainfons.get('NCBI Gene', '')
                else:
                    identifier = ainfons.get('NCBI Taxonomy', '')
                annotations.append({
                    'start': start,
                    'end': start + length,
                    'mention': mention,
                    'type': ann_type,
                    'identifier': identifier,
                    'hgvs': '',
                    'rs': '',
                    'gene': '',
                    'details': ainfons,
                })
    return passages, annotations


def parse_aioner_bioc(path):
    """Parse AIONER BioC XML; return list of NER annotation dicts (no identifiers)."""
    if not os.path.isfile(path):
        return []
    with open(path, encoding='utf-8') as fh:
        content = fh.read()
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        print(f'warning: could not parse {path}: {exc}', file=sys.stderr)
        return []
    annotations = []
    for doc in root.findall('document'):
        for passage in doc.findall('passage'):
            for ann in passage.findall('annotation'):
                ainfons = {i.get('key'): (i.text or '') for i in ann.findall('infon')}
                ann_type = ainfons.get('type', '')
                if not ann_type:
                    continue
                loc = ann.find('location')
                if loc is None:
                    continue
                start = int(loc.get('offset', 0))
                length = int(loc.get('length', 0))
                mention = ann.findtext('text', '')
                annotations.append({
                    'start': start,
                    'end': start + length,
                    'mention': mention,
                    'type': ann_type,
                    'identifier': '',
                    'hgvs': '',
                    'rs': '',
                    'gene': '',
                    'details': {},
                })
    return annotations


def collect_aioner_files(aioner_dir):
    """Collect AIONER BioC XML files, mirroring the GNorm2 directory structure."""
    return collect_gnorm2_files(aioner_dir)


def build_aioner_rows(doc_data, show_docs=True, civic_gene_map=None, civic_therapy_map=None):
    """Build HTML rows for the flat AIONER NER table (Mention | Type | Count | Docs)."""
    key_to_label = {doc['key']: doc['label'] for doc in doc_data}
    summary = {}
    for doc in doc_data:
        for ann in doc.get('aioner_annotations', []):
            skey = (ann['mention'], ann['type'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])
    summary = collapse_mention_summary(summary, id_index=None)
    rows = []
    for (mention, etype), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        style = ENTITY_STYLE.get(etype, DEFAULT_STYLE)
        type_chip = (f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
                     f'border-radius:3px;padding:1px 6px;font-size:0.82em">'
                     f'{html.escape(style["label"])}</span>')
        docs_td = ''
        if show_docs:
            sorted_doc_keys = sorted(info['docs'], key=_doc_key_sort)
            keys_display = html.escape(', '.join(sorted_doc_keys))
            labels_tip = html.escape(', '.join(key_to_label.get(k, k) for k in sorted_doc_keys))
            docs_td = f'<td title="{labels_tip}">{keys_display}</td>'
        if etype == 'Gene':
            mention_cell = civic_gene_link(mention, civic_gene_map)
        elif etype == 'Chemical':
            mention_cell = civic_therapy_link(mention, civic_therapy_map)
        else:
            mention_cell = html.escape(mention)
        rows.append(
            f'<tr data-type="{html.escape(etype)}">'
            f'<td>{mention_cell}</td>'
            f'<td>{type_chip}</td>'
            f'<td>{info["count"]}</td>'
            f'{docs_td}'
            f'</tr>'
        )
    return '\n'.join(rows)


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


def classify_gnorm2_path(rel_path):
    parts = rel_path.replace('\\', '/').split('/')
    if len(parts) == 1:
        stem = re.sub(r'\.xml$', '', parts[0])
        return 'Main Publication', stem
    if len(parts) == 3 and parts[0] == 's':
        return 'Supplementary PDF', parts[1]
    if len(parts) == 4 and parts[0] == 's':
        return 'Supplementary Spreadsheet', f'{parts[1]} / {parts[2]}'
    stem = re.sub(r'\.xml$', '', parts[-1])
    return 'Other', stem


def collect_gnorm2_files(gnorm2_dir):
    files = []
    for dirpath, dirnames, filenames in os.walk(gnorm2_dir):
        dirnames[:] = [d for d in sorted(dirnames) if d != 'tmp']
        for fname in sorted(filenames):
            if not fname.endswith('.xml'):
                continue
            full = os.path.join(dirpath, fname)
            rel = os.path.relpath(full, gnorm2_dir)
            category, label = classify_gnorm2_path(rel)
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
    """Return (rows, total_runtime_str).

    rows            — per-step rows for the HTML stats table (TOTAL row excluded).
    total_runtime_str — the runtime field from the TOTAL row, or '' if absent.
    """
    rows = []
    total_runtime = ''
    if not os.path.isfile(path):
        return rows, total_runtime
    with open(path, encoding='utf-8') as f:
        lines = f.readlines()
    if not lines:
        return rows, total_runtime
    header = lines[0].rstrip('\n').split('\t')
    for line in lines[1:]:
        parts = line.rstrip('\n').split('\t')
        if len(parts) < len(header):
            parts += [''] * (len(header) - len(parts))
        row = dict(zip(header, parts))
        if row.get('step_name') == 'TOTAL':
            total_runtime = row.get('runtime', '')
            continue
        rows.append(row)
    return rows, total_runtime


def parse_duration(s):
    """Parse a duration string like '1h 2m 34s', '5m 3s', '42s' → total seconds."""
    total = 0
    for num, unit in re.findall(r'(\d+)([hms])', s or ''):
        n = int(num)
        if unit == 'h':
            total += n * 3600
        elif unit == 'm':
            total += n * 60
        else:
            total += n
    return total


def format_duration(seconds):
    """Return elapsed seconds as a human-readable string, e.g. '1h 2m 34s'."""
    seconds = int(seconds)
    h, rem = divmod(seconds, 3600)
    m, s   = divmod(rem, 60)
    if h:
        return f"{h}h {m}m {s}s"
    if m:
        return f"{m}m {s}s"
    return f"{s}s"


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

    step_order = ['GROBID', 'GNorm2', 'tmVar3', 'AIONER', 'NLMChem', 'TaggerOne']
    rows_html = []
    step_secs = {s: 0 for s in step_order}
    total_chars_int = 0
    for label, steps in by_label.items():
        times = [steps.get(s, {}).get('runtime', '') for s in step_order]
        for s, t in zip(step_order, times):
            step_secs[s] += parse_duration(t)
        chars = next(
            (steps[s].get('chars', '') for s in reversed(step_order) if s in steps),
            ''
        )
        try:
            total_chars_int += int(chars)
        except (ValueError, TypeError):
            pass
        chars_display = human_chars(chars)
        chars_cell = (f'<td title="{html.escape(chars)} chars">{html.escape(chars_display)}</td>'
                      if chars_display != chars else f'<td>{html.escape(chars)}</td>')
        time_cells = ''.join(f'<td>{html.escape(t)}</td>' for t in times)
        rows_html.append(
            f'<tr><td>{html.escape(label)}</td>'
            f'{time_cells}'
            f'{chars_cell}</tr>'
        )

    total_time_cells = ''.join(
        f'<th>{html.escape(format_duration(step_secs[s])) if step_secs[s] else ""}</th>'
        for s in step_order
    )
    total_chars_str = str(total_chars_int)
    total_chars_display = human_chars(total_chars_str)
    total_chars_cell = (
        f'<th title="{html.escape(total_chars_str)} chars">{html.escape(total_chars_display)}</th>'
        if total_chars_display != total_chars_str
        else f'<th>{html.escape(total_chars_str)}</th>'
    )
    tfoot_row = (
        f'<tr style="border-top:2px solid #cbd5e1">'
        f'<th style="text-align:left">Total</th>'
        f'{total_time_cells}'
        f'{total_chars_cell}</tr>'
    )
    return '\n'.join(rows_html), tfoot_row


def load_taxon_names(taxon_ids):
    """Return {taxon_id_str: common_name} using ref_files/taxon-id_common_name_map.tsv."""
    if not taxon_ids:
        return {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tsv_path = os.path.join(script_dir, '..', '..', 'ref_files', 'taxon-id_common_name_map.tsv')
    if not os.path.isfile(tsv_path):
        print('warning: ref_files/taxon-id_common_name_map.tsv not found — taxonomy IDs will be shown as-is',
              file=sys.stderr)
        return {}
    remaining = set(taxon_ids)
    result = {}
    try:
        with open(tsv_path, encoding='utf-8') as f:
            for line in f:
                if not remaining:
                    break
                line = line.rstrip('\n')
                if '\t' not in line:
                    continue
                tid, name = line.split('\t', 1)
                if tid in remaining:
                    result[tid] = name
                    remaining.discard(tid)
    except Exception as e:
        print(f'warning: could not read taxon-id_common_name_map.tsv: {e}', file=sys.stderr)
    return result


def load_gene_symbols(gene_ids):
    """Return {gene_id_str: symbol} for each ID in gene_ids, using ref_files/gene_info.gz."""
    if not gene_ids:
        return {}
    script_dir = os.path.dirname(os.path.abspath(__file__))
    gz_path = os.path.join(script_dir, '..', '..', 'ref_files', 'gene_info_select.gz')
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


def load_civic_gene_map():
    """Return {gene_name: civic_id} for all genes in CIViC via civicpy. Returns {} on failure."""
    try:
        from civicpy import civic
        genes = civic.get_all_genes()
        return {g.name: g.id for g in genes}
    except Exception as e:
        print(f'warning: could not load CIViC gene map: {e}', file=sys.stderr)
        return {}


def load_civic_source_map():
    """Return ({pmid: civic_sid}, {pmcid: civic_sid}) for all PUBMED sources in CIViC."""
    try:
        from civicpy import civic
        sources = civic.get_all_sources()
        pubmed = [s for s in sources if s.source_type == 'PUBMED']
        pmid_map  = {s.citation_id: s.id for s in pubmed if s.citation_id}
        pmcid_map = {s.pmc_id: s.id      for s in pubmed if s.pmc_id}
        return pmid_map, pmcid_map
    except Exception as e:
        print(f'warning: could not load CIViC source map: {e}', file=sys.stderr)
        return {}, {}


def civic_source_html(run_title, pmid_map, pmcid_map):
    """Return a CIViC source link or 'not found' notice for run_title (PMID or PMC ID)."""
    sid = None
    if re.match(r'^PMC\d+$', run_title):
        sid = pmcid_map.get(run_title)
    elif re.match(r'^\d+$', run_title):
        sid = pmid_map.get(run_title)
    else:
        return ''
    if sid is not None:
        url = f'https://identifiers.org/civic.sid:{sid}'
        return (f'<a href="{html.escape(url)}" target="_blank" rel="noopener" '
                f'style="color:#93c5fd;text-decoration:none">'
                f'civic.sid:{sid}</a>')
    return '<span style="color:#94a3b8;font-size:0.9em">(source not found in CIViC)</span>'


def civic_gene_link(mention, civic_gene_map):
    """Return an <a> tag to the CIViC gene page if mention is an exact match, else escaped text."""
    gid = civic_gene_map.get(mention) if civic_gene_map else None
    if gid is None:
        return html.escape(mention)
    url = f'https://identifiers.org/civic.gid:{gid}'
    return (f'<a href="{html.escape(url)}" target="_blank" rel="noopener" '
            f'title="View {html.escape(mention)} in CIViC">'
            f'{html.escape(mention)}</a>')


def load_civic_therapy_map():
    """Return {name_lower: civic_tid} for all therapies in CIViC. Returns {} on failure."""
    try:
        from civicpy import civic
        therapies = civic.get_all_therapies()
        return {t.name.lower(): t.id for t in therapies}
    except Exception as e:
        print(f'warning: could not load CIViC therapy map: {e}', file=sys.stderr)
        return {}


def civic_therapy_link(mention, civic_therapy_map):
    """Return an <a> tag to the CIViC therapy page on case-insensitive match, else escaped text."""
    tid = civic_therapy_map.get(mention.lower()) if civic_therapy_map else None
    if tid is None:
        return html.escape(mention)
    url = f'https://identifiers.org/civic.tid:{tid}'
    return (f'<a href="{html.escape(url)}" target="_blank" rel="noopener" '
            f'title="View {html.escape(mention)} in CIViC">'
            f'{html.escape(mention)}</a>')


def _doc_key_sort(k):
    return (0 if k.startswith('m') else 1, int(k[1:]))


def build_variant_summary(doc_data, gene_map=None, show_docs=True):
    if gene_map is None:
        gene_map = {}
    key_to_label = {doc['key']: doc['label'] for doc in doc_data}
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] in GENE_TYPES or ann['type'] in ORGANISM_TYPES or ann['type'] in CHEMICAL_TYPES or ann['type'] in DISEASE_TYPES:
                continue
            skey = (ann['mention'], ann['type'], ann['hgvs'], ann['gene'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])

    rows = []
    for (mention, etype, hgvs, gene), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        style = ENTITY_STYLE.get(etype, VARIANT_DEFAULT_STYLE)
        chip = (f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
                f'border-radius:4px;padding:1px 6px;font-size:0.85em">'
                f'{html.escape(style["label"])}</span>')
        if gene and gene in gene_map:
            gene_cell = (f'<span title="Gene ID: {html.escape(gene)}">'
                         f'{html.escape(gene_map[gene])}</span>')
        else:
            gene_cell = html.escape(gene)
        docs_td = ''
        if show_docs:
            sorted_doc_keys = sorted(info['docs'], key=_doc_key_sort)
            keys_display = html.escape(', '.join(sorted_doc_keys))
            labels_tip = html.escape(', '.join(key_to_label.get(k, k) for k in sorted_doc_keys))
            docs_td = f'<td title="{labels_tip}">{keys_display}</td>'
        rows.append(
            f'<tr data-type="{html.escape(etype)}">'
            f'<td>{html.escape(mention)}</td>'
            f'<td>{chip}</td>'
            f'<td>{gene_cell}</td>'
            f'<td>{html.escape(hgvs)}</td>'
            f'<td>{info["count"]}</td>'
            f'{docs_td}'
            f'</tr>'
        )
    return '\n'.join(rows)


def build_gene_rows(doc_data, gene_map=None, show_docs=True, civic_gene_map=None):
    if gene_map is None:
        gene_map = {}
    key_to_label = {doc['key']: doc['label'] for doc in doc_data}
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in GENE_TYPES:
                continue
            skey = (ann['mention'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])

    rows = []
    for (mention, gene_id), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        if gene_id and gene_id in gene_map:
            symbol = gene_map[gene_id]
            inner = civic_gene_link(symbol, civic_gene_map)
            gene_cell = f'<span title="Gene ID: {html.escape(gene_id)}">{inner}</span>'
        else:
            gene_cell = civic_gene_link(gene_id, civic_gene_map) if gene_id else ''
        docs_td = ''
        if show_docs:
            sorted_doc_keys = sorted(info['docs'], key=_doc_key_sort)
            keys_display = html.escape(', '.join(sorted_doc_keys))
            labels_tip = html.escape(', '.join(key_to_label.get(k, k) for k in sorted_doc_keys))
            docs_td = f'<td title="{labels_tip}">{keys_display}</td>'
        rows.append(
            f'<tr data-type="Gene">'
            f'<td>{civic_gene_link(mention, civic_gene_map)}</td>'
            f'<td>{gene_cell}</td>'
            f'<td>{info["count"]}</td>'
            f'{docs_td}'
            f'</tr>'
        )
    return '\n'.join(rows)


def build_organism_rows(doc_data, taxon_map=None, show_docs=True):
    if taxon_map is None:
        taxon_map = {}
    key_to_label = {doc['key']: doc['label'] for doc in doc_data}
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in ORGANISM_TYPES:
                continue
            mention = ann['mention']
            mention_key = mention.lower() if ann['type'] == 'Species' else mention
            skey = (mention_key, ann['type'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])

    summary = collapse_mention_summary(summary, id_index=2)
    rows = []
    for (mention, etype, taxid), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        style = ENTITY_STYLE.get(etype, DEFAULT_STYLE)
        chip = (f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
                f'border-radius:4px;padding:1px 6px;font-size:0.85em">'
                f'{html.escape(style["label"])}</span>')
        if taxid and taxid in taxon_map:
            name_cell = f'<span title="Taxonomy ID: {html.escape(taxid)}">{html.escape(taxon_map[taxid])}</span>'
        else:
            name_cell = html.escape(taxid)
        docs_td = ''
        if show_docs:
            sorted_doc_keys = sorted(info['docs'], key=_doc_key_sort)
            keys_display = html.escape(', '.join(sorted_doc_keys))
            labels_tip = html.escape(', '.join(key_to_label.get(k, k) for k in sorted_doc_keys))
            docs_td = f'<td title="{labels_tip}">{keys_display}</td>'
        rows.append(
            f'<tr data-type="{html.escape(etype)}">'
            f'<td>{html.escape(mention)}</td>'
            f'<td>{chip}</td>'
            f'<td>{name_cell}</td>'
            f'<td>{info["count"]}</td>'
            f'{docs_td}'
            f'</tr>'
        )
    return '\n'.join(rows)


def _singular_candidates(word):
    """Return candidate singular forms of word, longest-suffix rule first."""
    results = []
    if word.endswith('ies') and len(word) >= 5:
        results.append(word[:-3] + 'y')
    if word.endswith('es') and not word.endswith('ies') and len(word) >= 5:
        results.append(word[:-2])
    if word.endswith('s') and not word.endswith('ss') and len(word) >= 5:
        results.append(word[:-1])
    return results


def collapse_mention_summary(summary, id_index=None, min_len=5):
    """Collapse a mention summary dict by first-letter case and singular/plural.

    summary  : {(mention, *rest): {'count': int, 'docs': set}}
    id_index : position of the identifier field in each key tuple.  When set,
               entries with the same normalized mention may merge even if one
               has an empty/'-' identifier; the resolved identifier wins.
               None → no identifier field (AIONER path).
    min_len  : minimum mention length to apply either rule.

    Returns a new collapsed dict with the same value structure.
    """
    def _empty(v):
        return not v or v == '-'

    def _canon(mention):
        return (mention[0].lower() + mention[1:]) if len(mention) >= min_len else mention

    def _non_id_rest(key):
        """Key fields excluding mention and the identifier."""
        if id_index is None:
            return key[1:]
        return key[1:id_index] + key[id_index + 1:]

    def _merge(entries):
        return {
            'count': sum(e['count'] for _, e in entries),
            'docs':  set().union(*(e['docs'] for _, e in entries)),
        }

    # ── Pass 1: first-letter case (within same identifier) ────────────────────
    groups = {}
    for key, info in summary.items():
        norm_id = '' if (id_index is not None and _empty(key[id_index])) else (key[id_index] if id_index is not None else None)
        gk = (_canon(key[0]),) + _non_id_rest(key) + ((norm_id,) if id_index is not None else ())
        groups.setdefault(gk, []).append((key, info))

    p1 = {}
    for entries in groups.values():
        best_key = max(entries, key=lambda e: (e[1]['count'], e[0][0][0].islower()))[0]
        if id_index is not None:
            best_id = next((k[id_index] for k, _ in entries if not _empty(k[id_index])), best_key[id_index])
            new_key = best_key[:id_index] + (best_id,) + best_key[id_index + 1:]
        else:
            new_key = best_key
        p1[new_key] = _merge(entries)

    # ── Pass 1b: merge empty-id entries into resolved-id entries ──────────────
    # (same canonical mention + non-id rest, one side has resolved id, other has dash/empty)
    if id_index is not None:
        by_canon = {}
        for key in p1:
            gk = (_canon(key[0]),) + _non_id_rest(key)
            by_canon.setdefault(gk, []).append(key)

        to_merge_1b = {}   # empty_key → dest_resolved_key
        for keys in by_canon.values():
            resolved = [k for k in keys if not _empty(k[id_index])]
            empties  = [k for k in keys if     _empty(k[id_index])]
            if resolved and empties:
                best_resolved = max(resolved, key=lambda k: p1[k]['count'])
                for ek in empties:
                    to_merge_1b[ek] = best_resolved

        if to_merge_1b:
            new_p1 = {}
            for key, info in p1.items():
                dest = to_merge_1b.get(key, key)
                if dest not in new_p1:
                    new_p1[dest] = {'count': 0, 'docs': set()}
                new_p1[dest]['count'] += info['count']
                new_p1[dest]['docs']  |= info['docs']
            p1 = new_p1

    # ── Pass 2: singular / plural ─────────────────────────────────────────────
    def _id_norm_rest(key):
        """Grouping rest with id normalized (for matching across empty/resolved)."""
        r = list(key[1:])
        if id_index is not None:
            r[id_index - 1] = '' if _empty(r[id_index - 1]) else r[id_index - 1]
        return tuple(r)

    by_rest = {}
    for key in p1:
        by_rest.setdefault(_id_norm_rest(key), {})[_canon(key[0])] = key

    plural_to_singular = {}
    for mention_map in by_rest.values():
        for canon, key in mention_map.items():
            for sing in _singular_candidates(canon):
                if sing in mention_map and mention_map[sing] is not key:
                    plural_to_singular[key] = mention_map[sing]
                    break

    p2 = {}
    for key, info in p1.items():
        dest = key
        while dest in plural_to_singular:
            dest = plural_to_singular[dest]
        if id_index is not None and dest is not key:
            if not _empty(key[id_index]) and _empty(dest[id_index]):
                dest = dest[:id_index] + (key[id_index],) + dest[id_index + 1:]
        if dest not in p2:
            p2[dest] = {'count': 0, 'docs': set()}
        p2[dest]['count'] += info['count']
        p2[dest]['docs']  |= info['docs']

    return p2


def build_chemical_rows(doc_data, show_docs=True, civic_therapy_map=None):
    key_to_label = {doc['key']: doc['label'] for doc in doc_data}
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in CHEMICAL_TYPES:
                continue
            skey = (ann['mention'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])

    summary = collapse_mention_summary(summary, id_index=1)
    rows = []
    for (mention, mesh_id), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        if mesh_id and mesh_id != '-':
            mesh_cell = html.escape(mesh_id)
        else:
            mesh_cell = '<span style="color:#94a3b8">—</span>'
        docs_td = ''
        if show_docs:
            sorted_doc_keys = sorted(info['docs'], key=_doc_key_sort)
            keys_display = html.escape(', '.join(sorted_doc_keys))
            labels_tip = html.escape(', '.join(key_to_label.get(k, k) for k in sorted_doc_keys))
            docs_td = f'<td title="{labels_tip}">{keys_display}</td>'
        rows.append(
            f'<tr data-type="Chemical">'
            f'<td>{civic_therapy_link(mention, civic_therapy_map)}</td>'
            f'<td>{mesh_cell}</td>'
            f'<td>{info["count"]}</td>'
            f'{docs_td}'
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


def _doc_table_block(tbl_id, types_present, default_style, onchange_js, rows_html, headers_html):
    filter_name = f'{tbl_id}-flt'
    sel_id = f'{tbl_id}-lim'
    disp_id = f'{tbl_id}-cnt'
    onchange_js = f"applyTableFilters('{tbl_id}','{filter_name}','{sel_id}','{disp_id}')"
    filter_bar = build_filter_bar(types_present, default_style, filter_name, onchange_js, sel_id, disp_id)
    return (
        f'{filter_bar}'
        f'<div style="overflow-x:auto;margin-bottom:1.5rem">'
        f'<table id="{tbl_id}" class="data-table"'
        f' data-filter-name="{filter_name}"'
        f' data-filter-limit="{sel_id}"'
        f' data-filter-display="{disp_id}">'
        f'<thead><tr>{headers_html}</tr></thead>'
        f'<tbody>{rows_html}</tbody>'
        f'</table></div>'
    )


def build_disease_rows(doc_data, show_docs=True):
    key_to_label = {doc['key']: doc['label'] for doc in doc_data}
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in DISEASE_TYPES:
                continue
            skey = (ann['mention'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])

    summary = collapse_mention_summary(summary, id_index=1)
    rows = []
    for (mention, mesh_id), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        id_cell = html.escape(mesh_id) if mesh_id else '<span style="color:#94a3b8">—</span>'
        docs_td = ''
        if show_docs:
            sorted_doc_keys = sorted(info['docs'], key=_doc_key_sort)
            keys_display = html.escape(', '.join(sorted_doc_keys))
            labels_tip = html.escape(', '.join(key_to_label.get(k, k) for k in sorted_doc_keys))
            docs_td = f'<td title="{labels_tip}">{keys_display}</td>'
        rows.append(
            f'<tr data-type="Disease">'
            f'<td>{html.escape(mention)}</td>'
            f'<td>{id_cell}</td>'
            f'<td>{info["count"]}</td>'
            f'{docs_td}'
            f'</tr>'
        )
    return '\n'.join(rows)


def write_mentions_tsv(tsv_path, doc_data, gene_map=None, taxon_map=None):
    """Write a normalized TSV combining all mention tables from the HTML report."""
    if gene_map is None:
        gene_map = {}
    if taxon_map is None:
        taxon_map = {}

    def _src(ann):
        return ann.get('source', '')

    rows = []

    # Variants
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] in GENE_TYPES or ann['type'] in ORGANISM_TYPES \
                    or ann['type'] in CHEMICAL_TYPES or ann['type'] in DISEASE_TYPES:
                continue
            skey = (ann['mention'], ann['type'], ann['hgvs'], ann['gene'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set(), 'sources': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])
            summary[skey]['sources'].add(_src(ann))
    for (mention, etype, hgvs, gene), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        rows.append(('Variant', etype, mention,
                     gene or '', gene_map.get(gene, '') if gene else '',
                     hgvs or '',
                     info['count'], ','.join(sorted(info['docs'], key=_doc_key_sort)),
                     ','.join(sorted(info['sources'] - {''}))))

    # Genes
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in GENE_TYPES:
                continue
            skey = (ann['mention'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set(), 'sources': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])
            summary[skey]['sources'].add(_src(ann))
    for (mention, gene_id), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        rows.append(('Gene', 'Gene', mention,
                     gene_id or '', gene_map.get(gene_id, '') if gene_id else '',
                     '',
                     info['count'], ','.join(sorted(info['docs'], key=_doc_key_sort)),
                     ','.join(sorted(info['sources'] - {''}))))

    # Chemicals
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in CHEMICAL_TYPES:
                continue
            skey = (ann['mention'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set(), 'sources': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])
            summary[skey]['sources'].add(_src(ann))
    for (mention, mesh_id), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        mesh = mesh_id if (mesh_id and mesh_id != '-') else ''
        rows.append(('Chemical', 'Chemical', mention,
                     mesh, '', '',
                     info['count'], ','.join(sorted(info['docs'], key=_doc_key_sort)),
                     ','.join(sorted(info['sources'] - {''}))))

    # Diseases
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in DISEASE_TYPES:
                continue
            skey = (ann['mention'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set(), 'sources': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])
            summary[skey]['sources'].add(_src(ann))
    for (mention, mesh_id), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        rows.append(('Disease', 'Disease', mention,
                     mesh_id or '', '', '',
                     info['count'], ','.join(sorted(info['docs'], key=_doc_key_sort)),
                     ','.join(sorted(info['sources'] - {''}))))

    # Organisms
    summary = {}
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['type'] not in ORGANISM_TYPES:
                continue
            mention = ann['mention']
            mention_key = mention.lower() if ann['type'] == 'Species' else mention
            skey = (mention_key, ann['type'], ann['identifier'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set(), 'sources': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])
            summary[skey]['sources'].add(_src(ann))
    for (mention, etype, taxid), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        rows.append(('Organism', etype, mention,
                     taxid or '', taxon_map.get(taxid, '') if taxid else '',
                     '',
                     info['count'], ','.join(sorted(info['docs'], key=_doc_key_sort)),
                     ','.join(sorted(info['sources'] - {''}))))

    # AIONER NER (no normalization)
    summary = {}
    for doc in doc_data:
        for ann in doc.get('aioner_annotations', []):
            skey = (ann['mention'], ann['type'])
            if skey not in summary:
                summary[skey] = {'count': 0, 'docs': set()}
            summary[skey]['count'] += 1
            summary[skey]['docs'].add(doc['key'])
    for (mention, etype), info in sorted(summary.items(), key=lambda x: -x[1]['count']):
        rows.append(('NER_AIONER', etype, mention,
                     '', '', '',
                     info['count'], ','.join(sorted(info['docs'], key=_doc_key_sort)),
                     'AIONER'))

    with open(tsv_path, 'w', encoding='utf-8', newline='') as f:
        f.write('entity_category\tentity_type\tmention\tidentifier\tidentifier_name\thgvs\tcount\tdoc_keys\tsource\n')
        for row in rows:
            f.write('\t'.join(str(x) for x in row) + '\n')


def build_annotation_legend(annotations):
    """Return an HTML color-legend strip for entity types present in annotations."""
    types_present = {ann['type'] for ann in annotations}
    if not types_present:
        return ''
    ordered = [
        'ProteinMutation', 'ProteinAllele', 'DNAMutation', 'SNP', 'Mutation',
        'Gene', 'FamilyName', 'GENERIF', 'Domain',
        'Species', 'Genus', 'Strain', 'CellLine',
        'Chemical', 'Disease',
    ]
    chips = []
    for etype in ordered:
        if etype not in types_present:
            continue
        style = ENTITY_STYLE[etype]
        chips.append(
            f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
            f'border-radius:4px;padding:3px 10px;font-size:0.82em;white-space:nowrap">'
            f'{html.escape(style["label"])}</span>'
        )
    for etype in sorted(types_present - set(ordered)):
        style = VARIANT_DEFAULT_STYLE
        chips.append(
            f'<span style="background:{style["bg"]};border:1px solid {style["border"]};'
            f'border-radius:4px;padding:3px 10px;font-size:0.82em;white-space:nowrap">'
            f'{html.escape(etype)}</span>'
        )
    if not chips:
        return ''
    return (
        '<div style="display:flex;flex-wrap:wrap;gap:6px;margin-bottom:1rem;'
        'padding-bottom:0.75rem;border-bottom:1px solid #e2e8f0">'
        + ''.join(chips)
        + '</div>'
    )


def build_doc_section(doc, doc_id, gene_map=None, taxon_map=None, civic_gene_map=None, civic_therapy_map=None):
    if gene_map is None:
        gene_map = {}
    if taxon_map is None:
        taxon_map = {}
    label = doc['label']
    category = doc['category']
    passages = doc['passages']
    single = [doc]

    full_text = '\n'.join(p['text'] for p in passages)

    variant_types = {a['type'] for a in doc['annotations']
                     if a['type'] not in GENE_TYPES and a['type'] not in ORGANISM_TYPES
                     and a['type'] not in CHEMICAL_TYPES and a['type'] not in DISEASE_TYPES}
    organism_types = {a['type'] for a in doc['annotations'] if a['type'] in ORGANISM_TYPES}

    var_block = _doc_table_block(
        f'var-tbl-{doc_id}', variant_types, VARIANT_DEFAULT_STYLE, None,
        build_variant_summary(single, gene_map, show_docs=False),
        '<th>Mention</th><th>Type</th><th>Gene</th><th>HGVS</th><th>Count</th>')

    gene_block = _doc_table_block(
        f'gene-tbl-{doc_id}', set(), DEFAULT_STYLE, None,
        build_gene_rows(single, gene_map, show_docs=False, civic_gene_map=civic_gene_map),
        '<th>Mention</th><th>Gene</th><th>Count</th>')

    org_block = _doc_table_block(
        f'org-tbl-{doc_id}', organism_types, DEFAULT_STYLE, None,
        build_organism_rows(single, taxon_map, show_docs=False),
        '<th>Mention</th><th>Type</th><th>Name</th><th>Count</th>')

    chem_rows = build_chemical_rows(single, show_docs=False, civic_therapy_map=civic_therapy_map)
    chem_block = _doc_table_block(
        f'chem-tbl-{doc_id}', set(), DEFAULT_STYLE, None,
        chem_rows,
        '<th>Mention</th><th>MeSH ID</th><th>Count</th>') if chem_rows else None

    dis_rows = build_disease_rows(single, show_docs=False)
    dis_block = _doc_table_block(
        f'dis-tbl-{doc_id}', set(), DEFAULT_STYLE, None,
        dis_rows,
        '<th>Mention</th><th>MeSH ID</th><th>Count</th>') if dis_rows else None

    highlighted = highlight_text(full_text, doc['annotations'])

    aioner_rows = build_aioner_rows([doc], show_docs=False, civic_gene_map=civic_gene_map, civic_therapy_map=civic_therapy_map)
    if aioner_rows:
        aioner_types = sorted({a['type'] for a in doc.get('aioner_annotations', [])})
        aioner_filter = build_filter_bar(
            set(aioner_types), DEFAULT_STYLE,
            f'aioner-type-{doc_id}', f'applyAIONERFilters_{doc_id}()',
            f'aioner-limit-{doc_id}', f'aioner-count-{doc_id}',
            type_order=AIONER_TYPE_ORDER)
        aioner_card = f'''
  <div class="card">
    <h2>NER Results (AIONER)</h2>
    <p style="color:#64748b;font-size:0.88em;margin:0 0 0.75rem">Raw named entity spans from AIONER — not normalized to database identifiers.</p>
    {aioner_filter}
    <div style="overflow-x:auto">
      <table class="data-table" id="aioner-tbl-{doc_id}"
             data-filter-name="aioner-type-{doc_id}"
             data-filter-limit="aioner-limit-{doc_id}"
             data-filter-display="aioner-count-{doc_id}">
        <thead><tr><th>Mention</th><th>Type</th><th>Count</th></tr></thead>
        <tbody>{aioner_rows}</tbody>
      </table>
    </div>
  </div>'''
    else:
        aioner_card = ''

    return f'''
<div id="{doc_id}" class="doc-section" style="display:none">
  <div style="margin-bottom:1rem">
    <button onclick="showMain()" style="padding:6px 14px;cursor:pointer;border:1px solid #cbd5e1;border-radius:6px;background:#f8fafc">&#8592; Back to summary</button>
  </div>
  <div class="card" style="margin-bottom:1rem">
    <h2 style="margin:0 0 0.25rem">{html.escape(label)}</h2>
    <div style="color:#64748b;font-size:0.9em">{html.escape(category)}</div>
  </div>
  <div class="card">
    <h2>Annotation Summary (Normalized)</h2>
    {build_tabbed_summary(f'doc-summary-{doc_id}', var_block, gene_block, org_block, chem_block, dis_block)}
  </div>
  {aioner_card}
  <div class="card">
    <h2>Document Text</h2>
    {build_annotation_legend(doc['annotations'])}
    <div style="font-family:monospace;font-size:0.88em;line-height:1.7;background:#f8fafc;border:1px solid #e2e8f0;border-radius:8px;padding:1.25rem;white-space:pre-wrap;word-break:break-word">
{highlighted}
    </div>
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
.tab-bar { display: flex; border-bottom: 2px solid #e2e8f0; margin-bottom: 1rem; gap: 0; }
.tab-btn { padding: 8px 18px; cursor: pointer; border: none; border-bottom: 2px solid transparent; background: none; font-size: 0.9rem; color: #64748b; margin-bottom: -2px; font-family: inherit; border-radius: 0; }
.tab-btn:hover { color: #1e293b; background: #f8fafc; }
.tab-btn.active { color: #1e293b; border-bottom-color: #2563eb; font-weight: 600; }
.tab-panel { display: none; }
.tab-panel.active { display: block; }
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
  var filterFn = table.dataset.filterFn;
  if (filterFn && window[filterFn]) {
    window[filterFn]();
  } else if (table.dataset.filterLimit) {
    applyTableFilters(table.id, table.dataset.filterName || null,
                      table.dataset.filterLimit, table.dataset.filterDisplay);
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
function applyTableFilters(tableId, filterName, limitId, displayId) {
  var limitEl = document.getElementById(limitId);
  var limit = limitEl ? limitEl.value : 'all';
  var filterInput = filterName ? document.querySelector('input[name="' + filterName + '"]:checked') : null;
  var filterType = filterInput ? filterInput.value : 'all';
  var rows = Array.from(document.querySelectorAll('#' + tableId + ' tbody tr'));
  var shown = 0, total = 0;
  rows.forEach(function(row) {
    var matchesType = (filterType === 'all' || row.dataset.type === filterType);
    if (!matchesType) { row.style.display = 'none'; return; }
    total++;
    var maxShow = (limit === 'all') ? Infinity : parseInt(limit);
    if (shown < maxShow) { row.style.display = ''; shown++; }
    else { row.style.display = 'none'; }
  });
  var display = document.getElementById(displayId);
  if (display) {
    display.textContent = (limit === 'all' || shown === total)
      ? 'Showing all ' + total + ' entries'
      : 'Showing top ' + shown + ' of ' + total + ' entries';
  }
}
function switchTab(containerId, tabName) {
  var c = document.getElementById(containerId);
  c.querySelectorAll('.tab-btn').forEach(function(b) { b.classList.toggle('active', b.dataset.tab === tabName); });
  c.querySelectorAll('.tab-panel').forEach(function(p) { p.classList.toggle('active', p.dataset.tab === tabName); });
}
function applyVariantFilters()  { applyTableFilters('variant-table',  'vfilter',            'variant-limit-select',  'variant-count-display'); }
function applyGeneFilters()     { applyTableFilters('gene-table',     null,                 'gene-limit-select',     'gene-count-display'); }
function applyOrganismFilters() { applyTableFilters('organism-table', 'ofilter',            'organism-limit-select', 'organism-count-display'); }
function applyChemicalFilters() { applyTableFilters('chemical-table', null,                 'chemical-limit-select', 'chemical-count-display'); }
function applyDiseaseFilters()  { applyTableFilters('disease-table',  null,                 'disease-limit-select',  'disease-count-display'); }
function applyAIONERFilters()   { applyTableFilters('aioner-table',   'aioner-type-filter', 'aioner-limit-select',   'aioner-count-display'); }
document.addEventListener('DOMContentLoaded', function() {
  document.querySelectorAll('.data-table').forEach(function(table) {
    var ths = table.querySelectorAll('th');
    ths.forEach(function(th, i) {
      th.addEventListener('click', function() { sortTable(table, i); });
    });
  });
  applyVariantFilters();
  applyGeneFilters();
  applyOrganismFilters();
  applyChemicalFilters();
  applyDiseaseFilters();
  applyAIONERFilters();
  document.querySelectorAll('.data-table[data-filter-limit]').forEach(function(table) {
    applyTableFilters(table.id, table.dataset.filterName || null,
                      table.dataset.filterLimit, table.dataset.filterDisplay);
  });
});
'''


AIONER_TYPE_ORDER = ['Mutation', 'Gene', 'FamilyName', 'Chemical', 'Disease', 'Species', 'CellLine']


def build_filter_bar(types_present, default_style, filter_name, onchange_js, limit_id, display_id,
                     limit_options=None, type_order=None):
    if limit_options is None:
        limit_options = [('10', 'Top 10'), ('25', 'Top 25'), ('50', 'Top 50'),
                         ('100', 'Top 100'), ('500', 'Top 500'), ('all', 'All')]
    if type_order:
        ordered = [t for t in type_order if t in types_present]
        ordered += sorted(t for t in types_present if t not in type_order)
        types = ordered
    else:
        types = sorted(types_present)
    buttons = []
    if filter_name:
        buttons.append(f'<label><input type="radio" name="{filter_name}" value="all" checked onchange="{onchange_js}"> All</label>')
        for etype in types:
            style = ENTITY_STYLE.get(etype, default_style)
            chip_style = (f'background:{style["bg"]};border:1px solid {style["border"]};'
                          f'border-radius:4px;padding:1px 6px;font-size:0.85em')
            buttons.append(
                f'<label><input type="radio" name="{filter_name}" value="{html.escape(etype)}" '
                f'onchange="{onchange_js}"> '
                f'<span style="{chip_style}">{html.escape(style["label"])}</span></label>'
            )
    options_html = ''.join(f'<option value="{v}">{l}</option>' for v, l in limit_options)
    limit_select = (
        f'<span style="margin-left:auto;display:flex;align-items:center;gap:6px">'
        f'Show: <select id="{limit_id}" onchange="{onchange_js}" '
        f'style="padding:2px 6px;border:1px solid #cbd5e1;border-radius:4px;font-size:0.9em">'
        f'{options_html}'
        f'</select>'
        f'<span id="{display_id}" style="color:#64748b;font-size:0.85em"></span>'
        f'</span>'
    )
    return '<div class="filter-bar">' + '\n'.join(buttons) + '\n' + limit_select + '</div>'


def build_tabbed_summary(container_id, var_block, gene_block, org_block, chem_block=None, dis_block=None):
    def btn(tab, label, active):
        cls = 'tab-btn active' if active else 'tab-btn'
        return (f'<button class="{cls}" data-tab="{tab}" '
                f'onclick="switchTab(\'{container_id}\',\'{tab}\')">{label}</button>')
    def panel(tab, content, active):
        cls = 'tab-panel active' if active else 'tab-panel'
        return f'<div class="{cls}" data-tab="{tab}">{content}</div>'
    chem_btn   = btn('chemical', 'Drugs', False) if chem_block is not None else ''
    chem_panel = panel('chemical', chem_block, False) if chem_block is not None else ''
    dis_btn    = btn('disease',  'Diseases',  False) if dis_block  is not None else ''
    dis_panel  = panel('disease',  dis_block,  False) if dis_block  is not None else ''
    return (
        f'<div id="{container_id}">'
        f'<div class="tab-bar">'
        f'{btn("variant","Variants",True)}'
        f'{btn("gene","Genes",False)}'
        f'{chem_btn}'
        f'{dis_btn}'
        f'{btn("organism","Organisms",False)}'
        f'</div>'
        f'{panel("variant", var_block, True)}'
        f'{panel("gene",    gene_block, False)}'
        f'{chem_panel}'
        f'{dis_panel}'
        f'{panel("organism",org_block,  False)}'
        f'</div>'
    )


def get_paper_title(doc_data):
    for doc in doc_data:
        if doc['category'] == 'Main Publication':
            for p in doc['passages']:
                if p['ptype'] in ('t', 'title'):
                    return p['text']
    return ''


def generate_html(run_dir, manifest, stats_rows, doc_data, gene_map=None, taxon_map=None,
                  civic_gene_map=None, civic_pmid_map=None, civic_pmcid_map=None,
                  civic_therapy_map=None, total_runtime=''):
    run_title = os.path.basename(os.path.abspath(run_dir))

    paper_title = get_paper_title(doc_data)
    paper_title_html = (
        f'<div style="font-size:1.35rem;font-weight:700;color:#1e293b;line-height:1.4;'
        f'margin-bottom:1.5rem;padding:1rem 1.25rem;background:#fff;border:1px solid #e2e8f0;'
        f'border-radius:10px">{html.escape(paper_title)}</div>'
        if paper_title else ''
    )

    runtime_row = (f'  <dt>Total run time</dt><dd>{html.escape(total_runtime)}</dd>\n'
                   if total_runtime else '')
    run_info_html = f'''
<dl class="run-info">
  <dt>Tool version</dt><dd>{html.escape(manifest.get("tool_version",""))}</dd>
  <dt>Run timestamp</dt><dd>{html.escape(manifest.get("run_timestamp",""))}</dd>
  <dt>Input directory</dt><dd>{html.escape(manifest.get("input_directory",""))}</dd>
{runtime_row}</dl>'''

    source_files_html = build_source_files_html(manifest)

    stats_table_html = ''
    if stats_rows:
        stats_tbody, stats_tfoot = build_pipeline_stats_table(stats_rows)
        stats_table_html = f'''
<div class="card">
  <h2>Pipeline Statistics</h2>
  <div style="overflow-x:auto">
    <table class="data-table">
      <thead><tr><th>Document</th><th>GROBID</th><th>GNorm2</th><th>tmVar3</th><th>AIONER</th><th>NLMChem</th><th>TaggerOne</th><th>Total chars</th></tr></thead>
      <tbody>{stats_tbody}</tbody>
      <tfoot>{stats_tfoot}</tfoot>
    </table>
  </div>
</div>'''

    variant_types = {ann['type'] for doc in doc_data for ann in doc['annotations']
                     if ann['type'] not in GENE_TYPES and ann['type'] not in ORGANISM_TYPES
                     and ann['type'] not in CHEMICAL_TYPES and ann['type'] not in DISEASE_TYPES}
    organism_types = {ann['type'] for doc in doc_data for ann in doc['annotations']
                      if ann['type'] in ORGANISM_TYPES}

    variant_filter_bar = build_filter_bar(
        variant_types, VARIANT_DEFAULT_STYLE,
        'vfilter', 'applyVariantFilters()', 'variant-limit-select', 'variant-count-display')
    variant_rows = build_variant_summary(doc_data, gene_map)
    var_block = (
        f'{variant_filter_bar}'
        f'<div style="overflow-x:auto">'
        f'<table class="data-table" id="variant-table" data-filter-fn="applyVariantFilters">'
        f'<thead><tr><th>Mention</th><th>Type</th><th>Gene</th><th>HGVS</th><th>Count</th><th>Docs</th></tr></thead>'
        f'<tbody>{variant_rows}</tbody></table></div>'
    )

    gene_filter_bar = build_filter_bar(
        set(), DEFAULT_STYLE,
        '', 'applyGeneFilters()', 'gene-limit-select', 'gene-count-display')
    gene_rows = build_gene_rows(doc_data, gene_map, civic_gene_map=civic_gene_map)
    gene_block = (
        f'{gene_filter_bar}'
        f'<div style="overflow-x:auto">'
        f'<table class="data-table" id="gene-table" data-filter-fn="applyGeneFilters">'
        f'<thead><tr><th>Mention</th><th>Gene</th><th>Count</th><th>Docs</th></tr></thead>'
        f'<tbody>{gene_rows}</tbody></table></div>'
    )

    organism_filter_bar = build_filter_bar(
        organism_types, DEFAULT_STYLE,
        'ofilter', 'applyOrganismFilters()', 'organism-limit-select', 'organism-count-display')
    organism_rows = build_organism_rows(doc_data, taxon_map)
    org_block = (
        f'{organism_filter_bar}'
        f'<div style="overflow-x:auto">'
        f'<table class="data-table" id="organism-table" data-filter-fn="applyOrganismFilters">'
        f'<thead><tr><th>Mention</th><th>Type</th><th>Name</th><th>Count</th><th>Docs</th></tr></thead>'
        f'<tbody>{organism_rows}</tbody></table></div>'
    )

    chem_filter_bar = build_filter_bar(
        set(), DEFAULT_STYLE,
        '', 'applyChemicalFilters()', 'chemical-limit-select', 'chemical-count-display')
    chemical_rows = build_chemical_rows(doc_data, civic_therapy_map=civic_therapy_map)
    chem_block = (
        f'{chem_filter_bar}'
        f'<div style="overflow-x:auto">'
        f'<table class="data-table" id="chemical-table" data-filter-fn="applyChemicalFilters">'
        f'<thead><tr><th>Mention</th><th>MeSH ID</th><th>Count</th><th>Docs</th></tr></thead>'
        f'<tbody>{chemical_rows}</tbody></table></div>'
    ) if chemical_rows else None

    dis_filter_bar = build_filter_bar(
        set(), DEFAULT_STYLE,
        '', 'applyDiseaseFilters()', 'disease-limit-select', 'disease-count-display')
    disease_rows = build_disease_rows(doc_data)
    dis_block = (
        f'{dis_filter_bar}'
        f'<div style="overflow-x:auto">'
        f'<table class="data-table" id="disease-table" data-filter-fn="applyDiseaseFilters">'
        f'<thead><tr><th>Mention</th><th>MeSH ID</th><th>Count</th><th>Docs</th></tr></thead>'
        f'<tbody>{disease_rows}</tbody></table></div>'
    ) if disease_rows else None

    annotation_section = (
        f'<div class="card"><h2>Annotation Summary (Normalized)</h2>'
        f'{build_tabbed_summary("main-summary", var_block, gene_block, org_block, chem_block, dis_block)}'
        f'</div>'
    )

    aioner_rows = build_aioner_rows(doc_data, civic_gene_map=civic_gene_map, civic_therapy_map=civic_therapy_map)
    if aioner_rows:
        aioner_types = sorted({a['type'] for doc in doc_data for a in doc.get('aioner_annotations', [])})
        aioner_filter_bar = build_filter_bar(
            set(aioner_types), DEFAULT_STYLE,
            'aioner-type-filter', 'applyAIONERFilters()',
            'aioner-limit-select', 'aioner-count-display',
            type_order=AIONER_TYPE_ORDER)
        aioner_section = (
            f'<div class="card"><h2>NER Results (AIONER)</h2>'
            f'<p style="color:#64748b;font-size:0.88em;margin:0 0 0.75rem">Raw named entity spans from AIONER — not normalized to database identifiers.</p>'
            f'{aioner_filter_bar}'
            f'<div style="overflow-x:auto">'
            f'<table class="data-table" id="aioner-table" data-filter-fn="applyAIONERFilters">'
            f'<thead><tr><th>Mention</th><th>Type</th><th>Count</th><th>Docs</th></tr></thead>'
            f'<tbody>{aioner_rows}</tbody></table></div>'
            f'</div>'
        )
    else:
        aioner_section = ''

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

    doc_sections = '\n'.join(build_doc_section(doc, doc['doc_id'], gene_map, taxon_map, civic_gene_map, civic_therapy_map) for doc in doc_data)

    civic_src_html = civic_source_html(run_title, civic_pmid_map or {}, civic_pmcid_map or {})
    civic_src_sep  = ' &mdash; ' if civic_src_html else ''

    return f'''<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>civic-pubtator report — PMID: {html.escape(run_title)}</title>
<style>{CSS}</style>
</head>
<body>
<div id="topbar">civic-pubtator report &mdash; <a href="https://pubmed.ncbi.nlm.nih.gov/{html.escape(run_title)}/" target="_blank" style="color:#93c5fd;text-decoration:none">PMID: {html.escape(run_title)}</a>{civic_src_sep}{civic_src_html}</div>
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
    {annotation_section}
    {aioner_section}
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
    stats_rows, total_runtime = parse_pipeline_stats(os.path.join(run_dir, 'pipeline_stats.tsv'))

    tmvar3_dir = os.path.join(run_dir, '04_tmvar3')
    tmvar3_dir = tmvar3_dir if os.path.isdir(tmvar3_dir) else None

    gnorm2_dir = os.path.join(run_dir, '03_gnorm2')
    gnorm2_dir = gnorm2_dir if os.path.isdir(gnorm2_dir) else None

    # Use GNorm2 BioC XML as primary source when available (survives tmVar3 timeouts).
    # Fall back to tmVar3 PubTator alone for backwards compatibility.
    gnorm2_files = collect_gnorm2_files(gnorm2_dir) if gnorm2_dir else []
    if gnorm2_files:
        primary_files = gnorm2_files
    elif tmvar3_dir:
        primary_files = collect_pubtator_files(tmvar3_dir)
        if not primary_files:
            print('warning: no .PubTator files found', file=sys.stderr)
    else:
        print(f'error: neither 03_gnorm2/ nor 04_tmvar3/ found in {run_dir}', file=sys.stderr)
        sys.exit(1)

    aioner_dir = os.path.join(run_dir, '05_aioner')
    aioner_dir = aioner_dir if os.path.isdir(aioner_dir) else None

    nlmchem_dir = os.path.join(run_dir, '06_nlmchem')
    if not os.path.isdir(nlmchem_dir):
        nlmchem_dir = None

    taggerone_dir = os.path.join(run_dir, '07_taggerone')
    if not os.path.isdir(taggerone_dir):
        taggerone_dir = None

    doc_data = []
    main_count = supp_count = 0
    for i, pf in enumerate(primary_files):
        if pf['category'] == 'Main Publication':
            main_count += 1
            key = f'm{main_count}'
        else:
            supp_count += 1
            key = f's{supp_count}'

        if gnorm2_files:
            # Primary: GNorm2 BioC XML → passages + Gene/Species/CellLine/etc.
            passages, annotations = parse_gnorm2_bioc(pf['path'])
            for a in annotations:
                a['source'] = 'GNorm2'
            rel_xml = pf['rel']  # e.g. "nihms313098.xml" or "s/foo/foo.xml"
            # Supplement with tmVar3 variant annotations when available
            if tmvar3_dir:
                pubtator_path = os.path.join(tmvar3_dir, rel_xml + '.PubTator')
                if os.path.isfile(pubtator_path):
                    _, tmvar_anns = parse_pubtator(pubtator_path)
                    for a in tmvar_anns:
                        if a['type'] not in GNORM2_TYPES:
                            a['source'] = 'tmVar3'
                            annotations.append(a)
        else:
            # Legacy path: tmVar3 PubTator only
            passages, annotations = parse_pubtator(pf['path'])
            for a in annotations:
                a['source'] = 'tmVar3'
            rel_xml = pf['rel'][:-len('.PubTator')] if pf['rel'].endswith('.PubTator') else pf['rel']

        if nlmchem_dir:
            chem_anns = parse_bioc_chemicals(os.path.join(nlmchem_dir, rel_xml))
            for a in chem_anns:
                a['source'] = 'NLMChem'
            annotations.extend(chem_anns)
        if taggerone_dir:
            dis_anns = parse_bioc_diseases(os.path.join(taggerone_dir, rel_xml))
            gene_mentions = {a['mention'] for a in annotations if a['type'] in GENE_TYPES}
            for a in dis_anns:
                a['source'] = 'TaggerOne'
            annotations.extend(a for a in dis_anns if a['mention'] not in gene_mentions)
        aioner_anns = parse_aioner_bioc(os.path.join(aioner_dir, rel_xml)) if aioner_dir else []
        for a in aioner_anns:
            a['source'] = 'AIONER'
        doc_data.append({
            'doc_id': f'doc-{i}',
            'key': key,
            'label': pf['label'],
            'category': pf['category'],
            'rel': pf['rel'],
            'passages': passages,
            'annotations': annotations,
            'aioner_annotations': aioner_anns,
        })

    gene_ids = set()
    for doc in doc_data:
        for ann in doc['annotations']:
            if ann['gene']:
                gene_ids.add(ann['gene'])
            if ann['type'] in GENE_TYPES and ann['identifier']:
                gene_ids.add(ann['identifier'])
    gene_map = load_gene_symbols(gene_ids)

    taxon_ids = {ann['identifier'] for doc in doc_data for ann in doc['annotations']
                 if ann['type'] in ORGANISM_TYPES and ann['identifier']}
    taxon_map = load_taxon_names(taxon_ids)

    civic_gene_map = load_civic_gene_map()
    civic_pmid_map, civic_pmcid_map = load_civic_source_map()
    civic_therapy_map = load_civic_therapy_map()

    html_content = generate_html(run_dir, manifest, stats_rows, doc_data, gene_map, taxon_map,
                                 civic_gene_map, civic_pmid_map, civic_pmcid_map, civic_therapy_map,
                                 total_runtime)

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    print(f'Wrote: {output_path}')

    tsv_path = os.path.splitext(output_path)[0] + '.tsv'
    write_mentions_tsv(tsv_path, doc_data, gene_map, taxon_map)
    print(f'Wrote: {tsv_path}')


if __name__ == '__main__':
    main()
