#!/usr/bin/env python3
import argparse, os, shutil, subprocess, sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))

def run(step, cmd):
    print(f"\n{'='*60}")
    print(f"Step {step}: {' '.join(cmd)}")
    print('='*60)
    result = subprocess.run(cmd)
    if result.returncode != 0:
        sys.exit(result.returncode)

def main():
    parser = argparse.ArgumentParser(
        description="Run the full PDF → BioC → GNorm2 → tmVar3 pipeline."
    )
    parser.add_argument("input",  help="Folder containing input PDF files")
    parser.add_argument("output", help="Base output directory")
    parser.add_argument("--clean", action="store_true",
                        help="Delete and recreate the three output directories before running")
    parser.add_argument("--start-step", type=int, default=1, choices=[1, 2, 3],
                        metavar="{1,2,3}",
                        help="Start from this step (1=GROBID, 2=GNorm2, 3=tmVar3; default: 1)")
    parser.add_argument("--xmx-gnorm2", default="32G", metavar="SIZE",
                        help="Java max heap for GNorm2 (default: 32G)")
    parser.add_argument("--xms-gnorm2", default="16G", metavar="SIZE",
                        help="Java initial heap for GNorm2 (default: 16G)")
    parser.add_argument("--xmx-tmvar", default="5G", metavar="SIZE",
                        help="Java max heap for tmVar3 (default: 5G)")
    parser.add_argument("--xms-tmvar", default="5G", metavar="SIZE",
                        help="Java initial heap for tmVar3 (default: 5G)")
    args = parser.parse_args()

    input_dir = os.path.abspath(args.input)
    base_dir  = os.path.abspath(args.output)

    if not os.path.isdir(input_dir):
        sys.exit(f"ERROR: Input folder not found: {input_dir}")

    grobid_dir = os.path.join(base_dir, "02_publications_grobid")
    gnorm2_dir = os.path.join(base_dir, "03_publications_gnorm2")
    tmvar_dir  = os.path.join(base_dir, "04_publications_tmvar3")

    step_dirs = {1: grobid_dir, 2: gnorm2_dir, 3: tmvar_dir}

    if args.clean:
        for step, d in step_dirs.items():
            if step >= args.start_step and os.path.exists(d):
                print(f"Cleaning {d} ...")
                shutil.rmtree(d)

    for d in step_dirs.values():
        os.makedirs(d, exist_ok=True)

    if args.start_step <= 1:
        run("1/3 PDF → BioC", [
            sys.executable, os.path.join(SCRIPTS_DIR, "pdf_to_bioc.py"),
            input_dir, grobid_dir,
        ])

    if args.start_step <= 2:
        run("2/3 GNorm2", [
            sys.executable, os.path.join(SCRIPTS_DIR, "run_gnorm2.py"),
            grobid_dir, gnorm2_dir,
            "--xmx", args.xmx_gnorm2, "--xms", args.xms_gnorm2,
        ])

    run("3/3 tmVar3", [
        sys.executable, os.path.join(SCRIPTS_DIR, "run_tmvar.py"),
        gnorm2_dir, tmvar_dir,
        "--xmx", args.xmx_tmvar, "--xms", args.xms_tmvar,
    ])

    print(f"\nPipeline complete. Results in {tmvar_dir}")

if __name__ == "__main__":
    main()
