#!/usr/bin/env python3
import argparse, os, subprocess, sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR    = os.path.dirname(SCRIPTS_DIR)
GNORM2_DIR  = os.path.join(REPO_DIR, "GNorm2")
JAR         = os.path.join(GNORM2_DIR, "GNormPlus.jar")
PYTHON_SCRIPT = os.path.join(GNORM2_DIR, "GeneNER_SpeAss_run.py")

def run(cmd, env):
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=GNORM2_DIR, env=env)
    if result.returncode != 0:
        sys.exit(result.returncode)

def main():
    parser = argparse.ArgumentParser(
        description="Run GNorm2 gene recognition and normalization on a folder of BioC XML files."
    )
    parser.add_argument("input_dir",  help="Folder containing BioC XML input files")
    parser.add_argument("output_dir", help="Folder where output files will be written")
    parser.add_argument("--xmx", default="32G", metavar="SIZE",
                        help="Java max heap size (default: 32G)")
    parser.add_argument("--xms", default="16G", metavar="SIZE",
                        help="Java initial heap size (default: 16G)")
    args = parser.parse_args()

    if not os.path.isfile(JAR):
        sys.exit(f"ERROR: GNormPlus.jar not found at {JAR}")

    input_dir  = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isdir(input_dir):
        sys.exit(f"ERROR: Input folder not found: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    tmp_sr  = os.path.join(output_dir, "tmp_SR")
    tmp_gnr = os.path.join(output_dir, "tmp_GNR")
    tmp_sa  = os.path.join(output_dir, "tmp_SA")
    for d in (tmp_sr, tmp_gnr, tmp_sa):
        os.makedirs(d, exist_ok=True)

    env = {**os.environ, "TF_USE_LEGACY_KERAS": "1"}

    java_cmd = ["java", f"-Xmx{args.xmx}", f"-Xms{args.xms}", "-jar", JAR]

    # Step 1: Species Recognition
    run(java_cmd + [input_dir, tmp_sr, "setup.SR.txt"], env)

    # Step 2: Species Assignment + Gene Name Recognition
    run([
        sys.executable, PYTHON_SCRIPT,
        "-i", tmp_sr, "-r", tmp_gnr, "-a", tmp_sa,
        "-n", "gnorm_trained_models/GeneNER/GeneNER-Bioformer-BEST.h5",
        "-s", "gnorm_trained_models/SpeAss/SpeAss-Bioformer-SG-BEST.h5",
    ], env)

    # Step 3: Gene Normalization
    run(java_cmd + [tmp_sa, output_dir, "setup.GN.txt"], env)

if __name__ == "__main__":
    main()
