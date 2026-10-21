"""Download the NESO Historic GB Generation Mix CSV and freeze a snapshot.

The full download changes as NESO updates the file, so only rows before
CUTOFF_EXCLUSIVE are kept in the snapshot used by every later step.
Writes data/snapshot.json with the facts that prepare.py checks.

Usage: python -m src.download_data
"""

import csv
import hashlib
import json
import urllib.request
from datetime import datetime, timezone

from src.config import (
    CUTOFF_EXCLUSIVE,
    DATA_RAW,
    RAW_DOWNLOAD,
    RAW_SNAPSHOT,
    SNAPSHOT_JSON,
    SOURCE_URL,
)


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def download(url, dest):
    request = urllib.request.Request(url, headers={"User-Agent": "gb-wind-forecast/1.0"})
    with urllib.request.urlopen(request, timeout=300) as response, open(dest, "wb") as out:
        while True:
            block = response.read(1 << 20)
            if not block:
                break
            out.write(block)


def cut(src, dest, cutoff):
    """Copy the header and every row whose DATETIME is before cutoff."""
    kept = 0
    first = last = None
    with open(src, newline="", encoding="utf-8") as fin, open(
        dest, "w", newline="", encoding="utf-8"
    ) as fout:
        reader = csv.reader(fin)
        writer = csv.writer(fout, lineterminator="\n")
        header = next(reader)
        writer.writerow(header)
        col = header.index("DATETIME")
        for row in reader:
            # ISO 8601 strings of equal length sort chronologically.
            if row[col][:19] < cutoff:
                writer.writerow(row)
                kept += 1
                first = row[col] if first is None else min(first, row[col])
                last = row[col] if last is None else max(last, row[col])
    return header, kept, first, last


def count_rows(path):
    with open(path, newline="", encoding="utf-8") as handle:
        return sum(1 for _ in handle) - 1


def main():
    DATA_RAW.mkdir(parents=True, exist_ok=True)
    downloaded_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    download(SOURCE_URL, RAW_DOWNLOAD)
    header, kept, first, last = cut(RAW_DOWNLOAD, RAW_SNAPSHOT, CUTOFF_EXCLUSIVE)
    facts = {
        "source_url": SOURCE_URL,
        "downloaded_at_utc": downloaded_at,
        "download_file": RAW_DOWNLOAD.name,
        "download_rows": count_rows(RAW_DOWNLOAD),
        "download_sha256": sha256(RAW_DOWNLOAD),
        "snapshot_file": RAW_SNAPSHOT.name,
        "snapshot_cutoff_exclusive": CUTOFF_EXCLUSIVE,
        "snapshot_rows": kept,
        "snapshot_first_datetime": first,
        "snapshot_last_datetime": last,
        "snapshot_sha256": sha256(RAW_SNAPSHOT),
        "columns": header,
    }
    SNAPSHOT_JSON.write_text(json.dumps(facts, indent=2) + "\n", encoding="utf-8", newline="\n")
    for key, value in facts.items():
        if key != "columns":
            print(f"{key}: {value}")


if __name__ == "__main__":
    main()
