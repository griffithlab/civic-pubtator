#!/usr/bin/env python3
import argparse, hashlib, os, sys, requests
import xml.etree.ElementTree as ET
from xml.sax.saxutils import escape

GROBID_BASE = "http://localhost:8070"
GROBID_URL = f"{GROBID_BASE}/api/processFulltextDocument"

def check_grobid():
    try:
        resp = requests.get(f"{GROBID_BASE}/api/isalive", timeout=5)
        if resp.status_code == 200:
            return
    except requests.ConnectionError:
        pass
    sys.exit(f"ERROR: GROBID does not appear to be running at {GROBID_BASE}\n"
             "Start it with: docker run --rm -p 8070:8070 lfoppiano/grobid:0.8.1")

def extract_with_grobid(pdf_path):
    with open(pdf_path, "rb") as f:
        resp = requests.post(GROBID_URL,
                             files={"input": f},
                             data={"consolidateHeader": 1},
                             timeout=120)
    resp.raise_for_status()
    return resp.text

def clean_text(text):
    return "".join(c for c in text if c.isprintable() or c in "\t\n\r")

def tei_to_sections(tei_xml):
    """Extract title, abstract, body from a structured scientific article."""
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    root = ET.fromstring(tei_xml)

    title_el = root.find(".//tei:titleStmt/tei:title", ns)
    title = " ".join(title_el.itertext()).strip() if title_el is not None else ""

    abstract_el = root.find(".//tei:abstract", ns)
    abstract = " ".join(abstract_el.itertext()).strip() if abstract_el is not None else ""

    body_parts = []
    for p in root.findall(".//tei:body//tei:p", ns):
        para = " ".join(p.itertext()).strip()
        if para:
            body_parts.append(para)
    body = " ".join(body_parts)

    return title, abstract, body

def extract_figures_and_tables(tei_xml):
    """Return (type, text) pairs for figure captions and tables found in the TEI.

    Tables use type 'table'; figure captions use type 'fig_caption'.
    Tables are flattened row-by-row so variant mentions embedded in cells
    are visible to downstream text-mining tools.
    """
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    root = ET.fromstring(tei_xml)
    passages = []

    for figure in root.findall(".//tei:figure", ns):
        head = figure.find("tei:head", ns)
        head_text = " ".join(head.itertext()).strip() if head is not None else ""

        if figure.get("type") == "table":
            parts = [head_text] if head_text else []
            for row in figure.findall(".//tei:row", ns):
                cells = [" ".join(c.itertext()).strip()
                         for c in row.findall("tei:cell", ns)]
                row_text = " ".join(c for c in cells if c)
                if row_text:
                    parts.append(row_text)
            text = " ".join(parts)
            if text:
                passages.append(("table", text))
        else:
            desc = figure.find("tei:figDesc", ns)
            desc_text = " ".join(desc.itertext()).strip() if desc is not None else ""
            # figDesc often starts with the same label as head; drop the head prefix if so
            if head_text and desc_text.startswith(head_text):
                text = desc_text
            else:
                text = " ".join(t for t in [head_text, desc_text] if t)
            if text:
                passages.append(("fig_caption", text))

    return passages


def tei_to_sections_supp(tei_xml):
    """
    For supplementary files: collapse all content into a single body passage.
    Returns (grobid_title, body) — caller decides whether to use grobid_title
    or a path-derived fallback.  Body may be empty if GROBID found no text.
    """
    ns = {"tei": "http://www.tei-c.org/ns/1.0"}
    root = ET.fromstring(tei_xml)

    title_el = root.find(".//tei:titleStmt/tei:title", ns)
    grobid_title = " ".join(title_el.itertext()).strip() if title_el is not None else ""

    parts = []
    abstract_el = root.find(".//tei:abstract", ns)
    if abstract_el is not None:
        text = " ".join(abstract_el.itertext()).strip()
        if text:
            parts.append(text)
    # Capture all text-bearing elements in the body, not just <p>
    body_el = root.find(".//tei:body", ns)
    if body_el is not None:
        for el in body_el.iter():
            if el.tag == f"{{{ns['tei']}}}body":
                continue
            text = (el.text or "").strip()
            if text:
                parts.append(text)
    body = " ".join(parts)

    return grobid_title, body

def extract_text_pymupdf(pdf_path):
    """Extract all text from a PDF using PyMuPDF (fallback for image-heavy PDFs)."""
    try:
        import fitz
    except ImportError:
        return ""
    import re
    doc = fitz.open(pdf_path)
    pages = []
    for page in doc:
        text = re.sub(r'\s+', ' ', page.get_text()).strip()
        if text:
            pages.append(text)
    doc.close()
    return " ".join(pages)

def write_bioc_xml(doc_id, passages, out_path):
    """Write a BioC XML document. passages is a list of (type, text) pairs."""
    offset = 0
    rendered = []
    for ptype, text in passages:
        text = clean_text(text.strip())
        if not text:
            continue
        rendered.append((ptype, offset, text))
        offset += len(text) + 1

    with open(out_path, "w", encoding="utf-8") as f:
        f.write('<?xml version="1.0" encoding="UTF-8"?>\n')
        f.write('<!DOCTYPE collection SYSTEM "BioC.dtd">\n')
        f.write('<collection>\n')
        f.write('<source>PubMed</source>\n')
        f.write('<date>20220101</date>\n')
        f.write('<key>BioC.key</key>\n')
        f.write('<document>\n')
        f.write(f'<id>{doc_id}</id>\n')
        for ptype, poffset, text in rendered:
            f.write('  <passage>\n')
            f.write(f'    <infon key="type">{ptype}</infon>\n')
            f.write(f'    <offset>{poffset}</offset>\n')
            f.write(f'    <text>{escape(text)}</text>\n')
            f.write('  </passage>\n')
        f.write('</document>\n')
        f.write('</collection>\n')

def process_folder(input_dir, output_dir, supplementary=False):
    os.makedirs(output_dir, exist_ok=True)
    # Used to derive fallback title for supplementary files
    parent_dir_name = os.path.basename(os.path.abspath(input_dir))

    for fname in sorted(os.listdir(input_dir)):
        if not fname.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(input_dir, fname)
        stem = os.path.splitext(fname)[0]
        doc_id = stem if stem.isdigit() else str(int(hashlib.md5(stem.encode()).hexdigest(), 16) % 10**8)
        out_path = os.path.join(output_dir, stem + ".xml")

        print(f"Processing {fname}...")
        try:
            tei_xml = extract_with_grobid(pdf_path)

            if supplementary:
                grobid_title, body = tei_to_sections_supp(tei_xml)

                # Fall back to PyMuPDF if GROBID returned no body text
                if not body:
                    body = extract_text_pymupdf(pdf_path)
                    if body:
                        print(f"  (GROBID returned no body; used PyMuPDF fallback)")

                # Use GROBID title if it looks reasonable, else derive from path
                if grobid_title and len(grobid_title) <= 200:
                    title = grobid_title
                elif parent_dir_name != stem:
                    title = f"{stem} — {parent_dir_name}"
                else:
                    title = stem
                write_bioc_xml(doc_id, [("title", title), ("body", body)], out_path)
                print(f"  → {out_path}  (title={bool(title)}, body={bool(body)})")
            else:
                title, abstract, body = tei_to_sections(tei_xml)
                extra = extract_figures_and_tables(tei_xml)
                n_caps = sum(1 for t, _ in extra if t == "fig_caption")
                n_tbls = sum(1 for t, _ in extra if t == "table")
                write_bioc_xml(doc_id,
                               [("title", title), ("abstract", abstract), ("body", body)] + extra,
                               out_path)
                print(f"  → {out_path}  (title={bool(title)}, abstract={bool(abstract)}, "
                      f"body={bool(body)}, fig_captions={n_caps}, tables={n_tbls})")

        except Exception as e:
            print(f"  ERROR on {fname}: {e}")

def main():
    parser = argparse.ArgumentParser(
        description="Convert PDFs to BioC XML via GROBID."
    )
    parser.add_argument("input_dir",  help="Folder containing input PDF files")
    parser.add_argument("output_dir", help="Folder where BioC XML files will be written")
    parser.add_argument("--supplementary", action="store_true",
                        help="Supplementary mode: treat all content as body, "
                             "derive title from path context rather than article structure")
    args = parser.parse_args()

    check_grobid()
    process_folder(os.path.abspath(args.input_dir), os.path.abspath(args.output_dir),
                   supplementary=args.supplementary)

if __name__ == "__main__":
    main()
