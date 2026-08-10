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
import hashlib
import json
import os
import re
import select
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


def _pub_banner(pmid, idx=None, n_total=None):
    bar = "═" * 70  # ══════ double-line box character
    tty = sys.stdout.isatty()
    label = f"PMID {idx}/{n_total}: {pmid}" if idx is not None else f"PUBLICATION: PMID {pmid}"
    if tty:
        return (
            f"\n{_BOLD_BLUE}{bar}{_RESET}\n"
            f"{_BOLD_BLUE}  {label}{_RESET}\n"
            f"{_BOLD_BLUE}{bar}{_RESET}\n"
        )
    return f"\n{'=' * 70}\n  {label}\n{'=' * 70}\n"


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


def list_bucket_pubids(bucket_name):
    """
    Return the set of PMIDs already present as top-level "directories" in
    gs://<bucket_name>/, via a single listing call. Replaces one gcloud
    invocation per PMID (a per-publication existence check), which becomes
    very slow once the bucket holds hundreds of publications.
    """
    result = subprocess.run(
        ["gcloud", "storage", "ls", f"gs://{bucket_name}/"],
        check=False, capture_output=True, text=True,
    )
    if result.returncode != 0:
        return set()
    prefix = f"gs://{bucket_name}/"
    pubids = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line.startswith(prefix):
            continue
        name = line[len(prefix):].strip("/")
        if name and "/" not in name:
            pubids.add(name)
    return pubids


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

IDCONV_URL = "https://www.ncbi.nlm.nih.gov/pmc/utils/idconv/v1.0/?ids={pmid}&format=json"
EFETCH_URL = f"{EUTILS_BASE}/efetch.fcgi?db=pmc&id={{pmc_id}}&rettype=xml&retmode=xml"
PMC_BASE   = "https://pmc.ncbi.nlm.nih.gov"


def get_pmc_id(pmid):
    """
    Return the PMC ID (as a string, without the "PMC" prefix) for the given
    PMID, or None if not in PMC. Raises RuntimeError on network failure.
    """
    url = IDCONV_URL.format(pmid=pmid)
    try:
        data = json.loads(_urlopen_with_retry(url, 15, "querying PMC idconv").decode())
    except json.JSONDecodeError as exc:
        raise RuntimeError(f"Error querying PMC idconv: {exc}") from exc

    records = data.get("records", [])
    if not records:
        return None
    pmcid = records[0].get("pmcid")
    if not pmcid:
        return None
    return pmcid[3:] if pmcid.startswith("PMC") else pmcid


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
        # Playwright's default SIGINT/SIGTERM/SIGHUP handling tears down the
        # browser on Ctrl+C — but we deliberately use Ctrl+C in-band (e.g. to
        # abandon a stuck Cloudflare wait) and expect the browser to keep
        # running afterward, so disable it here in favor of our own
        # try/except KeyboardInterrupt handling at each wait point.
        handle_sigint=False,
        handle_sigterm=False,
        handle_sighup=False,
        # Playwright defaults chromium_sandbox to False (adds --no-sandbox),
        # which triggers Chrome's "unsupported command-line flag" warning
        # banner. The real, signed Chrome on macOS supports sandboxing fine.
        chromium_sandbox=True,
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
    Returns False and prints an error if the wait times out or is abandoned
    (Ctrl+C) — e.g. once it's clear the challenge isn't going to pass.
    """
    if "just a moment" not in (page.title() or "").lower():
        return True
    print(
        "    Cloudflare challenge — please click the verification box in the browser.\n"
        "    (Ctrl+C to give up early and move on, instead of waiting out the timeout)",
        flush=True,
    )
    deadline = time.time() + _CF_TIMEOUT
    try:
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
    except KeyboardInterrupt:
        print(f"\r    Abandoned by user.{' ' * 25}", file=sys.stderr, flush=True)
        return False
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
            # is_visible()'s timeout kwarg is a no-op in this Playwright
            # version (deprecated, ignored) — it checks immediately and
            # never actually waits. wait_for is what actually blocks until
            # the fallback page has rendered the button.
            el.wait_for(state="visible", timeout=timeout)
            el.click()
            return True
        except Exception:
            pass
    # Fall back to a plain visible-text match — some fallback pages render
    # the clickable element without proper button/link ARIA semantics (e.g.
    # a styled <div>/<span> with a click handler), which the exact role
    # match above won't find at all.
    try:
        el = page.locator('button:has-text("Open"), a:has-text("Open")').first
        el.wait_for(state="visible", timeout=timeout)
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
                    toggle.wait_for(state="visible", timeout=3_000)
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
    '.tif', '.tiff', '.png', '.jpg', '.jpeg', '.gif',
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
    from urllib.parse import urlsplit, parse_qs

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

        # Require a recognisable downloadable file extension. Usually that's
        # on the URL path, but some download endpoints (e.g. Wiley's
        # action/downloadSupplement?...&file=name.doc) encode the real
        # filename in a query parameter instead — fall back to that.
        parsed = urlsplit(href)
        path_part = parsed.path
        _, ext = posixpath.splitext(path_part)
        filename = posixpath.basename(path_part)

        if ext.lower() not in _SUPP_EXTENSIONS:
            query_filename = None
            if parsed.query:
                qs = parse_qs(parsed.query)
                for key in ('file', 'filename'):
                    if qs.get(key):
                        query_filename = qs[key][0]
                        break
            if not query_filename:
                continue
            _, q_ext = posixpath.splitext(query_filename)
            if q_ext.lower() not in _SUPP_EXTENSIONS:
                continue
            ext = q_ext
            filename = query_filename

        href_lower    = href.lower()
        combined_text = (text + ' ' + title).lower()

        has_supp_url  = any(t in href_lower      for t in _SUPP_URL_TOKENS)
        has_supp_text = any(t in combined_text    for t in _SUPP_TEXT_TOKENS)

        if not (has_supp_url or has_supp_text):
            continue

        filename = filename or f"supplement_{len(found) + 1}{ext.lower()}"
        seen_urls.add(href)
        found.append((filename, href, text or title or filename))

    return found


# ── Staging-dir download watcher ──────────────────────────────────────────────
#
# Some publishers' Cloudflare protection flags the Playwright-controlled
# browser as automated no matter what (even a manual click in that window
# fails), while the same click in the user's ordinary, non-automated browser
# passes every time. Rather than fight that detection, we let the user do the
# challenge + download normally in their own browser (already opened as a
# manual reference — see run_download step 3a) and watch a staging directory
# for the finished file(s), then file them into place automatically.

_STAGING_IGNORE_SUFFIXES = (".crdownload", ".download", ".part", ".tmp")


def _clear_staging_dir(staging_dir):
    """
    Remove all files directly inside staging_dir (not subdirectories) so that
    a stale download from a previous publication — or an unrelated file the
    user's browser happened to save there — can't be mistaken for this
    publication's files. Only ever touches the exact directory the user
    configured as their browser's download location.
    """
    os.makedirs(staging_dir, exist_ok=True)
    removed = 0
    for name in os.listdir(staging_dir):
        path = os.path.join(staging_dir, name)
        if os.path.isfile(path):
            try:
                os.remove(path)
                removed += 1
            except OSError:
                pass
    if removed:
        print(f"  Cleared {removed} pre-existing file(s) from staging dir: {staging_dir}",
              flush=True)


def _list_staging_files(staging_dir):
    """Return full paths of non-hidden, non-partial-download files in staging_dir."""
    out = []
    for name in os.listdir(staging_dir):
        if name.startswith('.') or name.endswith(_STAGING_IGNORE_SUFFIXES):
            continue
        path = os.path.join(staging_dir, name)
        if os.path.isfile(path):
            out.append(path)
    return out


def _wait_for_staging_files(staging_dir, poll_interval=1.0, stable_secs=2.0):
    """
    Let the user download as many files as they want into staging_dir,
    showing a live count of how many are fully written (size unchanged for
    stable_secs, so an in-progress download isn't grabbed mid-write), until
    they press Enter to say they're done. There's no way to reliably guess
    in advance how many files they intend to provide, so this waits for an
    explicit "done" signal rather than trying to count.

    Ctrl+C is treated the same as Enter — both conclude with whatever is
    currently staged (which may be empty) rather than discarding progress
    already made.
    """
    print(f"    Waiting for file(s) to appear in: {staging_dir}", flush=True)
    print("    Download normally in the browser window already open, then "
          "press Enter here when done.", flush=True)
    last_size = {}
    stable_since = {}
    ready = []
    try:
        while True:
            now = time.time()
            seen = set(_list_staging_files(staging_dir))
            ready = []
            for f in seen:
                try:
                    size = os.path.getsize(f)
                except OSError:
                    continue
                if last_size.get(f) == size:
                    stable_since.setdefault(f, now)
                    if now - stable_since[f] >= stable_secs:
                        ready.append(f)
                else:
                    stable_since[f] = now
                last_size[f] = size
            for f in list(last_size):
                if f not in seen:
                    last_size.pop(f, None)
                    stable_since.pop(f, None)
            print(f"\r    {len(ready)} file(s) ready — press Enter when done ",
                  end="", flush=True)
            r, _, _ = select.select([sys.stdin], [], [], poll_interval)
            if r:
                sys.stdin.readline()
                break
    except KeyboardInterrupt:
        pass
    print(flush=True)
    return sorted(ready)


def _sha256(path):
    h = hashlib.sha256()
    with open(path, 'rb') as fh:
        for chunk in iter(lambda: fh.read(1 << 16), b''):
            h.update(chunk)
    return h.hexdigest()


# Filename tokens that suggest a staged file is (or isn't) the main article
# PDF, vs. supplementary material. Used only to order the disambiguation
# prompt so the most likely candidate is listed first — never to
# auto-select without the user's explicit confirmation.
_MAIN_PDF_POSITIVE_TOKENS = ('main', 'manuscript', 'article', 'fulltext', 'full-text', 'full_text')
# Short substrings on purpose: publishers commonly abbreviate these in
# filenames (e.g. AACR/CCR's "<doi>-sup-tab1.pdf", "-sup-fig2.pdf"), so
# matching only the spelled-out forms ("supp", "table", "figure") missed
# them entirely. 'sup' catches supp/supplement/sup-tab/sup-fig; 'tab' and
# 'fig' catch table(s)/figure(s) either spelled out or abbreviated;
# 'append' catches appendix.
_MAIN_PDF_NEGATIVE_TOKENS = (
    'sup', 'append', 'protocol', 'tab', 'fig', 'checklist', 'consort',
    'prisma', 'cover', 'response', 'reviewer', 'disclosure',
)


def _main_pdf_score(path):
    """
    Higher is more likely to be the main article PDF. Returns (keyword_score,
    size) so that when filenames give no keyword signal at all (e.g. a bare
    "2584.pdf"), the larger file — typically the full manuscript vs. a single
    supplementary table/figure — sorts first instead of falling back to
    arbitrary listing order.
    """
    name = os.path.basename(path).lower()
    score = 0
    for tok in _MAIN_PDF_POSITIVE_TOKENS:
        if tok in name:
            score += 2
    for tok in _MAIN_PDF_NEGATIVE_TOKENS:
        if tok in name:
            score -= 1
    try:
        size = os.path.getsize(path)
    except OSError:
        size = 0
    return (score, size)


def _place_staged_files(staged_paths, pdf_dest, need_pdf, supp_dir, expected_supp_names):
    """
    File each path in staged_paths into place:
      1. A staged file whose basename exactly matches one of
         expected_supp_names (supplementary files automation already knew
         about but couldn't download itself) is moved straight to
         <supp_dir>/<that name>.
      2. If need_pdf, the main article PDF is resolved from whatever's left:
         automatically if exactly one file remains, otherwise the user is
         asked which one it is.
      3. Any further leftover file is dropped into supp_dir under its own
         name, as bonus supplementary material automation didn't know about.

    Before any file is placed into supp_dir, its content is hashed and
    compared against files already there — e.g. the same supplementary PDF
    fetched automatically from PMC and again by hand from the publisher,
    under a different filename. An exact content match is discarded rather
    than saved as a duplicate.

    Returns (pdf_saved: bool, supp_saved: list[str]).
    """
    remaining = list(staged_paths)
    supp_saved = []
    os.makedirs(supp_dir, exist_ok=True)

    existing_hashes = {}
    for name in os.listdir(supp_dir):
        path = os.path.join(supp_dir, name)
        if os.path.isfile(path):
            try:
                existing_hashes[_sha256(path)] = path
            except OSError:
                pass

    def _move_into_supp(path, label):
        try:
            digest = _sha256(path)
        except OSError:
            digest = None
        if digest is not None and digest in existing_hashes:
            print(f"    Skipped {os.path.basename(path)} — identical content "
                  f"already saved as {os.path.basename(existing_hashes[digest])}",
                  flush=True)
            os.remove(path)
            return None
        base = os.path.basename(path)
        dest = os.path.join(supp_dir, base)
        if os.path.exists(dest):
            root, ext = os.path.splitext(base)
            n = 2
            while os.path.exists(dest):
                dest = os.path.join(supp_dir, f"{root}_{n}{ext}")
                n += 1
        shutil.move(path, dest)
        size = os.path.getsize(dest)
        print(f"    {label} → {dest}  ({size:,} bytes)", flush=True)
        if digest is not None:
            existing_hashes[digest] = dest
        return dest

    for path in list(remaining):
        base = os.path.basename(path)
        if base in expected_supp_names:
            dest = _move_into_supp(path, f"Matched {base}")
            if dest:
                supp_saved.append(dest)
            remaining.remove(path)

    pdf_saved = False
    if need_pdf and remaining:
        if len(remaining) == 1:
            choice = remaining[0]
        else:
            # List the candidate most likely to be the main article PDF
            # first (e.g. "main"/"manuscript" in the name ranks above
            # "supp"/"appendix"/"protocol"/"table") so it's easy to spot —
            # the user still has to pick a number, nothing is auto-selected.
            remaining.sort(key=_main_pdf_score, reverse=True)
            print("\n    Multiple unmatched files found in staging dir:", flush=True)
            for i, path in enumerate(remaining, 1):
                size = os.path.getsize(path)
                print(f"      [{i}] {os.path.basename(path)}  ({size:,} bytes)", flush=True)
            choice = None
            try:
                sel = input(
                    "    Which number is the main article PDF? (Enter to skip) … "
                ).strip()
                if sel:
                    idx = int(sel) - 1
                    if 0 <= idx < len(remaining):
                        choice = remaining[idx]
            except (KeyboardInterrupt, EOFError, ValueError):
                choice = None
        if choice:
            shutil.move(choice, pdf_dest)
            size = os.path.getsize(pdf_dest)
            print(f"    Saved main PDF → {pdf_dest}  ({size:,} bytes)", flush=True)
            pdf_saved = True
            remaining.remove(choice)

    for path in remaining:
        dest = _move_into_supp(path, "Extra file")
        if dest:
            supp_saved.append(dest)

    return pdf_saved, supp_saved


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

def run_download(pmid, doi, work_dir, staging_dir, headless=False,
                  profile_dir=DEFAULT_PROFILE_DIR):
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

    Anything automation could not save is resolved via staging_dir: the user
    downloads it normally in their own (non-automated) browser — already
    opened as a manual reference — and the script watches staging_dir for the
    finished file(s) and files them into place. staging_dir is cleared at the
    start of each call so a stale download from a previous publication can't
    be mistaken for this one's.

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

    _clear_staging_dir(staging_dir)

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
        # Reuse the blank tab Chrome always opens with instead of leaving it
        # sitting there unused and opening a second tab for real navigation.
        page = context.pages[0] if context.pages else context.new_page()

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
        elif not pmc_id:
            # No DOI and no PMC entry — automation has no path to the PDF at
            # all. Open the PubMed record so the user can hunt down the
            # source manually; this also makes the "no PDF saved" pause below
            # (3f) kick in instead of silently moving on to the next PMID.
            pubmed_url = f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/"
            print(f"\n  ┌─ Manual download reference ────────────────────────────────",
                  flush=True)
            print(f"  │  No DOI and no PMC entry found for this PMID.",
                  flush=True)
            print(f"  │  PubMed URL  : {pubmed_url}", flush=True)
            print(f"  │  Save PDF to : {pdf_dest}", flush=True)
            print(f"  │  Filename    : {pmid}.pdf", flush=True)
            print(f"  └────────────────────────────────────────────────────────────",
                  flush=True)
            try:
                subprocess.run(["open", pubmed_url], check=True)
                manual_browser_opened = True
            except Exception as exc:
                print(f"  (Could not open URL in browser: {exc})",
                      file=sys.stderr, flush=True)

        # 3b. If PMC had no supplementary files, scan the publisher page for
        # them first, on a separate tab. The main-PDF attempt below often
        # navigates the primary tab away from the article landing page (e.g.
        # clicking ascopubs.org's PDF link takes it to /doi/pdf/..., which
        # has no supplementary links at all) — scanning afterward on that
        # same tab would silently find nothing.
        pub_supps = []
        if not supp_downloads and doi:
            print("\n  Scanning publisher page for supplementary files …", flush=True)
            supp_page = context.new_page()
            try:
                supp_page.goto(f"https://doi.org/{doi}",
                                wait_until="domcontentloaded", timeout=60_000)
                try:
                    supp_page.wait_for_load_state("networkidle", timeout=8_000)
                except Exception:
                    pass
                _wait_for_cloudflare_if_present(supp_page)
                pub_supps = _scan_publisher_supplementary(supp_page)
            except Exception as exc:
                print(f"  Could not load publisher page: {exc}",
                      file=sys.stderr, flush=True)
            finally:
                supp_page.close()
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

        # 3c. Main PDF — publisher first
        print(f"\n  Main PDF ({pmid}.pdf):", flush=True)
        pdf_source = None
        if doi:
            pdf_ok = _try_publisher_pdf(page, doi, pdf_dest, PWTimeout)
        else:
            print("    No DOI available — skipping publisher attempt.", flush=True)
            pdf_ok = False
        if pdf_ok:
            pdf_source = "publisher"

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

        # 3f. Resolve anything automation could not save (main PDF and/or
        # supplementary files) via the staging-dir watcher: the user solves
        # any Cloudflare challenge and downloads normally in the browser
        # window already open (3a) — which passes challenges that the
        # automated browser can't, even with a manual click there — and the
        # script picks up the finished file(s) automatically instead of
        # requiring manual copy/rename/placement. Every file _place_staged_
        # files is handed gets moved somewhere (matched supplement, chosen
        # PDF, or bonus supplementary material) — nothing is ever discarded,
        # and the staging dir is only ever swept clean at the *start* of the
        # next publication (see _clear_staging_dir call above), not here.
        missing_supp = [
            (dest, os.path.basename(dest)) for dest, _url in supp_downloads
            if dest not in saved
        ]
        need_pdf    = pdf_dest not in saved
        swap_offer  = pdf_source == "pmc"
        expected_names = {name for _, name in missing_supp}

        if manual_browser_opened and (need_pdf or missing_supp):
            parts = []
            if need_pdf:
                parts.append("the main PDF")
            if missing_supp:
                parts.append(f"{len(missing_supp)} supplementary file(s)")
            print(f"\n  Automation did not save {' and '.join(parts)}.", flush=True)
            print(f"  Download {'them' if len(parts) > 1 else 'it'} normally "
                  f"in the browser window already open.", flush=True)
            staged = _wait_for_staging_files(staging_dir)
            if staged:
                pdf_saved, supp_saved = _place_staged_files(
                    staged, pdf_dest, need_pdf or swap_offer, supp_dir, expected_names,
                )
                if pdf_saved:
                    if pdf_dest not in saved:
                        saved.append(pdf_dest)
                    pdf_source = "manual"
                saved.extend(s for s in supp_saved if s not in saved)
            need_pdf   = pdf_dest not in saved
            swap_offer = pdf_source == "pmc"

        # 3g. The PMC copy is a fallback of last resort — if it's what ended up
        # saved, offer to swap in the publisher's version instead, using the
        # same journal page already open in the browser. Optional, so this
        # only waits for an explicit Enter rather than polling indefinitely.
        if manual_browser_opened and swap_offer:
            print(f"\n  Main PDF came from PubMed Central (publisher download failed or was skipped).",
                  flush=True)
            print(f"  If you'd prefer the publisher's version, download it now in the browser",
                  flush=True)
            print(f"  (into {staging_dir}), or press Enter to keep the PMC copy.", flush=True)
            try:
                input("\n  Press Enter to continue … ")
            except KeyboardInterrupt:
                print("\n  Cancelled — continuing …", flush=True)
            except EOFError:
                print(flush=True)
            staged = _list_staging_files(staging_dir)
            if staged:
                pdf_saved, supp_saved = _place_staged_files(
                    staged, pdf_dest, True, supp_dir, expected_names,
                )
                if pdf_saved:
                    size = os.path.getsize(pdf_dest)
                    print(f"  Replaced with publisher PDF → {pdf_dest}  ({size:,} bytes)",
                          flush=True)
                    pdf_source = "manual"
                saved.extend(s for s in supp_saved if s not in saved)
            else:
                size = os.path.getsize(pdf_dest)
                print(f"  Keeping PMC copy: {size:,} bytes", flush=True)

        try:
            context.close()
        except Exception as exc:
            # The browser may already be gone by this point (crashed, or
            # closed by the user after abandoning a Cloudflare wait or
            # relying entirely on the staging-dir fallback) — we already
            # have whatever we're going to get, so don't let a moot cleanup
            # failure crash the whole batch run.
            print(f"  (Browser context close warning: {exc})",
                  file=sys.stderr, flush=True)

    total = max(1 + len(supp_downloads), len(saved))
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
    else:
        # Even when the main PDF was saved, an empty s/ (no supplementary
        # files found or downloaded) is just clutter — remove it.
        try:
            if os.path.isdir(supp_dir) and not os.listdir(supp_dir):
                os.rmdir(supp_dir)
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
        "--staging-dir",
        metavar="DIR",
        help=(
            "Required with --download. Directory to watch for manually-"
            "downloaded files — set your browser's download location to "
            "this folder. When automation can't save a file itself (e.g. a "
            "publisher's Cloudflare check flags the automated browser even "
            "on a manual click), download it normally in the reference "
            "browser window that's already opened, and the script will pick "
            "the finished file(s) up from here automatically. Cleared at "
            "the start of each publication so stale/unrelated files already "
            "in this folder aren't mistaken for the current one's."
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
    if args.download and not args.staging_dir:
        parser.error("--staging-dir is required when using --download")
    staging_dir = os.path.expanduser(args.staging_dir) if args.staging_dir else None

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

    print(f"Listing existing publications in gs://{bucket}/ …", flush=True)
    existing_pubids = list_bucket_pubids(bucket)
    print(f"  Found {len(existing_pubids)} existing publication(s) in bucket.", flush=True)

    if args.download and not check_browser_dependencies():
        sys.exit(1)

    work_dir    = os.path.expanduser(args.output_dir)
    profile_dir = os.path.expanduser(args.profile_dir)

    n_total   = len(pmids)
    n_skipped = 0
    n_failed  = 0

    for idx, pmid in enumerate(pmids, 1):
        print(_pub_banner(pmid, idx if n_total > 1 else None, n_total), flush=True)

        # ── 2. Check for existing publication directory in bucket ──────────────
        if pmid in existing_pubids:
            print(
                f"WARNING: gs://{bucket}/{pmid}/ already exists. "
                "Skipping to avoid overwriting existing data.",
                file=sys.stderr, flush=True,
            )
            n_skipped += 1
            continue
        print(f"  gs://{bucket}/{pmid}/ not yet present — safe to proceed.", flush=True)

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
            n_saved = run_download(pmid, doi, work_dir, staging_dir,
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
