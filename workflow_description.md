# civic-pubtator workflow description

## Overall conceptual goal

Reproduce much of the functionality of PubTator 3.0 (https://doi.org/10.1093/nar/gkae235)
to annotate biomedical literature with entities important to CIViC curators:
**Genes, Variants, Drugs, Diseases, Species and Cell Lines**.

CIViC PubTator 3.0 consists of an NLP pipeline.

Since the PubTator 3.0 pipeline is not made available in a portable way it is being reverse
engineered (and modified in places) based on descriptions from the limited documentation
of component tools and the PubTator 3.0 publication. Here are relevant excerpts from that
publication:

> Articles are processed through three major steps: (i) named entity recognition (NER), provided
> by the recently developed deep-learning transformer model AIONER, (ii) identifier mapping
> and (iii) relation extraction, performed by BioREx of 12 common types of relations.
> The PubTator 3.0 processing pipeline: AIONER identifies six types of entities.
> Entity annotations are associated with database identifiers by specialized mappers and
> BioREx identifies relations between entities. PubTator 3.0 uses AIONER, a recently developed
> named entity recognition (NER) model, to recognize entities of six types: genes/proteins,
> chemicals, diseases, species, genetic variants, and cell lines. AIONER utilizes a flexible
> tagging scheme to integrate training data created separately into a single resource. These
> training datasets include NLM-Gene, NLM-Chem, NCBI-Disease, BC5CDR, tmVar3, Species-800,
> BioID and BioRED. Local abbreviations are identified using Ab3P.
>
> Entity mentions found by AIONER are normalized (linked) to a unique identifier in an
> appropriate entity database. Normalization is performed by a module designed for (or adapted
> to) each entity type, using the latest version. The recently-upgraded GNorm2 system normalizes
> genes to NCBI Gene identifiers and species mentions to NCBI Taxonomy. tmVar3, also recently
> upgraded, normalizes genetic variants; it uses dbSNP identifiers for variants listed in dbSNP
> and HGNV format otherwise. Chemicals are normalized by the NLM-Chem tagger to MeSH identifiers.
> TaggerOne normalizes diseases to MeSH and cell lines to Cellosaurus using a new
> normalization-only mode. This mode only applies the normalization model, which converts both
> mentions and lexicon names into high-dimensional TF-IDF vectors and learns a mapping, as
> before. However, it now augments the training data by mapping each lexicon name to itself,
> resulting in a large performance improvement for names present in the lexicon but not in the
> annotated training data. These enhancements provide a significant overall improvement in entity
> normalization performance.

---

## Preprocessing scripts

Before the main annotation tools run, two helper scripts prepare the input documents.

### `src/src/pipeline_steps/prepare_supplementary.py`

Converts supplementary files placed in `01_source/s/` into PDFs so that GROBID can process
them. It handles four file types:

- **PDF** — copied as-is into `01_source/s/<stem>/<stem>.pdf`
- **Word** (`.docx`, `.doc`) — converted to PDF, one PDF per document
- **Excel** (`.xlsx`, `.xls`) — converted to one PDF per worksheet, placed in
  `01_source/s/<stem>/tab_NN/<stem>.pdf`
- **PowerPoint** (`.pptx`, `.ppt`) — converted to PDF, one PDF per presentation

This script runs automatically at the start of each pipeline run when `01_source/s/` is
present. The converted PDFs are the inputs that GROBID and all subsequent annotation steps
actually see.

### LibreOffice (`soffice`)

LibreOffice is used by `src/src/pipeline_steps/prepare_supplementary.py` as the preferred converter for Word,
Excel, and PowerPoint files. It produces high-fidelity PDFs that preserve formatting and
layout. When LibreOffice is not installed the script falls back to `python-docx` +
`reportlab` for `.docx` files and `python-pptx` + `reportlab` for `.pptx` files (both
with reduced fidelity), and skips `.doc` and `.ppt` files entirely. Excel conversion
without LibreOffice also uses a `reportlab` fallback. Install with:

```
# macOS
brew install --cask libreoffice

# Ubuntu/Debian
sudo apt-get install -y libreoffice
```

### `src/pipeline_steps/pdf_to_bioc.py`

Wraps the GROBID REST API (expected at `http://localhost:8070`, typically run via Docker)
to convert PDFs into BioC XML. For each PDF it:

1. Sends the PDF to GROBID, which returns structured TEI XML
2. Parses the TEI XML and extracts text by section
3. Writes a BioC XML file with passages typed as `title`, `abstract`, `body`,
   `fig_caption`, and `table`

For **supplementary PDFs** (passed with `--supplementary`) the script uses a simpler
extraction mode — all content is collapsed into `title` + `body` — and falls back to
PyMuPDF for text extraction if GROBID returns an empty body. GROBID must be running
before this script is invoked.

---

## Overview of current pipeline

The pipeline starts with GROBID converting PDFs to BioC XML, then splits into two
independent annotation branches that both read from that GROBID output. All tools
are invoked in batch mode across all documents (main + supplementary) to amortize
model-loading startup costs.

```
01_source/ (PDFs)
     │
     │  prepare_supplementary.py converts non-PDF supplementary files first
     │
     ▼ pdf_to_bioc.py → GROBID (extracts structured text: title, abstract, body,
     │                          figure captions, tables)
02_grobid/ (BioC XML; no entity annotations yet)
     │
     ├──────────────────────────────┬──────────────────────────────────────┐
     │                              │                                      │
     ▼ GNorm2                       ▼ AIONER                              ▼ TaggerOne
(gene + species NER            (deep-learning NER for all            (joint NER + normalization;
 and normalization;             six entity types using                disease → MeSH/OMIM only;
 NCBI Gene IDs,                 NLM-Gene, NLM-Chem, BC5CDR,          reads GROBID output)
 NCBI Taxonomy IDs)             tmVar3 etc. training data;                 │
     │                           Ab3P for local abbreviations)        07_taggerone/
     │                              │
03_gnorm2/                     05_aioner/
     │                              │
     ▼ tmVar3                       ▼ NLMChem (+ Ab3P)
(variant NER and               (chemical normalization to
 normalization;                 MeSH identifiers;
 HGVS, RS#, CA#,               reads AIONER output — no NER)
 CorrespondingGene)                  │
     │                         06_nlmchem/
04_tmvar3/
(.PubTator + .BioC.XML)
     │
     └──────────────────────────────┴──────────────────────────────────────┘
                                    │
                          ▼ report_civic_pubtator.py
              report_<pmid>.html    annotated full text + entity summary tables
              report_<pmid>.tsv     normalized entity mention rows (one per unique mention+ID)
(reads: 04_tmvar3/ .PubTator → variants, genes, species, cell lines
        06_nlmchem/ BioC XML → chemicals (highlighted in purple)
        07_taggerone/ BioC XML → diseases (highlighted in rose))
```

### Output files

Five files are written to the publication root directory at the end of each run.

| File | Written by | Contents |
|---|---|---|
| `report_<pmid>.html` | `src/pipeline_steps/report_civic_pubtator.py` | Full annotated text for the main paper and each supplementary document, with entity mentions highlighted by type. Five collapsible summary tables (Variants, Genes, Chemicals, Diseases, Organisms) list each unique mention with its identifier, HGVS string (variants), and the documents it appears in. Pipeline stats and MANIFEST content are embedded at the top. |
| `report_<pmid>.tsv` | `src/pipeline_steps/report_civic_pubtator.py` | Tab-separated version of the same entity tables. Columns: `entity_category`, `entity_type`, `mention`, `identifier`, `identifier_name`, `hgvs`, `count`, `doc_keys`. One row per unique (mention, identifier) pair, sorted by descending count within each category. Suitable for downstream filtering or programmatic use. |
| `MANIFEST.txt` | `civic_pubtator.py` | Written at the start of the run. Records the tool version, run timestamp, input directory, and a size + modification-time inventory of all main and supplementary source files. |
| `pipeline_stats.log` | `civic_pubtator.py` | Human-readable run log appended throughout the pipeline. For each tool step and each input group (main paper + each supplementary), records the output directory, character count, word count, and per-file elapsed time. Ends with a `# Intermediates cleared` marker when cleanup ran. |
| `pipeline_stats.tsv` | `civic_pubtator.py` | Machine-readable counterpart to the log. Columns: `step_num`, `step_name`, `label`, `file`, `chars`, `words`, `time_s`. One row per output file per step, enabling cross-run performance comparisons. |

### Implementation notes vs. the PubTator 3.0 reference pipeline

The PubTator 3.0 paper describes TaggerOne running in a **normalization-only mode** that
takes pre-existing AIONER spans and applies only the normalization model, and covering both
diseases (MeSH) and cell lines (Cellosaurus). Our implementation differs in two ways:

- **No normalization-only mode.** The public TaggerOne v0.2.1 release always runs joint
  NER + normalization from scratch. The normalization-only mode was developed by NCBI
  specifically for PubTator 3.0 and was never publicly released. Passing AIONER output to
  TaggerOne would make no difference — it ignores pre-existing annotations in the input.

- **Disease-only model.** The `model_DISE.bin` model (the only disease/cell-line model in
  the public distribution) was trained on NCBI Disease + BC5CDR corpora with
  `--entityTypes Disease`. It produces `Disease` annotations normalized to MeSH/OMIM
  identifiers. There is no cell line model and no Cellosaurus lexicon in the public release.

**Cell line annotations** in the report come from **GNorm2** (step 2), which does recognize
cell line names (NIH3T3, SK-MEL-208, HEK293, etc.) and propagates them through tmVar3 into
the PubTator files. However, GNorm2 assigns **NCBI Taxonomy IDs** as identifiers (9606 =
human, 10090 = mouse) rather than Cellosaurus accessions (CVCL_xxxx). The NER is working;
cell-line-specific normalization to Cellosaurus would require a separate tool.

---

## Models used by each pipeline step

Each annotation tool loads one or more trained models when processing documents. The table below lists the specific model files used in our current configuration, with paths relative to the repository root. GROBID runs as an external Docker service; its internal model weights are not tracked here.

| Pipeline step | Tool / sub-step | Model file | File date |
|---|---|---|---|
| 03_gnorm2 | GNorm2 — Gene NER (Bioformer, Python) | `GNorm2/gnorm_trained_models/GeneNER/GeneNER-Bioformer-BEST.h5` | 2025-03-26 |
| 03_gnorm2 | GNorm2 — Species Assignment (Bioformer, Python) | `GNorm2/gnorm_trained_models/SpeAss/SpeAss-Bioformer-SG-BEST.h5` | 2025-03-26 |
| 03_gnorm2 | GNorm2 — Gene Name Recognition (CRF, Java) | `GNorm2/Dictionary/GNR.Model` | 2025-03-26 |
| 03_gnorm2 | GNorm2 — Concept Similarity (CRF, Java) | `GNorm2/Dictionary/SimConcept.Model` | 2025-03-26 |
| 04_tmvar3 | tmVar3 — Variant Mention Extraction (CRF++) | `tmvar/CRF/MentionExtractionUB.Model` | 2022-04-07 |
| 04_tmvar3 | tmVar3 — Variant Component Extraction (CRF++) | `tmvar/CRF/ComponentExtraction.Model` | 2022-04-07 |
| 05_aioner | AIONER — All-entity NER (Bioformer, Python) | `AIONER/AIONER_trained_models/AIONER/Bioformer-Softmax-BEST-AIO_tmvar3.20230416.h5` | 2023-04-16 |
| 06_nlmchem | NLMChem — Chemical normalization (TF-IDF dictionaries) | `NLMChem/NLMChemTaggerNormalizer/CHEM_NORM/data/` *(multiple files — see below)* | 2023-11-30 |
| 07_taggerone | TaggerOne — Disease NER + normalization (semi-Markov) | `TaggerOne/output/model_DISE.bin` | 2016-07-16 |

### Model descriptions

#### GNorm2 (step 03_gnorm2)

GNorm2 is a three-phase pipeline. Phases 1 and 3 are Java-based (GNormPlus) and use CRF models stored in `GNorm2/Dictionary/`; phase 2 is a Python deep-learning step.

**GeneNER-Bioformer-BEST.h5** — Bioformer transformer fine-tuned for gene and protein name recognition. "BEST" denotes the checkpoint with the highest validation-set F1 during training. Primary training corpus: NLM-Gene. Uses Bioformer-cased-v1.0 as the pre-trained base encoder (see below).

**SpeAss-Bioformer-SG-BEST.h5** — Bioformer transformer fine-tuned for species assignment. Given a passage with gene annotations, it assigns each gene mention to a species context (e.g., human vs. mouse). "SG" denotes a single-gene-per-annotation output configuration. Trained on Species-800 corpus. Also uses Bioformer-cased-v1.0.

**Bioformer-cased-v1.0** (shared base encoder for both models above) — An 8-layer BERT-like transformer (42 M parameters) pre-trained from scratch on 33 million PubMed abstracts and 1 million PMC full-text articles. Uses a biomedical-domain WordPiece vocabulary of 32,768 tokens. Approximately 3× faster than BERT-base while achieving comparable or better performance on biomedical NER benchmarks.

**GNR.Model** — CRF++ sequence-labeling model for gene name recognition inside GNormPlus (Java). Used in both the Species Recognition phase (step 1, to find gene spans that help bound species context) and the Gene Normalization phase (step 3) of the GNorm2 pipeline.

**SimConcept.Model** — CRF++ model used by GNormPlus's SimConcept normalization module, which clusters synonymous gene name surface forms to disambiguate multi-gene mentions and resolve the correct NCBI Gene ID.

#### tmVar3 (step 04_tmvar3)

tmVar3 uses two sequential CRF++ models for variant extraction, followed by Java-based HGVS construction and database lookups.

**MentionExtractionUB.Model** (232 MB) — Identifies text spans that describe genetic variants: DNA mutations, protein changes, copy number variants, SNPs, and fusion genes. "UB" refers to the UniqueB-IO sequence-labeling scheme used during training. Trained on a corpus combining tmVar annotations with BioCreative V CDR and additional full-text data.

**ComponentExtraction.Model** — Decomposes each identified variant span into structured subfields (e.g., reference allele, alternate allele, genomic position, variant type). These components are used downstream by `ToHGVs.java` to construct HGVS notation and to query dbSNP/ClinGen RS# databases.

#### AIONER (step 05_aioner)

**Bioformer-Softmax-BEST-AIO_tmvar3.20230416.h5** — Bioformer fine-tuned with a softmax output head using the All-In-One (AIO) multi-entity tagging scheme. The AIO scheme uses a unified label set so that a single model forward pass recognizes all six entity types simultaneously: Gene, Chemical, Disease, Mutation, Species, and CellLine. The "tmvar3" suffix indicates training with tmVar3-compatible variant annotations; "20230416" is the training date. Training data spans eight corpora: NLM-Gene, NLM-Chem, NCBI-Disease, BC5CDR, tmVar3, Species-800, BioID, and BioRED. Uses Bioformer-cased-v1.0 as the pre-trained base encoder.

#### NLMChem (step 06_nlmchem)

NLMChem chemical normalization is **not** a neural network. It uses TF-IDF sparse vector matching to link chemical surface forms to MeSH identifiers. All data files are dated 2023-11-30 and represent a November 2023 MeSH snapshot.

| File | Purpose |
|---|---|
| `data/name2ids_2023.txt.gz` | Chemical surface-form → MeSH ID lookup table |
| `data/id2ids_2023.txt.gz` | MeSH ID equivalence / cross-reference table |
| `data/chem_ids_2023.tsv` | MeSH ID → entity type metadata |
| `data/c_template_cache_2023.txt.gz` | Pre-computed TF-IDF character-level vector templates |
| `data/p_template_cache_2023.txt.gz` | Pre-computed TF-IDF phrase-level vector templates |
| `data/abbr_frequency_2020.json.gz` | Abbreviation frequency statistics (2020 snapshot) used for disambiguation |

#### TaggerOne (step 07_taggerone)

**model_DISE.bin** — A semi-Markov CRF model jointly trained for disease NER and normalization. Uses TF-IDF vector representations to map mention surface forms directly to MeSH or OMIM identifiers without a separate entity-linking step. Trained on the combined NCBI Disease and BC5CDR disease corpora. This is the only disease-trained model included in the public TaggerOne v0.2.1 distribution (released 2016). It does not incorporate deep learning; retraining requires approximately 40 GB of RAM and is driven by the CRF optimization loop described in Leaman & Lu (2016).

---

## File locations

Each publication lives in its own directory named by PMID (e.g. `/data/pub-data/28783719/`).
Supplementary PDFs follow the same step-numbered structure one level deeper under
`s/<supp_stem>/` within each step directory.

```
<pub_dir>/
├── 01_source/
│   ├── <paper>.pdf
│   └── s/
│       └── <supp_stem>/
│           └── <supp>.pdf          ← created by src/pipeline_steps/prepare_supplementary.py
│
├── 02_grobid/
│   ├── <paper>.xml
│   └── s/<supp_stem>/<supp>.xml
│
├── 03_gnorm2/
│   ├── <paper>.xml
│   └── s/<supp_stem>/<supp>.xml
│
├── 04_tmvar3/
│   ├── <paper>.xml.BioC.XML        ← BioC XML with variant + gene annotations
│   ├── <paper>.xml.PubTator        ← PubTator flat-file format (read by the report)
│   └── s/<supp_stem>/
│       ├── <supp>.xml.BioC.XML
│       └── <supp>.xml.PubTator
│
├── 05_aioner/
│   ├── <paper>.xml
│   └── s/<supp_stem>/<supp>.xml
│
├── 06_nlmchem/
│   ├── <paper>.xml
│   ├── abbreviations/<paper>.tsv   ← Ab3P abbreviation table for this document
│   └── s/<supp_stem>/
│       ├── <supp>.xml
│       └── abbreviations/<supp>.tsv
│
├── 07_taggerone/
│   ├── <paper>.xml
│   └── s/<supp_stem>/<supp>.xml
│
├── MANIFEST.txt                    ← tool version, run timestamp, source file inventory
├── pipeline_stats.tsv              ← per-document runtime and character-count stats per step
├── pipeline_stats.log              ← full human-readable log of the pipeline run
└── report_<pmid>.html              ← final HTML report
```

Hidden staging directories (dot-prefixed, e.g. `.gnorm2_staging_in/`,
`.tmvar3_staging_out/`, `.nlmchem_abbr_staging/`) are created automatically during batch
processing and removed on completion unless `--no-clear-intermediates` is passed.
