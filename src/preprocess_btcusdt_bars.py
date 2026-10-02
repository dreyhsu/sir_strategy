#!/usr/bin/env python3
"""Convert raw Binance BTCUSDT aggTrades CSVs into committed 1h, 15m and 3m bar CSVs.

The raw monthly aggTrades files are huge (tens of millions of rows). This script
streams each month once and writes compact 1-hour, 15-minute and 3-minute OHLCV
bars to ``data/btcusdt_bars/`` so they can be committed to git, pulled to another
machine, and used for backtesting and parameter tuning without ever re-touching the
ticks.

Bars are UTC bucket-anchored and the unconfirmed final bucket of each month is
dropped, matching ``build_time_bars`` in the existing BTC backtests. BTCUSDT is a
continuous 24/7 market, so every bar carries ``session_id = "continuous"``.
"""

from __future__ import annotations

import argparse
import csv
from pathlib import Path
from typing import Iterator, Sequence

import pandas as pd


# Self-contained (pandas-only) so preprocessing runs without plotly on any machine.
REQUIRED_COLUMNS = {
    "agg_trade_id", "price", "quantity", "first_trade_id",
    "last_trade_id", "transact_time", "is_buyer_maker",
}


def as_timestamp(timestamp_ms: int) -> pd.Timestamp:
    return pd.Timestamp(timestamp_ms, unit="ms", tz="UTC")


def iter_agg_trades(paths: Sequence[Path]) -> Iterator[tuple[float, float, int]]:
    """Yield (price, quantity, transact_time_ms) from Binance monthly aggTrades CSVs."""
    for path in paths:
        with path.open("r", encoding="utf-8", newline="") as file:
            reader = csv.DictReader(file)
            if reader.fieldnames is None:
                raise ValueError(f"Input CSV has no header row: {path}")
            missing = REQUIRED_COLUMNS.difference(reader.fieldnames)
            if missing:
                raise ValueError(f"Input CSV is missing columns in {path}: {sorted(missing)}")
            for csv_row, row in enumerate(reader, start=2):
                try:
                    yield (float(row["price"]), float(row["quantity"]), int(row["transact_time"]))
                except (TypeError, ValueError) as error:
                    raise ValueError(f"Invalid data in {path} at CSV row {csv_row}: {error}") from error


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "btcusdt"
DEFAULT_OUTPUT_DIR = ROOT / "data" / "btcusdt_bars"
HOURLY_MINUTES = 60
FIFTEEN_MINUTES = 15
THREE_MINUTES = 3


def parse_month(text: str) -> str:
    """Validate a YYYY-MM month string and return it normalised."""
    try:
        parsed = pd.Period(text, freq="M")
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(f"invalid month {text!r}; expected YYYY-MM") from error
    return f"{parsed.year:04d}-{parsed.month:02d}"


def month_range(start_month: str, end_month: str) -> list[str]:
    start = pd.Period(start_month, freq="M")
    end = pd.Period(end_month, freq="M")
    if end < start:
        raise ValueError("--end-month must be on or after --start-month")
    return [f"{period.year:04d}-{period.month:02d}" for period in pd.period_range(start, end, freq="M")]


def resolve_month_input(input_dir: Path, month: str) -> Path | None:
    """Return the aggTrades CSV for *month*, or None when it is not on disk."""
    candidate = input_dir / f"BTCUSDT-aggTrades-{month}.csv"
    return candidate if candidate.is_file() else None


class _BarAccumulator:
    """Single-timeframe UTC bucket accumulator that drops the last open bucket."""

    def __init__(self, minutes: int) -> None:
        self.bucket_ms = minutes * 60_000
        self.records: list[dict[str, object]] = []
        self.bucket: int | None = None
        self.open = self.high = self.low = self.close = 0.0
        self.volume = 0.0
        self.last_timestamp_ms = 0

    def _flush(self) -> None:
        assert self.bucket is not None
        self.records.append(
            {
                "bar_start_time": as_timestamp(self.bucket * self.bucket_ms),
                "timestamp": as_timestamp(self.last_timestamp_ms),
                "open": self.open,
                "high": self.high,
                "low": self.low,
                "close": self.close,
                "volume": self.volume,
                "session_id": "continuous",
            }
        )

    def add(self, price: float, quantity: float, timestamp_ms: int) -> None:
        bucket = timestamp_ms // self.bucket_ms
        if self.bucket is None:
            self.bucket = bucket
            self.open = self.high = self.low = self.close = price
            self.volume = 0.0
        elif bucket != self.bucket:
            self._flush()
            self.bucket = bucket
            self.open = self.high = self.low = self.close = price
            self.volume = 0.0
        self.high = max(self.high, price)
        self.low = min(self.low, price)
        self.close = price
        self.volume += price * quantity
        self.last_timestamp_ms = timestamp_ms

    def to_frame(self) -> pd.DataFrame:
        # The final in-progress bucket is intentionally never flushed.
        return pd.DataFrame(self.records)


def build_month_bars(path: Path, progress_rows: int) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Stream one month of aggTrades once and return (hourly, fifteen_minute, three_minute) bars."""
    hourly = _BarAccumulator(HOURLY_MINUTES)
    fifteen_minute = _BarAccumulator(FIFTEEN_MINUTES)
    three_minute = _BarAccumulator(THREE_MINUTES)
    rows = 0
    for price, quantity, timestamp_ms in iter_agg_trades([path]):
        hourly.add(price, quantity, timestamp_ms)
        fifteen_minute.add(price, quantity, timestamp_ms)
        three_minute.add(price, quantity, timestamp_ms)
        rows += 1
        if progress_rows and rows % progress_rows == 0:
            print(f"  {path.name}: streamed {rows:,} aggTrades")
    if rows == 0:
        raise ValueError(f"{path} contained no aggTrades")
    return hourly.to_frame(), fifteen_minute.to_frame(), three_minute.to_frame()


def write_bars(frame: pd.DataFrame, path: Path, minute_column: str) -> None:
    ordered = frame.rename(columns={"bar_start_time": minute_column})[
        ["timestamp", minute_column, "session_id", "open", "high", "low", "close", "volume"]
    ]
    path.parent.mkdir(parents=True, exist_ok=True)
    ordered.to_csv(path, index=False, encoding="utf-8-sig")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start-month", type=parse_month, default="2025-01")
    parser.add_argument("--end-month", type=parse_month, default="2026-08")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--overwrite", action="store_true", help="rebuild months whose CSVs already exist")
    parser.add_argument("--progress-rows", type=int, default=5_000_000)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    months = month_range(args.start_month, args.end_month)
    input_dir = args.input_dir.resolve()
    output_dir = args.output_dir.resolve()
    built = 0
    for month in months:
        hourly_path = output_dir / f"BTCUSDT_{month}_1h.csv"
        fifteen_minute_path = output_dir / f"BTCUSDT_{month}_15m.csv"
        three_minute_path = output_dir / f"BTCUSDT_{month}_3m.csv"
        if (
            hourly_path.is_file()
            and fifteen_minute_path.is_file()
            and three_minute_path.is_file()
            and not args.overwrite
        ):
            print(f"{month}: bars already exist; skipping (use --overwrite to rebuild)")
            continue
        source = resolve_month_input(input_dir, month)
        if source is None:
            print(f"{month}: no BTCUSDT-aggTrades-{month}.csv in {input_dir}; skipping")
            continue
        print(f"{month}: building bars from {source.name}")
        hourly, fifteen_minute, three_minute = build_month_bars(source, args.progress_rows)
        write_bars(hourly, hourly_path, "hour_start")
        write_bars(fifteen_minute, fifteen_minute_path, "minute_start")
        write_bars(three_minute, three_minute_path, "minute_start")
        print(
            f"{month}: wrote {len(hourly):,} hourly, {len(fifteen_minute):,} 15m "
            f"and {len(three_minute):,} 3m bars"
        )
        built += 1
    print(f"done: built {built} month(s)")


if __name__ == "__main__":
    main()
