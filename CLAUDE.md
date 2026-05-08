# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What This Project Is

tmVar3 is a Java-based biomedical text-mining pipeline that identifies and normalizes genetic variant mentions (DNA mutations, protein mutations, SNPs) in scientific literature. It extracts variants from PubTator or BioC XML input and maps them to standard identifiers (dbSNP RS#, ClinGen Allele Registry CA#, HGVS notation).

## Running the Tool

```bash
# Standard run — requires 5–10 GB heap
java -Xmx5G -Xms5G -jar tmVar.jar [InputFolder] [OutputFolder]

# Example
java -Xmx5G -Xms5G -jar tmVar.jar input output
```

Optional positional arguments (defaults in parens):
- `TrainTest` — `Test` (default) or `Train`
- `DeleteTmp` — delete temporary CRF files (default `true`)
- `DisplayRSnumOnly` — suppress CA# output (default `false`)
- `HideMultipleResult` — hide ambiguous mappings (default `false`)

The shell wrapper `tmVar.sh` sets these flags.

## Building / Compiling

The pre-built `tmVar.jar` (56 MB) is checked in. To recompile the Java source, use standard `javac` with the JARs in `bin/` and `lib/` on the classpath.

The C++ CRF++ module must be compiled separately (Linux only):

```bash
bash Installation.sh        # runs ./configure && make inside CRF/
```

Pre-compiled binaries (`CRF/crf_test`, `CRF/crf_learn`) are included for Linux.

## Input / Output Formats

**Input** — either format is auto-detected:
- **PubTator** — `PMID|t|Title` / `PMID|a|Abstract` lines, tab-separated annotation lines
- **BioC XML** — structured XML conforming to `BioC.dtd`

**Output** — BioC XML with added annotations containing:
- `tmVar` component breakdown
- HGVS notation
- `VariantGroup`, `CorrespondingGene`, RS#/CA# identifiers

## Architecture Overview

The pipeline runs sequentially through four main classes:

```
BioCConverter  →  MentionRecognition  →  PostProcessing  →  ToHGVs
(parse input)     (CRF feature          (structure          (HGVS + DB
                   extraction &          detected             normalization)
                   inference)            mentions)
```

**`tmVar.java`** — main entry point; loads all static resources (POS model, regex patterns, frequency tables, DB mappings) into global `HashMap`s, then drives the pipeline.

**`MentionRecognition.java`** — tokenizes and POS-tags each sentence (Stanford tagger), generates feature vectors, shells out to `CRF/crf_test` for sequence labeling, returns labeled spans.

**`PostProcessing.java`** — the largest class (259 KB); decomposes CRF output into structured variant mentions, handles sentence-level aggregation, formats BioC/PubTator output.

**`ToHGVs.java`** — converts variant strings to HGVS nomenclature and resolves RS#/CA# via SQLite lookups. Queries the chromosome-sharded `Database/var2rs_g.*.db` files and related databases.

**`CorrespondGene.java`** — optional gene-linking step; requires GNormPlus gene annotations as pre-input. Links variant mentions to specific gene IDs.

**`PrefixTree.java`** — trie-based dictionary for fast gene/species mention lookup with Greek letter and special character normalization.

**`BioCConverter.java`** — parses BioC XML using the Woodstox streaming parser; extracts passages and validates format.

## Key Model / Data Files

| Path | Purpose |
|---|---|
| `CRF/MentionExtractionUB.Model` | CRF model for identifying variant spans (232 MB) |
| `CRF/ComponentExtraction.Model` | CRF model for decomposing variant components (882 MB) |
| `lib/RegEx/DNAMutation.RegEx.txt` | Regex patterns for DNA variants |
| `lib/RegEx/ProteinMutation.RegEx.txt` | Regex patterns for protein variants |
| `lib/RegEx/SNP.RegEx.txt` | Regex patterns for SNP mentions |
| `lib/RegEx/MF.RegEx.2.txt` | Feature patterns for ML (70 KB) |
| `lib/taggers/english-left3words-distsim.tagger` | Stanford POS tagger model |
| `Database/*.db` | SQLite databases for variant normalization (~550 GB total) |
| `bin/filtering.txt` | False-positive filtering rules |

## Java Dependencies (all pre-bundled in `bin/` and `lib/`)

`bioc.jar`, `stanford-postagger.jar`, `mallet.jar`, `mallet-deps.jar`, `org.tartarus.snowball.jar`, `sqlite-jdbc-3.8.11.2.jar`, `pengyifan-pubtator.jar`, `java-json.jar`, `commons-lang-2.4.jar`

## Preprocessing Utilities

```bash
# Extract PubMed articles to PubTator format
perl PreProcessing.pl

# Convert PDF to BioC XML via GROBID (requires running GROBID service)
python3 pdf_to_bioc.py
```

## Gene Normalization Integration

tmVar3 can optionally link variants to genes using GNormPlus output. Run GNormPlus on the input first so that gene mention annotations are present in the BioC XML; `CorrespondGene.java` then maps variants to the nearest gene in the same sentence/passage. Without GNormPlus input the tool still extracts and normalizes variants but does not produce `CorrespondingGene` fields.
