#!/usr/bin/env python3
"""
backfill_figures.py — Fill in 02_grobid/figures/<stem>/ for publications that
were processed before figure-image cropping was added (see pdf_to_bioc.py /
save_figure_images).

For each publication directory this only re-runs the cheap GROBID call (with
teiCoordinates=figure) and crops figures out of the already-downloaded source
PDF; it does not touch 02_grobid/*.xml or any of 03_gnorm2 .. 07_taggerone /
the report, and does not re-run any of those steps. Safe to re-run: a
publication/PDF already backfilled (figures.json present) is skipped unless
--force is given.

civic_pubtator.py's default run deletes the *prepared* PDFs it converts
supplementary .docx/.xlsx/.pptx files into (01_source/s/<stem>/...), keeping
only the original office files. When a supplementary group was GROBID-processed
in the original run but its prepared PDF no longer exists, this script
re-invokes prepare_supplementary.py for that publication first (regenerating
all prepared PDFs under 01_source/s/ from the still-present originals) so the
figure crop has a PDF to work from. Pass --no-regenerate-supplementary to skip
this and only backfill groups whose PDF is already present.

Usage:
  python3 src/pipeline_steps/backfill_figures.py /data/pub-data
  python3 src/pipeline_steps/backfill_figures.py /data/pub-data/10088816 /data/pub-data/25971938
  python3 src/pipeline_steps/backfill_figures.py /data/pub-data --dry-run
"""
import argparse
import os
import subprocess
import sys

STEPS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR = os.path.dirname(os.path.dirname(STEPS_DIR))
sys.path.insert(0, STEPS_DIR)
sys.path.insert(0, REPO_DIR)

from pdf_to_bioc import check_grobid, extract_with_grobid, save_figure_images  # noqa: E402
from civic_pubtator import find_supplement_leaf_dirs, IGNORED_FILES  # noqa: E402

import json  # noqa: E402


def discover_pub_dirs(paths):
    """Each path is either a single publication dir (has 01_source directly)
    or a corpus root whose immediate children are publication dirs."""
    pub_dirs = []
    for raw in paths:
        top = os.path.abspath(raw)
        if not os.path.isdir(top):
            print(f"WARNING: not a directory, skipping: {top}", file=sys.stderr)
            continue
        if os.path.isdir(os.path.join(top, "01_source")):
            pub_dirs.append(top)
            continue
        children = sorted(
            os.path.join(top, name) for name in os.listdir(top)
            if os.path.isdir(os.path.join(top, name))
            and os.path.isdir(os.path.join(top, name, "01_source"))
        )
        if not children:
            print(f"WARNING: no publication dirs (with 01_source/) found under {top}",
                  file=sys.stderr)
        pub_dirs.extend(children)
    return pub_dirs


def expected_supplementary_groups(grobid_root):
    """rel paths (from grobid_root) of supplementary dirs that were GROBID-processed
    in the original run, found by walking 02_grobid/s for dirs containing a .xml."""
    expected = set()
    s_grobid = os.path.join(grobid_root, "s")
    if os.path.isdir(s_grobid):
        for dirpath, dirnames, filenames in os.walk(s_grobid):
            if any(f.lower().endswith(".xml") and not f.endswith(".extraction.json")
                   for f in filenames):
                expected.add(os.path.relpath(dirpath, grobid_root))
    return expected


def regenerate_supplementary_if_needed(pub_dir, args, stats):
    """Re-run prepare_supplementary.py so previously-cleared prepared PDFs
    (01_source/s/<stem>/...) exist again, if any expected group is missing one."""
    source_dir = os.path.join(pub_dir, "01_source")
    s_dir = os.path.join(source_dir, "s")
    if not os.path.isdir(s_dir):
        return

    grobid_root = os.path.join(pub_dir, "02_grobid")
    expected = expected_supplementary_groups(grobid_root)
    available = {rel for _, rel in find_supplement_leaf_dirs(source_dir)}
    if not (expected - available):
        return

    if args.dry_run:
        print(f"  WOULD REGENERATE supplementary PDFs in {s_dir} "
              f"({len(expected - available)} group(s) missing a PDF)")
        stats["pubs_would_regenerate"] += 1
        return

    cmd = [sys.executable, os.path.join(STEPS_DIR, "prepare_supplementary.py"), source_dir,
           "--max-rows", str(args.max_rows), "--max-tabs", str(args.max_tabs)]
    if args.no_libreoffice:
        cmd.append("--no-libreoffice")
    print(f"  Regenerating supplementary PDFs in {s_dir} ...")
    result = subprocess.run(cmd)
    if result.returncode != 0:
        print(f"  WARNING: prepare_supplementary.py exited {result.returncode} for {source_dir}",
              file=sys.stderr)
    stats["pubs_regenerated"] += 1


def iter_groups(pub_dir):
    """Yield (label, pdf_dir, grobid_out) for the main group and any
    supplementary leaf dirs, mirroring civic_pubtator.py's process_input()."""
    source_dir = os.path.join(pub_dir, "01_source")
    grobid_root = os.path.join(pub_dir, "02_grobid")
    yield "main", source_dir, grobid_root
    for abs_path, rel in find_supplement_leaf_dirs(source_dir):
        yield rel, abs_path, os.path.join(grobid_root, rel)


def backfill_group(pdf_dir, grobid_out, dpi, force, dry_run, stats):
    if not os.path.isdir(grobid_out):
        stats["groups_skipped_no_grobid"] += 1
        return

    pdf_names = sorted(
        f for f in os.listdir(pdf_dir)
        if f.lower().endswith(".pdf") and f not in IGNORED_FILES and not f.startswith("~$")
        and os.path.isfile(os.path.join(pdf_dir, f))
    )

    for fname in pdf_names:
        stem = os.path.splitext(fname)[0]
        pdf_path = os.path.join(pdf_dir, fname)
        bioc_path = os.path.join(grobid_out, stem + ".xml")
        if not os.path.isfile(bioc_path):
            print(f"  SKIP {pdf_path} (no existing {stem}.xml in {grobid_out}; "
                  f"GROBID never completed for this file)")
            stats["docs_skipped_no_bioc"] += 1
            continue

        fig_dir = os.path.join(grobid_out, "figures", stem)
        figures_json = os.path.join(fig_dir, "figures.json")
        if os.path.exists(figures_json) and not force:
            stats["docs_already_done"] += 1
            continue

        if dry_run:
            print(f"  WOULD BACKFILL {pdf_path} -> {fig_dir}")
            stats["docs_would_backfill"] += 1
            continue

        try:
            tei_xml = extract_with_grobid(pdf_path)
            n_imgs = save_figure_images(tei_xml, pdf_path, fig_dir, dpi=dpi)
            if not os.path.exists(figures_json):
                # No <figure> elements at all in the TEI — write a sentinel
                # so this file isn't re-fetched from GROBID on the next run.
                os.makedirs(fig_dir, exist_ok=True)
                with open(figures_json, "w", encoding="utf-8") as fh:
                    json.dump({"pdf": fname, "dpi": dpi, "figures": []}, fh, indent=2)
            print(f"  {pdf_path} -> {n_imgs} figure image(s) in {fig_dir}")
            stats["docs_backfilled"] += 1
            stats["images_written"] += n_imgs
        except Exception as e:
            print(f"  WARNING: figure backfill failed for {pdf_path}: {e}", file=sys.stderr)
            stats["docs_failed"] += 1


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_dirs", nargs="+",
                        help="One or more publication directories, or corpus root "
                             "directories whose immediate children are publication dirs")
    parser.add_argument("--figure-dpi", type=int, default=200, metavar="DPI",
                        help="Resolution of cropped figure PNGs (default: 200)")
    parser.add_argument("--force", action="store_true",
                        help="Re-crop even if figures.json already exists for a document")
    parser.add_argument("--dry-run", action="store_true",
                        help="List what would be backfilled without calling GROBID or "
                             "writing any files")
    parser.add_argument("--no-regenerate-supplementary", dest="regenerate_supplementary",
                        action="store_false",
                        help="Do not regenerate missing prepared supplementary PDFs; "
                             "just skip supplementary groups whose PDF is gone")
    parser.set_defaults(regenerate_supplementary=True)
    parser.add_argument("--max-rows", type=int, default=1000, metavar="N",
                        help="Passed through to prepare_supplementary.py (default: 1000)")
    parser.add_argument("--max-tabs", type=int, default=15, metavar="N",
                        help="Passed through to prepare_supplementary.py (default: 15)")
    parser.add_argument("--no-libreoffice", action="store_true",
                        help="Passed through to prepare_supplementary.py")
    args = parser.parse_args()

    if not args.dry_run:
        check_grobid()

    pub_dirs = discover_pub_dirs(args.input_dirs)
    if not pub_dirs:
        sys.exit("ERROR: no publication directories found")
    print(f"Found {len(pub_dirs)} publication director{'y' if len(pub_dirs) == 1 else 'ies'}")

    stats = {
        "groups_skipped_no_grobid": 0,
        "docs_skipped_no_bioc": 0,
        "docs_already_done": 0,
        "docs_would_backfill": 0,
        "docs_backfilled": 0,
        "docs_failed": 0,
        "images_written": 0,
        "pubs_regenerated": 0,
        "pubs_would_regenerate": 0,
    }

    for i, pub_dir in enumerate(pub_dirs, 1):
        pubid = os.path.basename(pub_dir)
        print(f"[{i}/{len(pub_dirs)}] {pubid}")
        if args.regenerate_supplementary:
            regenerate_supplementary_if_needed(pub_dir, args, stats)
        for label, pdf_dir, grobid_out in iter_groups(pub_dir):
            backfill_group(pdf_dir, grobid_out, args.figure_dpi, args.force, args.dry_run, stats)

    print()
    print("=" * 60)
    print(f"Publications scanned:        {len(pub_dirs)}")
    if args.dry_run:
        print(f"Pubs that would regenerate supplementary PDFs: {stats['pubs_would_regenerate']}")
        print(f"Docs that would be backfilled: {stats['docs_would_backfill']}")
    else:
        print(f"Pubs with supplementary PDFs regenerated: {stats['pubs_regenerated']}")
        print(f"Docs backfilled this run:    {stats['docs_backfilled']}")
        print(f"Figure images written:       {stats['images_written']}")
    print(f"Docs already backfilled:     {stats['docs_already_done']}")
    print(f"Docs failed:                  {stats['docs_failed']}")
    print(f"Docs skipped (no BioC yet):   {stats['docs_skipped_no_bioc']}")
    print(f"Groups skipped (no GROBID dir): {stats['groups_skipped_no_grobid']}")
    if stats["docs_failed"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
