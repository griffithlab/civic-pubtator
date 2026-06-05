#!/usr/bin/env python3
"""Wrapper to run NLMChem chemical normalization in the nlmchem conda environment.

Usage:
  python run_nlmchem.py <input_dir> <abbr_dir> <output_dir> [--nlmchem-python ENV]

  input_dir  — directory of BioC XML files (AIONER output)
  abbr_dir   — directory of abbreviation TSV files (Ab3P output, one per document)
  output_dir — directory where NLMChem will write annotated BioC XML files

The normalizer config uses CWD-relative data paths, so the subprocess is always
started with cwd=CHEM_NORM_DIR regardless of where this script is called from.
"""
import argparse, os, shutil, subprocess, sys

SCRIPTS_DIR   = os.path.dirname(os.path.abspath(__file__))
REPO_DIR      = os.path.dirname(SCRIPTS_DIR)
CHEM_NORM_DIR = os.path.join(REPO_DIR, 'NLMChem', 'NLMChemTaggerNormalizer', 'CHEM_NORM')
NORMALIZE_PY  = os.path.join(CHEM_NORM_DIR, 'src', 'normalize.py')
CONFIG        = os.path.join(CHEM_NORM_DIR, 'config_CHEM_MESH_2023.json')
DEFAULT_ENV   = 'nlmchem-py39'


def find_conda():
    for candidate in [
        shutil.which('conda'),
        '/opt/homebrew/Caskroom/miniforge/base/condabin/conda',
        os.path.expanduser('~/miniforge3/bin/conda'),
    ]:
        if candidate and os.path.isfile(candidate):
            return candidate
    return None


def python_cmd_prefix(nlmchem_python):
    """Return command prefix for running normalize.py in the correct Python environment."""
    if nlmchem_python and (os.sep in nlmchem_python or nlmchem_python.startswith('~')):
        return [os.path.expanduser(nlmchem_python)]
    env_name = nlmchem_python or DEFAULT_ENV
    conda = find_conda()
    if not conda:
        sys.exit(
            f"ERROR: conda env '{env_name}' requested but conda was not found. "
            "Install Miniconda/Miniforge or pass a full Python path via --nlmchem-python."
        )
    return [conda, 'run', '--no-capture-output', '-n', env_name, 'python']


def main():
    parser = argparse.ArgumentParser(description='Run NLMChem chemical normalization.')
    parser.add_argument('input_dir',  help='Directory of BioC XML input files (AIONER output)')
    parser.add_argument('abbr_dir',   help='Directory of abbreviation TSV files (Ab3P output)')
    parser.add_argument('output_dir', help='Directory for NLMChem-annotated BioC XML output')
    parser.add_argument('--nlmchem-python', default=None, metavar='PATH_OR_ENV',
                        help=f"Python interpreter or conda env name for NLMChem. "
                             f"Accepts a full path to a Python executable or a bare conda env "
                             f"name. Defaults to the '{DEFAULT_ENV}' conda env. "
                             f"Examples: --nlmchem-python nlmchem-py39  (conda env name) or "
                             f"--nlmchem-python /opt/conda/envs/nlmchem-py39/bin/python3")
    args = parser.parse_args()

    input_dir  = os.path.abspath(args.input_dir)
    abbr_dir   = os.path.abspath(args.abbr_dir)
    output_dir = os.path.abspath(args.output_dir)
    os.makedirs(output_dir, exist_ok=True)

    if not os.path.isfile(NORMALIZE_PY):
        sys.exit(f"ERROR: normalize.py not found at {NORMALIZE_PY}")

    cmd = python_cmd_prefix(args.nlmchem_python) + [
        '-u', NORMALIZE_PY,
        CONFIG, 'biocxml',
        abbr_dir, input_dir, output_dir,
    ]
    print('Running:', ' '.join(cmd))
    result = subprocess.run(cmd, cwd=CHEM_NORM_DIR)
    sys.exit(result.returncode)


if __name__ == '__main__':
    main()
