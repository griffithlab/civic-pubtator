#!/usr/bin/env python3
import argparse, os, shutil, subprocess, sys, tempfile

# ── LibreOffice detection ─────────────────────────────────────────────────────

def find_soffice():
    path = shutil.which("soffice")
    if path:
        return path
    mac_path = "/Applications/LibreOffice.app/Contents/MacOS/soffice"
    if os.path.isfile(mac_path):
        return mac_path
    return None

def soffice_convert(soffice, src, out_dir):
    """Convert src to PDF in out_dir via soffice. Returns path of created PDF."""
    # Set LD_LIBRARY_PATH so soffice.bin can find its internal libraries on Linux
    # without requiring a system-wide ldconfig entry (which causes conflicts).
    env = os.environ.copy()
    env['LD_LIBRARY_PATH'] = '/usr/lib/libreoffice/program:' + env.get('LD_LIBRARY_PATH', '')
    result = subprocess.run(
        [soffice, "--headless", "--convert-to", "pdf", "--outdir", out_dir, src],
        capture_output=True, text=True, env=env,
    )
    if result.returncode != 0:
        raise RuntimeError(f"soffice failed (exit {result.returncode}):\nSTDERR: {result.stderr.strip()}\nSTDOUT: {result.stdout.strip()}")
    stem = os.path.splitext(os.path.basename(src))[0]
    return os.path.join(out_dir, stem + ".pdf")

# ── Per-type processors ───────────────────────────────────────────────────────

def process_pdf(src, stem, s_dir):
    out_dir = os.path.join(s_dir, stem)
    os.makedirs(out_dir, exist_ok=True)
    dst = os.path.join(out_dir, stem + ".pdf")
    shutil.copy2(src, dst)
    print(f"  Copied → {dst}")

def process_word(src, stem, s_dir, soffice):
    out_dir = os.path.join(s_dir, stem)
    os.makedirs(out_dir, exist_ok=True)

    if soffice:
        created = soffice_convert(soffice, src, out_dir)
        # soffice names output after the source stem; rename to match our convention
        dst = os.path.join(out_dir, stem + ".pdf")
        if created != dst:
            os.replace(created, dst)
        print(f"  Word → PDF (soffice): {dst}")
        return

    # ── Fallback: python-docx + reportlab (.docx only) ───────────────────────
    ext = os.path.splitext(src)[1].lower()
    if ext == ".doc":
        print("  WARNING: .doc requires LibreOffice for conversion — skipping.")
        print("           macOS: brew install --cask libreoffice")
        print("           Ubuntu: sudo apt-get install -y libreoffice")
        return
    try:
        from docx import Document
    except ImportError:
        sys.exit("ERROR: python-docx not installed. Run: pip3 install python-docx")
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError:
        sys.exit("ERROR: reportlab not installed. Run: pip3 install reportlab")

    dst = os.path.join(out_dir, stem + ".pdf")
    doc = Document(src)
    styles = getSampleStyleSheet()
    story = []
    for para in doc.paragraphs:
        text = para.text.strip()
        if text:
            story.append(Paragraph(text, styles["Normal"]))
            story.append(Spacer(1, 4))
    SimpleDocTemplate(dst, pagesize=letter).build(story)
    print(f"  Word → PDF (reportlab fallback): {dst}")

def process_powerpoint(src, stem, s_dir, soffice):
    out_dir = os.path.join(s_dir, stem)
    os.makedirs(out_dir, exist_ok=True)

    if soffice:
        created = soffice_convert(soffice, src, out_dir)
        dst = os.path.join(out_dir, stem + ".pdf")
        if created != dst:
            os.replace(created, dst)
        print(f"  PowerPoint → PDF (soffice): {dst}")
        return

    # Fallback: python-pptx + reportlab (.pptx only)
    ext = os.path.splitext(src)[1].lower()
    if ext == ".ppt":
        print("  WARNING: .ppt requires LibreOffice for conversion — skipping.")
        print("           macOS: brew install --cask libreoffice")
        print("           Ubuntu: sudo apt-get install -y libreoffice")
        return
    try:
        from pptx import Presentation
    except ImportError:
        sys.exit("ERROR: python-pptx not installed. Run: pip3 install python-pptx")
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer
        from reportlab.lib.styles import getSampleStyleSheet
    except ImportError:
        sys.exit("ERROR: reportlab not installed. Run: pip3 install reportlab")

    dst = os.path.join(out_dir, stem + ".pdf")
    prs = Presentation(src)
    styles = getSampleStyleSheet()
    story = []
    for slide_num, slide in enumerate(prs.slides, start=1):
        story.append(Paragraph(f"<b>Slide {slide_num}</b>", styles["Heading2"]))
        for shape in slide.shapes:
            if shape.has_text_frame:
                for para in shape.text_frame.paragraphs:
                    text = para.text.strip()
                    if text:
                        story.append(Paragraph(text, styles["Normal"]))
                        story.append(Spacer(1, 4))
        story.append(Spacer(1, 12))
    SimpleDocTemplate(dst, pagesize=letter).build(story)
    print(f"  PowerPoint → PDF (reportlab fallback): {dst}")


def process_excel(src, stem, s_dir, soffice, max_rows):
    ext = os.path.splitext(src)[1].lower()
    tmp_xls_dir = None
    if not max_rows:
        max_rows = float('inf')

    if ext == ".xls":
        if soffice:
            tmp_xls_dir = tempfile.mkdtemp()
            env = os.environ.copy()
            env['LD_LIBRARY_PATH'] = '/usr/lib/libreoffice/program:' + env.get('LD_LIBRARY_PATH', '')
            result = subprocess.run(
                [soffice, "--headless", "--convert-to", "xlsx", "--outdir", tmp_xls_dir, src],
                capture_output=True, text=True, env=env,
            )
            if result.returncode != 0:
                shutil.rmtree(tmp_xls_dir, ignore_errors=True)
                raise RuntimeError(
                    f"soffice .xls→.xlsx failed:\nSTDERR: {result.stderr.strip()}\nSTDOUT: {result.stdout.strip()}"
                )
            src = os.path.join(tmp_xls_dir, stem + ".xlsx")
            print(f"  .xls → .xlsx (soffice): {src}")
        else:
            # fallback: xlrd reads .xls; write to temp .xlsx so openpyxl can load it below
            try:
                import xlrd
            except ImportError:
                sys.exit("ERROR: .xls requires LibreOffice or xlrd. Run: pip3 install xlrd")
            try:
                import openpyxl as _openpyxl
            except ImportError:
                sys.exit("ERROR: openpyxl not installed. Run: pip3 install openpyxl")
            tmp_xls_dir = tempfile.mkdtemp()
            wb_xls = xlrd.open_workbook(src)
            wb_out = _openpyxl.Workbook()
            wb_out.remove(wb_out.active)
            for sname in wb_xls.sheet_names():
                ws_in = wb_xls.sheet_by_name(sname)
                ws_out = wb_out.create_sheet(title=sname)
                for i in range(min(ws_in.nrows, max_rows)):
                    ws_out.append(ws_in.row_values(i))
            wb_xls.release_resources()
            tmp_xlsx = os.path.join(tmp_xls_dir, stem + ".xlsx")
            wb_out.save(tmp_xlsx)
            wb_out.close()
            src = tmp_xlsx
            print(f"  .xls → .xlsx (xlrd): {src}")

    try:
        import openpyxl
    except ImportError:
        sys.exit("ERROR: openpyxl not installed. Run: pip3 install openpyxl")

    wb = openpyxl.load_workbook(src, data_only=True)

    for tab_num, sheet_name in enumerate(wb.sheetnames, start=1):
        ws = wb[sheet_name]
        rows = []
        for i, row in enumerate(ws.iter_rows(values_only=True)):
            if i >= max_rows:
                break
            rows.append(row)

        if not rows:
            print(f"  Sheet '{sheet_name}' (tab {tab_num}): empty, skipping")
            continue

        tab_label = f"tab_{tab_num:02d}"
        out_dir = os.path.join(s_dir, stem, tab_label)
        os.makedirs(out_dir, exist_ok=True)
        dst = os.path.join(out_dir, f"{stem}.pdf")

        if soffice:
            from openpyxl.utils import get_column_letter
            tmp_dir = tempfile.mkdtemp()
            try:
                tmp_wb = openpyxl.Workbook()
                tmp_ws = tmp_wb.active
                tmp_ws.title = sheet_name
                for row in rows:
                    tmp_ws.append([v if v is not None else "" for v in row])

                # Auto-size columns based on content
                ncols = max(len(r) for r in rows)
                for col_idx in range(1, ncols + 1):
                    max_len = max(
                        len(str(r[col_idx - 1])) if col_idx <= len(r) and r[col_idx - 1] is not None else 0
                        for r in rows
                    )
                    tmp_ws.column_dimensions[get_column_letter(col_idx)].width = max(12, min(max_len + 2, 50))

                # Landscape, A3, fit all columns onto one page wide
                tmp_ws.page_setup.orientation = "landscape"
                tmp_ws.page_setup.paperSize = 8  # A3
                tmp_ws.page_setup.fitToWidth = 1
                tmp_ws.page_setup.fitToHeight = 0
                tmp_ws.sheet_properties.pageSetUpPr.fitToPage = True

                # Header: sheet name centred, tab number on the right
                tmp_ws.oddHeader.center.text = sheet_name
                tmp_ws.oddHeader.right.text  = f"Tab {tab_num}"

                tmp_xlsx = os.path.join(tmp_dir, f"{stem}.xlsx")
                tmp_wb.save(tmp_xlsx)
                created = soffice_convert(soffice, tmp_xlsx, tmp_dir)
                shutil.move(created, dst)
            finally:
                shutil.rmtree(tmp_dir, ignore_errors=True)
            print(f"  Sheet '{sheet_name}' (tab {tab_num}, {len(rows)} rows) → {dst} (soffice)")

        else:
            # ── Fallback: reportlab ───────────────────────────────────────────
            try:
                from reportlab.lib import colors
                from reportlab.lib.pagesizes import landscape, letter
                from reportlab.lib.styles import getSampleStyleSheet
                from reportlab.lib.units import inch
                from reportlab.platypus import SimpleDocTemplate, Spacer, Table, TableStyle, Paragraph
            except ImportError:
                sys.exit("ERROR: reportlab not installed. Run: pip3 install reportlab")

            MARGINS = 0.5 * inch
            MIN_COL_WIDTH = 1.3 * inch

            str_rows = [[str(v) if v is not None else "" for v in row] for row in rows]
            ncols = max(len(r) for r in str_rows)
            str_rows = [r + [""] * (ncols - len(r)) for r in str_rows]

            col_width  = max(MIN_COL_WIDTH, landscape(letter)[0] / ncols)
            page_width = max(landscape(letter)[0], ncols * col_width + 2 * MARGINS)
            page_height = landscape(letter)[1]
            font_size  = max(5, min(8, int(col_width / 0.12)))

            styles = getSampleStyleSheet()
            title = Paragraph(f"<b>{sheet_name}</b>  <font size='8'>(Tab {tab_num})</font>",
                              styles["Normal"])

            table = Table(str_rows, colWidths=[col_width] * ncols, repeatRows=1)
            table.setStyle(TableStyle([
                ("BACKGROUND",     (0, 0), (-1,  0), colors.grey),
                ("TEXTCOLOR",      (0, 0), (-1,  0), colors.whitesmoke),
                ("FONTSIZE",       (0, 0), (-1, -1), font_size),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.lightgrey]),
                ("GRID",           (0, 0), (-1, -1), 0.25, colors.black),
                ("VALIGN",         (0, 0), (-1, -1), "TOP"),
                ("WORDWRAP",       (0, 0), (-1, -1), True),
            ]))
            SimpleDocTemplate(dst, pagesize=(page_width, page_height),
                              leftMargin=MARGINS, rightMargin=MARGINS,
                              topMargin=MARGINS, bottomMargin=MARGINS).build(
                [title, Spacer(1, 0.15 * inch), table])
            print(f"  Sheet '{sheet_name}' (tab {tab_num}, {len(rows)} rows) → {dst} (reportlab fallback)")

    wb.close()
    if tmp_xls_dir:
        shutil.rmtree(tmp_xls_dir, ignore_errors=True)

# ── Main ──────────────────────────────────────────────────────────────────────

IGNORED_FILES = {".DS_Store"}

def main():
    parser = argparse.ArgumentParser(
        description="Convert supplementary files in <input_dir>/s/ to PDFs."
    )
    parser.add_argument("input_dir",
                        help="Source directory containing an s/ subdirectory")
    parser.add_argument("--no-libreoffice", action="store_true",
                        help="Use the reportlab/python-docx fallback even if LibreOffice is installed")
    parser.add_argument("--max-rows", type=int, default=1000, metavar="N",
                        help="Maximum rows to read per Excel sheet tab when converting "
                             ".xls/.xlsx to PDF (default: 1000; use 0 for no limit). "
                             "This caps the size of each converted table. In the main "
                             "pipeline a second filter, --max-chars, removes any document "
                             "whose total converted text still exceeds the character limit "
                             "after this row cap is applied.")
    args = parser.parse_args()

    if args.no_libreoffice:
        soffice = None
        print("LibreOffice disabled by --no-libreoffice; using reportlab/python-docx fallback.")
    else:
        soffice = find_soffice()
        if soffice:
            print(f"LibreOffice found: {soffice}")
        else:
            print("WARNING: LibreOffice (soffice) not found.")
            print("         Word and Excel conversion will use a basic fallback with reduced fidelity.")
            print("         For best results install LibreOffice:")
            print("           macOS:  brew install --cask libreoffice")
            print("           Ubuntu: sudo apt-get install -y libreoffice\n")

    input_dir = os.path.abspath(args.input_dir)
    s_dir = os.path.join(input_dir, "s")

    if not os.path.isdir(s_dir):
        print(f"No s/ subdirectory found in {input_dir}, nothing to do.")
        sys.exit(0)

    for fname in sorted(os.listdir(s_dir)):
        fpath = os.path.join(s_dir, fname)
        if not os.path.isfile(fpath) or fname in IGNORED_FILES or fname.startswith("~$"):
            continue

        stem = os.path.splitext(fname)[0]
        ext  = os.path.splitext(fname)[1].lower()

        print(f"\nProcessing: {fname}")

        if ext == ".pdf":
            process_pdf(fpath, stem, s_dir)
        elif ext in (".docx", ".doc"):
            process_word(fpath, stem, s_dir, soffice)
        elif ext in (".xlsx", ".xls"):
            process_excel(fpath, stem, s_dir, soffice, args.max_rows)
        elif ext in (".pptx", ".ppt"):
            process_powerpoint(fpath, stem, s_dir, soffice)
        else:
            print(f"  Unsupported type ({ext}), skipping.")

if __name__ == "__main__":
    main()
