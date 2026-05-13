#!/usr/bin/env python3
import argparse, datetime, os, shutil, subprocess, sys

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


def log_step_stats(log_path, tsv_path, base_dir, step_name, label, output_dir):
    """Append character/word stats to the log and TSV for all output files."""
    files = collect_output_files(output_dir)

    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # --- human-readable log ---
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n  >> {step_name}  {timestamp}\n")
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
    step_num  = {"GROBID": 1, "GNorm2": 2, "tmVar3": 3}.get(step_name, step_name)
    input_name = os.path.basename(label) if label != "main" else "main"
    with open(tsv_path, "a", encoding="utf-8") as f:
        for rel, chars, words in files:
            file_stem = os.path.splitext(os.path.basename(rel))[0]
            out_rel   = os.path.relpath(os.path.join(output_dir, rel), base_dir)
            f.write(f"{step_num}\t{step_name}\t{label}\t{file_stem}\t{out_rel}\t{chars}\t{words}\n")


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
        run(f"GROBID  [{label}]", grobid_cmd)
        log_step_stats(log_path, tsv_path, base_dir, "GROBID", label, grobid_out)
        enforce_max_chars(grobid_out, args.max_chars, log_path, "GROBID", label)

    xmx = args.memory
    xms = half_memory(args.memory)

    if args.start_step <= 2:
        run(f"GNorm2  [{label}]", [
            sys.executable, os.path.join(SCRIPTS_DIR, "run_gnorm2.py"),
            grobid_out, gnorm2_out,
            "--xmx", xmx, "--xms", xms,
        ])
        log_step_stats(log_path, tsv_path, base_dir, "GNorm2", label, gnorm2_out)
        enforce_max_chars(gnorm2_out, args.max_chars, log_path, "GNorm2", label)

    run(f"tmVar3  [{label}]", [
        sys.executable, os.path.join(SCRIPTS_DIR, "run_tmvar.py"),
        gnorm2_out, tmvar_out,
        "--xmx", xmx, "--xms", xms,
    ])
    log_step_stats(log_path, tsv_path, base_dir, "tmVar3", label, tmvar_out)


def process_input(input_dir, args):
    base_dir = os.path.dirname(input_dir)

    grobid_root = os.path.join(base_dir, "02_publications_grobid")
    gnorm2_root = os.path.join(base_dir, "03_publications_gnorm2")
    tmvar_root  = os.path.join(base_dir, "04_publications_tmvar3")
    log_path    = os.path.join(base_dir, "pipeline_stats.log")
    tsv_path    = os.path.join(base_dir, "pipeline_stats.tsv")

    # Clean top-level output dirs (covers supplementary subdirs too)
    if args.clean:
        for step, d in enumerate([grobid_root, gnorm2_root, tmvar_root], start=1):
            if step >= args.start_step and os.path.exists(d):
                print(red(f"Cleaning {d} ..."), file=sys.stderr)
                shutil.rmtree(d)
        for f in (log_path, tsv_path):
            if os.path.exists(f):
                print(red(f"Cleaning {f} ..."), file=sys.stderr)
                os.remove(f)

    # Write TSV header if file is new or empty
    if not os.path.exists(tsv_path) or os.path.getsize(tsv_path) == 0:
        with open(tsv_path, "w", encoding="utf-8") as f:
            f.write("step\tstep_name\tlabel\tinput_name\toutput_file\tchars\twords\n")

    # Write run header to log
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n{'#'*70}\n")
        f.write(f"# Pipeline run started: {timestamp}\n")
        f.write(f"# Input:      {input_dir}\n")
        f.write(f"# Start step: {args.start_step}\n")
        max_chars_str = f"{args.max_chars:,}" if args.max_chars else "unlimited"
        f.write(f"# Max chars:  {max_chars_str}\n")
        f.write(f"{'#'*70}\n")

    # Prepare supplementary PDFs if s/ exists
    s_dir = os.path.join(input_dir, "s")
    if os.path.isdir(s_dir):
        supp_cmd = [sys.executable, os.path.join(SCRIPTS_DIR, "prepare_supplementary.py"),
                    input_dir]
        if args.no_libreoffice:
            supp_cmd.append("--no-libreoffice")
        run("Supplementary prep", supp_cmd)

    # Main publications
    process_group(
        label      = "main",
        pdf_dir    = input_dir,
        grobid_out = grobid_root,
        gnorm2_out = gnorm2_root,
        tmvar_out  = tmvar_root,
        args       = args,
        log_path   = log_path,
        tsv_path   = tsv_path,
        base_dir   = base_dir,
    )

    # Supplementary leaf directories
    for abs_path, rel in find_supplement_leaf_dirs(input_dir):
        process_group(
            label        = rel,
            pdf_dir      = abs_path,
            grobid_out   = os.path.join(grobid_root, rel),
            gnorm2_out   = os.path.join(gnorm2_root, rel),
            tmvar_out    = os.path.join(tmvar_root,  rel),
            args         = args,
            log_path     = log_path,
            tsv_path     = tsv_path,
            base_dir     = base_dir,
            supplementary= True,
        )

    # Write run footer
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    with open(log_path, "a", encoding="utf-8") as f:
        f.write(f"\n# Pipeline run finished: {timestamp}\n")
        f.write(f"# Log: {log_path}\n")
        f.write(f"# TSV: {tsv_path}\n")

    print(red(f"\nDone: {input_dir}  →  {tmvar_root}"), file=sys.stderr)
    print(red(f"Stats log: {log_path}"), file=sys.stderr)
    print(red(f"Stats TSV: {tsv_path}"), file=sys.stderr)


def main():
    parser = argparse.ArgumentParser(
        description="Run the full PDF → BioC → GNorm2 → tmVar3 pipeline, "
                    "including supplementary files. Output base is derived as "
                    "the parent directory of each input_dir."
    )
    parser.add_argument("input_dirs", nargs="+",
                        help="One or more source directories containing input PDF files")
    parser.add_argument("--clean", action="store_true",
                        help="Delete and recreate output directories before running")
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
    args = parser.parse_args()

    for raw in args.input_dirs:
        input_dir = os.path.abspath(raw)
        if not os.path.isdir(input_dir):
            print(f"ERROR: Input folder not found: {input_dir}", file=sys.stderr)
            sys.exit(1)
        print(red(f"\n{'#'*60}"), file=sys.stderr)
        print(red(f"Processing input: {input_dir}"), file=sys.stderr)
        print(red(f"{'#'*60}"), file=sys.stderr)
        process_input(input_dir, args)


if __name__ == "__main__":
    main()
