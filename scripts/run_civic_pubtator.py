#!/usr/bin/env python3
import argparse, datetime, os, shutil, subprocess, sys, time

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

IGNORED_FILES = {".DS_Store"}

_RED   = "\033[91m"
_RESET = "\033[0m"

def red(text):
    return f"{_RED}{text}{_RESET}" if sys.stderr.isatty() else text


def run(label, cmd):
    bar = "=" * 60
    print(red(f"\n{bar}"), file=sys.stderr)
    print(red(f"{label}: {' '.join(cmd)}"), file=sys.stderr)
    print(red(bar), file=sys.stderr)
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
    """Read the version string from RELEASE at the repo root (one level up from scripts/)."""
    release_path = os.path.join(os.path.dirname(SCRIPTS_DIR), "RELEASE")
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
    """Walk output_dir (skipping tmp* subdirs) and return list of (rel_path, chars, words)."""
    files = []
    for root, dirs, filenames in os.walk(output_dir):
        dirs[:] = [d for d in sorted(dirs) if not d.startswith("tmp")]
        for fname in sorted(filenames):
            if fname.lower().endswith((".xml", ".txt")):
                fpath = os.path.join(root, fname)
                rel = os.path.relpath(fpath, output_dir)
                chars, words = count_file_stats(fpath)
                files.append((rel, chars, words))
    return files


def log_group_header(log_path, label, pdf_dir):
    """Write a visual separator to the log marking the start of a new input group."""
    bar = "-" * 70
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{bar}\n")
        f.write(f"Group:  {label}\n")
        f.write(f"Source: {pdf_dir}\n")
        f.write(f"{bar}\n")


def log_step_stats(log_path, tsv_path, base_dir, step_name, label, output_dir, elapsed):
    """Append character/word stats to the log and TSV for all output files."""
    files = collect_output_files(output_dir)

    timestamp    = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    duration_str = format_duration(elapsed)

    # --- human-readable log ---
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n  >> {step_name}  {timestamp}  ({duration_str})\n")
        f.write(f"     Output: {output_dir}\n")
        if not files:
            f.write("     (no .xml or .txt files found)\n")
        else:
            name_w = max(max(len(r) for r, _, _ in files), 40)
            f.write(f"     {'File':<{name_w}}  {'Chars':>12}  {'Words':>9}\n")
            f.write(f"     {'-'*name_w}  {'-'*12}  {'-'*9}\n")
            total_chars = total_words = 0
            for rel, chars, words in files:
                f.write(f"     {rel:<{name_w}}  {chars:>12,}  {words:>9,}\n")
                total_chars += chars
                total_words += words
            f.write(f"     {'TOTAL':<{name_w}}  {total_chars:>12,}  {total_words:>9,}\n")

    # --- TSV ---
    step_num   = {"GROBID": 1, "GNorm2": 2, "tmVar3": 3}.get(step_name, step_name)
    input_name = os.path.basename(label) if label != "main" else "main"
    with open(tsv_path, "a", encoding="utf-8") as f:
        for rel, chars, words in files:
            file_stem = os.path.splitext(os.path.basename(rel))[0]
            out_rel   = os.path.relpath(os.path.join(output_dir, rel), base_dir)
            f.write(f"{step_num}\t{step_name}\t{label}\t{chars}\t{words}\t{duration_str}\t{file_stem}\t{out_rel}\n")


def enforce_max_chars(output_dir, max_chars, log_path, step_name, label):
    """Remove any output files whose character count exceeds max_chars.

    Removed files won't be seen by subsequent steps, effectively abandoning
    that document for the rest of the pipeline.  Returns the list of removed
    relative paths.
    """
    if not max_chars:
        return []
    removed = []
    for root, dirs, filenames in os.walk(output_dir):
        dirs[:] = [d for d in sorted(dirs) if not d.startswith("tmp")]
        for fname in sorted(filenames):
            if fname.lower().endswith((".xml", ".txt")):
                fpath = os.path.join(root, fname)
                chars, _ = count_file_stats(fpath)
                if chars > max_chars:
                    rel = os.path.relpath(fpath, output_dir)
                    print(red(
                        f"WARNING: [{label}] {rel} — {chars:,} chars exceeds "
                        f"--max-chars {max_chars:,}; skipping this document"
                    ), file=sys.stderr)
                    with open(log_path, "a", encoding="utf-8") as f:
                        f.write(
                            f"  *** SKIPPED: {rel} — {chars:,} chars exceeds "
                            f"limit of {max_chars:,} ***\n"
                        )
                    os.remove(fpath)
                    removed.append(rel)
    return removed


def clear_intermediates(input_dir, base_dir, log_path):
    """Remove tmp dirs and non-XML files from output dirs; remove prepared supplement subdirs."""
    kept_exts = (".xml", ".xml.pubtator")

    # Scrub each output directory
    for out_dir in [
        os.path.join(base_dir, "02_grobid"),
        os.path.join(base_dir, "03_gnorm2"),
        os.path.join(base_dir, "04_tmvar3"),
    ]:
        if not os.path.isdir(out_dir):
            continue
        for root, dirs, files in os.walk(out_dir, topdown=True):
            for d in list(dirs):
                if d.startswith("tmp"):
                    shutil.rmtree(os.path.join(root, d))
                    dirs.remove(d)
            for fname in files:
                if not any(fname.lower().endswith(ext) for ext in kept_exts):
                    os.remove(os.path.join(root, fname))

    # Remove subdirectories created by prepare_supplementary.py (tab_NN/, etc.)
    s_dir = os.path.join(input_dir, "s")
    if os.path.isdir(s_dir):
        for stem_name in sorted(os.listdir(s_dir)):
            stem_path = os.path.join(s_dir, stem_name)
            if not os.path.isdir(stem_path):
                continue
            for subname in sorted(os.listdir(stem_path)):
                subpath = os.path.join(stem_path, subname)
                if os.path.isdir(subpath):
                    shutil.rmtree(subpath)

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


def process_group(label, pdf_dir, grobid_out, gnorm2_out, tmvar_out, args,
                  log_path, tsv_path, base_dir, supplementary=False):
    """Run the full GROBID → GNorm2 → tmVar3 pipeline for one directory of PDFs."""
    for d in (grobid_out, gnorm2_out, tmvar_out):
        os.makedirs(d, exist_ok=True)

    log_group_header(log_path, label, pdf_dir)

    if args.start_step <= 1:
        grobid_cmd = [
            sys.executable, os.path.join(SCRIPTS_DIR, "pdf_to_bioc.py"),
            pdf_dir, grobid_out,
        ]
        if supplementary:
            grobid_cmd.append("--supplementary")
        t0 = time.time()
        run(f"GROBID  [{label}]", grobid_cmd)
        log_step_stats(log_path, tsv_path, base_dir, "GROBID", label, grobid_out,
                       elapsed=time.time() - t0)
        enforce_max_chars(grobid_out, args.max_chars, log_path, "GROBID", label)

    xmx = args.memory
    xms = half_memory(args.memory)

    if args.start_step <= 2:
        gnorm2_cmd = [
            sys.executable, os.path.join(SCRIPTS_DIR, "run_gnorm2.py"),
            grobid_out, gnorm2_out,
            "--xmx", xmx, "--xms", xms,
        ]
        if args.gnorm2_python:
            gnorm2_cmd += ["--ml-python", args.gnorm2_python]
        t0 = time.time()
        run(f"GNorm2  [{label}]", gnorm2_cmd)
        log_step_stats(log_path, tsv_path, base_dir, "GNorm2", label, gnorm2_out,
                       elapsed=time.time() - t0)
        enforce_max_chars(gnorm2_out, args.max_chars, log_path, "GNorm2", label)

    t0 = time.time()
    run(f"tmVar3  [{label}]", [
        sys.executable, os.path.join(SCRIPTS_DIR, "run_tmvar.py"),
        gnorm2_out, tmvar_out,
        "--xmx", xmx, "--xms", xms,
    ])
    log_step_stats(log_path, tsv_path, base_dir, "tmVar3", label, tmvar_out,
                   elapsed=time.time() - t0)


def process_input(top_dir, args):
    source_dir  = os.path.join(top_dir, "01_source")
    grobid_root = os.path.join(top_dir, "02_grobid")
    gnorm2_root = os.path.join(top_dir, "03_gnorm2")
    tmvar_root  = os.path.join(top_dir, "04_tmvar3")
    log_path      = os.path.join(top_dir, "pipeline_stats.log")
    tsv_path      = os.path.join(top_dir, "pipeline_stats.tsv")
    manifest_path = os.path.join(top_dir, "MANIFEST.txt")

    # Clean top-level output dirs (covers supplementary subdirs too)
    if args.clean:
        for step, d in enumerate([grobid_root, gnorm2_root, tmvar_root], start=1):
            if step >= args.start_step and os.path.exists(d):
                print(red(f"Cleaning {d} ..."), file=sys.stderr)
                shutil.rmtree(d)
        for f in (log_path, tsv_path, manifest_path):
            if os.path.exists(f):
                print(red(f"Cleaning {f} ..."), file=sys.stderr)
                os.remove(f)

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
        f.write(f"# Start step: {args.start_step}\n")
        max_chars_str = f"{args.max_chars:,}" if args.max_chars else "unlimited"
        f.write(f"# Max chars:  {max_chars_str}\n")
        f.write(f"# Clear intermediates: {args.clear_intermediates}\n")
        gnorm2_py_str = args.gnorm2_python if args.gnorm2_python else f"{sys.executable} (default)"
        f.write(f"# GNorm2 Python: {gnorm2_py_str}\n")
        f.write(f"{'#'*70}\n")

    # Prepare supplementary PDFs if 01_source/s/ exists
    s_dir = os.path.join(source_dir, "s")
    if os.path.isdir(s_dir):
        supp_cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "prepare_supplementary.py"),
                    source_dir]
        if args.no_libreoffice:
            supp_cmd.append("--no-libreoffice")
        run("Supplementary prep", supp_cmd)

    # Write manifest of source files and tool version
    write_manifest(manifest_path, top_dir, source_dir,
                   read_release_version(), run_timestamp)

    # Main publications
    process_group(
        label      = "main",
        pdf_dir    = source_dir,
        grobid_out = grobid_root,
        gnorm2_out = gnorm2_root,
        tmvar_out  = tmvar_root,
        args       = args,
        log_path   = log_path,
        tsv_path   = tsv_path,
        base_dir   = top_dir,
    )

    # Supplementary leaf directories
    for abs_path, rel in find_supplement_leaf_dirs(source_dir):
        process_group(
            label        = rel,
            pdf_dir      = abs_path,
            grobid_out   = os.path.join(grobid_root, rel),
            gnorm2_out   = os.path.join(gnorm2_root, rel),
            tmvar_out    = os.path.join(tmvar_root,  rel),
            args         = args,
            log_path     = log_path,
            tsv_path     = tsv_path,
            base_dir     = top_dir,
            supplementary= True,
        )

    # Clear intermediate files and dirs
    if args.clear_intermediates:
        print(red("Clearing intermediates ..."), file=sys.stderr)
        clear_intermediates(source_dir, top_dir, log_path)

    # Write run footer
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n# Pipeline run finished: {timestamp}\n")
        f.write(f"# Log:      {log_path}\n")
        f.write(f"# TSV:      {tsv_path}\n")
        f.write(f"# Manifest: {manifest_path}\n")

    print(red(f"\nDone: {top_dir}  →  {tmvar_root}"), file=sys.stderr)
    print(red(f"Stats log: {log_path}"), file=sys.stderr)
    print(red(f"Stats TSV: {tsv_path}"), file=sys.stderr)
    print(red(f"Manifest:  {manifest_path}"), file=sys.stderr)


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
    parser.add_argument("--start-step", type=int, default=1, choices=[1, 2, 3],
                        metavar="{1,2,3}",
                        help="Start from this step (1=GROBID, 2=GNorm2, 3=tmVar3; default: 1)")
    parser.add_argument("--no-libreoffice", action="store_true",
                        help="Use reportlab/python-docx fallback instead of LibreOffice")
    parser.add_argument("--max-chars", type=int, default=1_000_000, metavar="N",
                        help="Skip any document whose output XML exceeds N characters "
                             "at any step; remaining steps are skipped for that document "
                             "(default: 1000000; use 0 for no limit)")
    parser.add_argument("--memory", default="32G", metavar="SIZE",
                        help="Java max heap for GNorm2 and tmVar3 (default: 32G); "
                             "initial heap is set to half this value")
    parser.add_argument("--gnorm2-python", default=None, metavar="PATH_OR_ENV",
                        help="Python interpreter for the GNorm2 ML step. "
                             "Accepts a full path to a Python executable or a "
                             "bare conda env name. Use the env created by "
                             "scripts/setup_gnorm2_conda.sh to enable Metal GPU "
                             "acceleration on Apple Silicon. Defaults to the "
                             "current interpreter. "
                             "Examples: "
                             "--gnorm2-python gnorm2-tf215  (conda env name) or "
                             "--gnorm2-python /opt/homebrew/Caskroom/miniforge"
                             "/base/envs/gnorm2-tf215/bin/python3  (full path)")
    args = parser.parse_args()

    # Validate all inputs before starting any work
    validated = []
    for raw in args.input_dirs:
        top_dir    = os.path.abspath(raw)
        source_dir = os.path.join(top_dir, "01_source")
        if not os.path.isdir(top_dir):
            print(f"ERROR: Directory not found: {top_dir}", file=sys.stderr)
            sys.exit(1)
        if not os.path.isdir(source_dir):
            print(
                f"ERROR: {top_dir} must contain a subdirectory named '01_source'.\n"
                f"  Place source PDF(s) in:          {source_dir}/\n"
                f"  Supplementary files (optional):  {source_dir}/s/",
                file=sys.stderr,
            )
            sys.exit(1)
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
        print(red(f"\n{'#'*60}"), file=sys.stderr)
        print(red(f"Processing: {top_dir}"), file=sys.stderr)
        print(red(f"{'#'*60}"), file=sys.stderr)
        process_input(top_dir, args)


if __name__ == "__main__":
    main()
