#!/usr/bin/env python
"""Download TAIFEX daily tick files and combine one futures contract into a CSV."""

from __future__ import annotations

import argparse
import csv
import io
import os
import tempfile
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


DEFAULT_URL_TEMPLATE = (
    "https://www.taifex.com.tw/file/taifex/Dailydownload/"
    "DailydownloadCSV/Daily_{date}.csv"
)
DEFAULT_OUTPUT = Path(__file__).resolve().parents[1] / "txf_tick" / "TMF_202608_transactions.csv"
EXPECTED_SOURCE_HEADERS = (
    "成交日期",
    "商品代號",
    "到期月份(週別)",
    "成交時間",
    "成交價格",
    "成交數量(B+S)",
    "近月價格",
    "遠月價格",
    "開盤集合競價",
)
OUTPUT_HEADERS = (
    "trade_date",
    "product_code",
    "contract_month",
    "trade_time",
    "trade_price",
    "trade_quantity_b_s",
)


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError("Use YYYY-MM-DD for dates.") from error


def iter_dates(start_date: date, end_date: date):
    current_date = start_date
    while current_date <= end_date:
        yield current_date
        current_date += timedelta(days=1)


def download_text(url: str, timeout: float, retries: int, retry_delay: float) -> str:
    last_error: Exception | None = None
    request = Request(url, headers={"User-Agent": "TMF tick-data downloader/1.0"})

    for attempt in range(retries):
        try:
            with urlopen(request, timeout=timeout) as response:
                status = response.getcode()
                if status is not None and status != 200:
                    raise RuntimeError(f"HTTP {status}")
                payload = response.read()
            if not payload or payload.lstrip().startswith(b"<"):
                raise RuntimeError("response is empty or HTML, not a CSV")
            return payload.decode("cp950")
        except (HTTPError, URLError, OSError, RuntimeError, UnicodeDecodeError) as error:
            last_error = error
            if attempt + 1 < retries:
                time.sleep(retry_delay * (attempt + 1))

    assert last_error is not None
    raise last_error


def write_matching_rows(
    csv_text: str,
    writer: csv.writer,
    product: str,
    contract_month: str,
) -> int:
    reader = csv.reader(io.StringIO(csv_text))
    try:
        header = next(reader)
    except StopIteration as error:
        raise ValueError("CSV has no header row") from error

    normalized_header = tuple(column.strip() for column in header)
    if normalized_header != EXPECTED_SOURCE_HEADERS:
        raise ValueError(f"unexpected CSV header: {normalized_header}")

    rows_written = 0
    for row in reader:
        cleaned_row = [cell.strip() for cell in row]
        if len(cleaned_row) >= len(OUTPUT_HEADERS) and cleaned_row[1] == product and cleaned_row[2] == contract_month:
            writer.writerow(cleaned_row[: len(OUTPUT_HEADERS)])
            rows_written += 1
    return rows_written


def run(args: argparse.Namespace) -> int:
    if args.start_date > args.end_date:
        raise ValueError("--start-date must be on or before --end-date.")
    if args.timeout <= 0:
        raise ValueError("--timeout must be greater than zero.")
    if args.retries < 1:
        raise ValueError("--retries must be at least one.")
    if args.retry_delay < 0:
        raise ValueError("--retry-delay cannot be negative.")

    args.output.parent.mkdir(parents=True, exist_ok=True)
    temp_path: Path | None = None
    valid_files = 0
    total_rows = 0

    try:
        with tempfile.NamedTemporaryFile(
            mode="w",
            encoding=args.output_encoding,
            newline="",
            prefix=f".{args.output.stem}.",
            suffix=".tmp",
            dir=args.output.parent,
            delete=False,
        ) as temp_file:
            temp_path = Path(temp_file.name)
            writer = csv.writer(temp_file)
            writer.writerow(OUTPUT_HEADERS)

            for current_date in iter_dates(args.start_date, args.end_date):
                date_key = current_date.strftime("%Y_%m_%d")
                url = args.url_template.format(date=date_key)
                try:
                    csv_text = download_text(url, args.timeout, args.retries, args.retry_delay)
                    rows = write_matching_rows(csv_text, writer, args.product, args.contract_month)
                except (HTTPError, URLError, OSError, RuntimeError, UnicodeDecodeError, ValueError) as error:
                    print(f"{current_date}: skipped ({error})")
                    continue

                valid_files += 1
                total_rows += rows
                print(f"{current_date}: downloaded, {rows} matching rows")

        if valid_files == 0:
            raise RuntimeError("No valid TAIFEX daily CSV files were downloaded. Output was not replaced.")

        os.replace(temp_path, args.output)
        temp_path = None
        print(f"Saved {total_rows} rows from {valid_files} valid daily file(s) to {args.output}")
        return total_rows
    finally:
        if temp_path is not None and temp_path.exists():
            temp_path.unlink()


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Download TAIFEX daily tick CSVs and combine one futures contract."
    )
    parser.add_argument("--start-date", required=True, type=parse_date, help="First TAIFEX daily-file date, YYYY-MM-DD.")
    parser.add_argument("--end-date", required=True, type=parse_date, help="Last TAIFEX daily-file date, YYYY-MM-DD.")
    parser.add_argument("--product", default="TMF", help="TAIFEX product code.")
    parser.add_argument("--contract-month", default="202608", help="TAIFEX contract month.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Combined CSV path.")
    parser.add_argument("--url-template", default=DEFAULT_URL_TEMPLATE, help="Daily CSV URL template. Use {date} for YYYY_MM_DD.")
    parser.add_argument("--output-encoding", default="utf-8-sig", help="Combined CSV encoding.")
    parser.add_argument("--timeout", type=float, default=30, help="Per-request timeout in seconds.")
    parser.add_argument("--retries", type=int, default=3, help="Download attempts per date.")
    parser.add_argument("--retry-delay", type=float, default=1.0, help="Base retry delay in seconds.")
    return parser.parse_args()


if __name__ == "__main__":
    try:
        run(parse_args())
    except (RuntimeError, ValueError) as error:
        raise SystemExit(f"Error: {error}")
