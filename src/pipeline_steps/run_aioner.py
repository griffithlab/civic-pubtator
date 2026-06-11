#!/usr/bin/env python3
import argparse, os, shutil, subprocess, sys

SCRIPTS_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_DIR      = os.path.dirname(os.path.dirname(SCRIPTS_DIR))
AIONER_DIR    = os.path.join(REPO_DIR, "AIONER")
AIONER_SCRIPT = os.path.join(AIONER_DIR, "AIONER_Run.py")

DEFAULT_MODEL = "AIONER_trained_models/AIONER/Bioformer-Softmax-BEST-AIO_tmvar3.20230416.h5"
DEFAULT_ENV   = "aioner-tf23-gpu"


def find_conda():
    for candidate in [
        shutil.which("conda"),
        "/opt/homebrew/Caskroom/miniforge/base/condabin/conda",
        os.path.expanduser("~/miniforge3/bin/conda"),
    ]:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def ml_cmd_prefix(aioner_python):
    """Return the command prefix for running the AIONER Python script.

    Accepts a full path to a Python executable or a bare conda env name.
    Defaults to the aioner-tf23 conda env.
    """
    if aioner_python is not None and (os.sep in aioner_python or aioner_python.startswith("~")):
        return [os.path.expanduser(aioner_python)]
    env_name = aioner_python if aioner_python is not None else DEFAULT_ENV
    conda = find_conda()
    if not conda:
        sys.exit(
            f"ERROR: conda env '{env_name}' requested but conda was not found. "
            "Install Miniforge or pass a full Python path via --aioner-python."
        )
    return [conda, "run", "--no-capture-output", "-n", env_name, "python"]


def run(cmd):
    print("Running:", " ".join(cmd))
    result = subprocess.run(cmd, cwd=AIONER_DIR)
    if result.returncode != 0:
        sys.exit(result.returncode)


def main():
    parser = argparse.ArgumentParser(
        description="Run AIONER NER on a folder of BioC XML or PubTator files."
    )
    parser.add_argument("input_dir",  help="Folder containing input files (BioC XML or PubTator)")
    parser.add_argument("output_dir", help="Folder where annotated output files will be written")
    parser.add_argument("--model", default=DEFAULT_MODEL, metavar="PATH",
                        help=f"AIONER model file, relative to AIONER/ dir "
                             f"(default: {DEFAULT_MODEL})")
    parser.add_argument("--entity", default="ALL", metavar="TYPE",
                        help="Entity type: Gene, Chemical, Disease, Mutation, "
                             "Species, CellLine, or ALL (default: ALL)")
    parser.add_argument("--threads", default="4", metavar="N",
                        help="Number of TensorFlow threads (default: 4)")
    parser.add_argument("--aioner-python", default=None, metavar="PATH_OR_ENV",
                        help=f"Python interpreter or conda env for AIONER. Accepts a full "
                             f"path to a Python executable or a bare conda env name. "
                             f"Defaults to the '{DEFAULT_ENV}' conda env (TF 2.6 + GPU). "
                             f"Use 'aioner-tf23' for the CPU-only fallback. "
                             f"Examples: --aioner-python aioner-tf23-gpu  (conda env name) or "
                             f"--aioner-python /path/to/python3  (full path)")
    args = parser.parse_args()

    if not os.path.isfile(AIONER_SCRIPT):
        sys.exit(f"ERROR: AIONER_Run.py not found at {AIONER_SCRIPT}")

    input_dir  = os.path.abspath(args.input_dir)
    output_dir = os.path.abspath(args.output_dir)

    if not os.path.isdir(input_dir):
        sys.exit(f"ERROR: Input folder not found: {input_dir}")

    os.makedirs(output_dir, exist_ok=True)

    # AIONER_Run.py builds paths via string concatenation (inpath+infile),
    # so both paths must have a trailing slash.
    if not input_dir.endswith("/"):
        input_dir += "/"
    if not output_dir.endswith("/"):
        output_dir += "/"

    cmd = [
        *ml_cmd_prefix(args.aioner_python),
        AIONER_SCRIPT,
        "--inpath",      input_dir,
        "--model",       args.model,
        "--entity",      args.entity,
        "--outpath",     output_dir,
        "--NUM_THREADS", args.threads,
    ]

    run(cmd)


if __name__ == "__main__":
    main()
