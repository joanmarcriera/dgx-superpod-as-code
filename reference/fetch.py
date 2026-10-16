#!/usr/bin/env python3
"""Re-download the third-party media listed in reference/*/SOURCES.csv.

Usage:  python3 reference/fetch.py [--dry-run]

Vendor photos, PDFs, logos and 3D assets are not committed (see .gitignore): their
provenance is. This script rebuilds reference/<pack>/media/ on a new machine. It skips
files that already exist, refuses HTML error pages (some rows point at a doc page, not a
file — those are reported so they can be fetched by hand), and never overwrites.
Stdlib only, so it runs on Apple's /usr/bin/python3.
"""
from __future__ import annotations

import csv
import sys
import urllib.request
from pathlib import Path

HERE = Path(__file__).resolve().parent
# A full browser UA string: motivaircorp.com (Akamai) answers 403 to a bare "Mozilla/5.0".
UA = {"User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 "
                    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"}


def fetch(url: str, dest: Path) -> str:
    """Download `url` to `dest`; returns "ok", or a reason it was not saved."""
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
            body = r.read()
            ctype = r.headers.get("Content-Type", "")
    except Exception as e:  # network errors are reported, not fatal
        return f"error: {e}"
    wants_html = dest.suffix.lower() in (".html", ".htm")
    if not wants_html and ("text/html" in ctype or body[:15].lower().startswith(b"<!doctype html")):
        return "got an HTML page (row points at a web page; fetch by hand)"
    dest.parent.mkdir(parents=True, exist_ok=True)
    dest.write_bytes(body)
    return "ok"


def main() -> int:
    dry = "--dry-run" in sys.argv
    missing = failed = 0
    for sources in sorted(HERE.glob("*/SOURCES.csv")):
        pack = sources.parent
        for row in csv.DictReader(sources.open(newline="")):
            path, url = (row.get("path") or "").strip(), (row.get("url") or "").strip()
            if not path.startswith("media/") or not url.startswith(("https://", "http://")):
                continue
            dest = (pack / path).resolve()
            if not dest.is_relative_to((pack / "media").resolve()):   # no ../ escapes
                print(f"{pack.name}/{path}: refused (outside {pack.name}/media/)")
                failed += 1
                continue
            if dest.exists():
                continue
            missing += 1
            status = "would fetch" if dry else fetch(url, dest)
            if status not in ("ok", "would fetch"):
                failed += 1
            print(f"{pack.name}/{path}: {status}")
    print(f"{missing} missing, {failed} not fetched")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
