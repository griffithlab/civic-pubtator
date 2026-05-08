#!/usr/bin/env python3
import argparse, os, subprocess, sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR    = os.path.dirname(SCRIPTS_DIR)
TMVAR_DIR   = os.path.join(REPO_DIR, "tmvar")
JAR         = os.path.join(TMVAR_DIR, "tmVar.jar")

def main():
    parser = argparse.ArgumentParser(
        description="Run tmVar3 variant extraction on a folder of BioC XML files."
    )
    parser.add_argument("input",  help="Folder containing BioC XML input files")
    parser.add_argument("output", help="Folder where output files will be written")
    parser.add_argument("--xmx",  default="5G", metavar="SIZE",
                        help="Java max heap size (default: 5G)")
    parser.add_argument("--xms",  default="5G", metavar="SIZE",
                        help="Java initial heap size (default: 5G)")
    parser.add_argument("--train", action="store_true",
                        help="Run in Train mode (default: Test)")
    parser.add_argument("--keep-tmp", action="store_true",
                        help="Keep temporary CRF files (default: deleted)")
    parser.add_argument("--rs-only", action="store_true",
                        help="Suppress CA# output, show RS# only")
    parser.add_argument("--hide-multiple", action="store_true",
                        help="Hide ambiguous/multiple mappings")
    args = parser.parse_args()

    if not os.path.isfile(JAR):
        sys.exit(f"ERROR: tmVar.jar not found at {JAR}")

    input_dir  = os.path.abspath(args.input)
    output_dir = os.path.abspath(args.output)

    if not os.path.isdir(input_dir):
        sys.exit(f"ERROR: Input folder not found: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    cmd = [
        "java", f"-Xmx{args.xmx}", f"-Xms{args.xms}",
        "-jar", JAR,
        input_dir,
        output_dir,
        "Train" if args.train else "Test",
        "false" if args.keep_tmp else "true",
        "true"  if args.rs_only else "false",
        "true"  if args.hide_multiple else "false",
    ]

    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=TMVAR_DIR)
    sys.exit(result.returncode)

if __name__ == "__main__":
    main()
