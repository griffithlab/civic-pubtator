# Mac Notes — civic-pubtator

This file collects macOS-specific setup instructions. Linux users do not need any of this.

---

## macOS setup

The tmVar3 archive ships with Linux CRF++ binaries that do not run on macOS.
After downloading the data files (see below), run the setup script once:

```bash
./src/mac/setup_macos.sh
```

This installs `crf++` via Homebrew and writes macOS-compatible shims into `tmvar/CRF/`.

---

## Downloading large data files (macOS)

```bash
./src/mac/download_data_files.sh
```

Run `./src/mac/setup_macos.sh` after this completes.

---

## GROBID manual install without Docker (macOS)

GROBID 0.8.1 requires **Java 17** (not Java 21).

```bash
# Install Java 17
brew install openjdk@17
export JAVA_HOME=$(brew --prefix openjdk@17)

wget https://github.com/kermitt2/grobid/archive/0.8.1.zip
unzip 0.8.1.zip
cd grobid-0.8.1
./gradlew clean install
./gradlew run
```

---

## Apple Silicon GPU acceleration (optional)

By default, GNorm2 runs its BERT-based ML step on CPU using the system Python
(TF 2.21). On Apple Silicon Macs, Metal GPU acceleration is available but
requires a separate Python 3.11 environment with TF 2.15 and `tensorflow-metal`
(the only Metal plugin released for TensorFlow, which targets TF 2.15).

### One-time setup

```bash
bash src/setup_conda_envs/setup_gnorm2_conda.sh
```

This script installs Miniforge via Homebrew (if not already present), creates
a conda environment named `gnorm2-tf215` with Python 3.11, and installs all
required packages including `tensorflow==2.15.0` and `tensorflow-metal==1.2.0`.
At the end it prints the exact Python path to use.

### Using the GPU environment

Pass the conda env name or Python path via `--gnorm2-python`:

```bash
# Using the conda env name (short form)
python3 civic_pubtator.py <run_dir> --gnorm2-python gnorm2-tf215

# Using the full Python path (printed by setup_conda_envs/setup_gnorm2_conda.sh)
python3 civic_pubtator.py <run_dir> \
    --gnorm2-python /opt/homebrew/Caskroom/miniforge/base/envs/gnorm2-tf215/bin/python3
```

Only the GNorm2 ML step (BERT inference) uses this environment. The GROBID and
tmVar3 steps continue to use the system Python.

### Verify GPU is active

```bash
conda run -n gnorm2-tf215 python -c "import tensorflow as tf; print(tf.config.list_physical_devices('GPU'))"
```

A working setup prints something like:
```
[PhysicalDevice(name='/physical_device:GPU:0', device_type='GPU')]
```
