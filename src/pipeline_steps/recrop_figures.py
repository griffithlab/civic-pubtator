#!/usr/bin/env python3
"""
recrop_figures.py — Re-crop figure images out of the source PDFs using the
GROBID TEI already saved in 02_grobid/, with a PyMuPDF layout heuristic for
figures GROBID could not box. Needs no GROBID server and never writes inside
the publication directories: everything goes under --out.

Why
---
pdf_to_bioc.save_figure_images() crops a figure from GROBID's <graphic> box
when there is one, else from the <figure> box. GROBID only reports <graphic>
boxes for embedded bitmaps, so vector figures (most charts, survival curves,
forest plots) fall back to the <figure> box. That box covers the text GROBID
attached to the figure (usually just the caption, sometimes stray body text),
not the drawing, so those crops are caption strips or paragraphs.

What this does, per figure
--------------------------
  * GROBID gave a <graphic> box: crop it as before, widened to take in touching
    vector items and short labels (axis titles, panel letters) that sit just
    outside the bitmap (--no-expand-graphic to disable).
  * Otherwise (the layout heuristic):
      1. Find the caption: the text block starting "Figure N" / "Fig. N" or
         containing the start of the TEI caption, preferring the page and
         position GROBID's figure coords point at.
      2. Collect the page's graphics: clusters of vector drawings
         (page.cluster_drawings) and placed images, ignoring page rules,
         header/footer furniture and anything inside a GROBID table box.
      3. Bound the figure zone above the caption by the nearest body-text
         paragraph, other caption or table in the same column (or below the
         caption, or beside it, when nothing is above).
      4. Crop the graphics in that zone plus the short text blocks touching
         them. The caption itself is left out: it is already in the TEI and
         in figures.json.
      5. If no caption or no graphics are found, fall back to GROBID's
         <figure> box, as the old cropper did (source "figure_fallback",
         reason "fallback_<why>"), unless that box is mostly text (text
         blocks cover >= 35% of it and graphics < 5%): then write no image
         (source "none") rather than a caption- or paragraph-only crop.
Tables are cropped exactly as pdf_to_bioc.py does (their <figure> box covers
the table itself).

Output
------
  <out>/<pub_id>/[<rel>/]<stem>/<id>_p<page>.png + figures.json
      Same layout and schema as 02_grobid/[<rel>/]figures/<stem>/figures.json,
      plus per item: "grobid_box" (graphic | figure | none: the box the old
      cropper used), "reason", and "caption_bbox" ([page, x0, y0, x1, y1] of
      the caption located in the PDF, figures only). Figure "source" is one of
      graphic | layout | figure_fallback | none; tables keep graphic | figure | none.
  <out>/recrop_summary.tsv   one row per figure/table
  <out>/review.html          (--review) old vs new crops for every figure not
                             boxed by GROBID's <graphic>, to eyeball results

Usage
-----
  python3 src/pipeline_steps/recrop_figures.py /data/pub-data --out /data/recrop
  python3 src/pipeline_steps/recrop_figures.py /data/pub-data/10088816 --out recrop --review
  python3 src/pipeline_steps/recrop_figures.py /data/pub-data --out recrop --include-supplementary
"""
import argparse
import csv
import glob
import gzip
import html
import json
import os
import random
import re
import shutil
import sys
import xml.etree.ElementTree as ET
from collections import Counter
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path

import fitz

STEPS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, STEPS_DIR)
from pdf_to_bioc import (FIGURE_PAD_PT, MIN_FIGURE_PT, MIN_TABLE_PT,  # noqa: E402
                         TEI_SUFFIX, parse_coords)

CROPPER = "recrop_figures/2"

NS = {"tei": "http://www.tei-c.org/ns/1.0"}
XML_ID = "{http://www.w3.org/XML/1998/namespace}id"

# Layout thresholds, in PDF points unless noted.
MARGIN_FRAC = 0.05       # top/bottom band of the page treated as running header/footer
SIDE_MARGIN_PT = 36      # text/graphics hugging the left/right page edge (e.g. "Downloaded from")
RULE_FRAC = 0.6          # thin lines longer than this fraction of the page are rules/column dividers
THIN_PT = 2.0
MIN_GRAPHIC_PT = 12      # images smaller than this in both dims are icons/glyphs
SCANNED_FRAC = 0.85      # an image covering this much of the page means a scanned page
BODY_WORDS = 15          # a text block this long, outside any graphic ...
BODY_MIN_WIDTH_PT = 120  # ... and at least this wide is body text, which bounds a figure
CAPTION_JOIN_PT = 3      # blocks this close below a caption are its continuation
LABEL_GAP_PT = 8         # short text within this distance of a figure belongs to it
GRAPHIC_GAP_PT = 10      # graphics within this distance of a figure are merged into it
EXPAND_GAP_PT = 6        # same, when widening a GROBID <graphic> box
EXPAND_MAX_RATIO = 3.0   # give up widening a <graphic> box if it grows beyond this area ratio
SIDE_GAP_PT = 40         # max gap between a side caption and its figure
MAX_DRAWINGS = 3000      # above this, snap drawings to a grid before clustering (dense plots)
SNAP_PT = 6

CAPTION_RE = re.compile(r"^(?:supplementa(?:ry|l)\s+)?(fig(?:ure)?s?|table)\s*\.?\s*(S?\d+)", re.I)
FIGNUM_RE = re.compile(r"fig(?:ure)?s?\s*\.?\s*(S?\d+)", re.I)
CAPTION_PREFIX_RE = re.compile(r"^\s*(?:supplementa(?:ry|l)\s+)?fig(?:ure)?s?\s*\.?\s*S?\d+\s*[.:|]?", re.I)
FACING_RE = re.compile(r"\b(?:facing|opposite)\s+page\b", re.I)
FACING_MIN_FRAC = 0.15   # a facing-page figure covers at least this much of its page
FACING_LABEL_GAP_PT = 12  # a whole-page figure's axis notes can sit a little further out
FALLBACK_TEXT_FRAC = 0.35     # a GROBID <figure> box this covered by text blocks ...
FALLBACK_GRAPHIC_FRAC = 0.05  # ... and less than this by graphics is text, not a figure


# -----------------------------------------------------------------------------
# Rect helpers
# -----------------------------------------------------------------------------
def _area(r):
    return max(0.0, r.width) * max(0.0, r.height)


def _gap(a, b):
    """Largest axis-aligned gap between two rects (0 when they touch or overlap)."""
    dx = max(0.0, a.x0 - b.x1, b.x0 - a.x1)
    dy = max(0.0, a.y0 - b.y1, b.y0 - a.y1)
    return max(dx, dy)


def _xoverlap(a, b):
    return min(a.x1, b.x1) - max(a.x0, b.x0)


def _yoverlap(a, b):
    return min(a.y1, b.y1) - max(a.y0, b.y0)


def _frac_inside(a, b):
    """Fraction of a's area that lies inside b."""
    if _area(a) <= 0:
        return 0.0
    i = fitz.Rect(a) & b
    return 0.0 if i.is_empty else _area(i) / _area(a)


def _union(rects):
    out = None
    for r in rects:
        out = fitz.Rect(r) if out is None else out | r
    return out


def _within_y(r, zone, tol=2.0):
    return r.y0 >= zone.y0 - tol and r.y1 <= zone.y1 + tol


def _norm(text):
    return re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()


def _cluster(page, rects):
    """Clusters of neighbouring vector-drawing rects (lone thin lines dropped)."""
    if not rects:
        return []
    if len(rects) > MAX_DRAWINGS:
        # Dense plots (scatter points, heatmap cells): snapping to a coarse grid
        # and de-duplicating keeps clustering fast without changing the extent.
        snapped = {(SNAP_PT * (r.x0 // SNAP_PT), SNAP_PT * (r.y0 // SNAP_PT),
                    SNAP_PT * -(-r.x1 // SNAP_PT), SNAP_PT * -(-r.y1 // SNAP_PT)) for r in rects}
        rects = [fitz.Rect(s) for s in snapped]
    if hasattr(page, "cluster_drawings"):
        return page.cluster_drawings(drawings=[{"rect": r} for r in rects],
                                     x_tolerance=3, y_tolerance=3)
    # Older PyMuPDF: naive merge of overlapping (3 pt inflated) rects.
    merged = []
    for r in rects:
        r = fitz.Rect(r)
        changed = True
        while changed:
            changed = False
            for m in merged:
                if _gap(m, r) <= 3:
                    merged.remove(m)
                    r |= m
                    changed = True
                    break
        merged.append(r)
    return [m for m in merged if m.width > 3 and m.height > 3]


# -----------------------------------------------------------------------------
# Page layout
# -----------------------------------------------------------------------------
class PageLayout:
    """Text blocks (always) and graphics (lazily) of one page."""

    def __init__(self, page, table_rects):
        self.page = page
        self.rect = page.rect
        h = self.rect.height
        self.top = self.rect.y0 + MARGIN_FRAC * h
        self.bottom = self.rect.y1 - MARGIN_FRAC * h
        self.tables = [fitz.Rect(t) + (-2, -2, 2, 2) for t in table_rects]
        self.blocks = []
        for x0, y0, x1, y1, text, _no, btype in page.get_text("blocks"):
            text = " ".join(text.split())
            if btype != 0 or not text:
                continue
            self.blocks.append({"rect": fitz.Rect(x0, y0, x1, y1), "text": text,
                                "caption_like": bool(CAPTION_RE.match(text))})
        self._graphics = None
        self.scanned = False

    def in_margin(self, r):
        return (r.y1 < self.top or r.y0 > self.bottom
                or r.x1 < self.rect.x0 + SIDE_MARGIN_PT or r.x0 > self.rect.x1 - SIDE_MARGIN_PT)

    def in_table(self, r):
        c = fitz.Point((r.x0 + r.x1) / 2, (r.y0 + r.y1) / 2)
        return any(c in t for t in self.tables)

    @property
    def graphics(self):
        if self._graphics is None:
            self._build_graphics()
        return self._graphics

    def _build_graphics(self):
        page, prect = self.page, self.rect
        page_area = _area(prect)
        graphics = []

        for info in page.get_image_info():
            r = fitz.Rect(info["bbox"]) & prect
            if r.is_empty:
                continue
            if _area(r) >= SCANNED_FRAC * page_area:
                self.scanned = True
                continue
            if (r.width < MIN_GRAPHIC_PT and r.height < MIN_GRAPHIC_PT) \
                    or self.in_margin(r) or self.in_table(r):
                continue
            graphics.append(r)

        rects = []
        for d in page.get_drawings():
            r = fitz.Rect(d["rect"])
            if r.x1 < r.x0 or r.y1 < r.y0:
                continue
            r &= prect
            if r.x1 < r.x0 or r.y1 < r.y0:
                continue
            if _area(r) > 0.5 * page_area:                         # page background / frame
                continue
            if (r.height <= THIN_PT and r.width > RULE_FRAC * prect.width) or \
               (r.width <= THIN_PT and r.height > RULE_FRAC * prect.height):
                continue                                           # rules, column dividers
            if self.in_margin(r) or self.in_table(r):
                continue
            fill, stroke = d.get("fill"), d.get("color")
            if stroke is None and fill is not None and all(c > 0.97 for c in fill):
                continue                                           # white masks/backgrounds
            rects.append(r)
        graphics.extend(_cluster(page, rects))
        self._graphics = graphics

        for b in self.blocks:
            r = b["rect"]
            inside = any(_frac_inside(r, g) > 0.5 for g in graphics)
            # Alphabetic words only: an axis row like "0 1 2 ... 15 Total No." is not prose.
            words = len(re.findall(r"[^\W\d_]{2,}", b["text"]))
            b["body"] = (not inside and words >= BODY_WORDS and r.width >= BODY_MIN_WIDTH_PT)
            b["label"] = not b["body"] and not b["caption_like"] and not self.in_margin(r)


class DocLayout:
    def __init__(self, doc, table_boxes):
        self.doc = doc
        self.table_boxes = table_boxes      # {page_no: [Rect]}
        self._pages = {}

    def page(self, pno):
        if pno not in self._pages:
            self._pages[pno] = PageLayout(self.doc[pno - 1], self.table_boxes.get(pno, []))
        return self._pages[pno]


# -----------------------------------------------------------------------------
# Caption + figure region
# -----------------------------------------------------------------------------
def expected_numbers(label, head, caption):
    """Figure numbers this TEI figure may carry, e.g. {"2"} or {"2", "3"} when
    GROBID merged two captions ("Figure 2 .Figure 3 .", label "23")."""
    nums = {m.group(1).upper()
            for text in (head, (caption or "")[:40])
            for m in FIGNUM_RE.finditer(text or "")}
    lab = (label or "").strip().upper()
    if not nums and re.fullmatch(r"S?\d{1,3}", lab):
        nums.add(lab)
    return nums


def find_captions(layout, hint_pages, anchors, nums, caption, max_candidates=4):
    """Ranked [(page_no, caption Rect)] where this figure's caption may be.

    The first entry is the best match (label at block start and/or the start of
    the TEI caption text, preferring GROBID's page and position). Later entries
    are short "Fig. N" label blocks elsewhere, which is how author manuscripts
    mark figures when all legends sit together on a "Figure Legends" page.
    """
    probe = _norm(CAPTION_PREFIX_RE.sub("", caption or ""))[:40]
    if len(probe) < 15:
        probe = ""
    if not nums and not probe:
        return []

    scored = []
    for pno in range(1, layout.doc.page_count + 1):
        for b in layout.page(pno).blocks:
            m = CAPTION_RE.match(b["text"])
            label_hit = bool(m and m.group(1).lower().startswith("fig") and m.group(2).upper() in nums)
            text_hit = bool(probe and probe in _norm(b["text"]))
            if not (label_hit or text_hit):
                continue
            score = 2.0 * label_hit + 2.0 * text_hit
            anchor = anchors.get(pno)
            if anchor is not None and b["rect"].intersects(anchor):
                score += 1
            if pno in hint_pages:
                score += 0.5
            short_label = label_hit and len(b["text"].split()) <= 8
            scored.append((score, short_label, pno, b))
    if not scored:
        return []
    scored.sort(key=lambda s: -s[0])
    picks = [scored[0]] + [s for s in scored[1:] if s[1] or s[0] >= 4][:max_candidates - 1]

    out = []
    for _, _, pno, blk in picks:
        cap = fitz.Rect(blk["rect"])
        grown = True
        while grown:                    # absorb the caption's continuation blocks
            grown = False
            for b in layout.page(pno).blocks:
                r = b["rect"]
                if cap.contains(r) or b["caption_like"]:
                    continue
                if 0 <= r.y0 - cap.y1 <= CAPTION_JOIN_PT and \
                        _xoverlap(r, cap) > 0.5 * min(r.width, cap.width):
                    cap |= r
                    grown = True
        out.append((pno, cap))
    return out


def _overlaps(a, b, frac=0.6):
    """True when the smaller of two rects lies mostly inside the other."""
    i = fitz.Rect(a) & b
    if i.is_empty:
        return False
    return _area(i) >= frac * min(_area(a), _area(b))


def _grow(lay, seeds, zone, graphic_gap, extra_exclude=None, label_gap=LABEL_GAP_PT):
    """Union of seeds plus graphics/labels in zone reachable within the gaps."""
    region = _union(seeds)
    used = set()
    changed = True
    while changed:
        changed = False
        for i, g in enumerate(lay.graphics):
            if i in used or not _within_y(g, zone):
                continue
            if _gap(g, region) <= graphic_gap:
                if extra_exclude is not None and g.intersects(extra_exclude):
                    continue
                region |= g
                used.add(i)
                changed = True
        for j, b in enumerate(lay.blocks):
            key = ("t", j)
            if key in used or not b.get("label") or not _within_y(b["rect"], zone):
                continue
            if extra_exclude is not None and b["rect"].intersects(extra_exclude):
                continue
            if _gap(b["rect"], region) <= label_gap:
                region |= b["rect"]
                used.add(key)
                changed = True
    return region & zone


def figure_region(lay, cap, labelled=True):
    """(Rect, where) of the figure belonging to caption `cap`, or (None, reason).
    `labelled`: the figure has a "Figure N" label; required for the frame rule,
    which would otherwise fire on GROBID false positives (running titles, body
    text) that happen to sit inside a bordered box."""
    if not lay.graphics and lay.scanned:
        return None, "scanned_page"
    bounds = [b["rect"] for b in lay.blocks
              if (b["body"] or b["caption_like"]) and not b["rect"].intersects(cap)]
    bounds += lay.tables

    def top_bound(y, xr):
        top = lay.top
        for r in bounds:
            if r.y1 <= y + 2 and _xoverlap(r, xr) > 0.3 * min(r.width, xr.width):
                top = max(top, r.y1)
        return top

    def bottom_bound(y, xr):
        bottom = lay.bottom
        for r in bounds:
            if r.y0 >= y - 2 and _xoverlap(r, xr) > 0.3 * min(r.width, xr.width):
                bottom = min(bottom, r.y0)
        return bottom

    # Caption drawn inside the figure's own frame or shaded panel (e.g. NEJM):
    # the figure is the part of that frame above (or below) the caption. A
    # frame with no room beside the caption is just a caption box; skip it.
    for g in (sorted(lay.graphics, key=_area) if labelled else []):
        if _frac_inside(cap, g) < 0.8:
            continue
        # Stop FIGURE_PAD_PT short of the caption so the crop padding stays off it.
        above_part = fitz.Rect(g.x0, g.y0, g.x1, cap.y0 - FIGURE_PAD_PT)
        below_part = fitz.Rect(g.x0, cap.y1 + FIGURE_PAD_PT, g.x1, g.y1)
        part = above_part if above_part.height >= below_part.height else below_part
        if part.width >= MIN_FIGURE_PT and part.height >= MIN_FIGURE_PT:
            return part, "frame"

    x0, x1 = lay.rect.x0, lay.rect.x1
    attempts = []
    above = fitz.Rect(x0, top_bound(cap.y0, cap), x1, cap.y0)
    attempts.append(("above", above,
                     [g for g in lay.graphics if _within_y(g, above) and _xoverlap(g, cap) > 5]))
    below = fitz.Rect(x0, cap.y1, x1, bottom_bound(cap.y1, cap))
    attempts.append(("below", below,
                     [g for g in lay.graphics if _within_y(g, below) and _xoverlap(g, cap) > 5]))
    side = [g for g in lay.graphics
            if not g.intersects(cap) and _yoverlap(g, cap) > 0.3 * min(g.height, cap.height)
            and _gap(g, cap) <= SIDE_GAP_PT]
    if side:
        su = _union(side)
        attempts.append(("side", fitz.Rect(x0, top_bound(su.y0, su), x1, bottom_bound(su.y1, su)),
                         side))

    for where, zone, seeds in attempts:
        if zone.height <= 0 or not seeds:
            continue
        region = _grow(lay, seeds, zone, GRAPHIC_GAP_PT, extra_exclude=cap)
        if where == "above":        # keep the crop padding off the caption
            region.y1 = min(region.y1, cap.y0 - FIGURE_PAD_PT)
        elif where == "below":
            region.y0 = max(region.y0, cap.y1 + FIGURE_PAD_PT)
        if region.is_empty or region.width < MIN_FIGURE_PT or region.height < MIN_FIGURE_PT:
            continue
        return region, where
    return None, ("scanned_page" if lay.scanned else "no_graphics_near_caption")


def facing_page_region(lay):
    """The figure on the page facing its caption ("Figure 2 (facing page)."):
    all graphics there without a figure/table caption of their own, provided
    one of them is large. Taking all of them keeps multi-panel figures whole
    when their panels are only joined by full-width rules (dropped as page
    furniture)."""
    page_area = _area(lay.rect)
    captions = [b["rect"] for b in lay.blocks if b["caption_like"]]
    cands = [g for g in lay.graphics
             if _area(g) >= 0.01 * page_area
             and not any(_gap(c, g) <= LABEL_GAP_PT for c in captions)]
    if not cands or max(_area(g) for g in cands) < FACING_MIN_FRAC * page_area:
        return None
    zone = fitz.Rect(lay.rect.x0, lay.top, lay.rect.x1, lay.bottom)
    return _grow(lay, cands, zone, GRAPHIC_GAP_PT, label_gap=FACING_LABEL_GAP_PT)


def expand_graphic(lay, rect, cap):
    """Widen a GROBID <graphic> box to touching vector items and labels."""
    zone = fitz.Rect(lay.rect.x0, lay.top, lay.rect.x1, lay.bottom)
    if cap is not None:
        if cap.y0 >= rect.y1 - 2:
            zone.y1 = min(zone.y1, cap.y0)
        elif cap.y1 <= rect.y0 + 2:
            zone.y0 = max(zone.y0, cap.y1)
    grown = _grow(lay, [rect], zone, EXPAND_GAP_PT, extra_exclude=cap)
    grown = rect if grown.is_empty else grown | rect      # never clip the bitmap itself
    if _area(grown) > EXPAND_MAX_RATIO * max(_area(rect), 1.0):
        return rect, False
    return grown, _area(grown) > _area(rect) * 1.01


# -----------------------------------------------------------------------------
# One document
# -----------------------------------------------------------------------------
def _text(el):
    return " ".join(el.itertext()).strip() if el is not None else ""


def _by_page(boxes):
    by_page = {}
    for page, x0, y0, x1, y1 in boxes:
        r = fitz.Rect(x0, y0, x1, y1)
        by_page[page] = by_page[page] | r if page in by_page else r
    return by_page


def _render(page, rect, dpi, out_dir, fname):
    r = fitz.Rect(rect.x0 - FIGURE_PAD_PT, rect.y0 - FIGURE_PAD_PT,
                  rect.x1 + FIGURE_PAD_PT, rect.y1 + FIGURE_PAD_PT) & page.rect
    pix = page.get_pixmap(clip=r, dpi=dpi)
    os.makedirs(out_dir, exist_ok=True)
    pix.save(os.path.join(out_dir, fname))
    return {"file": fname, "page": page.number + 1,
            "bbox": [round(v, 2) for v in r], "width_px": pix.width, "height_px": pix.height}


def recrop_document(tei_xml, pdf_path, out_dir, dpi=200, expand=True):
    """Write <out_dir>/<id>_p<page>.png + figures.json; return the records."""
    root = ET.fromstring(tei_xml)
    if os.path.isdir(out_dir):
        shutil.rmtree(out_dir)
    os.makedirs(out_dir, exist_ok=True)

    items = []
    for i, fig in enumerate(root.findall(".//tei:figure", NS)):
        is_table = fig.get("type") == "table"
        graphic_boxes = [b for g in fig.findall("tei:graphic", NS)
                         for b in parse_coords(g.get("coords"))]
        figure_boxes = parse_coords(fig.get("coords"))
        items.append({
            "is_table": is_table,
            "id": fig.get(XML_ID) or (f"tab_{i}" if is_table else f"fig_{i}"),
            "label": _text(fig.find("tei:label", NS)),
            "head": _text(fig.find("tei:head", NS)),
            "caption": _text(fig.find("tei:figDesc", NS)),
            "graphic_boxes": graphic_boxes,
            "figure_boxes": figure_boxes,
            "grobid_box": "graphic" if graphic_boxes else ("figure" if figure_boxes else "none"),
        })

    table_boxes = {}
    for it in items:
        if it["is_table"]:
            for pno, r in _by_page(it["graphic_boxes"] or it["figure_boxes"]).items():
                table_boxes.setdefault(pno, []).append(r)

    doc = fitz.open(pdf_path)
    try:
        layout = DocLayout(doc, table_boxes)
        emitted = []            # (page_no, Rect, id) of every figure region cropped so far
        results = {}

        def valid(pno):
            return 1 <= pno <= doc.page_count

        def crop_table(it):
            # Unchanged from pdf_to_bioc.save_figure_images().
            images = []
            for pno, r in sorted(_by_page(it["graphic_boxes"] or it["figure_boxes"]).items()):
                if not valid(pno):
                    continue
                rr = r & doc[pno - 1].rect
                if rr.width + 2 * FIGURE_PAD_PT < MIN_TABLE_PT or \
                        rr.height + 2 * FIGURE_PAD_PT < MIN_TABLE_PT:
                    continue
                images.append(_render(doc[pno - 1], rr, dpi, out_dir, f"{it['id']}_p{pno}.png"))
            source = it["grobid_box"] if images else "none"
            return source, images, (source if images else "no_box"), None

        def captions_for(it):
            anchors = {p: r for p, r in _by_page(it["figure_boxes"]).items() if valid(p)}
            hint_pages = set(anchors) | {p for p in _by_page(it["graphic_boxes"]) if valid(p)}
            nums = expected_numbers(it["label"], it["head"], it["caption"])
            return find_captions(layout, hint_pages, anchors, nums, it["caption"])

        def crop_graphic(it):
            caps = captions_for(it)
            cap_page, cap = caps[0] if caps else (None, None)
            images, expanded_any = [], False
            for pno, r in sorted(_by_page(it["graphic_boxes"]).items()):
                if not valid(pno):
                    continue
                lay = layout.page(pno)
                rr = r & lay.rect
                if rr.width + 2 * FIGURE_PAD_PT < MIN_FIGURE_PT or \
                        rr.height + 2 * FIGURE_PAD_PT < MIN_FIGURE_PT:
                    continue
                if expand:
                    rr, expanded = expand_graphic(lay, rr, cap if pno == cap_page else None)
                    expanded_any |= expanded
                emitted.append((pno, rr, it["id"]))
                images.append(_render(lay.page, rr, dpi, out_dir, f"{it['id']}_p{pno}.png"))
            reason = "graphic_expanded" if expanded_any else "graphic"
            return ("graphic" if images else "none"), images, reason, (cap_page, cap)

        def mostly_text(lay, r):
            area = max(_area(r), 1.0)
            text = sum(_area(b["rect"] & r) for b in lay.blocks if b["rect"].intersects(r))
            drawn = sum(_area(g & r) for g in lay.graphics if g.intersects(r))
            return text >= FALLBACK_TEXT_FRAC * area and drawn < FALLBACK_GRAPHIC_FRAC * area

        def crop_figure_box(it, reason, cap_info):
            # The layout search failed: keep GROBID's <figure> box, as
            # pdf_to_bioc.py would, unless it is mostly text (a caption strip or
            # a paragraph). A scanned page with no text layer passes; OCR text
            # counts as text.
            images = []
            for pno, r in sorted(_by_page(it["figure_boxes"]).items()):
                if not valid(pno):
                    continue
                lay = layout.page(pno)
                rr = r & lay.rect
                if rr.width + 2 * FIGURE_PAD_PT < MIN_FIGURE_PT or \
                        rr.height + 2 * FIGURE_PAD_PT < MIN_FIGURE_PT or mostly_text(lay, rr):
                    continue
                emitted.append((pno, rr, it["id"]))
                images.append(_render(lay.page, rr, dpi, out_dir, f"{it['id']}_p{pno}.png"))
            if images:
                return "figure_fallback", images, f"fallback_{reason}", cap_info
            return "none", [], reason, cap_info

        def crop_layout(it):
            caps = captions_for(it)
            if not caps:
                return "none", [], "caption_not_found", (None, None)
            reason = ""
            labelled = bool(expected_numbers(it["label"], it["head"], it["caption"]))
            for cap_page, cap in caps:
                lay = layout.page(cap_page)
                region, where = figure_region(lay, cap, labelled)
                if region is None:
                    reason = reason or where
                    continue
                dup = next((fid for p, r, fid in emitted if p == cap_page and _overlaps(r, region)),
                           None)
                if dup is not None:
                    reason = reason or f"same_region_as_{dup}"
                    continue
                emitted.append((cap_page, region, it["id"]))
                img = _render(lay.page, region, dpi, out_dir, f"{it['id']}_p{cap_page}.png")
                return "layout", [img], f"layout_{where}", (cap_page, cap)
            if FACING_RE.search(it["caption"] or ""):
                cap_page, cap = caps[0]
                for pno in (cap_page - 1, cap_page + 1):
                    if not valid(pno):
                        continue
                    lay = layout.page(pno)
                    region = facing_page_region(lay)
                    if region is None or region.is_empty or any(
                            p == pno and _overlaps(r, region) for p, r, _ in emitted):
                        continue
                    emitted.append((pno, region, it["id"]))
                    img = _render(lay.page, region, dpi, out_dir, f"{it['id']}_p{pno}.png")
                    return "layout", [img], "layout_facing_page", (cap_page, cap)
            return "none", [], reason, caps[0]

        # GROBID-boxed figures first, so the layout heuristic can recognise (and
        # skip) regions they already cover; then figures with a "Figure N"
        # label before label-less ones, which are often GROBID false positives
        # (body text, running headers) that would otherwise claim a real
        # figure's region first. Records keep TEI order regardless.
        order = sorted(range(len(items)), key=lambda k: (
            items[k]["is_table"], not items[k]["graphic_boxes"],
            not expected_numbers(items[k]["label"], items[k]["head"], items[k]["caption"])))
        for k in order:
            it = items[k]
            if it["is_table"]:
                results[k] = crop_table(it)
            elif it["graphic_boxes"]:
                results[k] = crop_graphic(it)
            else:
                results[k] = crop_layout(it)
                if results[k][0] == "none" and it["figure_boxes"]:
                    results[k] = crop_figure_box(it, *results[k][2:])

        records = {"figures": [], "tables": []}
        for k, it in enumerate(items):
            source, images, reason, cap_info = results[k]
            rec = {"id": it["id"], "label": it["label"], "head": it["head"],
                   "caption": it["caption"], "source": source, "images": images,
                   "grobid_box": it["grobid_box"], "reason": reason}
            if not it["is_table"]:
                cap_page, cap = cap_info
                rec["caption_bbox"] = [cap_page] + [round(v, 2) for v in cap] if cap else None
            records["tables" if it["is_table"] else "figures"].append(rec)
    finally:
        doc.close()

    with open(os.path.join(out_dir, "figures.json"), "w", encoding="utf-8") as fh:
        json.dump({"pdf": os.path.basename(pdf_path), "dpi": dpi, "cropper": CROPPER, **records},
                  fh, indent=2)
    return records


# -----------------------------------------------------------------------------
# Corpus driver
# -----------------------------------------------------------------------------
def discover_pub_dirs(paths):
    """Each path is a publication dir (has 01_source/) or a corpus root of them."""
    pub_dirs = []
    for raw in paths:
        top = os.path.abspath(raw)
        if os.path.isdir(os.path.join(top, "01_source")):
            pub_dirs.append(top)
        elif os.path.isdir(top):
            pub_dirs.extend(sorted(
                os.path.join(top, n) for n in os.listdir(top)
                if os.path.isdir(os.path.join(top, n, "01_source"))))
        else:
            print(f"WARNING: not a directory, skipping: {top}", file=sys.stderr)
    return pub_dirs


def find_docs(pub_dir, include_supplementary):
    """(rel, stem, tei_path, pdf_path) per saved TEI. rel is "" for the main
    group, else the supplementary dir relative to 02_grobid (e.g. "s/Table1")."""
    grobid = os.path.join(pub_dir, "02_grobid")
    pattern = os.path.join(grobid, "**", "*" + TEI_SUFFIX) if include_supplementary \
        else os.path.join(grobid, "*" + TEI_SUFFIX)
    docs = []
    for tei in sorted(glob.glob(pattern, recursive=include_supplementary)):
        rel = os.path.relpath(os.path.dirname(tei), grobid)
        rel = "" if rel == "." else rel
        stem = os.path.basename(tei)[:-len(TEI_SUFFIX)]
        pdf = os.path.join(pub_dir, "01_source", rel, stem + ".pdf")
        if rel and not os.path.isfile(pdf):
            # GROBID ran on a prepared copy (01_source/s/<stem>/<stem>.pdf) that
            # civic_pubtator.py deletes after the run. For native PDFs,
            # prepare_supplementary.py makes it with shutil.copy2, so the original
            # one level up is byte-identical and GROBID's coords still apply.
            original = os.path.join(pub_dir, "01_source", os.path.dirname(rel), stem + ".pdf")
            if os.path.isfile(original):
                pdf = original
        docs.append((rel, stem, tei, pdf))
    return docs


def _rows(pub_id, rel, stem, records, out_root, out_dir, old_files):
    rows = []
    for kind, key in (("figure", "figures"), ("table", "tables")):
        for rec in records.get(key, []):
            imgs = rec.get("images") or []
            rows.append({
                "pub_id": pub_id, "group": rel or "main", "stem": stem, "kind": kind,
                "id": rec["id"], "label": rec.get("label", ""),
                "grobid_box": rec.get("grobid_box", ""), "source": rec.get("source", ""),
                "reason": rec.get("reason", ""), "n_images": len(imgs),
                "pages": ",".join(str(i["page"]) for i in imgs),
                "width_px": imgs[0]["width_px"] if imgs else "",
                "height_px": imgs[0]["height_px"] if imgs else "",
                "caption_found": "" if kind == "table" else int(bool(rec.get("caption_bbox"))),
                "caption": rec.get("caption", ""),
                "new_files": [os.path.relpath(os.path.join(out_dir, i["file"]), out_root)
                              for i in imgs],
                "old_files": old_files.get((key, rec["id"]), []),
            })
    return rows


def _old_files(pub_dir, rel, stem):
    """{(section, id): [abs png paths]} from the existing 02_grobid figures.json."""
    old_dir = os.path.join(pub_dir, "02_grobid", rel, "figures", stem)
    out = {}
    try:
        with open(os.path.join(old_dir, "figures.json"), encoding="utf-8") as fh:
            data = json.load(fh)
    except (OSError, ValueError):
        return out
    for key in ("figures", "tables"):
        for rec in data.get(key, []):
            sect = "tables" if rec.get("id", "").startswith("tab") else key
            out[(sect, rec.get("id"))] = [os.path.join(old_dir, i["file"])
                                          for i in rec.get("images", [])]
    return out


def process_doc(task):
    pub_dir, rel, stem, tei_path, pdf_path, out_root, dpi, expand, force = task
    pub_id = os.path.basename(pub_dir)
    out_dir = os.path.join(out_root, pub_id, rel, stem)
    fj = os.path.join(out_dir, "figures.json")
    try:
        if not os.path.isfile(pdf_path):
            if rel:     # converted .docx/.xlsx/.pptx supplement; its prepared PDF was deleted
                return {"doc": f"{pub_id}/{rel}/{stem}", "error": None, "rows": [], "no_pdf": True}
            return {"doc": f"{pub_id}/{rel}/{stem}", "error": f"PDF not found: {pdf_path}", "rows": []}
        records = None
        if not force and os.path.isfile(fj):
            try:
                with open(fj, encoding="utf-8") as fh:
                    data = json.load(fh)
                if data.get("cropper") == CROPPER:
                    records = data
            except (OSError, ValueError):
                records = None
        skipped = records is not None
        if records is None:
            with gzip.open(tei_path, "rt", encoding="utf-8") as fh:
                tei_xml = fh.read()
            records = recrop_document(tei_xml, pdf_path, out_dir, dpi=dpi, expand=expand)
        rows = _rows(pub_id, rel, stem, records, out_root, out_dir,
                     _old_files(pub_dir, rel, stem))
        return {"doc": f"{pub_id}/{rel}/{stem}", "error": None, "rows": rows, "skipped": skipped}
    except Exception as e:  # keep going on one bad PDF/TEI
        return {"doc": f"{pub_id}/{rel}/{stem}", "error": f"{type(e).__name__}: {e}", "rows": []}


TSV_COLS = ["pub_id", "group", "stem", "kind", "id", "label", "grobid_box", "source",
            "reason", "n_images", "pages", "width_px", "height_px", "caption_found"]


def write_review(rows, out_root, limit, seed):
    """Side-by-side old vs new crops for figures GROBID did not box as <graphic>."""
    picks = [r for r in rows if r["kind"] == "figure"
             and (r["grobid_box"] != "graphic" or r["reason"] == "graphic_expanded")]
    if limit and len(picks) > limit:
        picks = random.Random(seed).sample(picks, limit)
    picks.sort(key=lambda r: (r["pub_id"], r["group"], r["stem"], r["id"]))

    def imgs(paths, relative):
        if not paths:
            return '<div class="none">no image</div>'
        out = []
        for p in paths:
            src = Path(p).as_posix() if relative else Path(p).as_uri()
            out.append(f'<a href="{html.escape(src)}"><img loading="lazy" src="{html.escape(src)}"></a>')
        return "".join(out)

    cards = []
    for r in picks:
        cards.append(
            f'<section><h2>{html.escape(r["pub_id"])} · {html.escape(r["group"])} · '
            f'{html.escape(r["id"])} (label {html.escape(r["label"] or "-")})</h2>'
            f'<p class="meta">{html.escape(r["grobid_box"])} → <b>{html.escape(r["source"])}</b> '
            f'({html.escape(r["reason"])})</p>'
            f'<p class="cap">{html.escape(r["caption"][:300])}</p>'
            f'<div class="pair"><div><h3>old</h3>{imgs(r["old_files"], False)}</div>'
            f'<div><h3>new</h3>{imgs(r["new_files"], True)}</div></div></section>')
    doc = f"""<!DOCTYPE html>
<html><head><meta charset="utf-8"><title>Figure re-crop review</title>
<style>
 body {{ font-family: system-ui, sans-serif; margin: 1.5rem; background: #fafafa; color: #1a1a1a; }}
 section {{ background: #fff; border: 1px solid #ddd; border-radius: 8px; padding: .8rem 1rem; margin-bottom: 1rem; }}
 h2 {{ font-size: 1rem; margin: 0; }} h3 {{ font-size: .75rem; color: #777; margin: .2rem 0; }}
 .meta {{ margin: .3rem 0; font-size: .85rem; }} .cap {{ font-size: .8rem; color: #555; margin: .3rem 0; }}
 .pair {{ display: grid; grid-template-columns: 1fr 1fr; gap: 1rem; }}
 img {{ max-width: 100%; max-height: 320px; border: 1px solid #ccc; display: block; margin-bottom: .4rem; }}
 .none {{ color: #b00; font-size: .85rem; }}
</style></head><body>
<h1>Figure re-crop review ({len(picks)} figures)</h1>
{''.join(cards)}
</body></html>"""
    path = os.path.join(out_root, "review.html")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(doc)
    return path


def main():
    parser = argparse.ArgumentParser(description=__doc__,
                                     formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("input_dirs", nargs="+",
                        help="Publication dirs, or corpus roots whose children are publication dirs")
    parser.add_argument("--out", required=True,
                        help="Output root (must be outside the input dirs). Keep it short on "
                             "Windows to stay under the 260-character path limit.")
    parser.add_argument("--include-supplementary", action="store_true",
                        help="Also re-crop supplementary PDFs (02_grobid/s/...)")
    parser.add_argument("--figure-dpi", type=int, default=200, metavar="DPI")
    parser.add_argument("--no-expand-graphic", dest="expand", action="store_false",
                        help="Crop GROBID <graphic> boxes as-is instead of widening them to "
                             "touching labels and vector items")
    parser.add_argument("--workers", type=int, default=max(1, (os.cpu_count() or 2) // 2))
    parser.add_argument("--force", action="store_true",
                        help="Redo documents already re-cropped by this cropper version")
    parser.add_argument("--review", action="store_true",
                        help="Write <out>/review.html comparing old and new figure crops")
    parser.add_argument("--review-limit", type=int, default=0, metavar="N",
                        help="Random sample of N figures in review.html (default: all)")
    parser.add_argument("--seed", type=int, default=0)
    args = parser.parse_args()

    out_root = os.path.abspath(args.out)
    pub_dirs = discover_pub_dirs(args.input_dirs)
    if not pub_dirs:
        sys.exit("ERROR: no publication directories found")
    for p in [os.path.abspath(x) for x in args.input_dirs] + pub_dirs:
        a, b = os.path.normcase(out_root), os.path.normcase(p)
        try:
            inside = os.path.commonpath([a, b]) == b
        except ValueError:          # different drives on Windows
            inside = False
        if inside:
            sys.exit(f"ERROR: --out {out_root} is inside input {p}; choose a separate directory")
    os.makedirs(out_root, exist_ok=True)

    tasks = []
    for pub_dir in pub_dirs:
        for rel, stem, tei, pdf in find_docs(pub_dir, args.include_supplementary):
            tasks.append((pub_dir, rel, stem, tei, pdf, out_root, args.figure_dpi,
                          args.expand, args.force))
    print(f"{len(pub_dirs)} publication(s), {len(tasks)} document(s) with a saved TEI "
          f"-> {out_root}")

    rows, errors, n_skipped, n_no_pdf = [], [], 0, 0
    with ProcessPoolExecutor(max_workers=args.workers) as pool:
        futures = [pool.submit(process_doc, t) for t in tasks]
        for n, fut in enumerate(as_completed(futures), 1):
            res = fut.result()
            if res["error"]:
                errors.append((res["doc"], res["error"]))
                print(f"  [{n}/{len(tasks)}] {res['doc']}: ERROR {res['error']}", file=sys.stderr)
            else:
                n_skipped += bool(res.get("skipped"))
                n_no_pdf += bool(res.get("no_pdf"))
                rows.extend(res["rows"])
            if n % 50 == 0 or n == len(tasks):
                print(f"  [{n}/{len(tasks)}] done")

    rows.sort(key=lambda r: (r["pub_id"], r["group"], r["stem"], r["kind"], r["id"]))
    tsv = os.path.join(out_root, "recrop_summary.tsv")
    with open(tsv, "w", encoding="utf-8", newline="") as fh:
        w = csv.DictWriter(fh, fieldnames=TSV_COLS, delimiter="\t", extrasaction="ignore")
        w.writeheader()
        w.writerows(rows)

    figs = [r for r in rows if r["kind"] == "figure"]
    print()
    print("=" * 60)
    print(f"Documents re-cropped: {len(tasks) - len(errors) - n_skipped - n_no_pdf}  "
          f"already done: {n_skipped}  no PDF: {n_no_pdf}  failed: {len(errors)}")
    if n_no_pdf:
        print("  (no PDF: converted supplements whose prepared PDF civic_pubtator.py deleted)")
    print(f"Figures: {len(figs)}   Tables: {len(rows) - len(figs)}")
    print("Figures by old GROBID box -> new source (reason):")
    for (old, new, why), n in sorted(Counter((r["grobid_box"], r["source"], r["reason"])
                                             for r in figs).items()):
        print(f"  {old:8s} -> {new:15s} {why:36s} {n:6d}")
    print(f"Summary: {tsv}")
    if args.review:
        print(f"Review:  {write_review(rows, out_root, args.review_limit, args.seed)}")
    if errors:
        sys.exit(1)


if __name__ == "__main__":
    main()
