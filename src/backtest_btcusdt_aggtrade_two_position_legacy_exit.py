#!/usr/bin/env python3
"""Stream BTCUSDT aggTrades files through the two-position legacy short strategy.

The input is the Binance USD-M Futures monthly aggTrades CSV. The initial run
validates it and creates compact hourly and notional-volume bars; later runs
reuse that cache and only stream the files for tick-ordered fills.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import pickle
from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterator, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from .backtest_tmf_tick_two_position_legacy_exit import add_optimized_layer_signals
    from .backtest_tmf_hourly_support_long import pine_style_zones
except ImportError:
    from backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from backtest_tmf_tick_two_position_legacy_exit import add_optimized_layer_signals
    from backtest_tmf_hourly_support_long import pine_style_zones


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "btcusdt"
DEFAULT_OUTPUT_DIR = ROOT / "btcusdt_tick"
UTC = timezone.utc
REQUIRED_COLUMNS = {
    "agg_trade_id",
    "price",
    "quantity",
    "first_trade_id",
    "last_trade_id",
    "transact_time",
    "is_buyer_maker",
}
CACHE_FORMAT_VERSION = 2


@dataclass
class OpenLot:
    group_id: int
    slot: int
    signal_time_ms: int
    entry_time_ms: int
    raw_entry_price: float
    entry_fill_price: float
    entry_fee_usdt: float
    entry_layer: str
    signal_tick_end_id: int
    resistance_id: int
    resistance_bottom: float
    resistance_top: float
    entry_stop_atr: float
    stop_price: float
    lowest_price: float
    highest_price: float


def timestamp_text(timestamp_ms: int) -> str:
    return datetime.fromtimestamp(timestamp_ms / 1000, UTC).isoformat()


def as_timestamp(timestamp_ms: int) -> pd.Timestamp:
    return pd.Timestamp(timestamp_ms, unit="ms", tz="UTC")


def iter_agg_trades(paths: Sequence[Path]) -> Iterator[tuple[int, int, float, float, int]]:
    """Yield a globally indexed, time-ordered stream from monthly aggTrades CSVs."""
    source_index = 0
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
                    yield (
                        source_index,
                        int(row["agg_trade_id"]),
                        float(row["price"]),
                        float(row["quantity"]),
                        int(row["transact_time"]),
                    )
                except (TypeError, ValueError) as error:
                    raise ValueError(f"Invalid data in {path} at CSV row {csv_row}: {error}") from error
                source_index += 1


def first_pass(
    input_paths: Sequence[Path],
    volume_bar_notional: float,
    max_gap_seconds: float,
    progress_rows: int,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Validate the source and build compact hourly and completed volume bars."""
    hourly_records: list[dict[str, object]] = []
    volume_records: list[dict[str, object]] = []
    last_timestamp_ms: int | None = None
    last_agg_id: int | None = None
    previous_price: float | None = None
    previous_direction = 1.0
    hour_bucket: int | None = None
    hour_open = hour_high = hour_low = hour_close = hour_notional = 0.0
    hour_last_timestamp = hour_tick_end_id = 0
    volume_open = volume_high = volume_low = volume_close = 0.0
    volume_notional = volume_signed_notional = 0.0
    volume_start_timestamp: int | None = None
    volume_start_tick_id: int | None = None
    rows = 0
    max_gap_ms = int(max_gap_seconds * 1000)

    for tick_id, agg_id, price, quantity, timestamp_ms in iter_agg_trades(input_paths):
        if not math.isfinite(price) or not math.isfinite(quantity) or price <= 0 or quantity <= 0:
            raise ValueError(f"Invalid non-positive price or quantity at {timestamp_text(timestamp_ms)}")
        if last_agg_id is not None and agg_id <= last_agg_id:
            raise ValueError(f"agg_trade_id is not strictly increasing at {timestamp_text(timestamp_ms)}")
        if last_timestamp_ms is not None:
            if timestamp_ms < last_timestamp_ms:
                raise ValueError(f"Timestamp moves backward at {timestamp_text(timestamp_ms)}")
            gap_ms = timestamp_ms - last_timestamp_ms
            if gap_ms > max_gap_ms:
                raise ValueError(
                    f"Data gap of {gap_ms / 1000:.3f}s from {timestamp_text(last_timestamp_ms)} "
                    f"to {timestamp_text(timestamp_ms)} exceeds --max-gap-seconds={max_gap_seconds:g}."
                )

        current_hour = timestamp_ms // 3_600_000
        notional = price * quantity
        if hour_bucket is None:
            hour_bucket = current_hour
            hour_open = hour_high = hour_low = hour_close = price
        elif current_hour != hour_bucket:
            hourly_records.append(
                {
                    "timestamp": as_timestamp(hour_last_timestamp),
                    "hour_start": as_timestamp(hour_bucket * 3_600_000),
                    "open": hour_open,
                    "high": hour_high,
                    "low": hour_low,
                    "close": hour_close,
                    "volume": hour_notional,
                    "session_id": "continuous",
                    "tick_end_id": hour_tick_end_id,
                }
            )
            hour_bucket = current_hour
            hour_open = hour_high = hour_low = hour_close = price
            hour_notional = 0.0
        hour_high = max(hour_high, price)
        hour_low = min(hour_low, price)
        hour_close = price
        hour_notional += notional
        hour_last_timestamp = timestamp_ms
        hour_tick_end_id = tick_id

        if previous_price is not None:
            price_change = price - previous_price
            if price_change > 0:
                previous_direction = 1.0
            elif price_change < 0:
                previous_direction = -1.0
        if volume_start_tick_id is None:
            volume_start_tick_id = tick_id
            volume_start_timestamp = timestamp_ms
            volume_open = volume_high = volume_low = volume_close = price
        volume_high = max(volume_high, price)
        volume_low = min(volume_low, price)
        volume_close = price
        volume_notional += notional
        volume_signed_notional += notional * previous_direction
        if volume_notional >= volume_bar_notional:
            volume_records.append(
                {
                    "bar_start_time": as_timestamp(volume_start_timestamp),
                    "timestamp": as_timestamp(timestamp_ms),
                    "open": volume_open,
                    "high": volume_high,
                    "low": volume_low,
                    "close": volume_close,
                    "volume": volume_notional,
                    "signed_volume": volume_signed_notional,
                    "tick_count": tick_id - volume_start_tick_id + 1,
                    "tick_start_id": volume_start_tick_id,
                    "tick_end_id": tick_id,
                    "session_id": "continuous",
                    "session_type": "continuous",
                    "session_date": as_timestamp(timestamp_ms).date(),
                }
            )
            volume_start_tick_id = None
            volume_start_timestamp = None
            volume_notional = volume_signed_notional = 0.0

        last_timestamp_ms = timestamp_ms
        last_agg_id = agg_id
        previous_price = price
        rows += 1
        if progress_rows and rows % progress_rows == 0:
            print(f"first pass: validated {rows:,} aggTrades")

    if rows == 0 or hour_bucket is None:
        raise ValueError("Input CSV contains no aggTrades.")
    hourly_records.append(
        {
            "timestamp": as_timestamp(hour_last_timestamp),
            "hour_start": as_timestamp(hour_bucket * 3_600_000),
            "open": hour_open,
            "high": hour_high,
            "low": hour_low,
            "close": hour_close,
            "volume": hour_notional,
            "session_id": "continuous",
            "tick_end_id": hour_tick_end_id,
        }
    )
    hourly = pd.DataFrame(hourly_records)
    volume_bars = pd.DataFrame(volume_records)
    if len(hourly) < 50:
        raise ValueError("Not enough completed hourly bars for the indicator.")
    if volume_bars.empty:
        raise ValueError("No completed notional-volume bars were generated.")
    return hourly, volume_bars, {
        "rows": rows,
        "input_files": [str(path) for path in input_paths],
        "first_timestamp": hourly_records[0]["hour_start"].isoformat(),
        "last_timestamp": as_timestamp(last_timestamp_ms).isoformat(),
        "volume_bars": len(volume_bars),
    }


def preprocessing_cache_metadata(input_paths: Sequence[Path], args: argparse.Namespace) -> dict[str, object]:
    """Return every source property that changes the compact bar cache."""
    return {
        "cache_format_version": CACHE_FORMAT_VERSION,
        "inputs": [
            {"path": str(path), "size_bytes": path.stat().st_size, "modified_ns": path.stat().st_mtime_ns}
            for path in input_paths
        ],
        "volume_bar_notional": args.volume_bar_notional,
        "max_gap_seconds": args.max_gap_seconds,
    }


def cache_paths(cache_dir: Path, metadata: dict[str, object]) -> tuple[Path, Path, Path]:
    fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode("utf-8")).hexdigest()[:16]
    prefix = f"BTCUSDT-aggTrades-{fingerprint}"
    return (
        cache_dir / f"{prefix}.metadata.json",
        cache_dir / f"{prefix}.hourly.pkl",
        cache_dir / f"{prefix}.volume_bars.pkl",
    )


def load_or_build_preprocessing(
    input_paths: Sequence[Path], args: argparse.Namespace
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Reuse validated compact bars when the source file and validation settings match."""
    metadata = preprocessing_cache_metadata(input_paths, args)
    if args.cache_dir is None:
        cache_dir = input_paths[0].parent / ".backtest_cache"
    else:
        cache_dir = args.cache_dir.resolve()
    metadata_path, hourly_path, volume_path = cache_paths(cache_dir, metadata)

    if not args.no_cache and not args.refresh_cache and all(path.is_file() for path in (metadata_path, hourly_path, volume_path)):
        try:
            saved = json.loads(metadata_path.read_text(encoding="utf-8"))
            if saved["source"] == metadata:
                hourly = pd.read_pickle(hourly_path)
                volume_bars = pd.read_pickle(volume_path)
                first_summary = saved["first_summary"]
                print(f"using validated preprocessing cache: {metadata_path}")
                return hourly, volume_bars, first_summary
        except (OSError, ValueError, KeyError, EOFError, pickle.UnpicklingError):
            print("preprocessing cache is unreadable; rebuilding it")

    print("no matching preprocessing cache; validating and building compact bars")
    hourly, volume_bars, first_summary = first_pass(
        input_paths, args.volume_bar_notional, args.max_gap_seconds, args.progress_rows
    )
    first_summary["hourly_bars"] = len(hourly)
    if not args.no_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        hourly.to_pickle(hourly_path)
        volume_bars.to_pickle(volume_path)
        metadata_path.write_text(
            json.dumps({"source": metadata, "first_summary": first_summary}, indent=2, sort_keys=True),
            encoding="utf-8",
        )
        print(f"saved validated preprocessing cache: {metadata_path}")
    return hourly, volume_bars, first_summary


def build_indicators(
    hourly: pd.DataFrame, volume_bars: pd.DataFrame, args: argparse.Namespace
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hourly = hourly.copy()
    previous_close = hourly["close"].shift(1)
    true_range = pd.concat(
        [
            hourly["high"] - hourly["low"],
            (hourly["high"] - previous_close).abs(),
            (hourly["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    hourly["structure_stop_atr"] = true_range.ewm(
        alpha=1 / args.stop_atr_length,
        adjust=False,
        min_periods=args.stop_atr_length,
    ).mean()
    hourly = add_adaptive_supertrend(
        hourly,
        args.atr_length,
        args.base_multiplier,
        args.min_multiplier,
        args.speed_lookback,
        args.low_speed,
        args.high_speed,
        args.smoothing_span,
    )
    zones = pine_style_zones(
        hourly,
        args.pivot_lookback,
        args.volume_filter_length,
        args.zone_atr_length,
        args.zone_box_width,
    )
    if zones.empty:
        signal_bars = volume_bars.copy()
        signal_bars["close_position"] = np.nan
        signal_bars["bearish_rejection"] = False
        signal_bars["resistance_id"] = pd.NA
        signal_bars["resistance_bottom"] = np.nan
        signal_bars["resistance_top"] = np.nan
        signal_bars["entry_layer"] = pd.NA
        signal_bars["resistance_reversal"] = False
        return hourly, signal_bars, zones
    signal_bars = add_optimized_layer_signals(volume_bars, hourly, zones, args.close_position_max)
    return hourly, signal_bars, zones


def close_group(
    positions: list[OpenLot],
    exit_timestamp_ms: int,
    raw_exit_price: float,
    reason: str,
    args: argparse.Namespace,
) -> tuple[list[dict[str, object]], dict[str, object], float]:
    exit_fill = raw_exit_price * (1 + args.slippage_bps / 10_000)
    exit_fee = exit_fill * args.position_btc * args.taker_fee_rate
    group_stop_price = min(lot.stop_price for lot in positions)
    records: list[dict[str, object]] = []
    for lot in positions:
        lot.lowest_price = min(lot.lowest_price, raw_exit_price)
        lot.highest_price = max(lot.highest_price, raw_exit_price)
        gross = (lot.entry_fill_price - exit_fill) * args.position_btc
        net = gross - lot.entry_fee_usdt - exit_fee
        records.append(
            {
                "group_id": lot.group_id,
                "slot": lot.slot,
                "signal_time": as_timestamp(lot.signal_time_ms),
                "entry_time": as_timestamp(lot.entry_time_ms),
                "exit_time": as_timestamp(exit_timestamp_ms),
                "raw_entry_price": lot.raw_entry_price,
                "entry_fill_price": lot.entry_fill_price,
                "raw_exit_price": raw_exit_price,
                "exit_fill_price": exit_fill,
                "quantity_btc": args.position_btc,
                "entry_fee_usdt": lot.entry_fee_usdt,
                "exit_fee_usdt": exit_fee,
                "gross_pnl_usdt": gross,
                "net_pnl_usdt": net,
                "entry_layer": lot.entry_layer,
                "signal_tick_end_id": lot.signal_tick_end_id,
                "resistance_id": lot.resistance_id,
                "resistance_bottom": lot.resistance_bottom,
                "resistance_top": lot.resistance_top,
                "entry_stop_atr": lot.entry_stop_atr,
                "stop_price": lot.stop_price,
                "group_stop_price": group_stop_price,
                "mfe_usdt": (lot.entry_fill_price - lot.lowest_price) * args.position_btc,
                "mae_usdt": (lot.entry_fill_price - lot.highest_price) * args.position_btc,
                "holding_hours": (exit_timestamp_ms - lot.entry_time_ms) / 3_600_000,
                "exit_reason": reason,
            }
        )
    first = positions[0]
    group_net = float(sum(record["net_pnl_usdt"] for record in records))
    group = {
        "group_id": first.group_id,
        "contract_count": len(positions),
        "first_entry_time": min(as_timestamp(lot.entry_time_ms) for lot in positions),
        "last_entry_time": max(as_timestamp(lot.entry_time_ms) for lot in positions),
        "exit_time": as_timestamp(exit_timestamp_ms),
        "average_entry_fill_price": float(np.mean([lot.entry_fill_price for lot in positions])),
        "raw_exit_price": raw_exit_price,
        "exit_fill_price": exit_fill,
        "gross_pnl_usdt": float(sum(record["gross_pnl_usdt"] for record in records)),
        "fees_usdt": float(sum(record["entry_fee_usdt"] + record["exit_fee_usdt"] for record in records)),
        "net_pnl_usdt": group_net,
        "group_stop_price": group_stop_price,
        "holding_hours": (exit_timestamp_ms - first.entry_time_ms) / 3_600_000,
        "exit_reason": reason,
    }
    return records, group, group_net


def second_pass(
    input_paths: Sequence[Path],
    hourly: pd.DataFrame,
    signal_bars: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Replay raw aggTrades with only compact signal/hourly maps in memory."""
    signals = {
        int(row.tick_end_id): row
        for row in signal_bars[signal_bars["resistance_reversal"]].itertuples(index=False)
    }
    hourly_states = [
        (
            int(row.tick_end_id),
            None if pd.isna(row.supertrend_direction) else int(row.supertrend_direction),
            None if pd.isna(row.structure_stop_atr) else float(row.structure_stop_atr),
        )
        for row in hourly.itertuples(index=False)
    ]
    hourly_index = 0
    current_direction: int | None = None
    current_stop_atr: float | None = None
    positions: list[OpenLot] = []
    pending_signal: object | None = None
    group_last_direction: int | None = None
    group_seen_bearish = False
    next_group_id = 0
    realized = 0.0
    peak_equity = args.initial_equity_usdt
    minimum_equity = args.initial_equity_usdt
    max_drawdown = 0.0
    contract_records: list[dict[str, object]] = []
    group_records: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    counters = defaultdict(int)
    last_timestamp_ms: int | None = None
    last_price: float | None = None
    previous_exposure = 0
    exposure_ms = defaultdict(int)
    next_sample_ms: int | None = None

    for tick_id, _agg_id, price, _quantity, timestamp_ms in iter_agg_trades(input_paths):
        if last_timestamp_ms is not None:
            exposure_ms[previous_exposure] += timestamp_ms - last_timestamp_ms
        last_timestamp_ms, last_price = timestamp_ms, price
        bullish_flip = False
        while hourly_index < len(hourly_states) and hourly_states[hourly_index][0] < tick_id:
            new_direction = hourly_states[hourly_index][1]
            new_stop_atr = hourly_states[hourly_index][2]
            hourly_index += 1
            if positions and new_direction is not None:
                if new_direction == -1:
                    group_seen_bearish = True
                if group_seen_bearish and group_last_direction == -1 and new_direction == 1:
                    bullish_flip = True
                group_last_direction = new_direction
            current_direction = new_direction
            current_stop_atr = new_stop_atr

        exited_this_tick = False
        if positions and price >= min(lot.stop_price for lot in positions):
            records, group, group_net = close_group(
                positions, timestamp_ms, price, "resistance_structure_stop", args
            )
            contract_records.extend(records)
            group_records.append(group)
            realized += group_net
            positions = []
            pending_signal = None
            group_last_direction = None
            group_seen_bearish = False
            counters["structure_stop_exits"] += 1
            exited_this_tick = True
        elif positions and bullish_flip:
            records, group, group_net = close_group(
                positions, timestamp_ms, price, "adaptive_hourly_supertrend_bullish_flip", args
            )
            contract_records.extend(records)
            group_records.append(group)
            realized += group_net
            positions = []
            pending_signal = None
            group_last_direction = None
            group_seen_bearish = False
            exited_this_tick = True

        if not exited_this_tick and pending_signal is not None:
            signal = pending_signal
            pending_signal = None
            if current_stop_atr is None:
                counters["canceled_missing_stop_atr"] += 1
            elif len(positions) < args.max_positions:
                if not positions:
                    next_group_id += 1
                    group_last_direction = current_direction
                    group_seen_bearish = current_direction == -1
                entry_fill = price * (1 - args.slippage_bps / 10_000)
                entry_fee = entry_fill * args.position_btc * args.taker_fee_rate
                positions.append(
                    OpenLot(
                        group_id=next_group_id,
                        slot=len(positions) + 1,
                        signal_time_ms=int(signal.timestamp.value // 1_000_000),
                        entry_time_ms=timestamp_ms,
                        raw_entry_price=price,
                        entry_fill_price=entry_fill,
                        entry_fee_usdt=entry_fee,
                        entry_layer=str(signal.entry_layer),
                        signal_tick_end_id=int(signal.tick_end_id),
                        resistance_id=int(signal.resistance_id),
                        resistance_bottom=float(signal.resistance_bottom),
                        resistance_top=float(signal.resistance_top),
                        entry_stop_atr=current_stop_atr,
                        stop_price=float(signal.resistance_top) + args.stop_atr_buffer * current_stop_atr,
                        lowest_price=price,
                        highest_price=price,
                    )
                )
                counters["filled_entries"] += 1
                counters["peak_positions"] = max(counters["peak_positions"], len(positions))

        for lot in positions:
            lot.lowest_price = min(lot.lowest_price, price)
            lot.highest_price = max(lot.highest_price, price)

        completed_signal = signals.get(tick_id)
        if completed_signal is not None:
            counters["signals"] += 1
            if not exited_this_tick and len(positions) >= args.max_positions:
                counters["ignored_at_capacity"] += 1
            elif not exited_this_tick and pending_signal is None:
                pending_signal = completed_signal

        unrealized = sum((lot.entry_fill_price - price) * args.position_btc - lot.entry_fee_usdt for lot in positions)
        equity = args.initial_equity_usdt + realized + unrealized
        peak_equity = max(peak_equity, equity)
        minimum_equity = min(minimum_equity, equity)
        max_drawdown = min(max_drawdown, equity - peak_equity)
        force_sample = exited_this_tick or completed_signal is not None
        if next_sample_ms is None or timestamp_ms >= next_sample_ms or force_sample:
            samples.append(
                {
                    "timestamp": as_timestamp(timestamp_ms),
                    "price": price,
                    "equity_usdt": equity,
                    "realized_usdt": realized,
                    "unrealized_usdt": unrealized,
                    "open_positions": len(positions),
                    "drawdown_usdt": equity - peak_equity,
                }
            )
            next_sample_ms = ((timestamp_ms // args.chart_sample_minutes // 60_000) + 1) * args.chart_sample_minutes * 60_000
        previous_exposure = len(positions)

    if positions and last_timestamp_ms is not None and last_price is not None:
        records, group, group_net = close_group(positions, last_timestamp_ms, last_price, "data_end", args)
        contract_records.extend(records)
        group_records.append(group)
        realized += group_net
        samples.append(
            {
                "timestamp": as_timestamp(last_timestamp_ms),
                "price": last_price,
                "equity_usdt": args.initial_equity_usdt + realized,
                "realized_usdt": realized,
                "unrealized_usdt": 0.0,
                "open_positions": 0,
                "drawdown_usdt": args.initial_equity_usdt + realized - peak_equity,
            }
        )
    contracts = pd.DataFrame(contract_records)
    groups = pd.DataFrame(group_records)
    samples_frame = pd.DataFrame(samples).drop_duplicates(subset=["timestamp"], keep="last")
    if not contracts.empty:
        contracts.insert(0, "trade_number", range(1, len(contracts) + 1))
        contracts["cumulative_net_pnl_usdt"] = contracts["net_pnl_usdt"].cumsum()
    if not groups.empty:
        groups["cumulative_net_pnl_usdt"] = groups["net_pnl_usdt"].cumsum()
    final_equity = args.initial_equity_usdt + realized
    elapsed_ms = sum(exposure_ms.values())
    summary = {
        "signals": counters["signals"],
        "filled_entries": counters["filled_entries"],
        "ignored_at_capacity": counters["ignored_at_capacity"],
        "structure_stop_exits": counters["structure_stop_exits"],
        "canceled_missing_stop_atr": counters["canceled_missing_stop_atr"],
        "contract_trades": len(contracts),
        "groups": len(groups),
        "net_pnl_usdt": realized,
        "final_equity_usdt": final_equity,
        "return_percent": (final_equity / args.initial_equity_usdt - 1) * 100,
        "minimum_equity_usdt": minimum_equity,
        "maximum_drawdown_usdt": -max_drawdown,
        "peak_positions": counters["peak_positions"],
        "exposure_percent": {
            count: duration / elapsed_ms * 100 if elapsed_ms else 0.0 for count, duration in exposure_ms.items()
        },
    }
    return contracts, groups, samples_frame, summary


def write_chart(
    path: Path,
    zones: pd.DataFrame,
    contracts: pd.DataFrame,
    samples: pd.DataFrame,
    initial_equity_usdt: float,
) -> None:
    """Create the same price / position / equity layout as the TMF backtest."""
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.62, 0.16, 0.22],
        subplot_titles=(
            "Sampled BTCUSDT price, resistance zones, and entries",
            "Open BTC positions",
            "Marked-to-market account equity",
        ),
    )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["price"], mode="lines", name="BTCUSDT (sampled)"),
        row=1,
        col=1,
    )
    chart_end = samples["timestamp"].iloc[-1]
    if not zones.empty:
        for zone in zones[zones["zone_type"] == "resistance"].itertuples(index=False):
            end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
            figure.add_shape(
                type="rect",
                x0=zone.created_time,
                x1=end,
                y0=zone.bottom,
                y1=zone.top,
                fillcolor="rgba(211,47,47,0.12)",
                line={"color": "rgba(211,47,47,0.55)", "width": 1},
                row=1,
                col=1,
            )
    if not contracts.empty:
        for _group_id, group_contracts in contracts.groupby("group_id", sort=False):
            ordered = group_contracts.sort_values("entry_time", kind="stable")
            first = ordered.iloc[0]
            segment_start = first["entry_time"]
            segment_stop = float(first["stop_price"])
            if len(ordered) > 1:
                second = ordered.iloc[1]
                figure.add_shape(
                    type="line",
                    x0=segment_start,
                    x1=second["entry_time"],
                    y0=segment_stop,
                    y1=segment_stop,
                    line={"color": "#ef6c00", "width": 1, "dash": "dash"},
                    row=1,
                    col=1,
                )
                segment_start = second["entry_time"]
                segment_stop = min(float(first["stop_price"]), float(second["stop_price"]))
            figure.add_shape(
                type="line",
                x0=segment_start,
                x1=ordered.iloc[-1]["exit_time"],
                y0=segment_stop,
                y1=segment_stop,
                line={"color": "#ef6c00", "width": 1, "dash": "dash"},
                row=1,
                col=1,
            )
        figure.add_trace(
            go.Scatter(
                x=contracts["entry_time"],
                y=contracts["entry_fill_price"],
                mode="markers",
                name="Short entry",
                marker={"symbol": "triangle-down", "size": 12, "color": "#6a1b9a"},
                text=[f"Group {group}, slot {slot}" for group, slot in zip(contracts["group_id"], contracts["slot"])],
            ),
            row=1, col=1,
        )
        exits = contracts.drop_duplicates("group_id", keep="last")
        figure.add_trace(
            go.Scatter(
                x=exits["exit_time"],
                y=exits["exit_fill_price"],
                mode="markers",
                name="Shared exit",
                marker={"symbol": "x", "size": 10, "color": "#00897b"},
                text=exits["exit_reason"],
            ),
            row=1,
            col=1,
        )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["open_positions"], mode="lines", line_shape="hv", name="Open positions"),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["equity_usdt"], mode="lines", name="Account equity"),
        row=3,
        col=1,
    )
    figure.add_hline(y=initial_equity_usdt, line_dash="dot", line_color="gray", row=3, col=1)
    figure.update_layout(title="BTCUSDT aggTrades two-position legacy short backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Positions", dtick=1, row=2, col=1)
    figure.update_yaxes(title_text="USDT", tickformat=",.0f", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def write_report(path: Path, args: argparse.Namespace, first_summary: dict[str, object], summary: dict[str, object]) -> None:
    input_files = "\n".join(f"  - `{input_path}`" for input_path in first_summary["input_files"])
    text = f"""# BTCUSDT aggTrades two-position legacy short backtest

- Inputs:
{input_files}
- Source rows: {first_summary['rows']:,}; completed hourly bars: {first_summary['hourly_bars']:,}; completed notional-volume bars: {first_summary['volume_bars']:,}.
- Period: {first_summary['first_timestamp']} to {first_summary['last_timestamp']}.
- Continuous 24/7 market. Volume bar threshold: US${args.volume_bar_notional:,.0f}; max permitted data gap: {args.max_gap_seconds:g} seconds.
- Initial equity: US${args.initial_equity_usdt:,.2f}; each layer: {args.position_btc:g} BTC; max layers: {args.max_positions}.
- Costs: {args.taker_fee_rate * 10_000:g} bps taker fee per side and {args.slippage_bps:g} bps adverse slippage per side. Funding is excluded.
- Pine resistance boxes use ATR({args.zone_atr_length}); each lot stop is resistance top + {args.stop_atr_buffer:.2f} × completed ATR({args.stop_atr_length}).

| Metric | Value |
| --- | ---: |
| Signals / filled entries | {summary['signals']} / {summary['filled_entries']} |
| Ignored at capacity | {summary['ignored_at_capacity']} |
| Structure-stop exits | {summary['structure_stop_exits']} |
| Entries skipped before stop ATR warms up | {summary['canceled_missing_stop_atr']} |
| Contract trades / groups | {summary['contract_trades']} / {summary['groups']} |
| Net P&L | US${summary['net_pnl_usdt']:,.2f} |
| Final equity | US${summary['final_equity_usdt']:,.2f} |
| Return | {summary['return_percent']:.2f}% |
| Minimum equity | US${summary['minimum_equity_usdt']:,.2f} |
| Maximum drawdown | US${summary['maximum_drawdown_usdt']:,.2f} |
| Peak positions | {summary['peak_positions']} |
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--input",
        type=Path,
        nargs="+",
        metavar="PATH",
        help=(
            "One or more monthly aggTrades CSV files or directories. Directories are expanded "
            "to BTCUSDT-aggTrades-YYYY-MM.csv files. Defaults to every matching CSV in data/btcusdt."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--cache-dir", type=Path, help="Directory for validated compact-bar caches (default: input/.backtest_cache).")
    parser.add_argument("--refresh-cache", action="store_true", help="Revalidate the input and replace its preprocessing cache.")
    parser.add_argument("--no-cache", action="store_true", help="Do not read or write preprocessing cache files.")
    parser.add_argument("--volume-bar-notional", type=float, default=1_000_000)
    parser.add_argument("--max-gap-seconds", type=float, default=60)
    parser.add_argument("--initial-equity-usdt", type=float, default=10_000)
    parser.add_argument("--position-btc", type=float, default=0.01)
    parser.add_argument("--max-positions", type=int, default=2)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-bps", type=float, default=2)
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--zone-atr-length", type=int, default=200)
    parser.add_argument("--zone-box-width", type=float, default=1.0)
    parser.add_argument("--stop-atr-length", type=int, default=20)
    parser.add_argument("--stop-atr-buffer", type=float, default=0.10)
    parser.add_argument("--close-position-max", type=float, default=0.35)
    parser.add_argument("--atr-length", type=int, default=10)
    parser.add_argument("--base-multiplier", type=float, default=3.0)
    parser.add_argument("--min-multiplier", type=float, default=0.8)
    parser.add_argument("--speed-lookback", type=int, default=2)
    parser.add_argument("--low-speed", type=float, default=0.25)
    parser.add_argument("--high-speed", type=float, default=0.8)
    parser.add_argument("--smoothing-span", type=int, default=2)
    parser.add_argument("--chart-sample-minutes", type=int, default=5)
    parser.add_argument("--progress-rows", type=int, default=5_000_000)
    args = parser.parse_args()
    positives = (args.volume_bar_notional, args.max_gap_seconds, args.initial_equity_usdt, args.position_btc, args.max_positions, args.pivot_lookback, args.volume_filter_length, args.zone_atr_length, args.stop_atr_length, args.atr_length, args.speed_lookback, args.smoothing_span, args.chart_sample_minutes)
    if min(positives) <= 0:
        parser.error("bar sizes, gap threshold, capital, position size, and indicator lengths must be positive")
    if not 0 < args.close_position_max <= 1:
        parser.error("--close-position-max must be in (0, 1]")
    if args.taker_fee_rate < 0 or args.slippage_bps < 0 or args.stop_atr_buffer < 0:
        parser.error("fees, slippage, and stop buffer must be non-negative")
    if args.refresh_cache and args.no_cache:
        parser.error("--refresh-cache and --no-cache cannot be used together")
    if not 0 < args.min_multiplier <= args.base_multiplier or args.high_speed <= args.low_speed:
        parser.error("invalid adaptive Supertrend parameters")
    return args


def resolve_input_paths(raw_inputs: Sequence[Path] | None) -> list[Path]:
    """Resolve CSV files and directories into chronological monthly input files."""
    candidates = raw_inputs if raw_inputs is not None else [DEFAULT_INPUT_DIR]
    paths: list[Path] = []
    for candidate in candidates:
        candidate = candidate.resolve()
        if candidate.is_dir():
            paths.extend(sorted(candidate.glob("BTCUSDT-aggTrades-????-??.csv")))
        elif candidate.is_file():
            paths.append(candidate)
        else:
            raise SystemExit(f"Error: input path does not exist: {candidate}")
    paths = sorted(set(paths))
    if not paths:
        raise SystemExit(
            "Error: no BTCUSDT-aggTrades-YYYY-MM.csv files were found. "
            "Pass one or more files with --input."
        )
    return paths


def output_stem(input_paths: Sequence[Path]) -> str:
    """Create a concise, range-specific name for generated backtest artifacts."""
    months = [path.stem.removeprefix("BTCUSDT-aggTrades-") for path in input_paths]
    period = months[0] if len(months) == 1 else f"{months[0]}_to_{months[-1]}"
    return f"BTCUSDT_{period}"


def main() -> None:
    args = parse_args()
    input_paths = resolve_input_paths(args.input)
    args.output_dir = args.output_dir.resolve()
    hourly, volume_bars, first_summary = load_or_build_preprocessing(input_paths, args)
    hourly, signal_bars, zones = build_indicators(hourly, volume_bars, args)
    print(f"first pass complete: hourly_bars={len(hourly):,} volume_bars={len(signal_bars):,}")
    contracts, groups, samples, summary = second_pass(input_paths, hourly, signal_bars, args)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = output_stem(input_paths)
    contracts.to_csv(args.output_dir / f"{stem}_contract_trades.csv", index=False, encoding="utf-8-sig")
    groups.to_csv(args.output_dir / f"{stem}_group_trades.csv", index=False, encoding="utf-8-sig")
    samples.to_csv(args.output_dir / f"{stem}_equity_samples.csv", index=False, encoding="utf-8-sig")
    write_chart(
        args.output_dir / f"{stem}_two_position_legacy_exit.html",
        zones,
        contracts,
        samples,
        args.initial_equity_usdt,
    )
    write_report(ROOT / "doc" / f"{stem.lower()}_two_position_legacy_exit.md", args, first_summary, summary)
    print(f"contracts={summary['contract_trades']} groups={summary['groups']} net_pnl_usdt={summary['net_pnl_usdt']:.2f}")


if __name__ == "__main__":
    main()
