# tmvar-arm
Version of tmvar working on ARM with detailed instructions and examples

## macOS Setup

The tmVar3 archive ships with Linux CRF++ binaries that do not run on macOS. After downloading the data files (see below), run the macOS setup script once to install CRF++ via Homebrew and replace the Linux binaries with shims that call the native macOS binaries:

```bash
./scripts/setup_macos.sh
```

This script will:
1. Install `crf++` via Homebrew if not already present
2. Write macOS-compatible shims for `crf_test` and `crf_learn` into `tmvar/CRF/`

On Linux, the pre-compiled binaries in `tmvar/CRF/` are used directly — no setup script needed.

## Downloading Large Data Files

The `tmvar/CRF/` and `tmvar/Database/` directories are not included in this repository because they are too large for GitHub (the CRF models alone are ~1 GB and the SQLite databases total ~550 GB). Download them from NCBI before running the pipeline:

```bash
./scripts/download_tmvar_data.sh
```

This script will:
1. Download the official tmVar3 archive from NCBI FTP (`tmVar3.tar.gz`) into a temporary directory
2. Extract it and move `CRF/` and `Database/` into `tmvar/`
3. Delete the temporary archive and all other extracted files

Expect the download to take some time depending on your connection speed.

**macOS users:** after this download completes, run `./scripts/setup_macos.sh` to configure the CRF++ binaries.

## PDF to BioC XML Conversion

`scripts/pdf_to_bioc.py` converts PDF files to BioC XML using a running GROBID service.

### Install Python dependencies

```bash
pip3 install -r requirements.txt
```

### Install and run GROBID

GROBID 0.8.1 requires **Java 17** (not Java 21). The easiest way to run it is via Docker, which avoids Java version issues entirely:

```bash
docker pull lfoppiano/grobid:0.8.1
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.1
```

Alternatively, install it manually (requires Java 17 — Java 21 will fail):

```bash
# Install Java 17 if needed (macOS)
brew install openjdk@17
export JAVA_HOME=$(brew --prefix openjdk@17)

# Download and unzip
wget https://github.com/kermitt2/grobid/archive/0.8.1.zip
unzip 0.8.1.zip
cd grobid-0.8.1

# Build
./gradlew clean install

# Run the service
./gradlew run
```

GROBID listens on `http://localhost:8070` by default. Confirm it is running before using `scripts/pdf_to_bioc.py`.

### Convert PDFs

```bash
./scripts/pdf_to_bioc.py <input_pdf_folder> <output_xml_folder>
```

## Example Workflow

The following shows the full pipeline using the included example publication (PMID 36922589).

### Step 1 — Install Python dependencies

```bash
pip3 install -r requirements.txt
```

### Step 2 — Download CRF models and databases

```bash
./scripts/download_tmvar_data.sh
```

### Step 3 — macOS only: configure CRF++ binaries

```bash
./scripts/setup_macos.sh
```

### Step 4 — (Optional) Convert PDF to BioC XML

If starting from a PDF, convert it first. Skip this step if you already have BioC XML input.

```bash
# Start GROBID (in a separate terminal or detached)
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.1

# Convert
./scripts/pdf_to_bioc.py \
    example_data/01_publications_source/36922589 \
    example_data/02_publications_tmvar_format/36922589
```

### Step 5 — Run tmVar

```bash
cd tmvar
java -Xmx5G -Xms5G -jar tmVar.jar \
    ../example_data/02_publications_tmvar_format/36922589 \
    ../example_data/03_publications_output/36922589
```

Output BioC XML and PubTator files will be written to `example_data/03_publications_output/36922589/`.
