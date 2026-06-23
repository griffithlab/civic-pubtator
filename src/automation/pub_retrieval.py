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
                           and supplementary files (PMC)
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
import urllib.request
import urllib.error

_SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
_REPO_DIR   = os.path.dirname(os.path.dirname(_SCRIPT_DIR))


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


def fetch_pubmed_summary(pmid):
    """
    Query NCBI eSummary for the given PMID.

    Returns the parsed JSON result dict for the article, or raises RuntimeError
    on network failure or an unexpected response shape.
    """
    url = ESUMMARY_URL.format(pmid=pmid)
    try:
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error fetching PubMed summary: {exc}") from exc
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
        with urllib.request.urlopen(req, timeout=15) as resp:
            return json.loads(resp.read().decode())
    except urllib.error.HTTPError as exc:
        if exc.code == 404:
            raise RuntimeError(f"DOI {doi!r} not found in Unpaywall database.") from exc
        raise RuntimeError(f"Unpaywall HTTP error {exc.code}: {exc.reason}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error reaching Unpaywall: {exc}") from exc
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
        with urllib.request.urlopen(url, timeout=15) as resp:
            data = json.loads(resp.read().decode())
    except (urllib.error.URLError, json.JSONDecodeError) as exc:
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
    try:
        with urllib.request.urlopen(url, timeout=30) as resp:
            xml = resp.read().decode("utf-8", errors="replace")
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Error fetching PMC XML for PMC{pmc_id}: {exc}") from exc

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
    'a[href*="/pdf/"][href$=".pdf"]',    # Springer, Nature
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
        args=["--disable-blink-features=AutomationControlled"],
        user_agent=(
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
            "AppleWebKit/537.36 (KHTML, like Gecko) "
            "Chrome/124.0.0.0 Safari/537.36"
        ),
    )
    try:
        return pw.chromium.launch_persistent_context(channel="chrome", **kwargs)
    except Exception:
        return pw.chromium.launch_persistent_context(**kwargs)


def _download_direct(page, url, dest, PWTimeout):
    """
    Download a single file from a direct URL using Playwright's download event.
    Returns True if saved successfully, False otherwise.
    """
    try:
        with page.expect_download(timeout=90_000) as dl_info:
            try:
                page.goto(url, wait_until="domcontentloaded", timeout=60_000)
            except Exception as nav_exc:
                if "Download is starting" not in str(nav_exc):
                    raise
        dl = dl_info.value
        dl.save_as(dest)
        size = os.path.getsize(dest)
        print(f"    Saved → {dest}  ({size:,} bytes)", flush=True)
        return True
    except PWTimeout:
        print(
            f"    TIMEOUT: no download started.\n"
            f"    The site may require interactive CAPTCHA resolution.",
            file=sys.stderr, flush=True,
        )
        return False
    except Exception as exc:
        print(f"    ERROR: {exc}", file=sys.stderr, flush=True)
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

    for selector in _PDF_LINK_SELECTORS:
        try:
            el = page.locator(selector).first
            if not el.is_visible(timeout=2_000):
                continue
            print(f"    Found PDF link ({selector})", flush=True)
            with page.expect_download(timeout=60_000) as dl_info:
                try:
                    el.click()
                except Exception as click_exc:
                    if "Download is starting" not in str(click_exc):
                        raise
            dl = dl_info.value
            dl.save_as(dest)
            size = os.path.getsize(dest)
            print(f"    Saved (publisher) → {dest}  ({size:,} bytes)", flush=True)
            return True
        except PWTimeout:
            continue  # selector found but click didn't trigger a download; try next
        except Exception:
            continue

    print("    No PDF download link found on publisher page.", file=sys.stderr, flush=True)
    return False


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
    falling back to PMC if the publisher page yields no downloadable link.
    Supplementary files are always fetched from PMC.

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
    total = 1 + len(supp_downloads)
    print(f"\nStarting {mode} browser — {total} file(s) to download …", flush=True)
    _ensure_pdf_preference(profile_dir)
    print(f"  Using browser profile: {profile_dir}", flush=True)

    saved = []
    with sync_playwright() as pw:
        context = _launch_browser(pw, headless, profile_dir)
        page    = context.new_page()

        # 3a. Main PDF — publisher first, PMC fallback
        os.makedirs(source_dir, exist_ok=True)
        print(f"\n  Main PDF ({pmid}.pdf):", flush=True)
        if doi:
            pdf_ok = _try_publisher_pdf(page, doi, pdf_dest, PWTimeout)
        else:
            print("    No DOI available — skipping publisher attempt.", flush=True)
            pdf_ok = False

        if not pdf_ok:
            if pmc_pdf:
                print(f"    Falling back to PMC: {pmc_pdf}", flush=True)
                pdf_ok = _download_direct(page, pmc_pdf, pdf_dest, PWTimeout)
            else:
                print("    No PMC PDF fallback available.", file=sys.stderr, flush=True)

        if pdf_ok:
            saved.append(pdf_dest)

        # 3b. Supplementary files — PMC
        if supp_downloads:
            print(f"\n  Supplementary files:", flush=True)
            os.makedirs(supp_dir, exist_ok=True)
            for dest, url in supp_downloads:
                print(f"  Downloading {os.path.basename(dest)} …", flush=True)
                if _download_direct(page, url, dest, PWTimeout):
                    saved.append(dest)

        context.close()

    print(f"\nDone — {len(saved)}/{total} file(s) saved.", flush=True)
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
    parser.add_argument("--pmid", required=True, help="PubMed ID of the publication")
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
            "Supplementary files are always fetched from PMC."
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

    pmid   = args.pmid.strip()
    bucket = args.bucket

    # ── 1. Validate the bucket ────────────────────────────────────────────────
    print(f"Checking bucket gs://{bucket}/ …", flush=True)
    ok, err = bucket_exists(bucket)
    if not ok:
        print(f"ERROR: Cannot access bucket gs://{bucket}/: {err}", file=sys.stderr, flush=True)
        sys.exit(1)
    print(f"  Bucket gs://{bucket}/ is accessible.", flush=True)

    # ── 2. Check for an existing publication directory ────────────────────────
    print(f"Checking for existing publication directory gs://{bucket}/{pmid}/ …", flush=True)
    if pubid_in_bucket(bucket, pmid):
        print(
            f"WARNING: gs://{bucket}/{pmid}/ already exists. "
            "Skipping further retrieval to avoid overwriting existing data.",
            file=sys.stderr, flush=True,
        )
        sys.exit(0)
    print("  Not yet present — safe to proceed.", flush=True)

    # ── 3. Fetch PubMed metadata and report the journal URL ───────────────────
    print(f"\nQuerying PubMed for PMID {pmid} …", flush=True)
    try:
        article = fetch_pubmed_summary(pmid)
    except RuntimeError as exc:
        print(f"ERROR: {exc}", file=sys.stderr, flush=True)
        sys.exit(1)

    title   = article.get("title", "(title unavailable)")
    journal = article.get("fulljournalname") or article.get("source", "(journal unavailable)")
    doi     = extract_doi(article)

    print(f"  Title:   {title}")
    print(f"  Journal: {journal}")
    if doi:
        print(f"  DOI:     {doi}")
        print(f"  URL:     {journal_url_from_doi(doi)}")
    else:
        print("  DOI:     (not available in PubMed record)")
        print(f"  URL:     https://pubmed.ncbi.nlm.nih.gov/{pmid}/")

    # ── 4. Unpaywall assessment (optional) ────────────────────────────────────
    if args.check_download:
        if doi:
            report_unpaywall(doi, args.email)
        else:
            print("\nWARNING: --check-download skipped — no DOI available for this record.",
                  file=sys.stderr, flush=True)

    # ── 5. Download files (optional) ─────────────────────────────────────────
    if args.download:
        if not check_browser_dependencies():
            sys.exit(1)
        work_dir    = os.path.expanduser(args.output_dir)
        profile_dir = os.path.expanduser(args.profile_dir)
        n_saved = run_download(pmid, doi, work_dir,
                               headless=args.headless, profile_dir=profile_dir)

        # ── 6. Sync to bucket (optional) ─────────────────────────────────────
        if args.bucket_sync:
            if n_saved:
                sync_to_bucket(bucket, pmid, work_dir)
            else:
                print(
                    "\nWARNING: --bucket-sync skipped — no files were saved.",
                    file=sys.stderr, flush=True,
                )


if __name__ == "__main__":
    main()
