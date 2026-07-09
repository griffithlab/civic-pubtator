#!/usr/bin/env python3
"""
pub_retrieval.py — Look up a PubMed publication, assess download feasibility,
                   and download the main PDF plus supplementary files.

Validates that the target GCS bucket exists and that the publication has not
already been staged there, then queries the NCBI E-utilities API to retrieve
the journal landing page URL for the given PubMed ID.

Usage:
    python src/automation/pub_retrieval.py --pmid <PMID> [options]

Options:
    --bucket gs://BUCKET   GCS bucket to check (default: gs://civic-pubtator-pub-data)
    --check-download       Query Unpaywall to assess open-access status and PDF
                           availability. One-off diagnostic only — not needed for
                           routine use since --download handles retrieval automatically.
    --email EMAIL          Email for Unpaywall API (required with --check-download)
    --download             Download main PDF (publisher page first, PMC fallback)
                           and supplementary files (PMC first, publisher page
                           fallback when PMC lists none)
    --output-dir DIR       Working root directory (default: current directory).
                           Creates <DIR>/<pmid>/01_source/ for the main PDF and
                           <DIR>/<pmid>/01_source/s/ for supplementary files.
    --profile-dir DIR      Persistent Chrome profile directory for browser sessions.
                           Reusing the same profile avoids re-solving reCAPTCHA on
                           repeat runs because Google's trust signals accumulate.
                           (default: ~/.civic-pubtator/browser-profile/)
    --bucket-sync          After a successful --download, upload results to the
                           GCS bucket via src/cloud/sync_pub_data.sh
    --headless             Run browser without a visible window (not recommended;
                           headed mode passes reCAPTCHA more reliably)

Examples:
    python src/automation/pub_retrieval.py --pmid 20407015
    python src/automation/pub_retrieval.py --pmid 20407015 --check-download --email you@example.com
    python src/automation/pub_retrieval.py --pmid 20407015 --download
    python src/automation/pub_retrieval.py --pmid 20407015 --download --output-dir /tmp/test/
    python src/automation/pub_retrieval.py --pmid 20407015 --download --profile-dir ~/my-chrome-profile/
"""

import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request
import urllib.error

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR   = os.path.dirname(os.path.dirname(_SCRIPT_DIR))

_BOLD_BLUE = "\033[1;94m"
_RESET     = "\033[0m"


def _pub_banner(pmid):
    bar = "═" * 70  # ══════ double-line box character
    tty = sys.stdout.isatty()
    if tty:
        return (
            f"\n{_BOLD_BLUE}{bar}{_RESET}\n"
            f"{_BOLD_BLUE}  PUBLICATION: PMID {pmid}{_RESET}\n"
            f"{_BOLD_BLUE}{bar}{_RESET}\n"
        )
    return f"\n{'=' * 70}\n  PUBLICATION: PMID {pmid}\n{'=' * 70}\n"


# ── GCS helpers ───────────────────────────────────────────────────────────────

def bucket_exists(bucket_name):
    """Return (True, None) if the bucket is accessible, else (False, error_str)."""
    result = subprocess.run(
        ["gcloud", "storage", "ls", f"gs://{bucket_name}/"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return False, result.stderr.strip()
    return True, None


def pubid_in_bucket(bucket_name, pmid):
    """Return True if gs://<bucket>/<pmid>/ already exists."""
    result = subprocess.run(
        ["gcloud", "storage", "ls", f"gs://{bucket_name}/{pmid}/"],
        check=False, capture_output=True, text=True,
    )
    return result.returncode == 0


# ── PubMed helpers ────────────────────────────────────────────────────────────

EUTILS_BASE  = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"
ESUMMARY_URL = f"{EUTILS_BASE}/esummary.fcgi?db=pubmed&retmode=json&id={{pmid}}"

# NCBI/Unpaywall/PMC endpoints occasionally hang or reset mid-response (read
# timeouts, connection resets) with no server-side indication of a real
# problem — retrying after a short backoff reliably succeeds.
_URLOPEN_RETRIES = 3
_URLOPEN_BACKOFF = 5  # seconds; doubles on each retry


def _urlopen_with_retry(url_or_req, timeout, description):
    """
    Wrapper around urllib.request.urlopen() that retries transient network
    errors (timeouts, connection resets) with exponential backoff.

    Returns the response body as bytes, or raises RuntimeError after
    exhausting retries. HTTPError is not retried (re-raised immediately)
    since callers may need to inspect the status code (e.g. 404s).
    """
    last_exc = None
    for attempt in range(1, _URLOPEN_RETRIES + 1):
        try:
            with urllib.request.urlopen(url_or_req, timeout=timeout) as resp:
                return resp.read()
        except urllib.error.HTTPError:
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError) as exc:
            last_exc = exc
            if attempt < _URLOPEN_RETRIES:
                wait = _URLOPEN_BACKOFF * (2 ** (attempt - 1))
                print(
                    f"  ({description}: {exc}; retrying in {wait}s "
                    f"[attempt {attempt}/{_URLOPEN_RETRIES}])",
                    file=sys.stderr, flush=True,
                )
                time.sleep(wait)
    raise RuntimeError(f"Error {description}: {last_exc}") from last_exc


def fetch_pubmed_summary(pmid):
    """
    Query NCBI eSummary for the given PMID.

    Returns the parsed JSON result dict for the article, or raises RuntimeError
    on network failure or an unexpected response shape.
    """
    url = ESUMMARY_URL.format(pmid=pmid)
    try:
        data = json.loads(_urlopen_with_retry(url, 15, "fetching PubMed summary").decode())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse PubMed response as JSON: {exc}") from exc

    result = data.get("result", {})
    if pmid not in result:
        raise RuntimeError(
            f"PMID {pmid} not found in PubMed eSummary response. "
            "Check that the ID is correct."
        )
    return result[pmid]


def extract_doi(article):
    """Return the DOI string from an eSummary article dict, or None if absent."""
    for item in article.get("articleids", []):
        if item.get("idtype") == "doi":
            value = item.get("value", "").strip()
            if value:
                return value
    return None


def journal_url_from_doi(doi):
    """Convert a DOI to its canonical https://doi.org/ resolver URL."""
    return f"https://doi.org/{doi}"


# ── Unpaywall helpers ─────────────────────────────────────────────────────────

UNPAYWALL_API = "https://api.unpaywall.org/v2/{doi}?email={email}"


def fetch_unpaywall(doi, email):
    """
    Query the Unpaywall API for open-access PDF availability.

    Returns the parsed JSON response dict, or raises RuntimeError on failure.
    Unpaywall returns HTTP 404 for DOIs it has no record of.
    """
    url = UNPAYWALL_API.format(doi=doi, email=email)
    req = urllib.request.Request(url, headers={"User-Agent": "pub_retrieval/1.0"})
    try:
        return json.loads(_urlopen_with_retry(req, 15, "reaching Unpaywall").decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(f"DOI {doi!r} not found in Unpaywall database.") from exc
        raise RuntimeError(f"Unpaywall HTTP error {exc.code}: {exc.reason}") from exc
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Could not parse Unpaywall response as JSON: {exc}") from exc


def report_unpaywall(doi, email):
    """Fetch Unpaywall data for doi and print a human-readable download assessment."""
    print(f"\nQuerying Unpaywall for DOI {doi} …", flush=True)
    try:
        data = fetch_unpaywall(doi, email)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}", file=sys.stderr, flush=True)
        return

    is_oa     = data.get("is_oa", False)
    oa_status = data.get("oa_status", "unknown")   # gold, green, hybrid, bronze, closed
    best      = data.get("best_oa_location") or {}
    pdf_url   = best.get("url_for_pdf")
    landing   = best.get("url_for_landing_page")
    host_type = best.get("host_type", "")          # publisher or repository
    license_  = best.get("license") or "unknown"

    print(f"\n  Open Access:  {'YES' if is_oa else 'NO'}  (status: {oa_status})")

    if is_oa and pdf_url:
        print(f"  Host type:    {host_type}")
        print(f"  License:      {license_}")
        print(f"  PDF URL:      {pdf_url}")
        if landing and landing != pdf_url:
            print(f"  Landing page: {landing}")
        print("\n  ASSESSMENT: Direct PDF download is likely feasible.")
    elif is_oa and landing:
        print(f"  Host type:    {host_type}")
        print(f"  Landing page: {landing}")
        print(f"  PDF URL:      (not provided by Unpaywall — may require HTML parsing)")
        print("\n  ASSESSMENT: OA paper but no direct PDF link; will need to scrape landing page.")
    else:
        print("  No open-access version found in Unpaywall.")
        print("\n  ASSESSMENT: Download will require institutional access or publisher login.")

    # List all OA locations for transparency
    locations = data.get("oa_locations", [])
    if len(locations) > 1:
        print(f"\n  All OA locations ({len(locations)} found):")
        for loc in locations:
            loc_pdf  = loc.get("url_for_pdf", "—")
            loc_host = loc.get("host_type", "?")
            loc_ver  = loc.get("version", "?")
            print(f"    [{loc_host} / {loc_ver}]  {loc_pdf}")


# ── PMC helpers ───────────────────────────────────────────────────────────────

ELINK_URL  = f"{EUTILS_BASE}/elink.fcgi?dbfrom=pubmed&db=pmc&id={{pmid}}&retmode=json"
EFETCH_URL = f"{EUTILS_BASE}/efetch.fcgi?db=pmc&id={{pmc_id}}&rettype=xml&retmode=xml"
PMC_BASE   = "https://pmc.ncbi.nlm.nih.gov"


def get_pmc_id(pmid):
    """
    Return the PMC ID (as a string) for the given PMID, or None if not in PMC.
    Raises RuntimeError on network failure.
    """
    url = ELINK_URL.format(pmid=pmid)
    try:
        data = json.loads(_urlopen_with_retry(url, 15, "querying PMC elink").decode())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Error querying PMC elink: {exc}") from exc

    for linkset in data.get("linksets", []):
        for db in linkset.get("linksetdbs", []):
            if db.get("dbto") == "pmc" and db.get("linkname") == "pubmed_pmc":
                links = db.get("links", [])
                if links:
                    return str(links[0])
    return None


def get_pmc_files(pmc_id):
    """
    Fetch PMC efetch XML and return a dict:
      {
        "pdf_url":      str | None,
        "supplementary": [
          {"label": str, "filename": str, "url": str, "mimetype": str, "caption": str},
          ...
        ]
      }

    Raises RuntimeError on network failure.
    """
    url = EFETCH_URL.format(pmc_id=pmc_id)
    xml = _urlopen_with_retry(
        url, 30, f"fetching PMC XML for PMC{pmc_id}"
    ).decode("utf-8", errors="replace")

    # Main PDF: look for <self-uri content-type="pdf" xlink:href="...">
    pdf_match = re.search(
        r'<self-uri[^>]+content-type=["\']pdf["\'][^>]+xlink:href=["\']([^"\']+)["\']',
        xml,
    ) or re.search(
        r'<self-uri[^>]+xlink:href=["\']([^"\']+\.pdf)["\']',
        xml,
    )
    pdf_filename = pdf_match.group(1) if pdf_match else None
    pdf_url = (
        f"{PMC_BASE}/articles/PMC{pmc_id}/pdf/{pdf_filename}"
        if pdf_filename else None
    )

    # Supplementary files: parse each <supplementary-material> block
    supp_blocks = re.findall(
        r'<supplementary-material[^>]*>(.*?)</supplementary-material>',
        xml, re.DOTALL,
    )
    supplementary = []
    for i, block in enumerate(supp_blocks, 1):
        href_match = re.search(r'xlink:href=["\']([^"\']+)["\']', block)
        if not href_match:
            continue
        filename = href_match.group(1)

        label_match = re.search(r'<label>([^<]+)</label>', block)
        label = label_match.group(1).strip() if label_match else str(i)

        cap_match = re.search(r'<caption>\s*<p[^>]*>([^<]+)', block)
        caption = cap_match.group(1).strip()[:120] if cap_match else ""

        mime_match     = re.search(r'mimetype=["\']([^"\']+)["\']', block)
        mime_sub_match = re.search(r'mime-subtype=["\']([^"\']+)["\']', block)
        mimetype = (
            f"{mime_match.group(1)}/{mime_sub_match.group(1)}"
            if mime_match and mime_sub_match else ""
        )

        supplementary.append({
            "label":    label,
            "filename": filename,
            "url":      f"{PMC_BASE}/articles/instance/{pmc_id}/bin/{filename}",
            "mimetype": mimetype,
            "caption":  caption,
        })

    return {"pdf_url": pdf_url, "supplementary": supplementary}


# ── Playwright helpers ────────────────────────────────────────────────────────

DEFAULT_PROFILE_DIR = os.path.expanduser("~/.civic-pubtator/browser-profile")

# PDF download link selectors tried in order on publisher landing pages.
# More specific patterns come first to avoid false positives.
_PDF_LINK_SELECTORS = [
    'a[href*="article-pdf"]',           # AACR, Oxford Academic
    'a[data-article-pdf="true"]',       # Nature / Springer Nature
    'a[href*="/doi/pdf/"]',             # Wiley Online Library (/doi/pdf/{DOI})
    'a[href*="/pdf/"][href$=".pdf"]',    # Springer, Nature (older patterns)
    'a[href$=".pdf"]',                   # generic .pdf href
    'a:has-text("Download PDF")',
    'a:has-text("PDF")',
    'a:has-text("Full Text (PDF)")',
    'a:has-text("Full text PDF")',
]


def _ensure_pdf_preference(profile_dir):
    """
    Write (or merge) always_open_pdf_externally=True into the Chrome Preferences
    file inside profile_dir.  Merges with any existing prefs so prior cookies and
    site data are not lost.
    """
    prefs_dir  = os.path.join(profile_dir, "Default")
    prefs_file = os.path.join(prefs_dir, "Preferences")
    os.makedirs(prefs_dir, exist_ok=True)

    prefs = {}
    if os.path.isfile(prefs_file):
        try:
            with open(prefs_file) as fh:
                prefs = json.load(fh)
        except (json.JSONDecodeError, OSError):
            pass

    prefs.setdefault("plugins", {})["always_open_pdf_externally"] = True

    with open(prefs_file, "w") as fh:
        json.dump(prefs, fh)


def _launch_browser(pw, headless, profile_dir):
    """Launch a persistent Chrome context (falls back to bundled Chromium)."""
    kwargs = dict(
        user_data_dir=profile_dir,
        headless=headless,
        accept_downloads=True,
        args=[
            "--disable-blink-features=AutomationControlled",
            "--disable-automation",
            "--disable-infobars",
        ],
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    try:
        ctx = pw.chromium.launch_persistent_context(channel="chrome", **kwargs)
    except Exception:
        ctx = pw.chromium.launch_persistent_context(**kwargs)
    # Suppress the navigator.webdriver property that automation-detection
    # scripts (including Cloudflare Turnstile) commonly check.
    ctx.add_init_script(
        "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
    )
    return ctx


_CF_TIMEOUT = 90  # seconds to wait for user to solve Cloudflare challenge


def _start_countdown(total_secs, label):
    """
    Start a background thread that prints a live countdown on one terminal line.
    Returns (thread, stop_event).  Caller must call stop_event.set() when done.
    """
    stop = threading.Event()
    width = len(label) + 20

    def _run():
        deadline = time.time() + total_secs
        while not stop.is_set():
            remaining = max(0, int(deadline - time.time()))
            print(f"\r    {label}: {remaining:3d}s remaining ",
                  end="", flush=True)
            stop.wait(timeout=1)
        print(f"\r{' ' * width}\r", end="", flush=True)

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    return t, stop


def _stop_countdown(t, stop, final_msg=""):
    stop.set()
    t.join(timeout=2)
    if final_msg:
        print(f"    {final_msg}", flush=True)


def _wait_for_cloudflare_if_present(page):
    """
    If the current page is a Cloudflare managed challenge ("Just a moment..."),
    print a prompt and poll every second with a live countdown until the
    challenge is solved or the timeout expires.
    Returns True once the challenge is gone (or if there was none).
    Returns False and prints an error if the wait times out.
    """
    if "just a moment" not in (page.title() or "").lower():
        return True
    print(
        "    Cloudflare challenge — please click the verification box in the browser.",
        flush=True,
    )
    deadline = time.time() + _CF_TIMEOUT
    while time.time() < deadline:
        remaining = int(deadline - time.time())
        print(f"\r    Waiting for challenge to be solved: {remaining:3d}s remaining ",
              end="", flush=True)
        try:
            resolved = page.evaluate(
                "() => !document.title.toLowerCase().includes('just a moment')"
            )
            if resolved:
                print(f"\r    Challenge passed — continuing.{' ' * 20}", flush=True)
                try:
                    page.wait_for_load_state("networkidle", timeout=10_000)
                except Exception:
                    pass
                return True
        except Exception:
            pass  # page may be mid-navigation; keep polling
        time.sleep(1)
    print(
        f"\r    Timed out waiting for Cloudflare challenge.{' ' * 15}",
        file=sys.stderr, flush=True,
    )
    return False


def _click_open_button_if_present(page, timeout=5_000):
    """
    Some Cloudflare-protected direct-download endpoints (e.g. ascopubs.org
    /doi/pdf/... URLs) pass the JS challenge automatically but then render a
    fallback page with an "Open" button/link — Cloudflare's redirect script
    cannot itself trigger a file download without a genuine user gesture, so
    it falls back to asking for one click. Click it automatically if present.
    Returns True if a click was performed.
    """
    for role in ("button", "link"):
        try:
            el = page.get_by_role(role, name="Open", exact=True).first
            if el.is_visible(timeout=timeout):
                el.click()
                return True
        except Exception:
            pass
    return False


def _download_direct(page, url, dest, PWTimeout):
    """
    Download a single file from a direct URL using Playwright's download event.
    Returns True if saved successfully, False otherwise.
    """
    t, stop = _start_countdown(90, "Waiting for download")
    try:
        with page.expect_download(timeout=90_000) as dl_info:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as nav_exc:
                if "Download is starting" not in str(nav_exc):
                    raise
        dl = dl_info.value
        _stop_countdown(t, stop)
        dl.save_as(dest)
        size = os.path.getsize(dest)
        print(f"    Saved → {dest}  ({size:,} bytes)", flush=True)
        return True
    except PWTimeout:
        _stop_countdown(t, stop, "TIMEOUT: no download started.")
        return False
    except Exception as exc:
        _stop_countdown(t, stop, f"ERROR: {exc}")
        return False


def _try_publisher_pdf(page, doi, dest, PWTimeout):
    """
    Navigate to the DOI landing page and attempt to find and click a PDF
    download link.  Tries a ranked list of CSS selectors across common publisher
    page layouts.  Returns True if the file was saved, False if no link was
    found or the download failed (caller should fall back to PMC).
    """
    doi_url = f"https://doi.org/{doi}"
    print(f"    Navigating to publisher page: {doi_url}", flush=True)
    try:
        page.goto(doi_url, wait_until="domcontentloaded", timeout=60_000)
    except Exception as exc:
        print(f"    Could not load publisher page: {exc}", file=sys.stderr, flush=True)
        return False

    # Publisher pages often never reach "networkidle" due to ongoing analytics
    # traffic — wait briefly for dynamic content to render, ignoring the timeout.
    try:
        page.wait_for_load_state("networkidle", timeout=8_000)
    except Exception:
        pass

    # Handle Cloudflare managed challenge on the article page itself.
    if not _wait_for_cloudflare_if_present(page):
        return False

    # LWW / Wolters Kluwer EJP platform: detected via wkhealth_pdf_url meta tag
    # or data-pdf-url attribute.  The PDF lives behind a "Download" dropdown —
    # we must click the toggle to open it, then click the "PDF" option.
    try:
        lww_pdf_url = page.evaluate("""
            () => {
                const m = document.querySelector('meta[name="wkhealth_pdf_url"]');
                if (m) return m.getAttribute('content');
                const d = document.querySelector('[data-pdf-url]');
                if (d) return d.getAttribute('data-pdf-url');
                return null;
            }
        """)
        if lww_pdf_url:
            # Approach 1: API fetch with browser session cookies — fast if the
            # server returns the PDF directly (avoids clicking entirely).
            try:
                r = page.request.get(lww_pdf_url)
                if r.ok and 'pdf' in r.headers.get('content-type', '').lower():
                    os.makedirs(os.path.dirname(dest), exist_ok=True)
                    with open(dest, 'wb') as fh:
                        fh.write(r.body())
                    size = os.path.getsize(dest)
                    print(f"    Saved (LWW API) → {dest}  ({size:,} bytes)",
                          flush=True)
                    return True
            except Exception:
                pass

            # Approach 2: open the "Download" dropdown, then click "PDF".
            print(f"    Detected LWW platform — opening Download dropdown …",
                  flush=True)
            for toggle_sel in [
                'button:has-text("Download")',
                'a:has-text("Download")',
            ]:
                try:
                    toggle = page.locator(toggle_sel).first
                    if toggle.is_visible(timeout=3_000):
                        toggle.click()
                        break
                except Exception:
                    pass
            # Wait for the PDF option to become visible inside the dropdown.
            pdf_opt = page.locator('a:has-text("PDF"), button:has-text("PDF")').first
            pdf_opt.wait_for(state="visible", timeout=5_000)
            print(f"    Found PDF option in dropdown", flush=True)
            # Click it — LWW may download on the current page or open a new tab.
            t, stop = _start_countdown(30, "Waiting for PDF download")
            try:
                with page.expect_download(timeout=30_000) as dl_info:
                    pdf_opt.click()
                _stop_countdown(t, stop)
                dl = dl_info.value
                dl.save_as(dest)
                size = os.path.getsize(dest)
                print(f"    Saved (publisher) → {dest}  ({size:,} bytes)",
                      flush=True)
                return True
            except Exception:
                _stop_countdown(t, stop)
            # If no download on this page, check for a new tab.
            t2, stop2 = _start_countdown(30, "Waiting for LWW to open PDF tab")
            try:
                with page.context.expect_page(timeout=30_000) as np_info:
                    try:
                        pdf_opt.click()
                    except Exception:
                        pass
                _stop_countdown(t2, stop2)
                new_page = np_info.value
                new_page.wait_for_load_state("domcontentloaded", timeout=15_000)
                t3, stop3 = _start_countdown(60, "Waiting for download in new tab")
                try:
                    with new_page.expect_download(timeout=60_000) as dl_info:
                        pass
                    _stop_countdown(t3, stop3)
                    dl = dl_info.value
                    dl.save_as(dest)
                    size = os.path.getsize(dest)
                    print(f"    Saved (publisher) → {dest}  ({size:,} bytes)",
                          flush=True)
                    return True
                except Exception:
                    _stop_countdown(t3, stop3)
            except Exception:
                _stop_countdown(t2, stop2)
    except Exception:
        pass

    for selector in _PDF_LINK_SELECTORS:
        try:
            locator = page.locator(selector)
            # Walk up to 5 matches per selector: the first match may be in a
            # hidden sticky header; a later match in the article body is visible.
            el = None
            for i in range(min(locator.count(), 5)):
                candidate = locator.nth(i)
                if candidate.is_visible(timeout=1_000):
                    el = candidate
                    break
            if el is None:
                continue
            print(f"    Found PDF link ({selector})", flush=True)
            # Start a countdown — clicking may trigger a Cloudflare challenge
            # before the download fires (e.g. Wiley /doi/pdf/ is gated).
            t, stop = _start_countdown(180, "Waiting for PDF download")
            try:
                with page.expect_download(timeout=180_000) as dl_info:
                    try:
                        el.click()
                    except Exception as click_exc:
                        if "Download is starting" not in str(click_exc):
                            raise
                    try:
                        page.wait_for_load_state("domcontentloaded", timeout=5_000)
                    except Exception:
                        pass
                    # Stop main countdown before Cloudflare check (which has
                    # its own per-second countdown display).
                    _stop_countdown(t, stop)
                    t = stop = None
                    if not _wait_for_cloudflare_if_present(page):
                        raise RuntimeError(
                            "Cloudflare challenge on PDF link not resolved"
                        )
                    if _click_open_button_if_present(page):
                        print(
                            "    Clicked \"Open\" on Cloudflare download fallback page",
                            flush=True,
                        )
            except PWTimeout:
                if stop is not None:
                    _stop_countdown(t, stop)
                continue
            except Exception:
                if stop is not None:
                    _stop_countdown(t, stop)
                continue
            if stop is not None:
                _stop_countdown(t, stop)
            dl = dl_info.value
            dl.save_as(dest)
            size = os.path.getsize(dest)
            print(f"    Saved (publisher) → {dest}  ({size:,} bytes)", flush=True)
            return True
        except Exception:
            continue

    print("    No PDF download link found on publisher page.", file=sys.stderr, flush=True)
    return False


_SUPP_EXTENSIONS = frozenset([
    '.pdf', '.doc', '.docx', '.xls', '.xlsx', '.ppt', '.pptx',
    '.zip', '.csv', '.txt', '.fasta', '.sdf',
])


def _scan_publisher_supplementary(page):
    """
    Scan the currently-loaded publisher page for supplementary file links.
    Returns list of (filename, url, display_text) tuples.
    Applies two independent heuristics:
      1. The href path contains a supplementary-indicating token.
      2. The visible link text/title contains a supplementary-indicating phrase.
    Only links with a recognised file extension are returned.
    """
    import posixpath

    _SUPP_URL_TOKENS = [
        'supplement', '/supp', 'supp-', 'supp_', 'suppl',
        'supporting-info', 'supporting_info',
        '/esm/',        # Springer Nature ESM CDN (static-content.springer.com/esm/)
    ]
    _SUPP_TEXT_TOKENS = [
        'supplement', 'table s', 'figure s', 'supp. ', 'supporting info',
    ]

    try:
        links = page.evaluate("""() =>
            Array.from(document.querySelectorAll('a[href]')).map(a => ({
                href: a.href,
                text: (a.innerText || a.textContent || '').trim().slice(0, 300),
                title: (a.title || '').trim()
            }))
        """)
    except Exception:
        return []

    seen_urls = set()
    found = []

    for link in links:
        href  = (link.get('href') or '').strip()
        text  = (link.get('text') or '').strip()
        title = (link.get('title') or '').strip()

        if not href or href.startswith(('javascript:', 'mailto:', '#')):
            continue
        if href in seen_urls:
            continue

        # Require a recognisable downloadable file extension
        path_part = href.split('?')[0].split('#')[0]
        _, ext = posixpath.splitext(path_part)
        if ext.lower() not in _SUPP_EXTENSIONS:
            continue

        href_lower    = href.lower()
        combined_text = (text + ' ' + title).lower()

        has_supp_url  = any(t in href_lower      for t in _SUPP_URL_TOKENS)
        has_supp_text = any(t in combined_text    for t in _SUPP_TEXT_TOKENS)

        if not (has_supp_url or has_supp_text):
            continue

        filename = posixpath.basename(path_part) or f"supplement_{len(found) + 1}{ext.lower()}"
        seen_urls.add(href)
        found.append((filename, href, text or title or filename))

    return found


# ── Browser dependency check ──────────────────────────────────────────────────

def check_browser_dependencies():
    """
    Verify that Playwright and at least one usable browser binary are present.
    Prints clear installation instructions and returns False if anything is missing.
    """
    # 1. Playwright Python package
    try:
        import playwright  # noqa: F401
    except ImportError:
        print(
            "ERROR: Playwright is not installed.\n"
            "\nTo install:\n"
            "  pip install playwright\n"
            "  playwright install chromium",
            file=sys.stderr, flush=True,
        )
        return False

    # 2. A usable browser binary — system Chrome (preferred) or Playwright Chromium
    chrome_paths = [
        "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",  # macOS
        "/usr/bin/google-chrome",                                          # Linux
        "/usr/bin/chromium-browser",
        "/usr/bin/chromium",
    ]
    has_system_chrome = any(os.path.isfile(p) for p in chrome_paths)

    pw_cache = os.path.expanduser("~/Library/Caches/ms-playwright")   # macOS
    if not os.path.isdir(pw_cache):
        pw_cache = os.path.expanduser("~/.cache/ms-playwright")        # Linux
    has_pw_chromium = os.path.isdir(pw_cache) and any(
        "chromium" in entry.lower() for entry in os.listdir(pw_cache)
    )

    if not has_system_chrome and not has_pw_chromium:
        print(
            "ERROR: No browser found for Playwright.\n"
            "\nTo install Playwright's bundled Chromium:\n"
            "  playwright install chromium\n"
            "\nAlternatively, install Google Chrome from https://www.google.com/chrome/",
            file=sys.stderr, flush=True,
        )
        return False

    return True


# ── Bucket sync ───────────────────────────────────────────────────────────────

def sync_to_bucket(bucket, pmid, work_dir):
    """
    Upload <work_dir>/<pmid>/ to gs://<bucket>/<pmid>/ using sync_pub_data.sh.
    Returns True on success, False on failure.
    """
    script = os.path.join(_REPO_DIR, "src", "cloud", "sync_pub_data.sh")
    cmd    = ["bash", script, "--bucket", bucket, "--local-dir", work_dir, "up", pmid]
    print(f"\nUploading {pmid}/ to gs://{bucket}/{pmid}/ …", flush=True)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        print(f"  ERROR: upload failed:\n{result.stderr.strip()}",
              file=sys.stderr, flush=True)
        return False
    if result.stdout.strip():
        for line in result.stdout.strip().splitlines():
            print(f"  {line}", flush=True)
    print("  Upload complete.", flush=True)
    return True


# ── Download orchestration ────────────────────────────────────────────────────

def run_download(pmid, doi, work_dir, headless=False, profile_dir=DEFAULT_PROFILE_DIR):
    """
    Download the main PDF and supplementary files for pmid into:

        <work_dir>/<pmid>/01_source/<pmid>.pdf          ← main PDF
        <work_dir>/<pmid>/01_source/s/<filename>        ← supplementary files

    The main PDF is attempted from the publisher's journal page first (via DOI),
    falling back to PMC if the publisher page yields no downloadable link. If
    the PMC fallback is what ultimately supplies the PDF, the session pauses
    (same as the total-failure case) so the user can manually swap in the
    publisher's version if they prefer it.
    Supplementary files are fetched from PMC when available; if PMC lists none,
    the publisher page is scanned for supplementary links as a fallback.

    All downloads share a single browser session so CAPTCHA cookies carry across.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        raise RuntimeError(
            "Playwright is not installed.\n"
            "  pip install playwright\n"
            "  playwright install chromium"
        )

    source_dir = os.path.join(work_dir, pmid, "01_source")
    supp_dir   = os.path.join(source_dir, "s")

    # 1. Resolve PMC ID (needed for supplementary files)
    print(f"\nLooking up PMC entry for PMID {pmid} …", flush=True)
    try:
        pmc_id = get_pmc_id(pmid)
    except RuntimeError as exc:
        print(f"  ERROR: {exc}", file=sys.stderr, flush=True)
        return

    if pmc_id:
        print(f"  Found PMC{pmc_id}", flush=True)
    else:
        print("  No PMC entry found — supplementary files will not be available.",
              file=sys.stderr, flush=True)

    # 2. Get PMC file list
    pmc_files = None
    if pmc_id:
        print("  Fetching file list from PMC efetch XML …", flush=True)
        try:
            pmc_files = get_pmc_files(pmc_id)
        except RuntimeError as exc:
            print(f"  ERROR fetching PMC file list: {exc}", file=sys.stderr, flush=True)

    pdf_dest  = os.path.join(source_dir, f"{pmid}.pdf")
    pmc_pdf   = pmc_files["pdf_url"] if pmc_files else None

    supp_downloads = []
    if pmc_files and pmc_files["supplementary"]:
        print(f"  Supplementary files ({len(pmc_files['supplementary'])}) → {supp_dir}/",
              flush=True)
        for sf in pmc_files["supplementary"]:
            label_tag = f"[S{sf['label']}]"
            mime_tag  = f"  ({sf['mimetype']})" if sf["mimetype"] else ""
            cap_tag   = f"  \"{sf['caption']}...\"" if sf["caption"] else ""
            print(f"    {label_tag}  {sf['filename']}{mime_tag}{cap_tag}", flush=True)
            supp_downloads.append(
                (os.path.join(supp_dir, sf["filename"]), sf["url"])
            )
    elif pmc_files:
        print("  No supplementary files found in PMC XML.", flush=True)

    # 3. Download everything in one browser session
    mode = "headless" if headless else "headed"
    print(f"\nStarting {mode} browser session …", flush=True)
    _ensure_pdf_preference(profile_dir)
    print(f"  Using browser profile: {profile_dir}", flush=True)

    saved = []
    with sync_playwright() as pw:
        context = _launch_browser(pw, headless, profile_dir)
        page    = context.new_page()

        # 3a. Open the journal page in the user's personal browser immediately
        # so they can follow along and manually download if automation fails.
        os.makedirs(source_dir, exist_ok=True)
        manual_browser_opened = False
        if doi:
            doi_url = f"https://doi.org/{doi}"
            print(f"\n  ┌─ Manual download reference ────────────────────────────────",
                  flush=True)
            print(f"  │  Journal URL : {doi_url}", flush=True)
            print(f"  │  Save PDF to : {pdf_dest}", flush=True)
            print(f"  │  Filename    : {pmid}.pdf", flush=True)
            print(f"  └────────────────────────────────────────────────────────────",
                  flush=True)
            try:
                subprocess.run(["open", doi_url], check=True)
                manual_browser_opened = True
            except Exception as exc:
                print(f"  (Could not open URL in browser: {exc})",
                      file=sys.stderr, flush=True)

        # 3b. Main PDF — publisher first
        print(f"\n  Main PDF ({pmid}.pdf):", flush=True)
        pdf_source = None
        if doi:
            pdf_ok = _try_publisher_pdf(page, doi, pdf_dest, PWTimeout)
        else:
            print("    No DOI available — skipping publisher attempt.", flush=True)
            pdf_ok = False
        if pdf_ok:
            pdf_source = "publisher"

        # 3c. If PMC had no supplementary files, scan the publisher page while
        # we are still on it — the PMC-PDF fallback below would navigate away.
        if not supp_downloads and doi:
            print("\n  Scanning publisher page for supplementary files …", flush=True)
            pub_supps = _scan_publisher_supplementary(page)
            if pub_supps:
                print(
                    f"  Found {len(pub_supps)} supplementary file(s) on publisher page:",
                    flush=True,
                )
                for filename, url, display in pub_supps:
                    print(f"    {display[:80]}  ({filename})", flush=True)
                    supp_downloads.append((os.path.join(supp_dir, filename), url))
            else:
                print("  No supplementary files found on publisher page.", flush=True)

        # 3d. PMC fallback if publisher PDF failed
        if not pdf_ok:
            if pmc_pdf:
                print(f"    Falling back to PMC: {pmc_pdf}", flush=True)
                pdf_ok = _download_direct(page, pmc_pdf, pdf_dest, PWTimeout)
                if pdf_ok:
                    pdf_source = "pmc"
            else:
                print("    No PMC PDF fallback available.", file=sys.stderr, flush=True)

        if pdf_ok:
            saved.append(pdf_dest)

        # 3e. Supplementary files — from PMC or publisher page
        if supp_downloads:
            print(f"\n  Supplementary files:", flush=True)
            os.makedirs(supp_dir, exist_ok=True)
            for dest, url in supp_downloads:
                print(f"  Downloading {os.path.basename(dest)} …", flush=True)
                if _download_direct(page, url, dest, PWTimeout):
                    saved.append(dest)

        # 3f. If automation could not save the PDF but the user's browser is
        # open on the journal page, pause so they can download it manually.
        if manual_browser_opened and pdf_dest not in saved:
            print(f"\n  Automation did not save a PDF.", flush=True)
            print(f"  Please download from the journal page in your browser and save to:",
                  flush=True)
            print(f"    {pdf_dest}", flush=True)
            try:
                input("\n  Press Enter when done … ")
            except KeyboardInterrupt:
                print("\n  Cancelled — continuing …", flush=True)
            except EOFError:
                print(flush=True)
            if os.path.isfile(pdf_dest):
                saved.append(pdf_dest)
                size = os.path.getsize(pdf_dest)
                print(f"  PDF confirmed: {size:,} bytes", flush=True)

        # 3g. The PMC copy is a fallback of last resort — if it's what ended up
        # saved, pause so the user can swap in the publisher's version instead,
        # using the same journal page already open in their browser.
        elif manual_browser_opened and pdf_source == "pmc":
            print(f"\n  Main PDF came from PubMed Central (publisher download failed or was skipped).",
                  flush=True)
            print(f"  If you'd prefer the publisher's version, download it now in the browser",
                  flush=True)
            print(f"  and save over:", flush=True)
            print(f"    {pdf_dest}", flush=True)
            try:
                input("\n  Press Enter to continue (replace the file first if desired) … ")
            except KeyboardInterrupt:
                print("\n  Cancelled — continuing …", flush=True)
            except EOFError:
                print(flush=True)
            if os.path.isfile(pdf_dest):
                size = os.path.getsize(pdf_dest)
                print(f"  Using PDF: {size:,} bytes", flush=True)

        context.close()

    total = 1 + len(supp_downloads)
    print(f"\nDone — {len(saved)}/{total} file(s) saved.", flush=True)

    # If nothing was saved at all — main PDF included — remove the (empty)
    # directories created for this attempt rather than leaving empty clutter
    # behind. Only removes dirs that are actually empty, so any pre-existing
    # or partially-populated content is left untouched.
    if not saved:
        pub_dir = os.path.join(work_dir, pmid)
        for d in (supp_dir, source_dir, pub_dir):
            try:
                if os.path.isdir(d) and not os.listdir(d):
                    os.rmdir(d)
            except OSError:
                pass

    return len(saved)


# ── Argument helpers ──────────────────────────────────────────────────────────

def parse_bucket_arg(raw):
    """Strip leading gs:// and trailing slashes from a bucket argument."""
    name = raw
    if name.startswith("gs://"):
        name = name[len("gs://"):]
    name = name.rstrip("/")
    if "/" in name:
        raise argparse.ArgumentTypeError(
            f"Expected a bucket name (gs://bucket-name), got a path: {raw!r}"
        )
    return name


# ── Main ──────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Validate a GCS bucket, look up a PubMed publication, "
                    "assess download feasibility, and download files.",
    )
    pmid_group = parser.add_mutually_exclusive_group(required=True)
    pmid_group.add_argument("--pmid", help="PubMed ID of the publication")
    pmid_group.add_argument(
        "--pmid-file",
        metavar="TSV",
        help=(
            "TSV file with a header row and PMIDs in the first column. "
            "Each PMID is processed in order, one at a time."
        ),
    )
    parser.add_argument(
        "--bucket",
        type=parse_bucket_arg,
        default="civic-pubtator-pub-data",
        metavar="gs://BUCKET",
        help="Target GCS bucket (default: gs://civic-pubtator-pub-data)",
    )
    parser.add_argument(
        "--check-download",
        action="store_true",
        help=(
            "Query Unpaywall to assess open-access status and PDF availability. "
            "Useful for a one-off check on an unfamiliar paper; not needed for "
            "routine use because --download handles retrieval automatically."
        ),
    )
    parser.add_argument(
        "--email",
        help="Email address for Unpaywall API requests (required with --check-download)",
    )
    parser.add_argument(
        "--download",
        action="store_true",
        help=(
            "Download the main PDF and supplementary files via a headed browser. "
            "The main PDF is fetched from the publisher's journal page first "
            "(via DOI), falling back to PMC if no link is found. "
            "Supplementary files are fetched from PMC when available; if PMC "
            "lists none, the publisher page is also scanned for supplementary links."
        ),
    )
    parser.add_argument(
        "--output-dir",
        metavar="DIR",
        default=".",
        help=(
            "Working root directory (default: current directory). "
            "Files are placed under <DIR>/<pmid>/01_source/ (main PDF) "
            "and <DIR>/<pmid>/01_source/s/ (supplementary files)."
        ),
    )
    parser.add_argument(
        "--profile-dir",
        metavar="DIR",
        default=DEFAULT_PROFILE_DIR,
        help=(
            f"Persistent Chrome profile directory (default: {DEFAULT_PROFILE_DIR}). "
            "Reusing the same profile across runs lets Google's reCAPTCHA trust "
            "accumulate so CAPTCHA challenges become less frequent over time."
        ),
    )
    parser.add_argument(
        "--headless",
        action="store_true",
        help="Run browser without a visible window (default: headed). "
             "Headed mode is more reliable for sites with reCAPTCHA or Cloudflare.",
    )
    parser.add_argument(
        "--bucket-sync",
        action="store_true",
        help=(
            "After a successful --download, upload the result to the GCS bucket "
            "using src/cloud/sync_pub_data.sh. Requires --download."
        ),
    )
    args = parser.parse_args()

    if args.check_download and not args.email:
        parser.error("--email is required when using --check-download")
    if args.bucket_sync and not args.download:
        parser.error("--bucket-sync requires --download")

    # ── Resolve PMID list ─────────────────────────────────────────────────────
    if args.pmid:
        pmids = [args.pmid.strip()]
    else:
        pmids = _load_pmids_from_tsv(args.pmid_file)
        if not pmids:
            print("ERROR: No valid PMIDs found in the file.", file=sys.stderr, flush=True)
            sys.exit(1)

    bucket = args.bucket

    # ── 1. Validate the bucket once (shared across all PMIDs) ─────────────────
    print(f"Checking bucket gs://{bucket}/ …", flush=True)
    ok, err = bucket_exists(bucket)
    if not ok:
        print(f"ERROR: Cannot access bucket gs://{bucket}/: {err}", file=sys.stderr, flush=True)
        sys.exit(1)
    print(f"  Bucket gs://{bucket}/ is accessible.", flush=True)

    if args.download and not check_browser_dependencies():
        sys.exit(1)

    work_dir    = os.path.expanduser(args.output_dir)
    profile_dir = os.path.expanduser(args.profile_dir)

    n_total   = len(pmids)
    n_skipped = 0
    n_failed  = 0

    for idx, pmid in enumerate(pmids, 1):
        if n_total > 1:
            print(f"\n{'═' * 60}", flush=True)
            print(f"  PMID {idx}/{n_total}: {pmid}", flush=True)
            print(f"{'═' * 60}", flush=True)

        print(_pub_banner(pmid), flush=True)

        # ── 2. Check for existing publication directory in bucket ──────────────
        print(f"Checking for existing publication directory gs://{bucket}/{pmid}/ …",
              flush=True)
        if pubid_in_bucket(bucket, pmid):
            print(
                f"WARNING: gs://{bucket}/{pmid}/ already exists. "
                "Skipping to avoid overwriting existing data.",
                file=sys.stderr, flush=True,
            )
            n_skipped += 1
            continue
        print("  Not yet present — safe to proceed.", flush=True)

        # ── 3. Fetch PubMed metadata ───────────────────────────────────────────
        print(f"\nQuerying PubMed for PMID {pmid} …", flush=True)
        try:
            article = fetch_pubmed_summary(pmid)
        except RuntimeError as exc:
            print(f"ERROR: {exc}", file=sys.stderr, flush=True)
            n_failed += 1
            continue

        title   = article.get("title", "(title unavailable)")
        journal = (article.get("fulljournalname")
                   or article.get("source", "(journal unavailable)"))
        doi     = extract_doi(article)

        print(f"  Title:   {title}")
        print(f"  Journal: {journal}")
        if doi:
            print(f"  DOI:     {doi}")
            print(f"  URL:     {journal_url_from_doi(doi)}")
        else:
            print("  DOI:     (not available in PubMed record)")
            print(f"  URL:     https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

        # ── 4. Unpaywall assessment (optional) ────────────────────────────────
        if args.check_download:
            if doi:
                report_unpaywall(doi, args.email)
            else:
                print(
                    "\nWARNING: --check-download skipped — no DOI for this record.",
                    file=sys.stderr, flush=True,
                )

        # ── 5. Download files (optional) ──────────────────────────────────────
        if args.download:
            n_saved = run_download(pmid, doi, work_dir,
                                   headless=args.headless, profile_dir=profile_dir)
            if not n_saved:
                n_failed += 1

            # ── 6. Sync to bucket (optional) ──────────────────────────────────
            if args.bucket_sync:
                if n_saved:
                    sync_to_bucket(bucket, pmid, work_dir)
                else:
                    print(
                        "\nWARNING: --bucket-sync skipped — no files were saved.",
                        file=sys.stderr, flush=True,
                    )

    if n_total > 1:
        print(f"\n{'═' * 60}", flush=True)
        print(f"  Batch complete: {n_total} PMID(s), "
              f"{n_skipped} skipped, {n_failed} failed.", flush=True)
        print(f"{'═' * 60}", flush=True)


def _load_pmids_from_tsv(path):
    """
    Read a TSV file with a header row and PMIDs in the first column.
    Returns a list of validated PMID strings.
    Prints a warning for any row where the first column is not a numeric PMID.
    """
    path = os.path.expanduser(path)
    if not os.path.isfile(path):
        print(f"ERROR: PMID file not found: {path}", file=sys.stderr, flush=True)
        sys.exit(1)

    pmids   = []
    skipped = 0
    with open(path, newline="", encoding="utf-8") as fh:
        for lineno, line in enumerate(fh, 1):
            fields = line.rstrip("\n").split("\t")
            if not fields:
                continue
            val = fields[0].strip()
            if lineno == 1:
                # Skip the header row — it should not be numeric.
                if not val.isdigit():
                    print(f"  TSV header: {val!r}", flush=True)
                    continue
                # If the first row IS numeric, treat it as data (no header).
                print(
                    f"WARNING: first row of {path!r} looks like a PMID, not a header. "
                    "Processing it as data.",
                    file=sys.stderr, flush=True,
                )
            if not val:
                continue
            if not val.isdigit():
                print(
                    f"WARNING: row {lineno} — first column {val!r} is not a numeric "
                    "PMID; skipping.",
                    file=sys.stderr, flush=True,
                )
                skipped += 1
                continue
            pmids.append(val)

    print(
        f"  Loaded {len(pmids)} PMID(s) from {path}"
        + (f" ({skipped} invalid row(s) skipped)" if skipped else ""),
        flush=True,
    )
    return pmids


if __name__ == "__main__":
    main()
