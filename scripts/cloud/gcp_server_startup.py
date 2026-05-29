#!/usr/bin/env python3
"""
GCP startup script for civic-pubtator VM.

Runs on every boot.  Uses sentinel files under /opt/.civic-pubtator/ to skip
steps that have already completed, so reboots are fast.

Directory layout on the VM:
  /opt/civic-pubtator/          repo clone
  /data/pub-data/               publication input/output data (sync from GCS)
  /data/tool-data/              model files (sync from GCS via sync_tool_data.sh)
  /opt/conda/                   Miniconda (pre-installed in DL VM image)
"""

import os
import sys

# ── constants ─────────────────────────────────────────────────────────────────

REPO_DIR     = '/opt/civic-pubtator'
DATA_DIR     = '/data'
PUB_DIR      = '/data/pub-data'
TOOL_DIR     = '/data/tool-data'
SENTINEL     = '/opt/.civic-pubtator'          # directory of per-step sentinels
MINICONDA_SH = '/tmp/miniconda.sh'
CONDA_PREFIX = '/opt/conda'                    # install target if not pre-installed
LOG          = '/var/log/civic-pubtator-setup.log'
GITHUB_REPO  = 'https://github.com/griffithlab/civic-pubtator.git'

# Candidate conda locations — DL VM images vary across releases.
_CONDA_CANDIDATES = [
    '/opt/conda/bin/conda',
    '/usr/local/conda/bin/conda',
    '/root/miniconda3/bin/conda',
    '/root/anaconda3/bin/conda',
]

def find_conda():
    for p in _CONDA_CANDIDATES:
        if os.path.isfile(p):
            return p
    return None

SYSTEM_PACKAGES = [
    'openjdk-17-jdk',       # GROBID
    'git',
    'curl',
    'wget',
    'screen',
    'zip',
    'unzip',
    'less',
    'vim',
    'python3-pip',
    'python3-dev',
    'python3-setuptools',
]


# ── helpers ───────────────────────────────────────────────────────────────────

def run(cmd, check=True):
    code = os.system(cmd)
    if check and code != 0:
        log(f'ERROR: command failed (exit {code}): {cmd}')
        sys.exit(code)
    return code


def log(msg):
    print(msg, flush=True)
    os.system(f'echo "{msg}" >> {LOG}')


def sentinel_path(step_name):
    return os.path.join(SENTINEL, step_name)


def is_done(step_name):
    return os.path.exists(sentinel_path(step_name))


def mark_done(step_name):
    open(sentinel_path(step_name), 'w').close()


def step(name):
    """Decorator: skip if sentinel exists, mark done on success."""
    def decorator(fn):
        def wrapper(*args, **kwargs):
            if is_done(name):
                log(f'[skip]  {name}')
                return
            log(f'[start] {name}')
            fn(*args, **kwargs)
            mark_done(name)
            log(f'[done]  {name}')
        return wrapper
    return decorator


# ── setup steps ───────────────────────────────────────────────────────────────

@step('create_directories')
def create_directories():
    for d in [SENTINEL, DATA_DIR, PUB_DIR, TOOL_DIR,
              f'{TOOL_DIR}/GNorm2', f'{TOOL_DIR}/AIONER',
              f'{TOOL_DIR}/tmvar', f'{TOOL_DIR}/NLMChem']:
        os.makedirs(d, exist_ok=True)
    run(f'chmod -R 777 {DATA_DIR}')


@step('install_packages')
def install_packages():
    run('apt-get update -qq')
    run('apt-get install -y ' + ' '.join(SYSTEM_PACKAGES))


@step('install_conda')
def install_conda():
    if find_conda():
        log(f'  conda already present: {find_conda()}')
        return
    log('  conda not found — installing Miniconda3')
    run(f'wget -q -O {MINICONDA_SH} '
        'https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh')
    run(f'bash {MINICONDA_SH} -b -p {CONDA_PREFIX}')
    run(f'rm -f {MINICONDA_SH}')
    # Make conda available in PATH for subsequent shell invocations
    run(f'{CONDA_PREFIX}/bin/conda init bash')


@step('accept_conda_tos')
def accept_conda_tos():
    """
    Anaconda requires explicit ToS acceptance for their default channels before
    any non-interactive conda create/install can proceed.  Accept once here so
    all subsequent env creation steps succeed unattended.
    """
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    for channel in [
        'https://repo.anaconda.com/pkgs/main',
        'https://repo.anaconda.com/pkgs/r',
    ]:
        run(f'{conda} tos accept --override-channels --channel {channel}', check=False)


@step('clone_repo')
def clone_repo():
    if os.path.isdir(os.path.join(REPO_DIR, '.git')):
        log('  repo already cloned, pulling latest')
        run(f'git -C {REPO_DIR} pull --ff-only')
    else:
        run(f'git clone {GITHUB_REPO} {REPO_DIR}')
    run(f'chmod -R 755 {REPO_DIR}/scripts')


@step('install_grobid')
def install_grobid():
    """Download and build GROBID under the repo's expected location."""
    grobid_dir = f'{REPO_DIR}/grobid'
    if os.path.isdir(grobid_dir):
        log('  GROBID directory already exists, skipping')
        return
    grobid_ver = '0.8.1'
    archive = f'/tmp/grobid-{grobid_ver}.zip'
    run(f'wget -q -O {archive} '
        f'https://github.com/kermitt2/grobid/archive/refs/tags/{grobid_ver}.zip')
    run(f'unzip -q {archive} -d /tmp/')
    run(f'mv /tmp/grobid-{grobid_ver} {grobid_dir}')
    run(f'chmod +x {grobid_dir}/gradlew')
    run(f'cd {grobid_dir} && ./gradlew clean install -x test --no-daemon -q')


@step('symlink_tool_dirs')
def symlink_tool_dirs():
    """
    Symlink large tool-data directories from /data/tool-data/ into the repo so
    pipeline scripts find them at their expected relative paths.  After running
    sync_tool_data.sh down, GCS data lands in /data/tool-data/ and these
    symlinks expose it inside the repo clone.
    """
    links = {
        f'{REPO_DIR}/GNorm2':   f'{TOOL_DIR}/GNorm2',
        f'{REPO_DIR}/AIONER':   f'{TOOL_DIR}/AIONER',
        f'{REPO_DIR}/tmvar':    f'{TOOL_DIR}/tmvar',
        f'{REPO_DIR}/NLMChem':  f'{TOOL_DIR}/NLMChem',
    }
    for link_path, target in links.items():
        if os.path.islink(link_path):
            log(f'  symlink exists: {link_path}')
        elif os.path.isdir(link_path):
            log(f'  real directory exists (not replacing): {link_path}')
        else:
            os.makedirs(target, exist_ok=True)
            os.symlink(target, link_path)
            log(f'  linked: {link_path} -> {target}')


@step('setup_conda_gnorm2')
def setup_conda_gnorm2():
    """GNorm2 env: Python 3.11, TF 2.15 with CUDA GPU support (no tensorflow-metal)."""
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    env = 'gnorm2-tf215'
    req = f'{REPO_DIR}/scripts/requirements_gnorm2_linux.txt'
    if not os.path.exists(req):
        log(f'ERROR: {req} not found — cannot set up GNorm2 environment')
        return
    if run(f'{conda} env list | grep -q "^{env} "', check=False) == 0:
        log(f'  env {env} already exists, skipping')
        return
    run(f'{conda} create -y -n {env} python=3.11')
    run(f'{conda} run -n {env} pip install --upgrade pip --root-user-action=ignore')
    run(f'{conda} run -n {env} pip install -r {req} --root-user-action=ignore')


@step('setup_conda_aioner')
def setup_conda_aioner():
    """AIONER env: Python 3.8, TF 2.3.0 via conda-forge.

    TF 2.3.0 was dropped from PyPI so it is installed from conda-forge.
    Python 3.8 is the newest TF 2.3.0 supports; 3.7 hits cython>=3.1
    build-dep failures because its manylinux1 wheels aren't recognised
    by modern pip.
    pip<23.1 is pinned at creation: pip 23.1+ uses @dataclass(slots=True)
    which requires Python 3.10+.
    """
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    env = 'aioner-tf23'
    req = f'{REPO_DIR}/scripts/requirements_aioner_linux.txt'
    if not os.path.exists(req):
        log(f'ERROR: {req} not found — cannot set up AIONER environment')
        return
    if run(f'{conda} env list | grep -q "^{env} "', check=False) == 0:
        log(f'  env {env} already exists, skipping')
        return
    run(f'{conda} create -y -n {env} python=3.8 "pip<23.1"')
    # TF 2.3.0 dropped from PyPI — install from conda-forge; addons still on PyPI
    run(f'{conda} install -y -n {env} -c conda-forge tensorflow=2.3.0')
    run(f'{conda} run -n {env} pip install --upgrade "pip<23.1" --root-user-action=ignore')
    run(f'{conda} run -n {env} pip install -r {req} --root-user-action=ignore')
    run(f'{conda} run -n {env} python -m spacy download en_core_web_sm')


@step('setup_conda_nlmchem')
def setup_conda_nlmchem():
    """NLMChem normalizer env: Python 3.9."""
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    env = 'nlmchem-py39'
    req = f'{REPO_DIR}/NLMChem/NLMChemTaggerNormalizer/requirements.txt'
    if not os.path.exists(req):
        log('  NLMChem not yet synced from GCS — run sync_tool_data.sh down first')
        return
    if run(f'{conda} env list | grep -q "^{env} "', check=False) == 0:
        log(f'  env {env} already exists, skipping')
        return
    run(f'{conda} create -y -n {env} python=3.9')
    run(f'{conda} run -n {env} pip install --upgrade pip --root-user-action=ignore')
    run(f'{conda} run -n {env} pip install -r {req} --root-user-action=ignore')


@step('add_aliases')
def add_aliases():
    aliases = [
        "alias ll='ls -lh'",
        f"alias cdrepo='cd {REPO_DIR}'",
        f"alias cdpub='cd {PUB_DIR}'",
        f"alias cdtools='cd {TOOL_DIR}'",
    ]
    with open('/root/.bash_aliases', 'a') as f:
        f.write('\n'.join(aliases) + '\n')


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    log('=== civic-pubtator startup ===')
    os.makedirs(SENTINEL, exist_ok=True)

    create_directories()
    install_packages()
    install_conda()
    accept_conda_tos()
    clone_repo()
    install_grobid()
    symlink_tool_dirs()
    setup_conda_gnorm2()
    setup_conda_aioner()
    setup_conda_nlmchem()
    add_aliases()

    log('=== startup complete ===')
    log('Next steps:')
    log('  1. Activate conda in your shell (once per login):')
    log('       source ~/.bashrc')
    log('  2. Sync model files from GCS:')
    log(f'       bash {REPO_DIR}/scripts/cloud/sync_tool_data.sh down')
    log('  3. Sync publication data from GCS:')
    log(f'       bash {REPO_DIR}/scripts/cloud/sync_pub_data.sh down')
    log('  4. Available conda environments:')
    log('       conda activate gnorm2-tf215')
    log('       conda activate aioner-tf23')
    log('       conda activate nlmchem-py39')


if __name__ == '__main__':
    main()
