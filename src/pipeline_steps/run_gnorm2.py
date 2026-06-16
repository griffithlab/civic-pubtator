#!/usr/bin/env python3
import argparse, os, shutil, subprocess, sys

def _write_setup_with_tmp(src_path, tmp_folder, dst_path):
    """Write a copy of a GNorm2 setup file with tmpFolder overridden to tmp_folder."""
    with open(src_path, encoding='utf-8') as f:
        lines = f.readlines()
    with open(dst_path, 'w', encoding='utf-8') as f:
        for line in lines:
            stripped = line.lstrip()
            if stripped.startswith('tmpFolder'):
                indent = line[:len(line) - len(stripped)]
                f.write(f'{indent}tmpFolder = {tmp_folder}\n')
            else:
                f.write(line)

SCRIPTS_DIR = os.path.dirname(os.path.abspath(__file__))
REPO_DIR    = os.path.dirname(os.path.dirname(SCRIPTS_DIR))
GNORM2_DIR  = os.path.join(REPO_DIR, "tools", "GNorm2")
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


DEFAULT_ENV = "gnorm2-tf215"


def ml_cmd_prefix(ml_python):
    """Return the command prefix for the GNorm2 ML step.

    Accepts either a path to a Python executable or a bare conda env name.
    A bare name (no path separator) is run via 'conda run -n <name> python'
    so the full conda environment is activated.
    """
    if ml_python is not None and (os.sep in ml_python or ml_python.startswith("~")):
        return [os.path.expanduser(ml_python)]
    env_name = ml_python if ml_python is not None else DEFAULT_ENV
    # bare name — treat as conda env
    conda = find_conda()
    if not conda:
        sys.exit(
            f"ERROR: conda env '{env_name}' requested but conda was not found. "
            "Install Miniforge or pass a full Python path via --ml-python."
        )
    return [conda, "run", "--no-capture-output", "-n", env_name, "python"]


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

    # GNorm2's Java code has a hardcoded File("tmp").listFiles() relative to cwd —
    # that directory must exist or the call throws. Keep it, but redirect the actual
    # intermediate files (abbreviations, SimConcept data, etc.) into output_dir so
    # they're cleaned up with the rest of the run's working files.
    os.makedirs(os.path.join(GNORM2_DIR, "tmp"), exist_ok=True)
    gnorm2_tmp = os.path.join(output_dir, "tmp_gnorm2")
    os.makedirs(gnorm2_tmp, exist_ok=True)

    # Write per-run setup files with tmpFolder pointing to gnorm2_tmp.
    # The originals use a relative "tmp" path (= GNorm2/tmp/); the overridden
    # copies use an absolute path so intermediates land in output_dir instead.
    setup_sr = os.path.join(GNORM2_DIR, "setup.SR.run.txt")
    setup_gn = os.path.join(GNORM2_DIR, "setup.GN.run.txt")
    _write_setup_with_tmp(os.path.join(GNORM2_DIR, "setup.SR.txt"), gnorm2_tmp, setup_sr)
    _write_setup_with_tmp(os.path.join(GNORM2_DIR, "setup.GN.txt"), gnorm2_tmp, setup_gn)

    # GCS sync doesn't preserve POSIX permissions — ensure binaries are executable.
    # If the file is owned by root (startup script ran as root), os.chmod will raise
    # PermissionError; in that case verify the bit is already set (startup should have
    # done it) and raise a clear error if it is not.
    for binary in ("Ab3P", "identify_abbr", "CRF/crf_test", "CRF/crf_learn"):
        p = os.path.join(GNORM2_DIR, binary)
        if os.path.isfile(p):
            try:
                os.chmod(p, os.stat(p).st_mode | 0o111)
            except PermissionError:
                if not os.access(p, os.X_OK):
                    raise RuntimeError(
                        f'Binary not executable and cannot chmod (not owner): {p}\n'
                        f'Run: sudo chmod a+x {p}'
                    )

    # TF_USE_LEGACY_KERAS=1 is needed for TF >= 2.16 where tensorflow.keras was
    # restructured and must redirect to tf_keras. The gnorm2-tf215 conda env uses
    # TF 2.15 where Keras 2.x is the default, so the flag must NOT be set there.
    # Only set it when a full Python path is explicitly given (path separator present),
    # which indicates a system Python that may carry TF >= 2.16.
    env = {**os.environ, "PYTHONNOUSERSITE": "1"}
    if args.ml_python is not None and (os.sep in args.ml_python or args.ml_python.startswith("~")):
        env["TF_USE_LEGACY_KERAS"] = "1"

    java_cmd = ["java", f"-Xmx{args.xmx}", f"-Xms{args.xms}", "-jar", JAR]

    try:
        # Step 1: Species Recognition
        run(java_cmd + [input_dir, tmp_sr, "setup.SR.run.txt"], env)

        # Step 2: Species Assignment + Gene Name Recognition
        run([
            *ml_cmd_prefix(args.ml_python), PYTHON_SCRIPT,
            "-i", tmp_sr, "-r", tmp_gnr, "-a", tmp_sa,
            "-n", "gnorm_trained_models/GeneNER/GeneNER-Bioformer-BEST.h5",
            "-s", "gnorm_trained_models/SpeAss/SpeAss-Bioformer-SG-BEST.h5",
        ], env)

        # Step 3: Gene Normalization
        run(java_cmd + [tmp_sa, output_dir, "setup.GN.run.txt"], env)

    finally:
        for p in (setup_sr, setup_gn):
            try:
                os.remove(p)
            except OSError:
                pass

if __name__ == "__main__":
    main()
