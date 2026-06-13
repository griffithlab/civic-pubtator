#!/usr/bin/env python3
import argparse, datetime, os, re, shutil, subprocess, sys, time
import xml.etree.ElementTree as ET

REPO_DIR  = os.path.dirname(os.path.abspath(__file__))
STEPS_DIR = os.path.join(REPO_DIR, "src", "pipeline_steps")
AB3P_DIR  = os.path.join(REPO_DIR, 'tools', 'Ab3P')

IGNORED_FILES = {".DS_Store"}

_LIGHT_BLUE = "\033[94m"
_RESET      = "\033[0m"

def light_blue(text):
    return f"{_LIGHT_BLUE}{text}{_RESET}" if sys.stderr.isatty() else text


def run(label, cmd):
    bar = "=" * 60
    print(light_blue(f"\n{bar}"), file=sys.stderr)
    print(light_blue(f"{label}: {' '.join(cmd)}"), file=sys.stderr)
    print(light_blue(bar), file=sys.stderr)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)


def half_memory(mem_str):
    """Return half of a Java heap size string (e.g. '32G' -> '16G', '5G' -> '2560M')."""
    unit  = mem_str[-1].upper()
    value = int(mem_str[:-1])
    if value % 2 == 0:
        return f"{value // 2}{unit}"
    multipliers = {"G": 1024, "M": 1024, "K": 1024}
    next_unit   = {"G": "M",  "M": "K",  "K": "B"}
    if unit in multipliers:
        return f"{value * multipliers[unit] // 2}{next_unit[unit]}"
    return f"{value // 2}{unit}"


def read_release_version():
    """Read the version string from RELEASE at the repo root."""
    release_path = os.path.join(REPO_DIR, "RELEASE")
    try:
        with open(release_path, encoding="utf-8") as f:
            return f.read().strip()
    except Exception:
        return "unknown"


def collect_source_files(source_dir):
    """Return list of (filename, size_bytes, mtime_str) for PDFs directly in source_dir."""
    results = []
    for fname in sorted(os.listdir(source_dir)):
        fpath = os.path.join(source_dir, fname)
        if (os.path.isfile(fpath)
                and fname.lower().endswith(".pdf")
                and fname not in IGNORED_FILES
                and not fname.startswith("~$")):
            st = os.stat(fpath)
            mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            results.append((fname, st.st_size, mtime))
    return results


def collect_supplementary_files(source_dir):
    """Return list of (rel_path, size_bytes, mtime_str) for original supplementary
    source files directly inside 01_source/s/ (.pdf, .docx, .xlsx, etc.).
    The subdirectories inside s/ are derived output from prepare_supplementary.py
    and are intentionally excluded."""
    s_dir = os.path.join(source_dir, "s")
    if not os.path.isdir(s_dir):
        return []
    results = []
    for fname in sorted(os.listdir(s_dir)):
        fpath = os.path.join(s_dir, fname)
        if (os.path.isfile(fpath)
                and fname not in IGNORED_FILES
                and not fname.startswith("~$")):
            st = os.stat(fpath)
            mtime = datetime.datetime.fromtimestamp(st.st_mtime).strftime("%Y-%m-%d %H:%M:%S")
            rel = os.path.relpath(fpath, source_dir)
            results.append((rel, st.st_size, mtime))
    return results


def write_manifest(manifest_path, top_dir, source_dir, version, run_timestamp):
    """Write MANIFEST.txt recording tool version and all source/supplementary files."""
    source_files = collect_source_files(source_dir)
    supp_files   = collect_supplementary_files(source_dir)

    bar  = "=" * 70
    dash = "-" * 70

    def _file_table(f, entries, base):
        if not entries:
            f.write("  (none)\n")
            return
        name_w = max(max(len(r) for r, _, _ in entries), 40)
        f.write(f"  {'File':<{name_w}}  {'Size (bytes)':>14}  Modified\n")
        f.write(f"  {'-'*name_w}  {'-'*14}  {'-'*19}\n")
        for rel, size, mtime in entries:
            f.write(f"  {rel:<{name_w}}  {size:>14,}  {mtime}\n")

    with open(manifest_path, "w", encoding="utf-8") as f:
        f.write(f"{bar}\n")
        f.write(f"MANIFEST — civic-pubtator pipeline\n")
        f.write(f"{bar}\n")
        f.write(f"Tool version:    {version}\n")
        f.write(f"Run timestamp:   {run_timestamp}\n")
        f.write(f"Input directory: {top_dir}\n")
        f.write(f"Source dir:      {source_dir}\n")
        f.write(f"\n{bar}\n")
        f.write(f"Source PDFs ({len(source_files)} file{'s' if len(source_files) != 1 else ''})\n")
        f.write(f"{dash}\n")
        _file_table(f, source_files, source_dir)
        f.write(f"\n{bar}\n")
        f.write(f"Supplementary files ({len(supp_files)} file{'s' if len(supp_files) != 1 else ''})\n")
        f.write(f"{dash}\n")
        _file_table(f, supp_files, source_dir)
        f.write(f"\n{bar}\n")


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


def count_file_stats(filepath):
    """Return (char_count, word_count) for a text file."""
    try:
        with open(filepath, encoding="utf-8", errors="replace") as f:
            text = f.read()
        return len(text), len(text.split())
    except Exception:
        return 0, 0


def collect_output_files(output_dir):
    """Return list of (rel_path, chars, words) for .xml/.txt files directly in output_dir.

    Non-recursive by design: each group's output dir contains only that group's
    files; subdirectories belong to other groups and are logged separately.
    """
    files = []
    if not os.path.isdir(output_dir):
        return files
    for fname in sorted(os.listdir(output_dir)):
        if fname.lower().endswith((".xml", ".txt")):
            fpath = os.path.join(output_dir, fname)
            if os.path.isfile(fpath):
                chars, words = count_file_stats(fpath)
                files.append((fname, chars, words))
    return files


def log_group_header(log_path, label, pdf_dir):
    """Write a visual separator to the log marking the start of a new input group."""
    bar = "-" * 70
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{bar}\n")
        f.write(f"Group:  {label}\n")
        f.write(f"Source: {pdf_dir}\n")
        f.write(f"{bar}\n")


def log_step_stats(log_path, tsv_path, base_dir, step_name, label, output_dir, elapsed,
                   file_elapsed=None):
    """Append character/word stats to the log and TSV for all output files.

    file_elapsed: optional dict mapping output basename → elapsed seconds.
    When provided, per-file timings appear in the log table and TSV rows.
    The step header still shows the total elapsed for context.
    """
    files = collect_output_files(output_dir)

    timestamp    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration_str = format_duration(elapsed)

    # --- human-readable log ---
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n  >> {step_name}  {timestamp}  ({duration_str} total)\n")
        f.write(f"     Output: {output_dir}\n")
        if not files:
            f.write("     (no .xml or .txt files found)\n")
        else:
            name_w = max(max(len(r) for r, _, _ in files), 40)
            if file_elapsed:
                f.write(f"     {'File':<{name_w}}  {'Chars':>12}  {'Words':>9}  {'Time':>10}\n")
                f.write(f"     {'-'*name_w}  {'-'*12}  {'-'*9}  {'-'*10}\n")
            else:
                f.write(f"     {'File':<{name_w}}  {'Chars':>12}  {'Words':>9}\n")
                f.write(f"     {'-'*name_w}  {'-'*12}  {'-'*9}\n")
            total_chars = total_words = 0
            for rel, chars, words in files:
                total_chars += chars
                total_words += words
                if file_elapsed:
                    secs = file_elapsed.get(os.path.basename(rel))
                    time_col = format_duration(secs) if secs is not None else "—"
                    f.write(f"     {rel:<{name_w}}  {chars:>12,}  {words:>9,}  {time_col:>10}\n")
                else:
                    f.write(f"     {rel:<{name_w}}  {chars:>12,}  {words:>9,}\n")
            f.write(f"     {'TOTAL':<{name_w}}  {total_chars:>12,}  {total_words:>9,}\n")

    # --- TSV ---
    step_num   = {"GROBID": 1, "GNorm2": 2, "tmVar3": 3, "AIONER": 4, "NLMChem": 5, "TaggerOne": 6}.get(step_name, step_name)
    input_name = os.path.basename(label) if label != "main" else "main"
    with open(tsv_path, "a", encoding="utf-8") as f:
        for rel, chars, words in files:
            file_stem = os.path.splitext(os.path.basename(rel))[0]
            out_rel   = os.path.relpath(os.path.join(output_dir, rel), base_dir)
            if file_elapsed:
                secs = file_elapsed.get(os.path.basename(rel))
                row_dur = format_duration(secs) if secs is not None else duration_str
            else:
                row_dur = duration_str
            f.write(f"{step_num}\t{step_name}\t{label}\t{chars}\t{words}\t{row_dur}\t{file_stem}\t{out_rel}\n")


def enforce_max_chars(output_dir, max_chars, log_path, step_name, label):
    """Remove any output files directly in output_dir whose char count exceeds max_chars.

    Removed files won't be seen by subsequent steps, effectively abandoning
    that document for the rest of the pipeline.  Returns the list of removed filenames.
    Non-recursive: each group is responsible only for its own immediate output files.
    """
    if not max_chars or not os.path.isdir(output_dir):
        return []
    removed = []
    for fname in sorted(os.listdir(output_dir)):
        if fname.lower().endswith((".xml", ".txt")):
            fpath = os.path.join(output_dir, fname)
            if not os.path.isfile(fpath):
                continue
            chars, _ = count_file_stats(fpath)
            if chars > max_chars:
                print(light_blue(
                    f"WARNING: [{label}] {fname} — {chars:,} chars exceeds "
                    f"--max-chars {max_chars:,}; skipping this document"
                ), file=sys.stderr)
                with open(log_path, "a", encoding="utf-8") as f:
                    f.write(
                        f"  *** SKIPPED: {fname} — {chars:,} chars exceeds "
                        f"limit of {max_chars:,} ***\n"
                    )
                os.remove(fpath)
                removed.append(fname)
    return removed


def clear_intermediates(input_dir, base_dir, log_path):
    """Remove staging dirs and supplementary stem dirs; preserve 02–07 output directories."""
    # Remove any staging dirs left behind by interrupted runs (normally cleaned in finally blocks)
    for staging_dir in [
        ".gnorm2_staging_in",   ".gnorm2_staging_out",
        ".aioner_staging_in",   ".aioner_staging_out",
        ".tmvar3_staging_in",   ".tmvar3_staging_out",
        ".taggerone_staging_in", ".taggerone_staging_out",
        ".nlmchem_staging_in",  ".nlmchem_staging_out",
        ".nlmchem_abbr_staging",
    ]:
        path = os.path.join(base_dir, staging_dir)
        if os.path.isdir(path):
            shutil.rmtree(path)

    # Remove stem-level directories created under 01_source/s/ (keep only the original files)
    s_dir = os.path.join(input_dir, "s")
    if os.path.isdir(s_dir):
        for entry in sorted(os.listdir(s_dir)):
            entry_path = os.path.join(s_dir, entry)
            if os.path.isdir(entry_path):
                shutil.rmtree(entry_path)

    with open(log_path, "a", encoding="utf-8") as f:
        f.write("# Intermediates cleared\n")


def find_supplement_leaf_dirs(input_dir):
    """
    Returns list of (abs_path, rel_from_input_dir) for directories under
    input_dir/s/<stem>/ (and deeper) that contain PDF files.
    Does not include input_dir/s/ itself (those are the original source files).
    """
    s_dir = os.path.join(input_dir, "s")
    if not os.path.isdir(s_dir):
        return []

    results = []
    for stem_name in sorted(os.listdir(s_dir)):
        stem_path = os.path.join(s_dir, stem_name)
        if not os.path.isdir(stem_path):
            continue
        for root, dirs, files in os.walk(stem_path):
            dirs.sort()
            has_pdf = any(
                f.lower().endswith(".pdf") and f not in IGNORED_FILES and not f.startswith("~$")
                for f in files
            )
            if has_pdf:
                results.append((root, os.path.relpath(root, input_dir)))
    return results


_ENRICH_TYPES = ('Gene', 'Species', 'CellLine')

def _extract_bioc_annotations(bioc_path):
    """Return list of (doc_id, start, end, text, etype, identifier) for Gene/Species/CellLine."""
    with open(bioc_path, encoding='utf-8') as fh:
        content = fh.read()
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        print(f'warning: could not parse {bioc_path}: {exc}', file=sys.stderr)
        return []
    results = []
    for doc in root.findall('document'):
        doc_id = doc.findtext('id', '')
        for passage in doc.findall('passage'):
            for ann in passage.findall('annotation'):
                infons = {i.get('key'): (i.text or '') for i in ann.findall('infon')}
                etype = infons.get('type', '')
                if etype not in _ENRICH_TYPES:
                    continue
                loc = ann.find('location')
                if loc is None:
                    continue
                start = int(loc.get('offset', 0))
                length = int(loc.get('length', 0))
                text = ann.findtext('text', '')
                if etype == 'Gene':
                    identifier = infons.get('NCBI Gene', '')
                else:
                    identifier = infons.get('NCBI Taxonomy', '').lstrip('*')
                results.append((doc_id, start, start + length, text, etype, identifier))
    return results


def enrich_pubtator_from_bioc(tmvar_dir):
    """Append Gene/Species/CellLine annotations from BioC XML into each .PubTator file."""
    for dirpath, _dirs, filenames in os.walk(tmvar_dir):
        for fname in sorted(filenames):
            if not fname.endswith('.BioC.XML'):
                continue
            bioc_path = os.path.join(dirpath, fname)
            pubtator_path = bioc_path[:-len('.BioC.XML')] + '.PubTator'
            if not os.path.isfile(pubtator_path):
                continue

            new_anns = _extract_bioc_annotations(bioc_path)
            if not new_anns:
                continue

            # Build set of already-present annotation keys to avoid duplicates
            existing = set()
            with open(pubtator_path, encoding='utf-8') as fh:
                for line in fh:
                    parts = line.rstrip('\n').split('\t')
                    if len(parts) >= 5:
                        try:
                            existing.add((parts[0], int(parts[1]), int(parts[2]), parts[3], parts[4]))
                        except ValueError:
                            pass

            lines_to_add = []
            for doc_id, start, end, text, etype, identifier in new_anns:
                if (doc_id, start, end, text, etype) not in existing:
                    lines_to_add.append(f'{doc_id}\t{start}\t{end}\t{text}\t{etype}\t{identifier}\n')

            if lines_to_add:
                with open(pubtator_path, 'a', encoding='utf-8') as fh:
                    fh.writelines(lines_to_add)
                rel = os.path.relpath(pubtator_path, tmvar_dir)
                print(f'  enriched {rel}: +{len(lines_to_add)} Gene/Species/CellLine annotations',
                      file=sys.stderr)


def collect_xml_files(dir_path):
    """Return sorted list of .xml file paths directly in dir_path (non-recursive).

    Non-recursive by design: each group's output dir contains only that group's
    files; subdirectories belong to other groups and are collected separately.
    """
    if not os.path.isdir(dir_path):
        return []
    return sorted(
        os.path.join(dir_path, fname)
        for fname in os.listdir(dir_path)
        if fname.lower().endswith(".xml")
        and os.path.isfile(os.path.join(dir_path, fname))
    )


def run_grobid_for_group(label, pdf_dir, grobid_out, args, log_path, tsv_path, base_dir,
                          supplementary=False):
    """Run GROBID for one directory of PDFs."""
    os.makedirs(grobid_out, exist_ok=True)
    log_group_header(log_path, label, pdf_dir)
    grobid_cmd = [sys.executable, os.path.join(STEPS_DIR, "pdf_to_bioc.py"), pdf_dir, grobid_out]
    if supplementary:
        grobid_cmd.append("--supplementary")
    t0 = time.time()
    run(f"GROBID  [{label}]", grobid_cmd)
    log_step_stats(log_path, tsv_path, base_dir, "GROBID", label, grobid_out,
                   elapsed=time.time() - t0)
    enforce_max_chars(grobid_out, args.max_chars, log_path, "GROBID", label)


def _build_flat_staging(all_files, staging_in):
    """
    Copy files into staging_in with numeric prefixes to avoid name collisions.

    all_files: list of (group_dict, src_path)
    Returns entries: list of (staging_name, original_fname, group_dict)
    """
    os.makedirs(staging_in, exist_ok=True)
    entries = []
    for i, (group, src_path) in enumerate(all_files):
        fname = os.path.basename(src_path)
        staging_name = f"{i:04d}_{fname}"
        shutil.copy2(src_path, os.path.join(staging_in, staging_name))
        entries.append((staging_name, fname, group))
    return entries


def _per_file_elapsed(entries, staging_out, t_start, output_suffix=""):
    """
    Derive per-file elapsed seconds from output file mtimes after a batch run.

    The first file absorbs startup overhead (mtime - t_start); each subsequent
    file is measured as mtime[i] - mtime[i-1].

    output_suffix: suffix appended to staging_name to locate the output file
                   (e.g. ".BioC.XML" for tmVar3, "" for GNorm2).
    Returns dict: original_fname + output_suffix → elapsed_seconds
    """
    timed = []
    for staging_name, fname, _group in entries:
        out_path = os.path.join(staging_out, staging_name + output_suffix)
        if os.path.exists(out_path):
            timed.append((fname + output_suffix, os.path.getmtime(out_path)))
    timed.sort(key=lambda x: x[1])
    result = {}
    prev = t_start
    for result_fname, mtime in timed:
        result[result_fname] = mtime - prev
        prev = mtime
    return result


def _log_batch_header(log_path, step_name, n_groups):
    bar = "=" * 70
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{bar}\n")
        f.write(f"{step_name} — batched across {n_groups} group(s)\n")
        f.write(f"{bar}\n")


def run_gnorm2_batched(groups, args, log_path, tsv_path, base_dir):
    """Run GNorm2 once across all groups combined, then distribute outputs."""
    all_files = [(g, p) for g in groups for p in collect_xml_files(g['grobid_out'])]
    if not all_files:
        return

    staging_in  = os.path.join(base_dir, ".gnorm2_staging_in")
    staging_out = os.path.join(base_dir, ".gnorm2_staging_out")
    try:
        entries = _build_flat_staging(all_files, staging_in)

        xmx = args.memory
        xms = half_memory(args.memory)
        gnorm2_cmd = [
            sys.executable, os.path.join(STEPS_DIR, "run_gnorm2.py"),
            staging_in, staging_out,
            "--xmx", xmx, "--xms", xms,
        ]
        if args.gnorm2_python:
            gnorm2_cmd += ["--ml-python", args.gnorm2_python]

        _log_batch_header(log_path, "GNorm2", len(groups))
        t0 = time.time()
        run("GNorm2  [all]", gnorm2_cmd)
        elapsed = time.time() - t0

        file_elapsed = _per_file_elapsed(entries, staging_out, t0)

        for staging_name, fname, group in entries:
            gnorm2_out = group['gnorm2_out']
            os.makedirs(gnorm2_out, exist_ok=True)
            out_src = os.path.join(staging_out, staging_name)
            if os.path.exists(out_src):
                shutil.copy2(out_src, os.path.join(gnorm2_out, fname))

        for g in groups:
            log_step_stats(log_path, tsv_path, base_dir, "GNorm2", g['label'],
                           g['gnorm2_out'], elapsed, file_elapsed=file_elapsed)
            enforce_max_chars(g['gnorm2_out'], args.max_chars, log_path, "GNorm2", g['label'])

    finally:
        if args.clear_intermediates:
            shutil.rmtree(staging_in, ignore_errors=True)
            shutil.rmtree(staging_out, ignore_errors=True)


def run_aioner_batched(groups, args, log_path, tsv_path, base_dir):
    """Run AIONER once across all groups combined, then distribute outputs.

    AIONER reads from GROBID output (same input as GNorm2) and writes
    NER-annotated BioC XML to 05_aioner/, independent of GNorm2/tmVar3.
    """
    all_files = [(g, p) for g in groups for p in collect_xml_files(g['grobid_out'])]
    if not all_files:
        return

    staging_in  = os.path.join(base_dir, ".aioner_staging_in")
    staging_out = os.path.join(base_dir, ".aioner_staging_out")
    try:
        entries = _build_flat_staging(all_files, staging_in)

        aioner_cmd = [
            sys.executable, os.path.join(STEPS_DIR, "run_aioner.py"),
            staging_in, staging_out,
        ]
        if args.aioner_python:
            aioner_cmd += ["--aioner-python", args.aioner_python]

        _log_batch_header(log_path, "AIONER", len(groups))
        t0 = time.time()
        run("AIONER   [all]", aioner_cmd)
        elapsed = time.time() - t0

        file_elapsed = _per_file_elapsed(entries, staging_out, t0)

        for staging_name, fname, group in entries:
            aioner_out = group['aioner_out']
            os.makedirs(aioner_out, exist_ok=True)
            out_src = os.path.join(staging_out, staging_name)
            if os.path.exists(out_src):
                shutil.copy2(out_src, os.path.join(aioner_out, fname))

        for g in groups:
            log_step_stats(log_path, tsv_path, base_dir, "AIONER", g['label'],
                           g['aioner_out'], elapsed, file_elapsed=file_elapsed)

    finally:
        if args.clear_intermediates:
            shutil.rmtree(staging_in, ignore_errors=True)
            shutil.rmtree(staging_out, ignore_errors=True)


def run_tmvar3_batched(groups, args, log_path, tsv_path, base_dir):
    """Run tmVar3 once across all groups combined, then distribute outputs."""
    all_files = [(g, p) for g in groups for p in collect_xml_files(g['gnorm2_out'])]
    if not all_files:
        return

    staging_in  = os.path.join(base_dir, ".tmvar3_staging_in")
    staging_out = os.path.join(base_dir, ".tmvar3_staging_out")
    try:
        entries = _build_flat_staging(all_files, staging_in)

        xmx = args.memory
        xms = half_memory(args.memory)
        tmvar_cmd = [
            sys.executable, os.path.join(STEPS_DIR, "run_tmvar.py"),
            staging_in, staging_out,
            "--xmx", xmx, "--xms", xms,
        ]
        if args.timeout_per_doc:
            tmvar_cmd += ["--timeout-per-doc", str(args.timeout_per_doc)]

        _log_batch_header(log_path, "tmVar3", len(groups))
        t0 = time.time()
        run("tmVar3  [all]", tmvar_cmd)
        elapsed = time.time() - t0

        # Use .BioC.XML mtime as the per-file timing anchor (written last by tmVar3).
        file_elapsed = _per_file_elapsed(entries, staging_out, t0, output_suffix=".BioC.XML")

        for staging_name, fname, group in entries:
            tmvar_out = group['tmvar_out']
            os.makedirs(tmvar_out, exist_ok=True)
            for suffix in (".PubTator", ".BioC.XML"):
                out_src = os.path.join(staging_out, staging_name + suffix)
                if os.path.exists(out_src):
                    shutil.copy2(out_src, os.path.join(tmvar_out, fname + suffix))

        for g in groups:
            enrich_pubtator_from_bioc(g['tmvar_out'])
            log_step_stats(log_path, tsv_path, base_dir, "tmVar3", g['label'],
                           g['tmvar_out'], elapsed, file_elapsed=file_elapsed)

    finally:
        if args.clear_intermediates:
            shutil.rmtree(staging_in, ignore_errors=True)
            shutil.rmtree(staging_out, ignore_errors=True)


def _extract_bioc_texts(bioc_path):
    """Return (doc_id, list_of_passage_texts) from a BioC XML file."""
    with open(bioc_path, encoding='utf-8') as fh:
        content = fh.read()
    content = re.sub(r'<!DOCTYPE[^>]*>', '', content)
    try:
        root = ET.fromstring(content)
    except ET.ParseError as exc:
        print(f'warning: could not parse {bioc_path}: {exc}', file=sys.stderr)
        return '', []
    doc_id = ''
    texts = []
    for doc in root.findall('document'):
        if not doc_id:
            doc_id = doc.findtext('id', '')
        for passage in doc.findall('passage'):
            text = (passage.findtext('text') or '').strip()
            if text:
                texts.append(text)
    return doc_id, texts


def _run_ab3p(texts):
    """Run Ab3P identify_abbr on a list of text strings; return (short, long) pairs.

    Ab3P must run from its own directory so that path_Ab3P resolves to ./WordData/.
    Input is fed via stdin (/dev/stdin); each text string becomes one input line.
    Output lines indented with two spaces carry the pipe-delimited SF|LF|precision.
    """
    ab3p_bin = os.path.join(AB3P_DIR, 'identify_abbr')
    combined = '\n'.join(texts)
    result = subprocess.run(
        [ab3p_bin, '/dev/stdin'],
        input=combined, capture_output=True, text=True,
        cwd=AB3P_DIR,
    )
    pairs = []
    for line in result.stdout.splitlines():
        if line.startswith('  ') and '|' in line:
            parts = line.strip().split('|')
            if len(parts) >= 2:
                pairs.append((parts[0], parts[1]))
    return pairs


def run_taggerone_batched(groups, args, log_path, tsv_path, base_dir):
    """Run TaggerOne across all groups combined, then distribute outputs.

    Reads from GROBID output (same input as AIONER/GNorm2).
    Skipped if --taggerone-model is not provided.
    """
    if not args.taggerone_model:
        return

    all_files = [(g, p) for g in groups for p in collect_xml_files(g['grobid_out'])]
    if not all_files:
        return

    staging_in  = os.path.join(base_dir, ".taggerone_staging_in")
    staging_out = os.path.join(base_dir, ".taggerone_staging_out")
    try:
        entries = _build_flat_staging(all_files, staging_in)

        xmx = args.memory
        xms = half_memory(args.memory)
        taggerone_cmd = [
            sys.executable, os.path.join(STEPS_DIR, "run_taggerone.py"),
            staging_in, staging_out,
            "--model", os.path.abspath(args.taggerone_model),
            "--xmx", xmx, "--xms", xms,
        ]

        _log_batch_header(log_path, "TaggerOne", len(groups))
        t0 = time.time()
        run("TaggerOne [all]", taggerone_cmd)
        elapsed = time.time() - t0

        file_elapsed = _per_file_elapsed(entries, staging_out, t0)

        for staging_name, fname, group in entries:
            taggerone_out = group['taggerone_out']
            os.makedirs(taggerone_out, exist_ok=True)
            out_src = os.path.join(staging_out, staging_name)
            if os.path.exists(out_src):
                shutil.copy2(out_src, os.path.join(taggerone_out, fname))

        for g in groups:
            log_step_stats(log_path, tsv_path, base_dir, "TaggerOne", g['label'],
                           g['taggerone_out'], elapsed, file_elapsed=file_elapsed)

    finally:
        if args.clear_intermediates:
            shutil.rmtree(staging_in,  ignore_errors=True)
            shutil.rmtree(staging_out, ignore_errors=True)


def run_nlmchem_batched(groups, args, log_path, tsv_path, base_dir):
    """Run Ab3P + NLMChem once across all groups combined, then distribute outputs.

    Ab3P is run per document (C++ binary, negligible startup) to generate
    abbreviation TSV files.  NLMChem is then run once on the flat staging
    dir to amortize its dictionary loading startup cost (~30 s).

    Abbreviation TSVs are saved permanently to each group's 06_nlmchem/abbreviations/
    directory (or 06_nlmchem/s/<rel>/abbreviations/ for supplementary groups) so
    they can be inspected alongside the NLMChem output.
    """
    all_files = [(g, p) for g in groups for p in collect_xml_files(g['aioner_out'])]
    if not all_files:
        return

    nlmchem_root = os.path.join(base_dir, '06_nlmchem')
    staging_in   = os.path.join(base_dir, '.nlmchem_staging_in')
    staging_out  = os.path.join(base_dir, '.nlmchem_staging_out')
    abbr_staging = os.path.join(base_dir, '.nlmchem_abbr_staging')
    os.makedirs(abbr_staging, exist_ok=True)

    try:
        entries = _build_flat_staging(all_files, staging_in)

        # --- Phase A: Ab3P abbreviation extraction ---
        for staging_name, fname, group in entries:
            staged_path = os.path.join(staging_in, staging_name)
            doc_id, texts = _extract_bioc_texts(staged_path)
            pairs = _run_ab3p(texts)

            # Permanent storage: one TSV per document, named by original stem
            abbr_dir = group['nlmchem_abbr_out']
            os.makedirs(abbr_dir, exist_ok=True)
            abbr_tsv = os.path.join(abbr_dir, os.path.splitext(fname)[0] + '.tsv')
            with open(abbr_tsv, 'w', encoding='utf-8') as fh:
                for short, long in pairs:
                    fh.write(f'{doc_id}\t{short}\t{long}\n')

            # Staging copy for this batch NLMChem run (named by staging stem so
            # it is unique in the flat abbr dir and matches no input filename)
            shutil.copy2(abbr_tsv,
                         os.path.join(abbr_staging,
                                      os.path.splitext(staging_name)[0] + '.tsv'))

        # --- Phase B: NLMChem normalization ---
        os.makedirs(nlmchem_root, exist_ok=True)
        nlmchem_cmd = [
            sys.executable, os.path.join(STEPS_DIR, "run_nlmchem.py"),
            staging_in, abbr_staging, staging_out,
            '--log', os.path.join(nlmchem_root, 'nlmchem.log'),
        ]
        if args.nlmchem_python:
            nlmchem_cmd += ['--nlmchem-python', args.nlmchem_python]

        _log_batch_header(log_path, 'NLMChem', len(groups))
        t0 = time.time()
        run('NLMChem [all]', nlmchem_cmd)
        elapsed = time.time() - t0

        file_elapsed = _per_file_elapsed(entries, staging_out, t0)

        for staging_name, fname, group in entries:
            nlmchem_out = group['nlmchem_out']
            os.makedirs(nlmchem_out, exist_ok=True)
            out_src = os.path.join(staging_out, staging_name)
            if os.path.exists(out_src):
                shutil.copy2(out_src, os.path.join(nlmchem_out, fname))

        for g in groups:
            log_step_stats(log_path, tsv_path, base_dir, 'NLMChem', g['label'],
                           g['nlmchem_out'], elapsed, file_elapsed=file_elapsed)

    finally:
        if args.clear_intermediates:
            shutil.rmtree(staging_in,   ignore_errors=True)
            shutil.rmtree(staging_out,  ignore_errors=True)
            shutil.rmtree(abbr_staging, ignore_errors=True)


def generate_report(top_dir, log_path):
    """Run report_civic_pubtator.py; return (html_path, tsv_path) on success or (None, None)."""
    run_title   = os.path.basename(os.path.abspath(top_dir))
    html_path   = os.path.join(top_dir, f'report_{run_title}.html')
    tsv_path    = os.path.join(top_dir, f'report_{run_title}.tsv')
    report_script = os.path.join(STEPS_DIR, "report_civic_pubtator.py")
    result = subprocess.run([sys.executable, report_script, top_dir])
    if result.returncode == 0:
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(f"# Report:   {html_path}\n")
            f.write(f"# ReportTSV:{tsv_path}\n")
        return html_path, tsv_path
    else:
        print(light_blue("WARNING: report generation failed"), file=sys.stderr)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write("# Report:   FAILED\n")
        return None, None


def process_input(top_dir, args):
    source_dir      = os.path.join(top_dir, "01_source")
    grobid_root     = os.path.join(top_dir, "02_grobid")
    gnorm2_root     = os.path.join(top_dir, "03_gnorm2")
    tmvar_root      = os.path.join(top_dir, "04_tmvar3")
    aioner_root     = os.path.join(top_dir, "05_aioner")
    nlmchem_root    = os.path.join(top_dir, "06_nlmchem")
    taggerone_root  = os.path.join(top_dir, "07_taggerone")
    log_path      = os.path.join(top_dir, "pipeline_stats.log")
    tsv_path      = os.path.join(top_dir, "pipeline_stats.tsv")
    manifest_path = os.path.join(top_dir, "MANIFEST.txt")

    # Clean top-level output dirs (covers supplementary subdirs too)
    if args.clean:
        for d in [grobid_root, gnorm2_root, tmvar_root, aioner_root, nlmchem_root, taggerone_root]:
            if os.path.exists(d):
                print(light_blue(f"Cleaning {d} ..."), file=sys.stderr)
                shutil.rmtree(d)
        run_title = os.path.basename(os.path.abspath(top_dir))
        for f in (log_path, tsv_path, manifest_path,
                  os.path.join(top_dir, f"report_{run_title}.html"),
                  os.path.join(top_dir, f"report_{run_title}.tsv")):
            if os.path.exists(f):
                print(light_blue(f"Cleaning {f} ..."), file=sys.stderr)
                os.remove(f)
        # Remove any staging dirs left over from a previous --no-clear-intermediates run
        for staging in (
            ".gnorm2_staging_in",     ".gnorm2_staging_out",
            ".tmvar3_staging_in",     ".tmvar3_staging_out",
            ".aioner_staging_in",     ".aioner_staging_out",
            ".nlmchem_staging_in",    ".nlmchem_staging_out",    ".nlmchem_abbr_staging",
            ".taggerone_staging_in",  ".taggerone_staging_out",
        ):
            d = os.path.join(top_dir, staging)
            if os.path.exists(d):
                print(light_blue(f"Cleaning {d} ..."), file=sys.stderr)
                shutil.rmtree(d)

    # Write TSV header if file is new or empty
    if not os.path.exists(tsv_path) or os.path.getsize(tsv_path) == 0:
        with open(tsv_path, "w", encoding="utf-8") as f:
            f.write("step\tstep_name\tlabel\tchars\twords\truntime\tinput_name\toutput_file\n")

    # Write run header to log
    run_timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    timestamp = run_timestamp
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'#'*70}\n")
        f.write(f"# Pipeline run started: {timestamp}\n")
        f.write(f"# Input dir:  {top_dir}\n")
        f.write(f"# Source dir: {source_dir}\n")

        max_rows_str  = f"{args.max_rows:,}"  if args.max_rows  else "unlimited"
        max_chars_str = f"{args.max_chars:,}" if args.max_chars else "unlimited"
        timeout_str   = f"{args.timeout_per_doc}s" if args.timeout_per_doc else "unlimited"
        f.write(f"# Max rows (Excel): {max_rows_str}\n")
        f.write(f"# Max chars:        {max_chars_str}\n")
        f.write(f"# tmVar timeout/doc: {timeout_str}\n")
        f.write(f"# Clear intermediates: {args.clear_intermediates}\n")
        gnorm2_py_str = args.gnorm2_python if args.gnorm2_python else f"{sys.executable} (default)"
        f.write(f"# GNorm2 Python: {gnorm2_py_str}\n")
        f.write(f"{'#'*70}\n")

    # Prepare supplementary PDFs if 01_source/s/ exists
    s_dir = os.path.join(source_dir, "s")
    if os.path.isdir(s_dir):
        supp_cmd = [sys.executable, os.path.join(STEPS_DIR, "prepare_supplementary.py"),
                    source_dir]
        if args.no_libreoffice:
            supp_cmd.append("--no-libreoffice")
        supp_cmd += ["--max-rows", str(args.max_rows)]
        run("Supplementary prep", supp_cmd)

    # Write manifest of source files and tool version
    write_manifest(manifest_path, top_dir, source_dir,
                   read_release_version(), run_timestamp)

    # Discover all groups (main publication + supplementary leaf dirs)
    groups = [{
        'label':            'main',
        'pdf_dir':          source_dir,
        'grobid_out':       grobid_root,
        'gnorm2_out':       gnorm2_root,
        'tmvar_out':        tmvar_root,
        'aioner_out':       aioner_root,
        'nlmchem_out':      nlmchem_root,
        'nlmchem_abbr_out': os.path.join(nlmchem_root, 'abbreviations'),
        'taggerone_out':    taggerone_root,
        'supplementary':    False,
    }]
    for abs_path, rel in find_supplement_leaf_dirs(source_dir):
        groups.append({
            'label':            rel,
            'pdf_dir':          abs_path,
            'grobid_out':       os.path.join(grobid_root, rel),
            'gnorm2_out':       os.path.join(gnorm2_root, rel),
            'tmvar_out':        os.path.join(tmvar_root,  rel),
            'aioner_out':       os.path.join(aioner_root, rel),
            'nlmchem_out':      os.path.join(nlmchem_root, rel),
            'nlmchem_abbr_out': os.path.join(nlmchem_root, rel, 'abbreviations'),
            'taggerone_out':    os.path.join(taggerone_root, rel),
            'supplementary':    True,
        })

    # Phase 1: GROBID — one invocation per group (no shared startup cost)
    for g in groups:
        run_grobid_for_group(
            g['label'], g['pdf_dir'], g['grobid_out'],
            args, log_path, tsv_path, top_dir,
            supplementary=g['supplementary'],
        )

    # Phase 2: GNorm2 — one invocation for all groups combined
    run_gnorm2_batched(groups, args, log_path, tsv_path, top_dir)

    # Phase 3: tmVar3 — one invocation for all groups combined
    run_tmvar3_batched(groups, args, log_path, tsv_path, top_dir)

    # Phase 4: AIONER — one invocation for all groups combined (reads GROBID output)
    run_aioner_batched(groups, args, log_path, tsv_path, top_dir)

    # Phase 5: NLMChem — Ab3P abbreviation extraction then chemical normalization
    run_nlmchem_batched(groups, args, log_path, tsv_path, top_dir)

    # Phase 6: TaggerOne — disease/chemical NER and normalization (skipped if no model given)
    run_taggerone_batched(groups, args, log_path, tsv_path, top_dir)

    # Write run footer
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n# Pipeline run finished: {timestamp}\n")
        f.write(f"# Log:      {log_path}\n")
        f.write(f"# TSV:      {tsv_path}\n")
        f.write(f"# Manifest: {manifest_path}\n")

    # Generate HTML report and mentions TSV (must happen before clearing intermediates)
    report_html, report_tsv = generate_report(top_dir, log_path)

    # Clear intermediate files and dirs
    if args.clear_intermediates:
        print(light_blue("Clearing intermediates ..."), file=sys.stderr)
        clear_intermediates(source_dir, top_dir, log_path)

    last_root = taggerone_root if args.taggerone_model else nlmchem_root
    print(light_blue(f"\nDone: {top_dir}  →  {last_root}"), file=sys.stderr)
    print(light_blue(f"Stats log: {log_path}"), file=sys.stderr)
    print(light_blue(f"Stats TSV: {tsv_path}"), file=sys.stderr)
    print(light_blue(f"Manifest:  {manifest_path}"), file=sys.stderr)
    if report_html:
        print(light_blue(f"Report:    {report_html}"), file=sys.stderr)
    if report_tsv:
        print(light_blue(f"ReportTSV: {report_tsv}"), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Run the full PDF → BioC → GNorm2 → tmVar3 pipeline. "
                    "Each input_dir must contain a '01_source' subdirectory holding "
                    "the source PDF(s). Output directories 02_grobid, 03_gnorm2, and "
                    "04_tmvar3 are created as siblings of 01_source inside input_dir. "
                    "Supplementary files are optional; if provided, place them under "
                    "01_source/s/<stem>/."
    )
    parser.add_argument("input_dirs", nargs="+",
                        help="One or more top-level directories, each containing a "
                             "'01_source' subdirectory with source PDF(s)")
    parser.add_argument("--clean", action="store_true",
                        help="Delete and recreate output directories before running")
    parser.add_argument("--no-clear-intermediates", dest="clear_intermediates",
                        action="store_false",
                        help="Keep tmp dirs and prepared supplement PDFs after pipeline completes")
    parser.set_defaults(clear_intermediates=True)

    parser.add_argument("--no-libreoffice", action="store_true",
                        help="Use reportlab/python-docx fallback instead of LibreOffice")
    parser.add_argument("--max-rows", type=int, default=1000, metavar="N",
                        help="Maximum rows to read per Excel sheet tab when converting "
                             "supplementary .xls/.xlsx files to PDF (default: 1000; "
                             "use 0 for no limit). Applied first, at the conversion stage. "
                             "See also --max-chars.")
    parser.add_argument("--max-chars", type=int, default=1_000_000, metavar="N",
                        help="Skip any document whose converted output exceeds N characters "
                             "at any annotation step; all remaining steps are skipped for "
                             "that document (default: 1000000; use 0 for no limit). Applied "
                             "after --max-rows: --max-rows caps each Excel table at the PDF "
                             "conversion stage; --max-chars then drops any document that is "
                             "still too large for the annotation pipeline.")
    parser.add_argument("--timeout-per-doc", type=int, default=0, metavar="SECONDS",
                        help="Per-document timeout for tmVar3 in seconds (0 = no limit). "
                             "When a document exceeds this limit its CRF++ subprocess is "
                             "killed and processing continues with the next document.")
    parser.add_argument("--memory", default="32G", metavar="SIZE",
                        help="Java max heap for GNorm2 and tmVar3 (default: 32G); "
                             "initial heap is set to half this value")
    parser.add_argument("--gnorm2-python", default=None, metavar="PATH_OR_ENV",
                        help="Python interpreter or conda env for the GNorm2 ML step. "
                             "Accepts a full path to a Python executable or a "
                             "bare conda env name. Defaults to the 'gnorm2-tf215' "
                             "conda env. "
                             "Examples: "
                             "--gnorm2-python gnorm2-tf215  (conda env name) or "
                             "--gnorm2-python /opt/homebrew/Caskroom/miniforge"
                             "/base/envs/gnorm2-tf215/bin/python3  (full path)")
    parser.add_argument("--aioner-python", default=None, metavar="PATH_OR_ENV",
                        help="Python interpreter or conda env for AIONER. "
                             "Accepts a full path to a Python executable or a "
                             "bare conda env name. Defaults to the 'aioner-tf23' "
                             "conda env. "
                             "Examples: "
                             "--aioner-python aioner-tf23  (conda env name) or "
                             "--aioner-python /path/to/envs/aioner-tf23/bin/python3")
    default_taggerone_model = os.path.join(REPO_DIR, "tools", "TaggerOne", "output", "model_DISE.bin")
    parser.add_argument("--taggerone-model", default=default_taggerone_model, metavar="PATH",
                        help="Path to a trained TaggerOne model (.bin file). "
                             "Runs TaggerOne disease/chemical NER and normalization on "
                             "GROBID output as the final pipeline step (07_taggerone/). "
                             "Set to empty string to skip this step. "
                             f"Default: {default_taggerone_model}")
    parser.add_argument("--nlmchem-python", default=None, metavar="PATH_OR_ENV",
                        help="Python interpreter or conda env for NLMChem. "
                             "Accepts a full path to a Python executable or a "
                             "bare conda env name. Defaults to the 'nlmchem-py39' "
                             "conda env. "
                             "Examples: "
                             "--nlmchem-python nlmchem-py39  (conda env name) or "
                             "--nlmchem-python /path/to/envs/nlmchem-py39/bin/python3")
    parser.add_argument("--quiet-tf", action="store_true",
                        help="Suppress TensorFlow and HuggingFace Transformers "
                             "informational messages (sets TF_CPP_MIN_LOG_LEVEL=3, "
                             "TRANSFORMERS_VERBOSITY=error, and filters TF UserWarnings).")
    args = parser.parse_args()

    if args.quiet_tf:
        os.environ['TF_CPP_MIN_LOG_LEVEL'] = '3'
        os.environ['TRANSFORMERS_VERBOSITY'] = 'error'
        os.environ['PYTHONWARNINGS'] = 'ignore::UserWarning:tensorflow'

    # Validate all inputs before starting any work
    validated = []
    for raw in args.input_dirs:
        top_dir    = os.path.abspath(raw)
        source_dir = os.path.join(top_dir, "01_source")
        if not os.path.isdir(top_dir):
            print(f"ERROR: Directory not found: {top_dir}", file=sys.stderr)
            sys.exit(1)
        if not os.path.isdir(source_dir):
            # Auto-create 01_source/ and move PDFs into it
            pdfs_in_top = [
                f for f in os.listdir(top_dir)
                if (os.path.isfile(os.path.join(top_dir, f))
                    and f.lower().endswith(".pdf")
                    and not f.startswith("~$")
                    and f not in IGNORED_FILES)
            ]
            if not pdfs_in_top:
                print(
                    f"ERROR: No PDF files found in {top_dir} and '01_source' subdirectory "
                    f"does not exist. Place at least one source PDF in {top_dir}/",
                    file=sys.stderr,
                )
                sys.exit(1)
            os.makedirs(source_dir)
            for fname in pdfs_in_top:
                shutil.move(os.path.join(top_dir, fname), os.path.join(source_dir, fname))
            s_dir = os.path.join(top_dir, "s")
            if os.path.isdir(s_dir):
                shutil.move(s_dir, os.path.join(source_dir, "s"))
                print(
                    light_blue(f"NOTE: Created {source_dir}/ and moved {len(pdfs_in_top)} PDF(s) and s/ into it."),
                    file=sys.stderr,
                )
            else:
                print(
                    light_blue(f"NOTE: Created {source_dir}/ and moved {len(pdfs_in_top)} PDF(s) into it."),
                    file=sys.stderr,
                )
        has_pdf = any(
            f.lower().endswith(".pdf") and not f.startswith("~$") and f not in IGNORED_FILES
            for f in os.listdir(source_dir)
            if os.path.isfile(os.path.join(source_dir, f))
        )
        if not has_pdf:
            print(
                f"ERROR: No PDF files found in {source_dir}.\n"
                f"  Place at least one source PDF directly in that directory.\n"
                f"  Supplementary files are optional; if provided, place them under "
                f"{source_dir}/s/<stem>/",
                file=sys.stderr,
            )
            sys.exit(1)
        validated.append(top_dir)

    for top_dir in validated:
        print(light_blue(f"\n{'#'*60}"), file=sys.stderr)
        print(light_blue(f"Processing: {top_dir}"), file=sys.stderr)
        print(light_blue(f"{'#'*60}"), file=sys.stderr)
        process_input(top_dir, args)


if __name__ == "__main__":
    main()
