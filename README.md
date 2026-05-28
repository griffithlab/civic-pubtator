# civic-pubtator

Pipeline for extracting and normalising genetic variant mentions from biomedical PDFs using GROBID → GNorm2 → tmVar3.

---

## Table of contents

1. [Quick start](#quick-start)
2. [Directory structure](#directory-structure)
3. [Setup](#setup)
   - [macOS](#macos-setup)
   - [Python dependencies](#python-dependencies)
   - [GROBID](#grobid)
   - [Downloading large data files](#downloading-large-data-files)
4. [Running the pipeline](#running-the-pipeline)
   - [Basic usage](#basic-usage)
   - [Supplementary files](#supplementary-files)
   - [All options](#all-options)
5. [Output files](#output-files)
6. [Apple Silicon GPU acceleration (optional)](#apple-silicon-gpu-acceleration-optional)

---

## Quick start

```bash
# 1. One-time setup (macOS)
./scripts/setup_macos.sh

# 2. Start GROBID (in a separate terminal)
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.1

# 3. Run the pipeline
python3 scripts/run_civic_pubtator.py /path/to/my_run/
```

`/path/to/my_run/` must contain a `01_source/` subdirectory with at least one PDF.

---

## Directory structure

The pipeline expects and produces a fixed layout inside each run directory:

```
my_run/
├── 01_source/          ← place source PDFs here before running
│   ├── paper1.pdf
│   ├── paper2.pdf
│   └── s/              ← optional: supplementary files (see below)
│       ├── paper1.xlsx
│       └── paper2.docx
├── 02_grobid/          ← GROBID BioC XML output (created automatically)
├── 03_gnorm2/          ← GNorm2 output (created automatically)
├── 04_tmvar3/          ← tmVar3 output (created automatically)
├── MANIFEST.txt        ← record of input files and tool version
├── pipeline_stats.log  ← human-readable per-step stats
└── pipeline_stats.tsv  ← machine-readable per-step stats
```

---

## Setup

### macOS setup

The tmVar3 archive ships with Linux CRF++ binaries that do not run on macOS.
After downloading the data files (see below), run the setup script once:

```bash
./scripts/setup_macos.sh
```

This installs `crf++` via Homebrew and writes macOS-compatible shims into `tmvar/CRF/`.
On Linux, the pre-compiled binaries are used directly — no setup needed.

### Python dependencies

```bash
pip3 install -r requirements.txt
```

### GROBID

GROBID 0.8.1 requires **Java 17** (not Java 21). The easiest way to run it is via Docker:

```bash
docker pull lfoppiano/grobid:0.8.1
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.1
```

GROBID must be running on `http://localhost:8070` before you start the pipeline.

<details>
<summary>Manual GROBID install (without Docker)</summary>

```bash
# Install Java 17 (macOS)
brew install openjdk@17
export JAVA_HOME=$(brew --prefix openjdk@17)

wget https://github.com/kermitt2/grobid/archive/0.8.1.zip
unzip 0.8.1.zip
cd grobid-0.8.1
./gradlew clean install
./gradlew run
```
</details>

### Downloading large data files

The `tmvar/CRF/` and `tmvar/Database/` directories are not in this repository
(CRF models ~1 GB, SQLite databases ~550 GB). Download from NCBI before running:

```bash
./scripts/download_data_files.sh
```

**macOS users:** run `./scripts/setup_macos.sh` after this completes.

---

## Running the pipeline

### Basic usage

```bash
python3 scripts/run_civic_pubtator.py <run_dir> [<run_dir2> ...]
```

Each `run_dir` must contain a `01_source/` subdirectory with at least one PDF.
Multiple run directories can be processed in one invocation.

### Supplementary files

Place supplementary files for a paper under `01_source/s/` using the same stem
as the corresponding source PDF:

```
01_source/
├── paper1.pdf
└── s/
    ├── paper1.xlsx     ← supplementary spreadsheet for paper1
    └── paper1.docx     ← supplementary document for paper1
```

Supported formats: `.pdf`, `.docx`, `.doc`, `.xlsx`, `.xls`.
Excel files are split by sheet — each sheet is converted to a separate PDF and
processed independently. LibreOffice is used for conversion when available
(`brew install --cask libreoffice`); a reportlab fallback is used otherwise.

### All options

```
usage: run_civic_pubtator.py [-h] [--clean] [--no-clear-intermediates]
                             [--start-step {1,2,3}] [--no-libreoffice]
                             [--max-chars N] [--memory SIZE]
                             [--gnorm2-python PATH_OR_ENV]
                             input_dirs [input_dirs ...]
```

| Option | Default | Description |
|---|---|---|
| `--clean` | off | Delete and recreate output directories before running |
| `--no-clear-intermediates` | off | Keep tmp dirs and prepared supplement PDFs after the run |
| `--start-step {1,2,3}` | `1` | Resume from a specific step (1=GROBID, 2=GNorm2, 3=tmVar3) |
| `--no-libreoffice` | off | Use the reportlab/python-docx fallback for supplement conversion |
| `--max-chars N` | `1000000` | Skip documents whose output XML exceeds N characters; use `0` for no limit |
| `--memory SIZE` | `32G` | Java max heap for GNorm2 and tmVar3; initial heap is set to half this value |
| `--gnorm2-python PATH_OR_ENV` | system Python | Python interpreter for the GNorm2 ML step — accepts a full path or a conda env name (see [Apple Silicon GPU acceleration](#apple-silicon-gpu-acceleration-optional)) |

---

## Output files

Each run directory receives three output files alongside the `02_grobid/`,
`03_gnorm2/`, and `04_tmvar3/` processing directories.

### `MANIFEST.txt`

Created at the start of each run. Records the tool version (from `RELEASE`),
run timestamp, and a table of every source PDF and supplementary file that was
submitted for processing.

### `pipeline_stats.log`

Human-readable log of each pipeline step with per-file character and word counts
and step runtime. Example entry:

```
  >> GNorm2  2026-05-14 09:12:43  (4m 17s)
     Output: /path/to/03_gnorm2
     File                                      Chars         Words
     ----------------------------------------  ------------  ---------
     paper1.xml                                   142,381     22,604
     TOTAL                                        142,381     22,604
```

### `pipeline_stats.tsv`

Machine-readable table with one row per output file per step. Columns:

| Column | Description |
|---|---|
| `step` | Step number (1=GROBID, 2=GNorm2, 3=tmVar3) |
| `step_name` | Step name |
| `label` | Input group (`main` or supplementary path) |
| `chars` | Character count of the output file |
| `words` | Word count of the output file |
| `runtime` | Wall-clock time for the step (e.g. `4m 17s`) |
| `input_name` | Stem of the input file |
| `output_file` | Relative path to the output file |

---

## Apple Silicon GPU acceleration (optional)

By default, GNorm2 runs its BERT-based ML step on CPU using the system Python
(TF 2.21). On Apple Silicon Macs, Metal GPU acceleration is available but
requires a separate Python 3.11 environment with TF 2.15 and `tensorflow-metal`
(the only Metal plugin released for TensorFlow, which targets TF 2.15).

### One-time setup

```bash
bash scripts/setup_gnorm2_conda.sh
```

This script installs Miniforge via Homebrew (if not already present), creates
a conda environment named `gnorm2-tf215` with Python 3.11, and installs all
required packages including `tensorflow==2.15.0` and `tensorflow-metal==1.2.0`.
At the end it prints the exact Python path to use.

### Using the GPU environment

Pass the conda env name or Python path via `--gnorm2-python`:

```bash
# Using the conda env name (short form)
python3 scripts/run_civic_pubtator.py <run_dir> --gnorm2-python gnorm2-tf215

# Using the full Python path (printed by setup_gnorm2_conda.sh)
python3 scripts/run_civic_pubtator.py <run_dir> \
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
