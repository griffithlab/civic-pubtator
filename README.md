# civic-pubtator

Pipeline for annotating biomedical PDFs with named entities relevant to CIViC curators: genes, variants, drugs, diseases, species, and cell lines.

---

## Acknowledgements

This project is an attempt to create a standalone, reproducible version of the
[PubTator 3.0](https://doi.org/10.1093/nar/gkae235) entity recognition and
normalization pipeline. PubTator 3.0 is developed and maintained by the National
Center for Biotechnology Information (NCBI). Because the PubTator 3.0 pipeline is
not publicly portable, this implementation reverse-engineers the component tools
based on their documentation and the PubTator 3.0 publication.

The following tools are used, roughly in pipeline order:

| Tool | Role |
|---|---|
| [GROBID](https://github.com/kermitt2/grobid) | Converts PDFs to structured BioC XML (title, abstract, body, figures, tables) |
| [AIONER](https://github.com/ncbi/AIONER/) | Deep-learning NER for all six entity types (genes, chemicals, diseases, species, variants, cell lines) |
| [GNorm2](https://github.com/ncbi/GNorm2/) | Gene and species NER + normalization to NCBI Gene / NCBI Taxonomy IDs |
| [tmVar3](https://github.com/ncbi/tmVar3) | Genetic variant NER + normalization to dbSNP RS#, HGVS, and ClinGen CA# |
| [NLMChem](https://pubmed.ncbi.nlm.nih.gov/33767203/) | Chemical/drug normalization to MeSH identifiers (reads AIONER NER output) |
| [TaggerOne](https://pubmed.ncbi.nlm.nih.gov/27283952/) | Disease NER + normalization to MeSH/OMIM identifiers |

---

## Table of contents

1. [Quick start](#quick-start)
2. [Directory structure](#directory-structure)
3. [Setup](#setup)
   - [Python dependencies](#python-dependencies)
   - [GROBID](#grobid)
   - [Downloading large data files](#downloading-large-data-files)
4. [Running the pipeline](#running-the-pipeline)
   - [Basic usage](#basic-usage)
   - [Supplementary files](#supplementary-files)
   - [All options](#all-options)
5. [Output files](#output-files)

> **macOS users:** see [Mac_Notes.md](Mac_Notes.md) for platform-specific setup
> and optional Apple Silicon GPU acceleration.

---

## Quick start — Google Cloud

The pipeline is designed to run on Google Cloud Platform (GCP). Large tool model
files (CRF models, BERT weights, SQLite databases) live in a GCS bucket and are
synced to the VM on startup; publication data is synced separately before and
after each run.

### 0. One-time setup (per project / per user)

**Project setup** — run once ever to create the VPC network, subnet, firewall
rule, and GCS bucket that all VMs share:

```bash
bash scripts/cloud/create_gcp_resources.sh \
    <gcp-project> <bucket-name> <allowed-ip-cidr> <region> [retention-policy]
```

**User setup** — run once after your first SSH login to a new VM. Fixes
directory ownership, configures your git identity, generates an SSH key and
walks you through adding it to GitHub, and installs Claude Code:

```bash
python3 scripts/cloud/user_environment_config.py
```

### 1. Start a VM

```bash
bash scripts/cloud/start_gcp_vm.sh <instance-name> --project <gcp-project>
```

This creates an `n1-highmem-8` VM (52 GB RAM) with an NVIDIA T4 GPU and a 750 GB
SSD. A startup script (`scripts/cloud/gcp_server_startup.py`) runs automatically
on first boot and handles everything: installing system packages and Java, cloning
the repo, building GROBID (registered as a systemd service), syncing tool model
files from GCS, compiling CRF++ for tmVar3 and GNorm2, and creating all required
conda environments. Watch startup progress from inside the VM with:

```bash
sudo journalctl -u google-startup-scripts -f
```

### 2. Sync publication data

Copy source PDFs down from GCS (or upload a new paper's `01_source/` directory):

```bash
# Download all papers
bash scripts/cloud/sync_pub_data.sh --bucket civic-pubtator-pub-data down

# Download one paper
bash scripts/cloud/sync_pub_data.sh --bucket civic-pubtator-pub-data down 28783719
```

### 3. Run the pipeline

```bash
python3 scripts/run_civic_pubtator.py /data/pub-data/28783719/
```

### 4. Upload results and stop the VM

```bash
# Upload results for one paper
bash scripts/cloud/sync_pub_data.sh --bucket civic-pubtator-pub-data up 28783719

# Delete the VM when done to avoid ongoing charges
gcloud compute instances delete <instance-name> --zone us-central1-f --project <gcp-project>
```

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
├── 05_aioner/          ← AIONER output (created automatically)
├── 06_nlmchem/         ← NLMChem output (created automatically)
├── 07_taggerone/       ← TaggerOne output (created automatically)
├── MANIFEST.txt        ← record of input files and tool version
├── pipeline_stats.log  ← human-readable per-step stats
└── pipeline_stats.tsv  ← machine-readable per-step stats
```

---

## Setup

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

### Downloading large data files

The `tmvar/CRF/` and `tmvar/Database/` directories are not in this repository
(CRF models ~1 GB, SQLite databases ~550 GB). Download from NCBI before running:

```bash
./scripts/download_data_files.sh
```

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
processed independently. LibreOffice is used for conversion when available;
a reportlab fallback is used otherwise.

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
| `--gnorm2-python PATH_OR_ENV` | system Python | Python interpreter for the GNorm2 ML step — accepts a full path or a conda env name |

---

## Output files

Each run directory receives three output files alongside the processing directories.

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
| `step` | Step number (1=GROBID, 2=GNorm2, 3=tmVar3, 4=AIONER, 5=NLMChem, 6=TaggerOne) |
| `step_name` | Step name |
| `label` | Input group (`main` or supplementary path) |
| `chars` | Character count of the output file |
| `words` | Word count of the output file |
| `runtime` | Wall-clock time for the step (e.g. `4m 17s`) |
| `input_name` | Stem of the input file |
| `output_file` | Relative path to the output file |
