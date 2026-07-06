#!/usr/bin/env python3
"""
GCP startup script for civic-pubtator VM.

Runs on every boot.  Uses sentinel files under /opt/.civic-pubtator/ to skip
steps that have already completed, so reboots are fast.

Directory layout on the VM:
  /opt/civic-pubtator/          repo clone; tool dirs live here directly
  /data/pub-data/               publication input/output data (sync from GCS)
  /opt/conda/                   Miniconda (pre-installed in DL VM image)

Tool model files (large, gitignored) are synced from GCS into each tool's
directory inside the repo: /opt/civic-pubtator/tools/{GNorm2,AIONER,tmvar,NLMChem}/
"""

import os
import sys

# ── constants ─────────────────────────────────────────────────────────────────

REPO_DIR     = '/opt/civic-pubtator'
TOOL_DIR     = '/opt/civic-pubtator/tools'
GCS_CONDA_ENVS = 'gs://civic-pubtator-tool-data/conda-envs'
DATA_DIR     = '/data'
PUB_DIR      = '/data/pub-data'
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

def restore_conda_env(conda, env_name):
    """Try to restore a conda env from a GCS conda-pack tarball.

    Downloads gs://…/conda-envs/{env_name}.tar.gz, extracts it into the conda
    envs directory, and runs conda-unpack to fix any hardcoded paths.

    Returns True if the env is now ready (restored or already existed),
    False if the GCS tarball was not found so the caller should fall back to
    a live conda/pip install.
    """
    conda_base = os.path.dirname(os.path.dirname(conda))
    env_dir = os.path.join(conda_base, 'envs', env_name)
    if os.path.isdir(env_dir):
        log(f'  env {env_name} already present at {env_dir}')
        return True

    gcs_url = f'{GCS_CONDA_ENVS}/{env_name}.tar.gz'
    tmp_tar = f'/tmp/{env_name}.tar.gz'

    log(f'  trying GCS restore: {gcs_url}')
    if run(f'gcloud storage cp {gcs_url} {tmp_tar}', check=False) != 0:
        log(f'  GCS tarball not found — falling back to live install')
        run(f'rm -f {tmp_tar}', check=False)
        return False

    log(f'  unpacking {env_name} into {env_dir} ...')
    os.makedirs(env_dir, exist_ok=True)
    run(f'tar -xzf {tmp_tar} -C {env_dir}')
    run(f'{env_dir}/bin/python {env_dir}/bin/conda-unpack')
    # conda-unpack runs as root and may write __pycache__ .pyc files with 600
    # permissions; make the env world-readable so non-root users can pack it.
    run(f'chmod -R a+rX {env_dir}')
    run(f'rm -f {tmp_tar}')
    log(f'  restored {env_name} from GCS pack')
    return True


SYSTEM_PACKAGES = [
    'openjdk-21-jdk',       # tmVar.jar requires Java 21 (class file version 65.0); also runs GNorm2
    'openjdk-17-jdk',       # GROBID build requires Java 17: its bundled Gradle rejects Java 21 API changes
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
    'libreoffice-nogui',    # Word/Excel conversion in run_civic_pubtator.py (headless server)
    'build-essential',     # gcc/g++/make — needed to compile tmVar's bundled CRF++ from source
    'poppler-utils',       # pdftotext — PDF text extraction for source word count comparison
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
    with open(LOG, 'a') as _fh:
        _fh.write(msg + '\n')


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
    for d in [SENTINEL, DATA_DIR, PUB_DIR]:
        os.makedirs(d, exist_ok=True)
    run(f'chmod -R 777 {DATA_DIR}')


@step('install_packages')
def install_packages():
    run('apt-get update -qq')
    run('DEBIAN_FRONTEND=noninteractive apt-get upgrade -y -q')
    run('apt-get install -y ' + ' '.join(SYSTEM_PACKAGES))


@step('install_conda')
def install_conda():
    if find_conda():
        log(f'  conda already present: {find_conda()}')
    else:
        log('  conda not found — installing Miniconda3')
        run(f'wget -q -O {MINICONDA_SH} '
            'https://repo.anaconda.com/miniconda/Miniconda3-latest-Linux-x86_64.sh')
        run(f'bash {MINICONDA_SH} -b -p {CONDA_PREFIX}')
        run(f'rm -f {MINICONDA_SH}')
    # Expose conda to all users (not just root) via a system-wide profile.d entry.
    # conda init bash only writes to the calling user's ~/.bashrc, so SSH logins
    # as a non-root user would have no conda in PATH without this.
    conda_prefix = os.path.dirname(os.path.dirname(find_conda() or f'{CONDA_PREFIX}/bin/conda'))
    profile_d = '/etc/profile.d/conda.sh'
    with open(profile_d, 'w') as f:
        f.write(f'. "{conda_prefix}/etc/profile.d/conda.sh"\n')
        f.write('conda activate base\n')
    run(f'chmod 644 {profile_d}')


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


@step('configure_git')
def configure_git():
    run('git config --system core.fileMode false')


@step('clone_repo')
def clone_repo():
    if os.path.isdir(os.path.join(REPO_DIR, '.git')):
        log('  repo already cloned, pulling latest')
        run(f'git -C {REPO_DIR} pull --ff-only')
    else:
        run(f'git clone {GITHUB_REPO} {REPO_DIR}')
    # git clone on Linux auto-sets core.fileMode=true in .git/config, overriding
    # the system setting — explicitly disable it in the local repo config.
    run(f'git -C {REPO_DIR} config core.fileMode false')
    run(f'chmod -R 755 {REPO_DIR}/src')


@step('install_civic_pubtator_bin')
def install_civic_pubtator_bin():
    """Make civic_pubtator.py executable and symlink it into /usr/local/bin/.

    This lets any user run `civic-pubtator` from any directory without
    specifying the full path.  The symlink is stable: __file__ inside the
    script always resolves to the repo path, so all relative tool paths work
    correctly regardless of where the command is invoked.
    """
    script = os.path.join(REPO_DIR, 'civic_pubtator.py')
    run(f'chmod +x {script}')
    run(f'ln -sf {script} /usr/local/bin/civic-pubtator')
    log(f'  civic-pubtator → {script}')


@step('compile_tmvar_crf')
def compile_tmvar_crf():
    """Compile tmVar's bundled CRF++ from source (runs after sync_tool_data).

    tmvar/CRF/ is gitignored; the C++ source arrives via sync_tool_data from GCS.
    Three Linux-specific fixes are required:
      1. ./configure  — regenerates the Makefile for Linux; the GCS copy carries a
                        Mac-generated Makefile with Homebrew paths hardcoded.
      2. sed patch    — CRF++ uses make_pair<int,int>(lvalue,lvalue) which is valid
                        in C++14 but fails under the C++17 default of g++ 11+.
                        Removing the explicit template args lets the compiler deduce them.
      3. -std=c++14 -fPIE — c++14 for the make_pair fix; -fPIE because modern Ubuntu
                        links executables as PIE by default and object files must match.
    """
    crf_dir = f'{REPO_DIR}/tools/tmvar/CRF'
    run(f'chmod +x {crf_dir}/configure')
    run(f'cd {crf_dir} && ./configure')
    run(f"sed -i 's/std::make_pair<int, int>(/std::make_pair(/g' {crf_dir}/feature_index.cpp")
    run(f'cd {crf_dir} && make clean && make CXXFLAGS="-std=c++14 -O3 -Wall -fPIE" crf_test crf_learn')
    run(f'chmod a+x {crf_dir}/crf_test {crf_dir}/crf_learn')
    log(f'  compiled: {crf_dir}/crf_test, {crf_dir}/crf_learn')


@step('compile_gnorm2_crf')
def compile_gnorm2_crf():
    """Compile GNorm2's bundled CRF++ from source (runs after sync_tool_data).

    GNorm2's Java layer (GNR.java, SimConcept.java) shells out to CRF/crf_test
    for gene normalization ranking and similarity concept tasks.  The GCS tarball
    carries Linux-compiled binaries but they are dynamically linked against
    libcrfpp.so.0 with paths from the original build machine, so they fail on a
    fresh VM.  Recompiling from source fixes this.  Same three fixes as tmVar:
      1. ./configure  — regenerates the Makefile for this machine.
      2. sed patch    — removes explicit make_pair<int,int> template args that
                        fail under the C++17 default of g++ 11+.
      3. -std=c++14 -fPIE — required for the make_pair fix and PIE linking.
    """
    crf_dir = f'{REPO_DIR}/tools/GNorm2/CRF'
    run(f'chmod +x {crf_dir}/configure')
    run(f'cd {crf_dir} && ./configure')
    run(f"sed -i 's/std::make_pair<int, int>(/std::make_pair(/g' {crf_dir}/feature_index.cpp")
    run(f'cd {crf_dir} && make clean && make CXXFLAGS="-std=c++14 -O3 -Wall -fPIE" crf_test crf_learn')
    run(f'chmod a+x {crf_dir}/crf_test {crf_dir}/crf_learn')
    log(f'  compiled: {crf_dir}/crf_test, {crf_dir}/crf_learn')


@step('install_ncbitextlib')
def install_ncbitextlib():
    """Build NCBITextLib static library from source checked into the repo.

    NCBITextLib/lib/Makefile produces libText.a; Ab3P links against it.
    Source is vendored directly in the repo (no external clone needed).
    """
    dest = f'{REPO_DIR}/tools/NCBITextLib'
    run(f'cd {dest}/lib && make')
    log(f'  built: {dest}/lib/libText.a')


@step('install_ab3p')
def install_ab3p():
    """Build Ab3P abbreviation resolver from source checked into the repo.

    Ab3P identifies abbreviation long-form/short-form pairs in biomedical text.
    The Makefiles hardcode an old repo-root path for NCBITEXTLIB; we patch both
    to the correct tools/ location before building.  `make` runs
    three sub-targets in sequence: library (libAb3P.a) → programs (binaries)
    → data (converts WordData text files into binary hash/set formats that
    identify_abbr loads at runtime; output is gitignored and rebuilt each VM).
    Source is vendored directly in the repo (no external clone needed).
    """
    dest = f'{REPO_DIR}/tools/Ab3P'
    ncbi_lib = f'{REPO_DIR}/tools/NCBITextLib'
    # Both Makefiles hardcode the old repo-root path; patch to the tools/ location.
    for mf in [f'{dest}/Makefile', f'{dest}/lib/Makefile']:
        run(f"sed -i 's|NCBITEXTLIB=.*|NCBITEXTLIB={ncbi_lib}|' {mf}")
    run(f'cd {dest} && make')
    log(f'  built: {dest}/identify_abbr')


@step('install_grobid')
def install_grobid():
    """Download and build GROBID under the repo's expected location."""
    grobid_dir = f'{REPO_DIR}/tools/grobid'
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
    # GROBID 0.8.1's build.gradle uses report.enabled() which was removed in Gradle 8.x,
    # and its bundled Gradle doesn't support Java 21.  Build under Java 17 to avoid both;
    # GROBID's compiled classes run fine on the Java 21 system default at runtime.
    run(f'cd {grobid_dir} && JAVA_HOME=/usr/lib/jvm/java-17-openjdk-amd64 '
        f'./gradlew clean install -x test --no-daemon -q')


@step('install_monitor_service')
def install_monitor_service():
    """Install the civic-pubtator-monitor as a systemd service that starts on boot.

    The monitor polls the GCS bucket for new publications and runs the pipeline
    on any that have not yet been processed.  It depends on GROBID being up, so
    Wants/After=grobid.service ensures both start together and in the right order.
    """
    unit = f"""\
[Unit]
Description=civic-pubtator GCS bucket monitor
Documentation=https://github.com/griffithlab/civic-pubtator
After=network-online.target grobid.service
Wants=network-online.target grobid.service

[Service]
Type=simple
User=mgriffit
Group=mgriffit
WorkingDirectory={REPO_DIR}

Environment=PATH=/snap/bin:{CONDA_PREFIX}/bin:{CONDA_PREFIX}/condabin:/usr/local/bin:/usr/local/sbin:/usr/bin:/bin
Environment=HOME=/home/mgriffit
Environment=PYTHONUNBUFFERED=1

ExecStart={CONDA_PREFIX}/bin/python3 {REPO_DIR}/src/automation/monitor_pub_bucket.py \\
    --results-repo /data/civic-pubtator-data/

StandardOutput=append:{PUB_DIR}/monitor.log
StandardError=append:{PUB_DIR}/monitor.log

Restart=on-failure
RestartSec=300

[Install]
WantedBy=multi-user.target
"""
    unit_path = '/etc/systemd/system/civic-pubtator-monitor.service'
    with open(unit_path, 'w') as f:
        f.write(unit)
    run('systemctl daemon-reload')
    run('systemctl enable civic-pubtator-monitor')


@step('install_grobid_service')
def install_grobid_service():
    """Install GROBID as a systemd service that starts on boot.

    Uses ./gradlew run --no-daemon: with --no-daemon Gradle stays in the
    foreground blocking until GROBID exits, so systemd tracks the correct
    process.  The gradlew install task compiles classes but does not produce
    a runnable fat JAR, so direct java -jar is not available.
    """
    grobid_dir = f'{REPO_DIR}/tools/grobid'

    unit = f"""\
[Unit]
Description=GROBID PDF parsing service
After=network.target

[Service]
Type=simple
WorkingDirectory={grobid_dir}
ExecStart={grobid_dir}/gradlew run --no-daemon
Restart=on-failure
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
    unit_path = '/etc/systemd/system/grobid.service'
    with open(unit_path, 'w') as f:
        f.write(unit)
    run('systemctl daemon-reload')
    run('systemctl enable grobid')
    run('systemctl start grobid')


@step('sync_tool_data')
def sync_tool_data():
    """Download large tool model files from GCS into each tool's repo directory.

    Uses gcloud storage rsync so only missing/changed files are transferred.
    Must run before conda env setup so any tool binaries are present when
    subsequent steps fix their execute permissions.
    """
    sync_script = f'{REPO_DIR}/src/cloud/sync_tool_data.sh'
    run(f'bash {sync_script}')
    # Tools write runtime files into their own directories (e.g. GNorm2 writes
    # setup.SR.run.txt).  Make the tree writable by all users so the pipeline
    # works before the user has run user_environment_config.py.
    run(f'chmod -R a+w {REPO_DIR}/tools')
    # GCS sync strips POSIX execute bits — restore them on known binaries.
    # CRF++ binaries are handled separately in compile_tmvar_crf/compile_gnorm2_crf
    # (they're compiled after the sync), but GNorm2's pre-built Ab3P binaries arrive
    # from GCS and need their execute bits set here.
    for binary in [
        f'{REPO_DIR}/tools/GNorm2/Ab3P',
        f'{REPO_DIR}/tools/GNorm2/identify_abbr',
        f'{REPO_DIR}/tools/Ab3P/identify_abbr',
    ]:
        if os.path.isfile(binary):
            os.chmod(binary, os.stat(binary).st_mode | 0o111)


@step('setup_conda_gnorm2')
def setup_conda_gnorm2():
    """GNorm2 env: Python 3.11, TF 2.15 with CUDA GPU support (no tensorflow-metal)."""
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    env = 'gnorm2-tf215'
    if restore_conda_env(conda, env):
        return
    req = f'{REPO_DIR}/src/requirements/requirements_gnorm2_linux.txt'
    if not os.path.exists(req):
        log(f'ERROR: {req} not found — cannot set up GNorm2 environment')
        return
    run(f'{conda} create -y -n {env} python=3.11')
    run(f'{conda} run -n {env} pip install --upgrade pip --root-user-action=ignore')
    run(f'{conda} run -n {env} pip install -r {req} --root-user-action=ignore')
    # TF 2.15 is built against CUDA 12.2/cuDNN 8, but the env's default nvidia-*
    # packages are CUDA 13/cuDNN 9.  Install the matching cu12 libraries so the
    # GPU is visible to TensorFlow.
    run(f'{conda} run -n {env} pip install nvidia-cudnn-cu12==8.9.4.25 nvidia-curand-cu12 --root-user-action=ignore')


@step('setup_conda_aioner')
def setup_conda_aioner():
    """AIONER CPU env: Python 3.8, TF 2.3.0 via conda-forge (CPU-only fallback).

    TF 2.3.0 was dropped from PyPI so it is installed from conda-forge.
    Python 3.8 is the newest TF 2.3.0 supports; 3.7 hits cython>=3.1
    build-dep failures because its manylinux1 wheels aren't recognised
    by modern pip.
    pip<23.1 is pinned at creation: pip 23.1+ uses @dataclass(slots=True)
    which requires Python 3.10+.
    """
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    env = 'aioner-tf23'
    if restore_conda_env(conda, env):
        return
    req = f'{REPO_DIR}/src/requirements/requirements_aioner_linux.txt'
    if not os.path.exists(req):
        log(f'ERROR: {req} not found — cannot set up AIONER environment')
        return
    run(f'{conda} create -y -n {env} python=3.8 "pip<23.1"')
    # TF 2.3.0 dropped from PyPI — install from conda-forge; addons still on PyPI.
    # Pin tensorflow-estimator=2.3.0 together so conda solves the constraint at once;
    # without it conda-forge resolves to estimator 2.6.0 which TF 2.3 rejects.
    run(f'{conda} install -y -n {env} -c conda-forge tensorflow=2.3.0 tensorflow-estimator=2.3.0')
    run(f'{conda} run -n {env} pip install --upgrade "pip<23.1" --root-user-action=ignore')
    run(f'{conda} run -n {env} pip install -r {req} --root-user-action=ignore')
    run(f'{conda} run -n {env} python -m spacy download en_core_web_sm')


@step('setup_conda_aioner_gpu')
def setup_conda_aioner_gpu():
    """AIONER GPU env: Python 3.8, TF 2.6.0 GPU build via conda-forge.

    TF 2.6.0 is the oldest tensorflow-gpu version still available on conda-forge.
    It differs from the CPU env (TF 2.3.0) but AIONER's tensorflow-addons usage is
    limited to tfa.text.crf functions that are stable across versions; tensorflow-addons
    0.14.0 is the matching version for TF 2.6.  conda-forge's tensorflow-gpu=2.6.0
    pulls in cudatoolkit=11.2 and cudnn=8.1 automatically as dependencies; the GCP
    DL VM driver (CUDA 12.x) supports the CUDA 11.2 runtime via backward compatibility.

    Version pins are strict matches to TF 2.6.0's own requirements:
      numpy~=1.19.2        TF requires ~=1.19.2; h5py's dep pulls 1.24+ without this pin
      h5py~=3.1.0          TF requires ~=3.1.0; conda installs 2.10.0 which mismatches
      typing_extensions==3.7.4.3   TF requires ~=3.7.4; pip/conda conflict leaves old .py
      typeguard==2.13.3    tensorflow-addons 0.14.0 works with 2.x only; 3.x/4.x require
                           is_typeddict from typing_extensions which 3.7.4.3 lacks
    h5py and the typing pins are installed last with --force-reinstall so pip actually
    overwrites the conda-managed files rather than leaving the dist-info/file out of sync.
    """
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    env = 'aioner-tf23-gpu'
    if restore_conda_env(conda, env):
        return
    run(f'{conda} create -y -n {env} python=3.8 "pip<23.1"')
    # tensorflow-gpu=2.6.0 from conda-forge pulls in cudatoolkit=11.2 + cudnn=8.1.
    run(f'{conda} install -y -n {env} -c conda-forge tensorflow-gpu=2.6.0')
    run(f'{conda} run -n {env} pip install tensorflow-addons==0.14.0 --root-user-action=ignore')
    run(f'{conda} run -n {env} pip install '
        f'"numpy~=1.19.2" '
        f'transformers==4.18.0 tokenizers==0.12.1 huggingface-hub==0.5.1 '
        f'stanza==1.4.0 spacy==2.3.9 '
        f'bioc==2.0.post4 lxml==4.8.0 '
        f'tqdm==4.64.0 scipy==1.4.1 torch==1.11.0 '
        f'--root-user-action=ignore')
    run(f'{conda} run -n {env} python -m spacy download en_core_web_sm')
    # Force-reinstall to overwrite conda-managed files that pip's resolver leaves stale.
    run(f'{conda} run -n {env} pip install '
        f'"h5py~=3.1.0" "typing_extensions==3.7.4.3" "typeguard==2.13.3" '
        f'--force-reinstall --root-user-action=ignore')


@step('setup_conda_nlmchem')
def setup_conda_nlmchem():
    """NLMChem normalizer env: Python 3.9."""
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    env = 'nlmchem-py39'
    if restore_conda_env(conda, env):
        return
    req = f'{REPO_DIR}/src/requirements/requirements_nlmchem_linux.txt'
    if not os.path.exists(req):
        log(f'ERROR: {req} not found — cannot set up NLMChem environment')
        return
    run(f'{conda} create -y -n {env} python=3.9 "pip<23.1"')
    run(f'{conda} run -n {env} pip install --upgrade "pip<23.1" --root-user-action=ignore')
    run(f'{conda} run -n {env} pip install -r {req} --root-user-action=ignore')


@step('setup_conda_base')
def setup_conda_base():
    """Install main project requirements into the base conda env.

    This makes scripts/ commands available without activating a tool-specific
    env — just source ~/.bashrc (which activates base) and run.
    """
    conda = find_conda() or f'{CONDA_PREFIX}/bin/conda'
    req = f'{REPO_DIR}/requirements.txt'
    if not os.path.exists(req):
        log(f'ERROR: {req} not found — cannot set up base conda environment')
        return
    run(f'{conda} run -n base pip install --upgrade pip --root-user-action=ignore')
    run(f'{conda} run -n base pip install -r {req} --root-user-action=ignore')


@step('add_aliases')
def add_aliases():
    aliases = [
        "alias ll='ls -lh'",
        f"alias cdrepo='cd {REPO_DIR}'",
        f"alias cdpub='cd {PUB_DIR}'",
        f"alias cdtools='cd {TOOL_DIR}'",
    ]
    # Write to /etc/profile.d so aliases are available for all users, not just root.
    with open('/etc/profile.d/civic-pubtator-aliases.sh', 'w') as f:
        f.write('\n'.join(aliases) + '\n')
    run('chmod 644 /etc/profile.d/civic-pubtator-aliases.sh')


# ── entry point ───────────────────────────────────────────────────────────────

def main():
    log('=== civic-pubtator startup ===')
    os.makedirs(SENTINEL, exist_ok=True)

    create_directories()
    install_packages()
    install_conda()
    accept_conda_tos()
    configure_git()
    clone_repo()
    install_civic_pubtator_bin()
    install_grobid()
    install_grobid_service()
    install_monitor_service()
    sync_tool_data()
    install_ncbitextlib()  # source arrives from GCS via sync_tool_data
    install_ab3p()         # same
    compile_tmvar_crf()    # must run after sync_tool_data: CRF source comes from GCS
    compile_gnorm2_crf()   # same reason: GNorm2/CRF/ binaries are not portable across machines
    setup_conda_base()
    setup_conda_gnorm2()
    setup_conda_aioner()
    setup_conda_aioner_gpu()
    setup_conda_nlmchem()
    add_aliases()

    # Start the monitor service now that all setup is complete.  On subsequent
    # boots the service is already running (enabled via systemd), so this is a
    # no-op; on first boot it kicks off the polling loop immediately.
    run('systemctl start civic-pubtator-monitor', check=False)

    log('=== startup complete ===')
    log('Next steps:')
    log('  1. Run per-user setup (once, first SSH login only):')
    log(f'       python3 {REPO_DIR}/src/cloud/user_environment_config.py')
    log('     This fixes directory ownership, configures git, and sets up your GitHub SSH key.')
    log('  2. Activate conda in your shell (once per login):')
    log('       source ~/.bashrc')
    log('  3. Sync publication data from GCS:')
    log(f'       bash {REPO_DIR}/src/cloud/sync_pub_data.sh down')
    log('  4. Available conda environments:')
    log('       conda activate gnorm2-tf215')
    log('       conda activate aioner-tf23')
    log('       conda activate aioner-tf23-gpu')
    log('       conda activate nlmchem-py39')


if __name__ == '__main__':
    main()
