#!/usr/bin/env python3
"""Wrapper to run TaggerOne disease/chemical NER and normalization.

TaggerOne processes one BioC XML file per JVM invocation, loading the full
model (~20 GB) each time.  Keep that in mind for large batches.

Usage:
  python run_taggerone.py <input_dir> <output_dir> --model <model.bin>
"""
import argparse, glob, os, subprocess, sys

SCRIPTS_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_DIR      = os.path.dirname(os.path.dirname(SCRIPTS_DIR))
TAGGERONE_DIR = os.path.join(REPO_DIR, "tools", "TaggerOne")
LIBS_DIR      = os.path.join(TAGGERONE_DIR, "libs")
AB3P_DIR      = os.path.join(REPO_DIR, "tools", "Ab3P")


def build_classpath():
    jars = sorted(glob.glob(os.path.join(LIBS_DIR, "*.jar")))
    if not jars:
        sys.exit(f"ERROR: No JARs found in {LIBS_DIR}")
    return ":".join(jars)


def main():
    parser = argparse.ArgumentParser(
        description="Run TaggerOne disease/chemical NER and normalization on BioC XML files."
    )
    parser.add_argument("input_dir",  help="Directory of BioC XML input files")
    parser.add_argument("output_dir", help="Directory for annotated BioC XML output")
    parser.add_argument("--model",    required=True, metavar="PATH",
                        help="Trained TaggerOne model (.bin file, e.g. output/model_DISE.bin)")
    parser.add_argument("--format",   default="BioC", choices=["BioC", "Pubtator"],
                        help="Input/output file format (default: BioC)")
    parser.add_argument("--xmx",      default="24G", metavar="SIZE",
                        help="Java max heap size (default: 24G)")
    parser.add_argument("--xms",      default="24G", metavar="SIZE",
                        help="Java initial heap size (default: 24G)")
    parser.add_argument("--verbose",  action="store_true",
                        help="Set Java log level to debug (default: warn)")
    args = parser.parse_args()

    model      = os.path.abspath(args.model)
    input_dir  = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isfile(model):
        sys.exit(f"ERROR: Model file not found: {model}")
    if not os.path.isdir(input_dir):
        sys.exit(f"ERROR: Input directory not found: {input_dir}")

    ab3p_bin = os.path.join(AB3P_DIR, "identify_abbr")
    if not os.path.isfile(ab3p_bin):
        sys.exit(
            f"ERROR: Ab3P binary not found: {ab3p_bin}\n"
            f"       Build Ab3P with: cd {AB3P_DIR} && make"
        )
    os.chmod(ab3p_bin, os.stat(ab3p_bin).st_mode | 0o111)

    os.makedirs(output_dir, exist_ok=True)

    classpath = build_classpath()
    log_level = "debug" if args.verbose else "warn"
    java_props = [
        f"-Dorg.slf4j.simpleLogger.defaultLogLevel={log_level}",
        "-Dorg.slf4j.simpleLogger.showThreadName=false",
        "-Dorg.slf4j.simpleLogger.showLogName=false",
        "-Dorg.slf4j.simpleLogger.logFile=System.out",
    ]

    input_files = sorted(glob.glob(os.path.join(input_dir, "*.xml")))
    if not input_files:
        sys.exit(f"ERROR: No .xml files found in {input_dir}")

    temp_dir = os.path.join(output_dir, "tmp_abbr")
    os.makedirs(temp_dir, exist_ok=True)
    # Ab3P command is run inside AB3P_DIR; the relative ./identify_abbr resolves there.
    abbr_source = "|".join([
        "ncbi.taggerOne.abbreviation.Ab3PAbbreviationSource",
        "./identify_abbr",
        AB3P_DIR,
        temp_dir,
        "1000",
    ])

    for input_file in input_files:
        fname = os.path.basename(input_file)
        output_file = os.path.join(output_dir, fname)

        cmd = [
            "java", f"-Xmx{args.xmx}", f"-Xms{args.xms}",
            *java_props,
            "-cp", classpath,
            "ncbi.taggerOne.ProcessText",
            "--inputFilename",                  input_file,
            "--fileFormat",                     args.format,
            "--outputFilename",                 output_file,
            "--modelInputFilename",             model,
            "--useSentenceBreaker",             "true",
            "--abbreviationPostProcessingArgs", "1|1|false",
            "--consistencyPostProcessingArgs",  "10|1",
            "--abbreviationSource",             abbr_source,
        ]

        print(f"Processing: {fname}")
        print("Running:", " ".join(cmd))
        result = subprocess.run(cmd, cwd=TAGGERONE_DIR)
        if result.returncode != 0:
            sys.exit(result.returncode)


if __name__ == "__main__":
    main()
