#!/usr/bin/env python3
import argparse, os, shutil, subprocess, sys

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR    = os.path.dirname(SCRIPTS_DIR)
GNORM2_DIR  = os.path.join(REPO_DIR, "GNorm2")
JAR         = os.path.join(GNORM2_DIR, "GNormPlus.jar")
PYTHON_SCRIPT = os.path.join(GNORM2_DIR, "GeneNER_SpeAss_run.py")

def find_conda():
    """Return the path to the conda executable, or None if not found."""
    for candidate in [
        shutil.which("conda"),
        "/opt/homebrew/Caskroom/miniforge/base/condabin/conda",
        os.path.expanduser("~/miniforge3/bin/conda"),
    ]:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def ml_cmd_prefix(ml_python):
    """Return the command prefix for the GNorm2 ML step.

    Accepts either a path to a Python executable or a bare conda env name.
    A bare name (no path separator) is run via 'conda run -n <name> python'
    so the full conda environment is activated.
    """
    if ml_python is None:
        return [sys.executable]
    if os.sep in ml_python or ml_python.startswith("~"):
        return [os.path.expanduser(ml_python)]
    # bare name — treat as conda env
    conda = find_conda()
    if not conda:
        sys.exit(
            f"ERROR: --ml-python '{ml_python}' looks like a conda env name but "
            "conda was not found. Install Miniforge or pass a full Python path."
        )
    return [conda, "run", "--no-capture-output", "-n", ml_python, "python"]


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
    parser.add_argument("--ml-python", default=None, metavar="PATH_OR_ENV",
                        help="Python interpreter for the GNorm2 ML step "
                             "(GeneNER_SpeAss_run.py). Accepts a full path to a "
                             "Python executable or a bare conda env name. "
                             "Defaults to the current interpreter. "
                             "Examples: "
                             "--ml-python gnorm2-tf215  (conda env name) or "
                             "--ml-python /opt/homebrew/Caskroom/miniforge/base"
                             "/envs/gnorm2-tf215/bin/python3  (full path)")
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

    # TF_USE_LEGACY_KERAS=1 is needed for TF >= 2.16 (system Python) where
    # tensorflow.keras was restructured and must be redirected to tf_keras.
    # When using a custom --ml-python (e.g. the conda env with TF 2.15),
    # Keras 2.x is already the default so the flag is not set — it would
    # break things by redirecting to tf_keras which isn't installed there.
    env = {**os.environ}
    if args.ml_python is None:
        env["TF_USE_LEGACY_KERAS"] = "1"

    java_cmd = ["java", f"-Xmx{args.xmx}", f"-Xms{args.xms}", "-jar", JAR]

    # Step 1: Species Recognition
    run(java_cmd + [input_dir, tmp_sr, "setup.SR.txt"], env)

    # Step 2: Species Assignment + Gene Name Recognition
    run([
        *ml_cmd_prefix(args.ml_python), PYTHON_SCRIPT,
        "-i", tmp_sr, "-r", tmp_gnr, "-a", tmp_sa,
        "-n", "gnorm_trained_models/GeneNER/GeneNER-Bioformer-BEST.h5",
        "-s", "gnorm_trained_models/SpeAss/SpeAss-Bioformer-SG-BEST.h5",
    ], env)

    # Step 3: Gene Normalization
    run(java_cmd + [tmp_sa, output_dir, "setup.GN.txt"], env)

if __name__ == "__main__":
    main()
