# tmvar-arm
Version of tmvar working on ARM with detailed instructions and examples

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

## PDF to BioC XML Conversion

`scripts/pdf_to_bioc.py` converts PDF files to BioC XML using a running GROBID service.

### Install Python dependencies

```bash
pip3 install -r requirements.txt
```

### Install and run GROBID

GROBID requires Java 11+. The easiest way to run it is via Docker:

```bash
docker pull lfoppiano/grobid:0.8.1
docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.1
```

Alternatively, install it manually:

```bash
# Download and unzip
wget https://github.com/kermitt2/grobid/archive/0.8.1.zip
unzip 0.8.1.zip
cd grobid-0.8.1

# Build (requires Gradle)
./gradlew clean install

# Run the service
./gradlew run
```

GROBID listens on `http://localhost:8070` by default. Confirm it is running before using `scripts/pdf_to_bioc.py`.

### Convert PDFs

```bash
./scripts/pdf_to_bioc.py <input_pdf_folder> <output_xml_folder>
```
