#!/usr/bin/env python
"""Backtest the hourly-resistance / 3-minute UT Bot short strategy on TXF 1-minute bars.

This mirrors ``backtest_tmf_hourly_resistance_utbot_3m_short`` exactly at the
strategy level; only the data layer differs. Instead of reconstructing bars from
raw TAIFEX ticks, it reads a single flat 1-minute OHLCV CSV (Date, Time, Open,
High, Low, Close, Volume) such as ``data/txf_10years/TXF20210101_20231231.csv``
and aggregates it into the hourly and 3-minute bars the strategy expects.
"""

from __future__ import annotations

import argparse
from datetime import date, datetime
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .backtest_tmf_dense_long import add_sessions
    from .backtest_tmf_hourly_resistance_utbot_3m_short import (
        BAR_MINUTES,
        add_hourly_strategy_features,
        add_ut_bot_state,
        attach_hourly_features,
        backtest_strategy,
        performance_summary,
        write_html_report,
        write_markdown_report,
    )
except ImportError:
    from backtest_tmf_dense_long import add_sessions
    from backtest_tmf_hourly_resistance_utbot_3m_short import (
        BAR_MINUTES,
        add_hourly_strategy_features,
        add_ut_bot_state,
        attach_hourly_features,
        backtest_strategy,
        performance_summary,
        write_html_report,
        write_markdown_report,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT = ROOT / "data" / "txf_10years" / "TXF20210101_20231231.csv"
DEFAULT_OUTPUT_DIR = ROOT / "txf_tick"
DEFAULT_DOC_DIR = ROOT / "doc"
DEFAULT_START = date(2021, 1, 1)
DEFAULT_END = date(2023, 12, 31)
DEFAULT_PERIOD = "2021-01-01_to_2023-12-31"
CSV_COLUMNS = ("Date", "Time", "Open", "High", "Low", "Close", "Volume")


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def load_minute_bars(path: Path, start_date: date, end_date: date) -> pd.DataFrame:
    """Load a flat 1-minute OHLCV CSV and return session-tagged minute bars.

    The output columns match a per-minute view of the tick pipeline: ``timestamp``
    (bar close time), ``open/high/low/close`` and ``volume``, plus the day/night
    ``session_id`` fields produced by :func:`add_sessions`.
    """
    frame = pd.read_csv(path)
    header = tuple(frame.columns)
    if header != CSV_COLUMNS:
        raise ValueError(f"Unexpected TXF minute headers in {path}: {header}")
    frame["timestamp"] = pd.to_datetime(
        frame["Date"].astype(str) + " " + frame["Time"].astype(str),
        format="%Y/%m/%d %H:%M:%S",
        errors="coerce",
    )
    frame = frame.rename(
        columns={"Open": "open", "High": "high", "Low": "low", "Close": "close", "Volume": "volume"}
    )
    for column in ("open", "high", "low", "close", "volume"):
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame = frame.dropna(subset=["timestamp", "open", "high", "low", "close", "volume"])
    # A night session opens the previous calendar evening (15:00), so trim by the
    # session date rather than the raw timestamp to keep whole sessions intact.
    tagged = add_sessions(frame)
    session_day = tagged["session_date"].dt.date
    mask = (session_day >= start_date) & (session_day <= end_date)
    tagged = tagged.loc[mask].copy()
    if tagged.empty:
        raise ValueError("No minute bars fall inside the requested date range.")
    columns = ["timestamp", "open", "high", "low", "close", "volume", "session_id", "session_type", "session_date"]
    return tagged[columns].sort_values("timestamp", kind="stable").reset_index(drop=True)


def resample_session_bars(minute_bars: pd.DataFrame, bar_minutes: int) -> pd.DataFrame:
    """Aggregate 1-minute OHLCV bars into ``bar_minutes`` bars anchored per session.

    Buckets anchor to the first minute of each session (day 08:45, night 15:00),
    matching the tick pipeline. Idle slots are dropped rather than forward-filled.
    """
    if bar_minutes < 1:
        raise ValueError("bar_minutes must be positive")
    frame = minute_bars.copy().sort_values("timestamp", kind="stable")
    session_anchor = frame.groupby("session_id", sort=False)["timestamp"].transform("min")
    elapsed_seconds = (frame["timestamp"] - session_anchor).dt.total_seconds()
    bucket_index = (elapsed_seconds // (bar_minutes * 60)).astype("int64")
    frame["bar_start"] = session_anchor + pd.to_timedelta(bucket_index * bar_minutes * 60, unit="s")
    grouped = frame.groupby(["session_id", "bar_start"], sort=True, observed=True)
    result = grouped.agg(
        timestamp=("timestamp", "last"),
        open=("open", "first"),
        high=("high", "max"),
        low=("low", "min"),
        close=("close", "last"),
        volume=("volume", "sum"),
    ).reset_index()
    return result.sort_values("timestamp", kind="stable").reset_index(drop=True)


def build_hourly_bars(minute_bars: pd.DataFrame) -> pd.DataFrame:
    hourly = resample_session_bars(minute_bars, 60)
    return hourly.rename(columns={"bar_start": "hour_start"})


def build_three_minute_bars(minute_bars: pd.DataFrame, bar_minutes: int = BAR_MINUTES) -> pd.DataFrame:
    bars = resample_session_bars(minute_bars, bar_minutes)
    # Downstream strategy code reads the bucket label from ``minute_start``.
    return bars.rename(columns={"bar_start": "minute_start"})


def write_reports(args: argparse.Namespace, minute_count: int, hourly, bar_state, trades, zones, summary) -> None:
    # Reuse the reference report writers; they read ``args`` attributes for labels.
    write_markdown_report(
        args.report_output, args, 1, minute_count, hourly, bar_state, trades, zones, summary
    )
    write_html_report(args.html_output, args, hourly, bar_state, trades, zones, summary)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest the hourly-resistance / 3-minute UT Bot short strategy on TXF 1-minute bars."
    )
    parser.add_argument("--input", type=Path, default=DEFAULT_INPUT)
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START)
    parser.add_argument("--end-date", type=parse_date, default=DEFAULT_END)
    parser.add_argument("--product", default="TXF")
    parser.add_argument("--contract-month", default="TXF2021-2023")
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--box-atr-length", type=int, default=200)
    parser.add_argument("--box-width", type=float, default=1.0)
    parser.add_argument("--risk-atr-length", type=int, default=20)
    parser.add_argument("--adjust-atr-length", type=int, default=10)
    parser.add_argument("--speed-lookback", type=int, default=2)
    parser.add_argument("--speed-smoothing", type=int, default=2)
    parser.add_argument("--base-multiplier", type=float, default=4.5)
    parser.add_argument("--minimum-multiplier", type=float, default=1.5)
    parser.add_argument("--low-speed", type=float, default=0.25)
    parser.add_argument("--high-speed", type=float, default=0.8)
    parser.add_argument("--ut-sensitivity", type=float, default=2.0)
    parser.add_argument("--ut-atr-period", type=int, default=10)
    parser.add_argument("--initial-stop-atr", type=float, default=0.5)
    parser.add_argument("--trailing-atr", type=float, default=3.0)
    parser.add_argument("--top-adjust-ratio", type=float, default=0.5)
    parser.add_argument("--reentry-timeout-minutes", type=int, default=15)
    parser.add_argument("--breakout-invalidate-atr", type=float, default=1.5)
    parser.add_argument("--trend-sma-length", type=int, default=100)
    parser.add_argument("--trend-slope-hours", type=int, default=24)
    parser.add_argument("--max-uptrend-slope", type=float, default=0.5)
    parser.add_argument("--approach-atr", type=float, default=0.25)
    parser.add_argument("--max-entry-below-atr", type=float, default=1.5)
    parser.add_argument("--stop-swing-lookback", type=int, default=20)
    parser.add_argument("--slippage-per-side", type=float, default=2.0)
    parser.add_argument(
        "--hourly-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TXF_utbot3m_hourly_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--bar-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TXF_utbot3m_bar_state_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--trades-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TXF_utbot3m_trades_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--zones-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TXF_utbot3m_dynamic_zones_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--report-output", type=Path,
        default=DEFAULT_DOC_DIR / f"txf_utbot3m_backtest_{DEFAULT_PERIOD}.md",
    )
    parser.add_argument(
        "--html-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TXF_utbot3m_backtest_{DEFAULT_PERIOD}.html",
    )
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    positive_lengths = (
        args.pivot_lookback, args.volume_filter_length, args.box_atr_length, args.risk_atr_length,
        args.adjust_atr_length, args.speed_lookback, args.speed_smoothing, args.ut_atr_period,
        args.trend_sma_length, args.trend_slope_hours, args.stop_swing_lookback,
    )
    if min(positive_lengths) < 1:
        parser.error("all lengths must be positive")
    if args.ut_sensitivity <= 0:
        parser.error("--ut-sensitivity must be positive")
    if min(args.box_width, args.initial_stop_atr, args.trailing_atr, args.breakout_invalidate_atr, args.approach_atr, args.max_entry_below_atr, args.slippage_per_side) < 0:
        parser.error("width, ATR multipliers, and slippage must be non-negative")
    if not 0 <= args.top_adjust_ratio <= 1:
        parser.error("--top-adjust-ratio must be between 0 and 1")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must exceed --low-speed")
    if args.reentry_timeout_minutes < 1:
        parser.error("--reentry-timeout-minutes must be positive")
    return args


def main() -> None:
    args = parse_args()
    minute_bars = load_minute_bars(args.input, args.start_date, args.end_date)
    hourly = add_hourly_strategy_features(
        build_hourly_bars(minute_bars), args.pivot_lookback, args.volume_filter_length, args.box_atr_length,
        args.box_width, args.risk_atr_length, args.adjust_atr_length,
        args.speed_lookback, args.speed_smoothing, args.base_multiplier,
        args.minimum_multiplier, args.low_speed, args.high_speed,
    )
    hourly = hourly.sort_values("timestamp", kind="stable").reset_index(drop=True)
    trend_sma = hourly["close"].rolling(args.trend_sma_length).mean()
    hourly["uptrend_slope"] = (trend_sma / trend_sma.shift(args.trend_slope_hours) - 1.0) * 100.0
    bars = build_three_minute_bars(minute_bars)
    bars = add_ut_bot_state(bars, sensitivity=args.ut_sensitivity, atr_period=args.ut_atr_period)
    bars = attach_hourly_features(bars, hourly)
    bars["uptrend_slope"] = bars["hourly_confirmation_time"].map(
        hourly.set_index("timestamp")["uptrend_slope"]
    )
    trades, bar_state, zone_segments = backtest_strategy(
        bars, args.initial_stop_atr, args.trailing_atr, args.top_adjust_ratio,
        args.reentry_timeout_minutes, args.breakout_invalidate_atr, args.max_uptrend_slope,
        args.approach_atr, args.max_entry_below_atr, args.stop_swing_lookback,
        args.slippage_per_side,
    )
    summary = performance_summary(trades)
    for output in (args.hourly_output, args.bar_output, args.trades_output, args.zones_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(args.hourly_output, index=False, encoding="utf-8-sig")
    bar_state.to_csv(args.bar_output, index=False, encoding="utf-8-sig")
    trades.to_csv(args.trades_output, index=False, encoding="utf-8-sig")
    zone_segments.to_csv(args.zones_output, index=False, encoding="utf-8-sig")
    write_reports(args, len(minute_bars), hourly, bar_state, trades, zone_segments, summary)
    print(
        f"minutes={len(minute_bars)} hourly={len(hourly)} bars={len(bar_state)} "
        f"trades={summary['trades']} net_points={float(summary.get('net_points', 0)):.1f}"
    )
    print(f"report={args.report_output}")
    print(f"html={args.html_output}")


if __name__ == "__main__":
    main()
