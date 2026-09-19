#!/usr/bin/env python3
"""Download and extract Binance BTCUSDT aggTrades for January 2026 to August 2026.

The source is Binance's public USD-M Futures archive. No API key is needed.
The resulting CSVs are intentionally left in Binance's original format:
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
START_MONTH = "2026-01"
END_MONTH = "2026-08"
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


def sha256(path: Path) -> str:
    """Compute SHA-256 hash of file at *path*."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def generate_month_range(start_month: str, end_month: str) -> list[str]:
    """Generate a list of month strings from start_month to end_month inclusive.
    
    Args:
        start_month: Start month in YYYY-MM format (e.g., '2026-01')
        end_month: End month in YYYY-MM format (e.g., '2026-08')
    
    Returns:
        List of month strings in YYYY-MM format
    """
    start_year, start_mon = map(int, start_month.split("-"))
    end_year, end_mon = map(int, end_month.split("-"))
    
    months = []
    year = start_year
    month = start_mon
    
    while year < end_year or (year == end_year and month <= end_mon):
        months.append(f"{year:04d}-{month:02d}")
        month += 1
        if month > 12:
            month = 1
            year += 1
    
    return months


def download_month(
    symbol: str,
    month: str,
    output_dir: Path,
    timeout: float,
    force: bool,
    skip_checksum: bool,
) -> Path:
    """Download and extract aggTrades CSV for a single month.
    
    Returns:
        Path to the extracted CSV file
    """
    archive_name = f"{symbol}-aggTrades-{month}.zip"
    csv_name = f"{symbol}-aggTrades-{month}.csv"
    archive_url = (
        "https://data.binance.vision/data/futures/um/monthly/aggTrades/"
        f"{symbol}/{archive_name}"
    )
    checksum_url = f"{archive_url}.CHECKSUM"
    archive_path = output_dir / archive_name
    csv_path = output_dir / csv_name

    # Download archive if needed
    if archive_path.exists() and not force:
        print(f"  Archive already exists, reusing: {archive_path}")
    else:
        print(f"  Downloading {archive_url}")
        download(archive_url, archive_path, timeout)

    # Verify checksum
    if not skip_checksum:
        request = Request(checksum_url, headers={"User-Agent": USER_AGENT})
        with urlopen(request, timeout=timeout) as response:
            checksum_text = response.read().decode("utf-8")
        match = re.search(r"\b([a-fA-F0-9]{64})\b", checksum_text)
        if not match:
            raise RuntimeError(f"Could not parse SHA-256 checksum from {checksum_url}")
        expected_checksum_value = match.group(1).lower()
        actual_checksum = sha256(archive_path)
        if actual_checksum != expected_checksum_value:
            raise RuntimeError(
                f"SHA-256 mismatch for {archive_path}: "
                f"expected {expected_checksum_value}, got {actual_checksum}"
            )
        print("  SHA-256 checksum verified.")

    # Extract CSV
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
            raise RuntimeError(
                f"Expected one CSV in archive; found {len(csv_members)}"
            )

        member = csv_members[0]
        member_path = PurePosixPath(member.filename)
        if member_path.is_absolute() or ".." in member_path.parts or len(member_path.parts) != 1:
            raise RuntimeError(f"Unsafe CSV path in archive: {member.filename}")
        if member_path.name != csv_name:
            raise RuntimeError(f"Unexpected CSV name in archive: {member_path.name}")
        if csv_path.exists() and not force:
            print(f"  CSV already exists, skipping extraction: {csv_path}")
        else:
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

    return csv_path


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--timeout", type=float, default=60, help="Network timeout in seconds (default: 60).")
    parser.add_argument("--force", action="store_true", help="Re-download and replace existing archives and CSVs.")
    parser.add_argument("--skip-checksum", action="store_true", help="Do not download and verify Binance's SHA-256 checksums.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if args.timeout <= 0:
        raise SystemExit("Error: --timeout must be greater than zero.")

    output_dir = args.output_dir.resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    months = generate_month_range(START_MONTH, END_MONTH)
    print(f"Downloading {SYMBOL} aggTrades for months: {', '.join(months)}")

    try:
        for month in months:
            print(f"\nProcessing {month}:")
            csv_path = download_month(
                SYMBOL,
                month,
                output_dir,
                args.timeout,
                args.force,
                args.skip_checksum,
            )
            print(f"  Ready: {csv_path}")

        print(f"\nAll downloads complete. Files saved in: {output_dir}")
    except (HTTPError, URLError, OSError, RuntimeError, zipfile.BadZipFile) as error:
        raise SystemExit(f"Error: {error}") from error


if __name__ == "__main__":
    main()
