#!/usr/bin/env python3
"""
Download tool data files listed in source_tarballs.tsv and upload them to a
GCS bucket, organized by target subdirectory.  Files already present in the
bucket are skipped.

Usage:
    python3 create_tool_data_bucket.py <bucket-name>

Example:
    python3 create_tool_data_bucket.py civic-pubtator-tool-data
"""

import argparse
import csv
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

TARBALLS_TSV = Path(__file__).parent / "source_tarballs.tsv"


def gcs_object_exists(bucket: str, target: str, filename: str) -> bool:
    gcs_path = f"gs://{bucket}/{target}/{filename}"
    result = subprocess.run(
        ["gcloud", "storage", "ls", gcs_path],
        capture_output=True,
    )
    return result.returncode == 0


def upload_to_gcs(local_path: Path, bucket: str, target: str, filename: str) -> None:
    gcs_dest = f"gs://{bucket}/{target}/{filename}"
    subprocess.run(
        ["gcloud", "storage", "cp", str(local_path), gcs_dest],
        check=True,
    )


def download_file(url: str, dest: Path) -> None:
    print(f"  Downloading {url} ...")
    urllib.request.urlretrieve(url, dest)


def read_tarballs(tsv_path: Path) -> list[dict]:
    with tsv_path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        return [row for row in reader if row.get("URL", "").strip()]


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("bucket", help="GCS bucket name (e.g. civic-pubtator-tool-data)")
    args = parser.parse_args()

    bucket = args.bucket
    rows = read_tarballs(TARBALLS_TSV)

    if not rows:
        print("No entries found in TSV — nothing to do.")
        sys.exit(0)

    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)
        for row in rows:
            target = row["Target"].strip()
            url = row["URL"].strip()
            filename = url.split("/")[-1]
            gcs_path = f"gs://{bucket}/{target}/{filename}"

            print(f"\n[{target}] {filename}")

            if gcs_object_exists(bucket, target, filename):
                print(f"  Already in bucket at {gcs_path} — skipping.")
                continue

            local_file = tmp / filename
            try:
                download_file(url, local_file)
            except Exception as exc:
                print(f"  ERROR downloading {url}: {exc}", file=sys.stderr)
                continue

            print(f"  Uploading to {gcs_path} ...")
            try:
                upload_to_gcs(local_file, bucket, target, filename)
                print("  Done.")
            except subprocess.CalledProcessError as exc:
                print(f"  ERROR uploading: {exc}", file=sys.stderr)
            finally:
                local_file.unlink(missing_ok=True)

    print("\nAll entries processed.")


if __name__ == "__main__":
    main()
