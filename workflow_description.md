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

### `scripts/prepare_supplementary.py`

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

LibreOffice is used by `prepare_supplementary.py` as the preferred converter for Word,
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

### `scripts/pdf_to_bioc.py`

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
                     report_<pmid>.html
(04_tmvar3/ .PubTator → variants, genes, species, cell lines
 06_nlmchem/ BioC XML → drugs (highlighted in purple)
 07_taggerone/ BioC XML → diseases (highlighted in rose))
```

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
│           └── <supp>.pdf          ← created by prepare_supplementary.py
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
