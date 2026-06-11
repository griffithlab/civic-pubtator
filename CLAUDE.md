# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Goal

**civic-pubtator** aims to reproduce much of the functionality of PubTator 3.0 to annotate biomedical literature with entities important to CIViC curators: **Genes, Variants, Drugs, Diseases, Species, and Cell Lines**.

Because the PubTator 3.0 pipeline is not publicly portable, it is being reverse-engineered and adapted based on the component tools' documentation and the PubTator 3.0 publication. The published pipeline works as follows:

- **NER** — AIONER (deep-learning transformer) recognizes six entity types: genes/proteins, chemicals, diseases, species, genetic variants, cell lines.
- **Normalization** — Specialized mappers link each entity type to a database identifier:
  - Genes/species → NCBI Gene / NCBI Taxonomy via **GNorm2**
  - Genetic variants → dbSNP RS# or HGVS notation via **tmVar3**
  - Chemicals → MeSH via NLM-Chem
  - Diseases / cell lines → MeSH / Cellosaurus via TaggerOne
- **Relation extraction** — BioREx identifies 12 common relation types between entities.

The **current pipeline** approximates this with tools that are available. GROBID output feeds two independent annotation branches:

```
PDFs → GROBID → 02_grobid/ (BioC XML)
                     │
          ┌──────────┼─────────────────────┐
          │          │                     │
       GNorm2     AIONER              TaggerOne
       (gene +    (all 6 NER          (disease NER +
        species    entity types)       normalization)
        norm)         │                     │
          │        NLMChem            07_taggerone/
       tmVar3      (chemical norm;
       (variant +   reads AIONER out)
        gene norm)     │
          │        06_nlmchem/
       04_tmvar3/
          │
     pipeline_steps/report_civic_pubtator.py → report_<pmid>.html
```

All tools run in **batch mode** — all documents across all groups (main + supplementary) are processed in a single tool invocation to amortize model-loading startup costs. The orchestrating script is `scripts/run_civic_pubtator.py`.

The `scripts/` directory is organised into three subdirectories:
- `scripts/pipeline_steps/` — per-step wrapper scripts invoked by the orchestrator (`pdf_to_bioc.py`, `prepare_supplementary.py`, `run_gnorm2.py`, `run_tmvar.py`, `run_aioner.py`, `run_nlmchem.py`, `run_taggerone.py`, `report_civic_pubtator.py`)
- `scripts/setup_conda_envs/` — one-time environment setup scripts (`setup_gnorm2_conda.sh`, `setup_aioner_conda.sh`, `setup_nlmchem_conda.sh`, `check_gpu.py`)
- `scripts/cloud/` and `scripts/mac/` — infrastructure and platform-specific helpers

Per-publication directory structure:
```
<pub_dir>/01_source/        ← source PDFs (+ s/ subdir for supplementary)
<pub_dir>/02_grobid/        ← GROBID BioC XML output
<pub_dir>/03_gnorm2/        ← GNorm2 annotated BioC XML (gene + species)
<pub_dir>/04_tmvar3/        ← tmVar3 BioC XML + PubTator files (variant + gene)
<pub_dir>/05_aioner/        ← AIONER NER-annotated BioC XML (all 6 entity types)
<pub_dir>/06_nlmchem/       ← NLMChem BioC XML (chemical → MeSH); + abbreviations/
<pub_dir>/07_taggerone/     ← TaggerOne BioC XML (disease → MeSH/OMIM)
<pub_dir>/MANIFEST.txt      ← run metadata
<pub_dir>/pipeline_stats.tsv / pipeline_stats.log
<pub_dir>/report_<pmid>.html
```

The HTML report (`scripts/pipeline_steps/report_civic_pubtator.py`) currently reads from:
- `04_tmvar3/*.PubTator` — passages, variants, genes, species, cell lines
- `06_nlmchem/*.xml` — chemical annotations (merged in, highlighted in fuchsia)

Steps 05 (AIONER) and 07 (TaggerOne) outputs are produced but not yet read by the reporter.

---

## Known Tool Capabilities and Limitations

### TaggerOne (v0.2.1 public release)

- **Disease-only.** The `model_DISE.bin` model was trained with `--entityTypes Disease` on NCBI Disease + BC5CDR corpora. It produces only `Disease` annotations normalized to MeSH/OMIM. Chemicals are explicitly ignored during training.
- **No normalization-only mode.** The PubTator 3.0 paper describes TaggerOne running in a "normalization-only mode" (applying normalization to pre-existing AIONER spans). That mode was developed by NCBI and was **never publicly released**. The v0.2.1 JAR has no equivalent.
- **Passing AIONER output to TaggerOne would not help.** `ProcessText` ignores existing annotations in the input BioC XML and always runs its own NER from scratch.
- **No cell line model.** No Cellosaurus lexicon or cell-line-trained model exists in the public v0.2.1 distribution.

### GNorm2 — CellLine annotations

GNorm2 produces `CellLine` annotations (e.g. NIH3T3, SK-MEL-208, HEK293) that flow through tmVar3 into the PubTator files and report. However, the identifiers assigned are **NCBI Taxonomy IDs** (`9606` = human, `10090` = mouse), not Cellosaurus accessions (CVCL_xxxx). GNorm2 identifies the host organism of the cell line, not the specific cell line entry. Cellosaurus normalization would require a separate tool.

### NLMChem

Reads AIONER output (step 5) as input. Produces `Chemical` annotations normalized to MeSH identifiers. Unresolvable chemicals receive identifier `-`. Now integrated into the HTML report via `parse_bioc_chemicals()` in `pipeline_steps/report_civic_pubtator.py`.

---

## What This Project Is (tmVar3 component)

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
python3 scripts/pipeline_steps/pdf_to_bioc.py
```

## Gene Normalization Integration

tmVar3 can optionally link variants to genes using GNormPlus output. Run GNormPlus on the input first so that gene mention annotations are present in the BioC XML; `CorrespondGene.java` then maps variants to the nearest gene in the same sentence/passage. Without GNormPlus input the tool still extracts and normalizes variants but does not produce `CorrespondingGene` fields.
