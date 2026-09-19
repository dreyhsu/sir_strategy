#!/usr/bin/env python3
"""Download and extract Binance BTCUSDT aggTrades for August 2026.

The source is Binance's public USD-M Futures archive. No API key is needed.
The resulting CSV is intentionally left in Binance's original format:
aggregate tradeId, price, quantity, first tradeId, last tradeId, time,
isBuyerMaker
"""

from __future__ import annotations

import argparse
import hashlib
import os
import re
import shutil
import tempfile
import zipfile
from pathlib import Path, PurePosixPath
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


SYMBOL = "BTCUSDT"
MONTH = "2026-08"
ARCHIVE_NAME = f"{SYMBOL}-aggTrades-{MONTH}.zip"
CSV_NAME = f"{SYMBOL}-aggTrades-{MONTH}.csv"
ARCHIVE_URL = (
    "https://data.binance.vision/data/futures/um/monthly/aggTrades/"
    f"{SYMBOL}/{ARCHIVE_NAME}"
)
CHECKSUM_URL = f"{ARCHIVE_URL}.CHECKSUM"
DEFAULT_OUTPUT_DIR = Path(__file__).resolve().parents[1] / "data" / "btcusdt"
USER_AGENT = "TXF-analysis Binance archive downloader/1.0"


def download(url: str, destination: Path, timeout: float) -> None:
    """Download *url* atomically to *destination*."""
    request = Request(url, headers={"User-Agent": USER_AGENT})
    temp_path: Path | None = None
    try:
        with urlopen(request, timeout=timeout) as response, tempfile.NamedTemporaryFile(
            mode="wb", prefix=f".{destination.name}.", suffix=".part", dir=destination.parent, delete=False
        ) as temporary:
            temp_path = Path(temporary.name)
            shutil.copyfileobj(response, temporary, length=1024 * 1024)
        os.replace(temp_path, destination)
        temp_path = None
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def expected_checksum(timeout: float) -> str:
    request = Request(CHECKSUM_URL, headers={"User-Agent": USER_AGENT})
    with urlopen(request, timeout=timeout) as response:
        text = response.read().decode("utf-8")
    match = re.search(r"\b([a-fA-F0-9]{64})\b", text)
    if not match:
        raise RuntimeError(f"Could not parse SHA-256 checksum from {CHECKSUM_URL}")
    return match.group(1).lower()


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def extract_csv(archive_path: Path, csv_path: Path, force: bool) -> None:
    """Extract the one expected CSV, rejecting unsafe archive member paths."""
    with zipfile.ZipFile(archive_path) as archive:
        bad_member = archive.testzip()
        if bad_member:
            raise RuntimeError(f"Archive is corrupt (first bad member: {bad_member})")

        csv_members = [
            member
            for member in archive.infolist()
            if not member.is_dir() and member.filename.lower().endswith(".csv")
        ]
        if len(csv_members) != 1:
            raise RuntimeError(f"Expected one CSV in archive; found {len(csv_members)}")

        member = csv_members[0]
        member_path = PurePosixPath(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts or len(member_path.parts) != 1:
            raise RuntimeError(f"Unsafe CSV path in archive: {member.filename}")
        if member_path.name != CSV_NAME:
            raise RuntimeError(f"Unexpected CSV name in archive: {member_path.name}")
        if csv_path.exists() and not force:
            print(f"CSV already exists, skipping extraction: {csv_path}")
            return

        temp_path: Path | None = None
        try:
            with archive.open(member) as source, tempfile.NamedTemporaryFile(
                mode="wb", prefix=f".{csv_path.name}.", suffix=".part", dir=csv_path.parent, delete=False
            ) as temporary:
                temp_path = Path(temporary.name)
                shutil.copyfileobj(source, temporary, length=1024 * 1024)
            os.replace(temp_path, csv_path)
            temp_path = None
        finally:
            if temp_path is not None and temp_path.exists():
                temp_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout", type=float, default=60, help="Network timeout in seconds (default: 60).")
    parser.add_argument("--force", action="store_true", help="Re-download and replace existing archive and CSV.")
    parser.add_argument("--skip-checksum", action="store_true", help="Do not download and verify Binance's SHA-256 checksum.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.timeout <= 0:
        raise SystemExit("Error: --timeout must be greater than zero.")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    archive_path = output_dir / ARCHIVE_NAME
    csv_path = output_dir / CSV_NAME

    try:
        if archive_path.exists() and not args.force:
            print(f"Archive already exists, reusing it: {archive_path}")
        else:
            print(f"Downloading {ARCHIVE_URL}")
            download(ARCHIVE_URL, archive_path, args.timeout)

        if not args.skip_checksum:
            expected = expected_checksum(args.timeout)
            actual = sha256(archive_path)
            if actual != expected:
                raise RuntimeError(f"SHA-256 mismatch for {archive_path}: expected {expected}, got {actual}")
            print("SHA-256 checksum verified.")

        extract_csv(archive_path, csv_path, args.force)
        print(f"Ready: {csv_path}")
    except (HTTPError, URLError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise SystemExit(f"Error: {error}") from error


if __name__ == "__main__":
    main()
