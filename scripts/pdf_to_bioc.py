#!/usr/bin/env python3
import os, sys, hashlib, requests
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

def tei_to_sections(tei_xml):
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

def write_bioc_xml(doc_id, title, abstract, body, out_path):
    passages = []
    offset = 0

    for text, ptype in [(title, "title"), (abstract, "abstract"), (body, "body")]:
        text = text.strip()
        if not text:          # skip empty passages — this is critical
            continue
        # strip non-XML characters
        text = "".join(c for c in text if c.isprintable() or c in "\t\n\r")
        passages.append((ptype, offset, text))
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

        for ptype, poffset, text in passages:
            f.write('  <passage>\n')
            f.write(f'    <infon key="type">{ptype}</infon>\n')
            f.write(f'    <offset>{poffset}</offset>\n')
            f.write(f'    <text>{escape(text)}</text>\n')
            f.write('  </passage>\n')

        f.write('</document>\n')
        f.write('</collection>\n')

def process_folder(input_dir, output_dir):
    os.makedirs(output_dir, exist_ok=True)
    for fname in sorted(os.listdir(input_dir)):
        if not fname.lower().endswith(".pdf"):
            continue
        pdf_path = os.path.join(input_dir, fname)
        stem = os.path.splitext(fname)[0]
        # Use stem as doc ID if it's numeric (e.g. a PMID), else hash it
        doc_id = stem if stem.isdigit() else str(int(hashlib.md5(stem.encode()).hexdigest(), 16) % 10**8)

        print(f"Processing {fname}...")
        try:
            tei_xml = extract_with_grobid(pdf_path)
            title, abstract, body = tei_to_sections(tei_xml)
            out_path = os.path.join(output_dir, stem + ".xml")
            write_bioc_xml(doc_id, title, abstract, body, out_path)
            print(f"  → {out_path}  (title={bool(title)}, abstract={bool(abstract)}, body={bool(body)})")
        except Exception as e:
            print(f"  ERROR on {fname}: {e}")

if len(sys.argv) != 3:
    sys.exit("Usage: pdf_to_bioc.py <input_dir> <output_dir>")
check_grobid()
process_folder(sys.argv[1], sys.argv[2])
