"""
monitor_pub_bucket.py — Automated civic-pubtator pipeline monitor for GCS.

Polls a Google Cloud Storage bucket for new publication directories and runs
the civic-pubtator pipeline on any that have not yet been fully processed.

Usage:
    python src/automation/monitor_pub_bucket.py [--bucket BUCKET] [--sleep SECONDS]

Each polling cycle:
  1. Remediates structural issues in the bucket: moves PDFs and s/ directories
     that sit directly under <pubid>/ into the expected <pubid>/01_source/
     wrapper, and deletes any stray .DS_Store files.
  2. For each publication not yet processed (missing any of the five expected
     output files in GCS), localizes the data, runs the pipeline, and uploads
     results back to the bucket.  Publications that fail are recorded in
     DATA_ROOT/.monitor_failures.json and skipped on subsequent cycles.
     Remove a pubid from that file to allow a retry.
  3. Sleeps for --sleep seconds before repeating.

Interrupt with Ctrl-C to stop gracefully.
"""

import argparse
import datetime
import json
import logging
import os
import subprocess
import sys
import time

SCRIPT_DIR    = os.path.dirname(os.path.abspath(__file__))
REPO_DIR      = os.path.dirname(os.path.dirname(SCRIPT_DIR))
DATA_ROOT     = "/data/pub-data"
FAILURES_FILE = os.path.join(DATA_ROOT, ".monitor_failures.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s %(levelname)s %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
log = logging.getLogger(__name__)


# ── Failure registry ──────────────────────────────────────────────────────────

def load_failures():
    """Return the failure registry as {pubid: {timestamp, reason}}, or {} if absent."""
    if not os.path.isfile(FAILURES_FILE):
        return {}
    try:
        with open(FAILURES_FILE) as fh:
            return json.load(fh)
    except (json.JSONDecodeError, OSError) as exc:
        log.warning("Could not read failures file %s: %s", FAILURES_FILE, exc)
        return {}


def record_failure(pubid, reason):
    """
    Add pubid to the failure registry and log prominently.

    The registry lives at DATA_ROOT/.monitor_failures.json.  Remove a pubid
    entry from that file to allow the monitor to retry it.
    """
    failures = load_failures()
    failures[pubid] = {
        "timestamp": datetime.datetime.now().isoformat(timespec="seconds"),
        "reason": reason,
    }
    os.makedirs(DATA_ROOT, exist_ok=True)
    with open(FAILURES_FILE, "w") as fh:
        json.dump(failures, fh, indent=2)
    log.error(
        "FAILURE — %s: %s  (recorded in %s; remove entry to retry)",
        pubid, reason, FAILURES_FILE,
    )


# ── Low-level GCS helpers ─────────────────────────────────────────────────────

def _gcs_ls(path, recursive=False):
    """Return (lines, None) from `gcloud storage ls`, or (None, error_str) on failure."""
    cmd = ["gcloud", "storage", "ls"]
    if recursive:
        cmd.append("--recursive")
    cmd.append(path)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        return None, result.stderr.strip()
    return result.stdout.splitlines(), None


def _gcs_mv(src, dest):
    """Log and execute `gcloud storage mv <src> <dest>`."""
    cmd = ["gcloud", "storage", "mv", src, dest]
    log.info("Remediation: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        log.warning("mv failed (%s → %s): %s", src, dest, result.stderr.strip())


def _gcs_rm(path):
    """Log and execute `gcloud storage rm <path>`."""
    cmd = ["gcloud", "storage", "rm", path]
    log.info("Remediation: %s", " ".join(cmd))
    result = subprocess.run(cmd, check=False, capture_output=True, text=True)
    if result.returncode != 0:
        log.warning("rm failed (%s): %s", path, result.stderr.strip())


# ── Bucket enumeration ────────────────────────────────────────────────────────

def list_pubids(bucket):
    """Return a sorted list of publication IDs (top-level directories) in the bucket."""
    lines, err = _gcs_ls(f"gs://{bucket}/")
    if lines is None:
        log.warning("Failed to list bucket gs://%s/: %s", bucket, err)
        return []
    prefix = f"gs://{bucket}/"
    pubids = []
    for line in lines:
        line = line.strip()
        if line.startswith(prefix) and line.endswith("/"):
            pubid = line[len(prefix):].rstrip("/")
            if pubid:
                pubids.append(pubid)
    return sorted(pubids)


def is_processed(bucket, pubid):
    """Return True only if all five expected pipeline output files exist in the bucket."""
    required = [
        f"gs://{bucket}/{pubid}/MANIFEST.txt",
        f"gs://{bucket}/{pubid}/pipeline_stats.log",
        f"gs://{bucket}/{pubid}/pipeline_stats.tsv",
        f"gs://{bucket}/{pubid}/report_{pubid}.html",
        f"gs://{bucket}/{pubid}/report_{pubid}.tsv",
    ]
    for path in required:
        result = subprocess.run(
            ["gcloud", "storage", "ls", path],
            check=False, capture_output=True, text=True,
        )
        if result.returncode != 0:
            return False
    return True


# ── Bucket remediation ────────────────────────────────────────────────────────

def remediate_bucket(bucket, pubids):
    """Inspect and fix structural issues in the bucket before processing."""
    _fix_missing_01_source(bucket, pubids)
    _remove_ds_store(bucket)


def _fix_missing_01_source(bucket, pubids):
    """
    For any pubid that lacks an 01_source/ subdirectory, move any top-level PDF
    and/or s/ directory into <pubid>/01_source/.
    """
    for pubid in pubids:
        lines, err = _gcs_ls(f"gs://{bucket}/{pubid}/")
        if lines is None:
            log.warning("Could not list gs://%s/%s/: %s", bucket, pubid, err)
            continue

        prefix = f"gs://{bucket}/{pubid}/"
        names = set()
        for line in lines:
            line = line.strip()
            if line.startswith(prefix):
                name = line[len(prefix):].rstrip("/")
                if name:
                    names.add(name)

        if "01_source" in names:
            continue  # already has the expected structure

        moved_any = False

        pdf_name = f"{pubid}.pdf"
        if pdf_name in names:
            _gcs_mv(f"{prefix}{pdf_name}", f"{prefix}01_source/{pdf_name}")
            moved_any = True

        if "s" in names:
            _gcs_mv(f"{prefix}s/", f"{prefix}01_source/s/")
            moved_any = True

        if moved_any:
            log.info("Remediation: restructured %s into 01_source/", pubid)


def _remove_ds_store(bucket):
    """Delete any .DS_Store files found anywhere in the bucket."""
    lines, err = _gcs_ls(f"gs://{bucket}/", recursive=True)
    if lines is None:
        log.warning("Failed to list bucket recursively for .DS_Store scan: %s", err)
        return

    ds_files = [line.strip() for line in lines if line.strip().endswith(".DS_Store")]
    for path in ds_files:
        _gcs_rm(path)


# ── Publication processing ────────────────────────────────────────────────────

def localize(bucket, pubid):
    """Download publication data from GCS to /data/pub-data/<pubid>/."""
    cmd = [
        os.path.join(REPO_DIR, "src", "cloud", "sync_pub_data.sh"),
        "--bucket", bucket, "down", pubid,
    ]
    log.info("Localizing %s from gs://%s/", pubid, bucket)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=REPO_DIR)
    if result.returncode != 0:
        log.error("sync down failed for %s:\n%s", pubid, result.stderr.strip())
        return False
    return True


def run_pipeline(pubid):
    """
    Run civic-pubtator for the given pubid, capturing all stdout/stderr to
    /data/pub-data/<pubid>/civic_pubtator_run.log.  Returns True if the process
    exited cleanly, False otherwise.
    """
    pub_dir  = os.path.join(DATA_ROOT, pubid)
    run_log  = os.path.join(pub_dir, "civic_pubtator_run.log")
    pipeline = os.path.join(REPO_DIR, "civic_pubtator.py")

    cmd = [
        sys.executable, pipeline,
        "--clean", "--quiet-tf", "--timeout-per-doc", "600",
        pub_dir,
    ]
    log.info("Running pipeline for %s (output → %s)", pubid, run_log)
    os.makedirs(pub_dir, exist_ok=True)

    with open(run_log, "w") as fh:
        result = subprocess.run(
            cmd, check=False, stdout=fh, stderr=subprocess.STDOUT, cwd=REPO_DIR,
        )

    if result.returncode != 0:
        log.error("Pipeline exited %d for %s — see %s", result.returncode, pubid, run_log)
        return False
    return True


def validate_pub_dir(pubid):
    """
    Check the local publication directory structure before running the pipeline.

    Returns a list of error strings describing any problems found.  An empty
    list means the directory looks ready to process.  Add further checks here
    as new edge cases are discovered.
    """
    pub_dir = os.path.join(DATA_ROOT, pubid)
    errors = []

    if not os.path.isdir(pub_dir):
        return [f"{pub_dir} does not exist"]

    if not os.listdir(pub_dir):
        return [f"{pub_dir} is empty"]

    source_dir = os.path.join(pub_dir, "01_source")
    if not os.path.isdir(source_dir):
        errors.append("01_source/ directory is missing")
        return errors  # further checks require 01_source

    pdfs = [f for f in os.listdir(source_dir) if f.lower().endswith(".pdf")]
    if not pdfs:
        errors.append("no PDF found in 01_source/")

    return errors


def check_local_outputs(pubid):
    """Return a list of expected output filenames missing under /data/pub-data/<pubid>/."""
    pub_dir = os.path.join(DATA_ROOT, pubid)
    expected = [
        "MANIFEST.txt",
        "pipeline_stats.log",
        "pipeline_stats.tsv",
        f"report_{pubid}.html",
        f"report_{pubid}.tsv",
    ]
    return [f for f in expected if not os.path.isfile(os.path.join(pub_dir, f))]


def upload(bucket, pubid):
    """Upload processed publication data from /data/pub-data/<pubid>/ to GCS."""
    cmd = [
        os.path.join(REPO_DIR, "src", "cloud", "sync_pub_data.sh"),
        "--bucket", bucket, "up", pubid,
    ]
    log.info("Uploading results for %s to gs://%s/", pubid, bucket)
    result = subprocess.run(cmd, check=False, capture_output=True, text=True, cwd=REPO_DIR)
    if result.returncode != 0:
        log.error("sync up failed for %s:\n%s", pubid, result.stderr.strip())
        return False
    return True


# ── Main polling loop ─────────────────────────────────────────────────────────

def run_cycle(bucket):
    """Run one polling cycle: remediate bucket, then process all pending publications."""
    log.info("=== Cycle start — bucket: gs://%s/ ===", bucket)

    pubids = list_pubids(bucket)
    log.info("Found %d publication(s) in bucket.", len(pubids))

    remediate_bucket(bucket, pubids)

    failures = load_failures()

    pending = []
    for pubid in pubids:
        if pubid in failures:
            log.warning(
                "Skipping %s — previously failed on %s: %s",
                pubid, failures[pubid]["timestamp"], failures[pubid]["reason"],
            )
        elif not is_processed(bucket, pubid):
            pending.append(pubid)

    log.info("%d publication(s) pending processing.", len(pending))

    for pubid in pending:
        log.info("--- Processing %s ---", pubid)

        if not localize(bucket, pubid):
            record_failure(pubid, "localization failed (sync down error)")
            continue

        errors = validate_pub_dir(pubid)
        if errors:
            record_failure(pubid, "invalid input structure — " + "; ".join(errors))
            continue

        run_pipeline(pubid)  # non-fatal; output presence decides whether to upload

        missing = check_local_outputs(pubid)
        if missing:
            record_failure(
                pubid,
                "incomplete pipeline output — missing: " + ", ".join(missing),
            )
            continue

        upload(bucket, pubid)
        log.info("Successfully processed and uploaded %s.", pubid)

    log.info("=== Cycle complete ===")


def main():
    parser = argparse.ArgumentParser(
        description="Monitor a GCS bucket and run civic-pubtator on new publications."
    )
    parser.add_argument(
        "--bucket", default="civic-pubtator-pub-data",
        help="GCS bucket name to monitor (default: civic-pubtator-pub-data)",
    )
    parser.add_argument(
        "--sleep", type=int, default=300,
        help="Seconds to sleep between polling cycles (default: 300)",
    )
    args = parser.parse_args()

    log.info(
        "Starting monitor — bucket: gs://%s/, poll interval: %ds",
        args.bucket, args.sleep,
    )
    try:
        while True:
            run_cycle(args.bucket)
            log.info("Sleeping %ds until next cycle.", args.sleep)
            time.sleep(args.sleep)
    except KeyboardInterrupt:
        log.info("Interrupted by user. Exiting.")


if __name__ == "__main__":
    main()
