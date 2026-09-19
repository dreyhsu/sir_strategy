#!/usr/bin/env python3
"""Extract transaction rows for a futures product and contract month."""

from __future__ import annotations

import argparse
import csv
from pathlib import Path


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "txf_tick" / "Daily_2026_08_07.csv"
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
ENGLISH_HEADERS = (
    "trade_date",
    "product_code",
    "contract_month",
    "trade_time",
    "trade_price",
    "trade_quantity_b_s",
)
OUTPUT_COLUMN_COUNT = len(ENGLISH_HEADERS)


def extract_transactions(
    source: Path,
    output: Path,
    product: str,
    contract_month: str,
    source_encoding: str,
    output_encoding: str,
) -> int:
    output.parent.mkdir(parents=True, exist_ok=True)
    rows_written = 0

    with source.open("r", newline="", encoding=source_encoding) as f_in:
        reader = csv.reader(f_in)
        header = next(reader)
        normalized_header = tuple(column.strip() for column in header)
        if normalized_header != EXPECTED_SOURCE_HEADERS:
            raise ValueError(
                "Unexpected source CSV headers. "
                f"Expected {EXPECTED_SOURCE_HEADERS}, got {normalized_header}"
            )

        with output.open("w", newline="", encoding=output_encoding) as f_out:
            writer = csv.writer(f_out)
            writer.writerow(ENGLISH_HEADERS)

            for row in reader:
                cleaned_row = [cell.strip() for cell in row]
                if (
                    len(cleaned_row) >= OUTPUT_COLUMN_COUNT
                    and cleaned_row[1] == product
                    and cleaned_row[2] == contract_month
                ):
                    writer.writerow(cleaned_row[:OUTPUT_COLUMN_COUNT])
                    rows_written += 1

    return rows_written


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extract rows matching a product code and contract month from a TXF tick CSV."
    )
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Input daily tick CSV path.")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT, help="Output CSV path.")
    parser.add_argument("--product", default="TMF", help="Product code to extract.")
    parser.add_argument("--contract-month", default="202608", help="Contract month to extract.")
    parser.add_argument(
        "--source-encoding",
        default="cp950",
        help="Input CSV encoding.",
    )
    parser.add_argument(
        "--output-encoding",
        default="utf-8-sig",
        help="Output CSV encoding.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    count = extract_transactions(
        source=args.source,
        output=args.output,
        product=args.product.strip(),
        contract_month=args.contract_month.strip(),
        source_encoding=args.source_encoding,
        output_encoding=args.output_encoding,
    )
    print(f"Saved {count} rows to {args.output}")


if __name__ == "__main__":
    main()
