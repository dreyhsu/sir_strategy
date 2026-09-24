#!/usr/bin/env python3
"""Backtest 5-minute Pine diamonds with hourly adaptive-Supertrend exits."""

from __future__ import annotations

import argparse
import hashlib
import json
import pickle
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Sequence

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_btcusdt_aggtrade_two_position_legacy_exit import (
        DEFAULT_OUTPUT_DIR,
        as_timestamp,
        iter_agg_trades,
        load_or_build_preprocessing,
        output_stem,
        resolve_input_paths,
    )
    from .backtest_btcusdt_volume_supertrend_short import add_hourly_structure_atr
    from .backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from .backtest_tmf_hourly_diamond_short import add_pine_diamond_signals
    from .backtest_tmf_hourly_support_long import pine_style_zones
except ImportError:
    from backtest_btcusdt_aggtrade_two_position_legacy_exit import (
        DEFAULT_OUTPUT_DIR,
        as_timestamp,
        iter_agg_trades,
        load_or_build_preprocessing,
        output_stem,
        resolve_input_paths,
    )
    from backtest_btcusdt_volume_supertrend_short import add_hourly_structure_atr
    from backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from backtest_tmf_hourly_diamond_short import add_pine_diamond_signals
    from backtest_tmf_hourly_support_long import pine_style_zones


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "doc"
FIVE_MINUTE_CACHE_VERSION = 1


@dataclass
class OpenShort:
    signal_time_ms: int
    signal_tick_end_id: int
    entry_time_ms: int
    entry_tick_id: int
    raw_entry_price: float
    entry_fill_price: float
    entry_fee_usdt: float
    signal_type: str
    structure_type: str
    structure_id: int
    stop_anchor: float
    hourly_stop_atr: float
    stop_price: float
    lowest_price: float
    highest_price: float


def _cross_over(current_a: float, previous_a: float, current_b: float, previous_b: float) -> bool:
    values = (current_a, previous_a, current_b, previous_b)
    return bool(all(pd.notna(value) for value in values) and current_a > current_b and previous_a <= previous_b)


def _cross_under(current_a: float, previous_a: float, current_b: float, previous_b: float) -> bool:
    values = (current_a, previous_a, current_b, previous_b)
    return bool(all(pd.notna(value) for value in values) and current_a < current_b and previous_a >= previous_b)


def build_time_bars(
    ticks: Iterable[tuple[int, int, float, float, int]],
    minutes: int,
) -> pd.DataFrame:
    """Build exchange-anchored UTC bars and discard the unconfirmed final bucket."""
    bucket_ms = minutes * 60_000
    records: list[dict[str, object]] = []
    current_bucket: int | None = None
    bar_open = bar_high = bar_low = bar_close = bar_volume = 0.0
    bar_start_tick_id = bar_end_tick_id = 0
    bar_last_timestamp_ms = 0

    for tick_id, _agg_id, price, quantity, timestamp_ms in ticks:
        bucket = timestamp_ms // bucket_ms
        if current_bucket is None:
            current_bucket = bucket
            bar_open = bar_high = bar_low = bar_close = price
            bar_volume = 0.0
            bar_start_tick_id = tick_id
        elif bucket != current_bucket:
            records.append(
                {
                    "bar_start_time": as_timestamp(current_bucket * bucket_ms),
                    "timestamp": as_timestamp(bar_last_timestamp_ms),
                    "open": bar_open,
                    "high": bar_high,
                    "low": bar_low,
                    "close": bar_close,
                    "volume": bar_volume,
                    "tick_start_id": bar_start_tick_id,
                    "tick_end_id": bar_end_tick_id,
                    "session_id": "continuous",
                }
            )
            current_bucket = bucket
            bar_open = bar_high = bar_low = bar_close = price
            bar_volume = 0.0
            bar_start_tick_id = tick_id
        bar_high = max(bar_high, price)
        bar_low = min(bar_low, price)
        bar_close = price
        bar_volume += price * quantity
        bar_end_tick_id = tick_id
        bar_last_timestamp_ms = timestamp_ms

    return pd.DataFrame(records)


def five_minute_cache_path(
    input_paths: Sequence[Path], cache_dir: Path, confirmation_minutes: int,
    max_gap_seconds: float = 60,
) -> tuple[Path, Path]:
    metadata = {
        "version": FIVE_MINUTE_CACHE_VERSION,
        "confirmation_minutes": confirmation_minutes,
        "max_gap_seconds": max_gap_seconds,
        "inputs": [
            {"path": str(path), "size": path.stat().st_size, "mtime_ns": path.stat().st_mtime_ns}
            for path in input_paths
        ],
    }
    fingerprint = hashlib.sha256(json.dumps(metadata, sort_keys=True).encode()).hexdigest()[:16]
    return (
        cache_dir / f"BTCUSDT-aggTrades-{fingerprint}.{confirmation_minutes}min.pkl",
        cache_dir / f"BTCUSDT-aggTrades-{fingerprint}.{confirmation_minutes}min.json",
    )


def load_or_build_time_bars(
    input_paths: Sequence[Path], args: argparse.Namespace
) -> pd.DataFrame:
    cache_dir = (
        args.cache_dir.resolve() if args.cache_dir is not None else input_paths[0].parent / ".backtest_cache"
    )
    bars_path, metadata_path = five_minute_cache_path(
        input_paths, cache_dir, args.confirmation_minutes, args.max_gap_seconds
    )
    if not args.no_cache and not args.refresh_cache and bars_path.is_file() and metadata_path.is_file():
        try:
            return pd.read_pickle(bars_path)
        except (OSError, EOFError, pickle.UnpicklingError):
            pass
    bars = build_time_bars(iter_agg_trades(input_paths), args.confirmation_minutes)
    if not args.no_cache:
        cache_dir.mkdir(parents=True, exist_ok=True)
        bars.to_pickle(bars_path)
        metadata_path.write_text(
            json.dumps(
                {
                    "confirmation_minutes": args.confirmation_minutes,
                    "rows": len(bars),
                    "inputs": [str(path) for path in input_paths],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return bars


def add_five_minute_diamonds(
    bars: pd.DataFrame,
    hourly_state: pd.DataFrame,
    stop_atr_buffer: float,
) -> pd.DataFrame:
    """Apply the Pine crossing/role logic to 5-minute bars using completed hourly levels."""
    result = bars.copy().sort_values("tick_end_id", kind="stable").reset_index(drop=True)
    for column in (
        "support_top", "support_bottom", "resistance_bottom", "resistance_top",
        "short_stop_anchor", "hourly_stop_atr",
    ):
        result[column] = np.nan
    for column in ("support_id", "resistance_id", "short_structure_id"):
        result[column] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    for column in (
        "breakout_resistance", "resistance_holds", "support_holds", "breakout_support",
        "resistance_as_support_holds", "support_as_resistance_holds", "short_signal",
        "green_exit_signal",
    ):
        result[column] = False
    result["short_signal_type"] = pd.Series([None] * len(result), dtype="object")
    result["short_structure_type"] = pd.Series([None] * len(result), dtype="object")
    result["green_exit_signal_type"] = pd.Series([None] * len(result), dtype="object")

    state_columns = [
        "tick_end_id", "support_id", "support_top", "support_bottom", "resistance_id",
        "resistance_bottom", "resistance_top", "structure_stop_atr",
    ]
    hourly_rows = list(
        hourly_state[state_columns].sort_values("tick_end_id", kind="stable").itertuples(index=False)
    )
    hourly_index = 0
    state: object | None = None
    resistance_is_support: bool | None = None
    support_is_resistance: bool | None = None

    for index, bar in result.iterrows():
        while hourly_index < len(hourly_rows) and int(hourly_rows[hourly_index].tick_end_id) < int(bar["tick_end_id"]):
            state = hourly_rows[hourly_index]
            hourly_index += 1
        if state is None:
            continue
        for column in ("support_top", "support_bottom", "resistance_bottom", "resistance_top"):
            result.at[index, column] = getattr(state, column)
        for column in ("support_id", "resistance_id"):
            value = getattr(state, column)
            if pd.notna(value):
                result.at[index, column] = int(value)
        result.at[index, "hourly_stop_atr"] = state.structure_stop_atr
        if index == 0:
            continue

        current_low = float(result.at[index, "low"])
        previous_low = float(result.at[index - 1, "low"])
        current_high = float(result.at[index, "high"])
        previous_high = float(result.at[index - 1, "high"])
        resistance_top = result.at[index, "resistance_top"]
        resistance_bottom = result.at[index, "resistance_bottom"]
        support_top = result.at[index, "support_top"]
        support_bottom = result.at[index, "support_bottom"]
        breakout_resistance = _cross_over(
            current_low, previous_low, resistance_top, result.at[index - 1, "resistance_top"]
        )
        resistance_holds = _cross_under(
            current_high, previous_high, resistance_bottom, result.at[index - 1, "resistance_bottom"]
        )
        support_holds = _cross_over(
            current_low, previous_low, support_top, result.at[index - 1, "support_top"]
        )
        breakout_support = _cross_under(
            current_high, previous_high, support_bottom, result.at[index - 1, "support_bottom"]
        )
        resistance_as_support = breakout_resistance and resistance_is_support is True
        support_as_resistance = breakout_support and support_is_resistance is True
        result.at[index, "breakout_resistance"] = breakout_resistance
        result.at[index, "resistance_holds"] = resistance_holds
        result.at[index, "support_holds"] = support_holds
        result.at[index, "breakout_support"] = breakout_support
        result.at[index, "resistance_as_support_holds"] = resistance_as_support
        result.at[index, "support_as_resistance_holds"] = support_as_resistance

        red_types: list[str] = []
        anchors: list[tuple[float, str, int]] = []
        if resistance_holds and pd.notna(result.at[index, "resistance_id"]):
            red_types.append("resistance_holds")
            anchors.append((float(resistance_top), "resistance", int(result.at[index, "resistance_id"])))
        if support_as_resistance and pd.notna(result.at[index, "support_id"]):
            red_types.append("support_as_resistance_holds")
            anchors.append((float(support_top), "support_as_resistance", int(result.at[index, "support_id"])))
        if red_types:
            anchor, structure_type, structure_id = max(anchors, key=lambda item: item[0])
            result.at[index, "short_signal"] = True
            result.at[index, "short_signal_type"] = "+".join(red_types)
            result.at[index, "short_stop_anchor"] = anchor
            result.at[index, "short_structure_type"] = structure_type
            result.at[index, "short_structure_id"] = structure_id

        green_types: list[str] = []
        if support_holds:
            green_types.append("support_holds")
        if resistance_as_support:
            green_types.append("resistance_as_support_holds")
        if green_types:
            result.at[index, "green_exit_signal"] = True
            result.at[index, "green_exit_signal_type"] = "+".join(green_types)

        if breakout_resistance:
            resistance_is_support = True
        elif resistance_holds:
            resistance_is_support = False
        if breakout_support:
            support_is_resistance = True
        elif support_holds:
            support_is_resistance = False

    result["stop_price"] = result["short_stop_anchor"] + stop_atr_buffer * result["hourly_stop_atr"]
    return result


def optional_float(value: object) -> float:
    return np.nan if pd.isna(value) else float(value)


def build_indicators(
    hourly_raw: pd.DataFrame,
    five_minute_raw: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build hourly Pine zones/Supertrend and causal 5-minute diamond signals."""
    hourly = add_hourly_structure_atr(hourly_raw, args.stop_atr_length)
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
    # Save the adaptive ATR because the Pine calculation also has a column named ``atr``.
    hourly = hourly.rename(columns={"atr": "supertrend_atr"})
    hourly = add_pine_diamond_signals(
        hourly,
        args.pivot_lookback,
        args.volume_filter_length,
        args.zone_atr_length,
        args.zone_box_width,
    )
    five_minute = add_five_minute_diamonds(five_minute_raw, hourly, args.stop_atr_buffer)
    zones = pine_style_zones(
        hourly_raw,
        args.pivot_lookback,
        args.volume_filter_length,
        args.zone_atr_length,
        args.zone_box_width,
    )
    return hourly, five_minute, zones


def close_short(
    position: OpenShort,
    exit_tick_id: int,
    exit_time_ms: int,
    raw_exit_price: float,
    reason: str,
    quantity_btc: float,
    taker_fee_rate: float,
    slippage_bps: float,
    *,
    exit_signal_time_ms: int | None = None,
    exit_supertrend: float = np.nan,
    exit_direction: float = np.nan,
) -> tuple[dict[str, object], float]:
    exit_fill = raw_exit_price * (1 + slippage_bps / 10_000)
    exit_fee = exit_fill * quantity_btc * taker_fee_rate
    position.lowest_price = min(position.lowest_price, raw_exit_price)
    position.highest_price = max(position.highest_price, raw_exit_price)
    raw_pnl = (position.raw_entry_price - raw_exit_price) * quantity_btc
    gross = (position.entry_fill_price - exit_fill) * quantity_btc
    net = gross - position.entry_fee_usdt - exit_fee
    return {
        "signal_time": as_timestamp(position.signal_time_ms),
        "entry_time": as_timestamp(position.entry_time_ms),
        "exit_signal_time": as_timestamp(exit_signal_time_ms) if exit_signal_time_ms is not None else pd.NaT,
        "exit_time": as_timestamp(exit_time_ms),
        "signal_tick_end_id": position.signal_tick_end_id,
        "entry_tick_id": position.entry_tick_id,
        "exit_tick_id": exit_tick_id,
        "raw_entry_price": position.raw_entry_price,
        "entry_fill_price": position.entry_fill_price,
        "raw_exit_price": raw_exit_price,
        "exit_fill_price": exit_fill,
        "quantity_btc": quantity_btc,
        "entry_fee_usdt": position.entry_fee_usdt,
        "exit_fee_usdt": exit_fee,
        "raw_price_pnl_usdt": raw_pnl,
        "gross_pnl_usdt": gross,
        "slippage_cost_usdt": raw_pnl - gross,
        "net_pnl_usdt": net,
        "mfe_usdt": (position.entry_fill_price - position.lowest_price) * quantity_btc,
        "mae_usdt": (position.entry_fill_price - position.highest_price) * quantity_btc,
        "holding_hours": (exit_time_ms - position.entry_time_ms) / 3_600_000,
        "signal_type": position.signal_type,
        "structure_type": position.structure_type,
        "structure_id": position.structure_id,
        "stop_anchor": position.stop_anchor,
        "hourly_stop_atr": position.hourly_stop_atr,
        "stop_price": position.stop_price,
        "exit_supertrend": exit_supertrend,
        "exit_supertrend_direction": exit_direction,
        "exit_reason": reason,
    }, net


def backtest(
    ticks: Iterable[tuple[int, int, float, float, int]],
    five_minute: pd.DataFrame,
    hourly: pd.DataFrame,
    *,
    initial_equity_usdt: float = 10_000,
    position_btc: float = 0.01,
    taker_fee_rate: float = 0.0005,
    slippage_bps: float = 2,
    chart_sample_minutes: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Replay raw trades. Completed bars are processed only after their last tick."""
    signals = {int(row.tick_end_id): row for row in five_minute.itertuples(index=False)}
    hourly_rows = list(
        hourly[["tick_end_id", "timestamp", "supertrend", "supertrend_direction"]]
        .sort_values("tick_end_id", kind="stable").itertuples(index=False)
    )
    hour_index = 0
    current_direction: int | None = None
    current_supertrend = np.nan
    position: OpenShort | None = None
    pending_entry: object | None = None
    seen_bearish_since_entry = False
    pending_flip_time_ms: int | None = None
    realized = 0.0
    trades_out: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    counters = defaultdict(int)
    exposure_ms = 0
    total_ms = 0
    previous_open = False
    last_time: int | None = None
    last_tick: int | None = None
    last_price: float | None = None
    next_sample: int | None = None
    peak_equity = minimum_equity = initial_equity_usdt
    max_drawdown = 0.0

    for tick_id, _agg_id, price, _quantity, timestamp_ms in ticks:
        if last_time is not None:
            delta = timestamp_ms - last_time
            total_ms += delta
            if previous_open:
                exposure_ms += delta
        last_time, last_tick, last_price = timestamp_ms, tick_id, price
        event = False
        exited = False

        # A state stamped on an hourly bar is known only on a later raw trade.
        while hour_index < len(hourly_rows) and int(hourly_rows[hour_index].tick_end_id) < tick_id:
            hour = hourly_rows[hour_index]
            hour_index += 1
            if pd.isna(hour.supertrend_direction):
                continue
            new_direction = int(hour.supertrend_direction)
            if position is not None:
                if new_direction == -1:
                    seen_bearish_since_entry = True
                if seen_bearish_since_entry and current_direction == -1 and new_direction == 1:
                    pending_flip_time_ms = int(hour.timestamp.value // 1_000_000)
                    counters["bullish_flip_signals"] += 1
            current_direction = new_direction
            current_supertrend = optional_float(hour.supertrend)

        # Raw structure stop has priority over a Supertrend exit on the same tick.
        if position is not None and price >= position.stop_price:
            record, net = close_short(
                position, tick_id, timestamp_ms, price, "structure_stop", position_btc,
                taker_fee_rate, slippage_bps, exit_supertrend=current_supertrend,
                exit_direction=np.nan if current_direction is None else current_direction,
            )
            trades_out.append(record)
            realized += net
            counters["structure_stop_exits"] += 1
            position = None
            pending_flip_time_ms = None
            exited = event = True
        elif position is not None and pending_flip_time_ms is not None:
            record, net = close_short(
                position, tick_id, timestamp_ms, price, "adaptive_hourly_supertrend_bullish_flip",
                position_btc, taker_fee_rate, slippage_bps,
                exit_signal_time_ms=pending_flip_time_ms,
                exit_supertrend=current_supertrend,
                exit_direction=np.nan if current_direction is None else current_direction,
            )
            trades_out.append(record)
            realized += net
            counters["bullish_flip_exits"] += 1
            position = None
            pending_flip_time_ms = None
            exited = event = True

        if not exited and pending_entry is not None and position is None:
            signal = pending_entry
            pending_entry = None
            if pd.isna(signal.stop_price):
                counters["skipped_missing_stop_atr"] += 1
            else:
                entry_fill = price * (1 - slippage_bps / 10_000)
                entry_fee = entry_fill * position_btc * taker_fee_rate
                position = OpenShort(
                    int(signal.timestamp.value // 1_000_000), int(signal.tick_end_id), timestamp_ms,
                    tick_id, price, entry_fill, entry_fee, str(signal.short_signal_type),
                    str(signal.short_structure_type), int(signal.short_structure_id),
                    float(signal.short_stop_anchor), float(signal.hourly_stop_atr),
                    float(signal.stop_price), price, price,
                )
                seen_bearish_since_entry = current_direction == -1
                counters["filled_entries"] += 1
                event = True

        if position is not None:
            position.lowest_price = min(position.lowest_price, price)
            position.highest_price = max(position.highest_price, price)

        completed = signals.get(tick_id)
        signal_event = False
        if completed is not None:
            for key in (
                "resistance_holds", "support_as_resistance_holds", "support_holds",
                "resistance_as_support_holds",
            ):
                if bool(getattr(completed, key)):
                    counters[key] += 1
            if bool(completed.short_signal):
                counters["red_signals"] += 1
                signal_event = True
                if not exited and position is None and pending_entry is None:
                    pending_entry = completed
                else:
                    counters["ignored_while_occupied"] += 1
            if bool(completed.green_exit_signal):
                counters["green_signals"] += 1
                signal_event = True

        unrealized = 0.0
        if position is not None:
            unrealized = (position.entry_fill_price - price) * position_btc - position.entry_fee_usdt
        equity = initial_equity_usdt + realized + unrealized
        peak_equity = max(peak_equity, equity)
        minimum_equity = min(minimum_equity, equity)
        drawdown = equity - peak_equity
        max_drawdown = min(max_drawdown, drawdown)
        if next_sample is None or timestamp_ms >= next_sample or event or signal_event:
            samples.append({
                "timestamp": as_timestamp(timestamp_ms), "price": price, "equity_usdt": equity,
                "realized_usdt": realized, "unrealized_usdt": unrealized,
                "open_positions": int(position is not None), "drawdown_usdt": drawdown,
            })
            next_sample = (timestamp_ms // (chart_sample_minutes * 60_000) + 1) * chart_sample_minutes * 60_000
        previous_open = position is not None

    # A final pending signal has no later trade and is deliberately discarded.
    if position is not None and last_tick is not None and last_time is not None and last_price is not None:
        record, net = close_short(
            position, last_tick, last_time, last_price, "data_end", position_btc,
            taker_fee_rate, slippage_bps, exit_supertrend=current_supertrend,
            exit_direction=np.nan if current_direction is None else current_direction,
        )
        trades_out.append(record)
        realized += net
        counters["data_end_exits"] += 1
        final_equity = initial_equity_usdt + realized
        samples.append({
            "timestamp": as_timestamp(last_time), "price": last_price, "equity_usdt": final_equity,
            "realized_usdt": realized, "unrealized_usdt": 0.0, "open_positions": 0,
            "drawdown_usdt": final_equity - peak_equity,
        })
        minimum_equity = min(minimum_equity, final_equity)
        max_drawdown = min(max_drawdown, final_equity - peak_equity)

    trades = pd.DataFrame(trades_out)
    if not trades.empty:
        trades.insert(0, "trade_number", range(1, len(trades) + 1))
        trades["cumulative_net_pnl_usdt"] = trades["net_pnl_usdt"].cumsum()
    equity = pd.DataFrame(samples)
    if not equity.empty:
        equity = equity.drop_duplicates(subset=["timestamp"], keep="last")
    wins = trades[trades["net_pnl_usdt"] > 0] if not trades.empty else trades
    losses = trades[trades["net_pnl_usdt"] < 0] if not trades.empty else trades
    gross_profit = float(wins["net_pnl_usdt"].sum()) if not wins.empty else 0.0
    gross_loss = float(losses["net_pnl_usdt"].sum()) if not losses.empty else 0.0
    summary: dict[str, object] = dict(counters)
    summary.update({
        "trades": len(trades), "wins": len(wins), "losses": len(losses),
        "win_rate_percent": len(wins) / len(trades) * 100 if len(trades) else 0.0,
        "profit_factor": gross_profit / abs(gross_loss) if gross_loss < 0 else None,
        "raw_price_pnl_usdt": float(trades["raw_price_pnl_usdt"].sum()) if not trades.empty else 0.0,
        "slippage_cost_usdt": float(trades["slippage_cost_usdt"].sum()) if not trades.empty else 0.0,
        "fees_usdt": float((trades["entry_fee_usdt"] + trades["exit_fee_usdt"]).sum()) if not trades.empty else 0.0,
        "net_pnl_usdt": realized, "final_equity_usdt": initial_equity_usdt + realized,
        "return_percent": realized / initial_equity_usdt * 100,
        "minimum_equity_usdt": minimum_equity, "maximum_drawdown_usdt": -max_drawdown,
        "average_holding_hours": float(trades["holding_hours"].mean()) if not trades.empty else 0.0,
        "exposure_percent": exposure_ms / total_ms * 100 if total_ms else 0.0,
    })
    for key in (
        "resistance_holds", "support_as_resistance_holds", "support_holds",
        "resistance_as_support_holds", "red_signals", "green_signals", "filled_entries",
        "ignored_while_occupied", "skipped_missing_stop_atr", "bullish_flip_signals",
        "bullish_flip_exits", "structure_stop_exits", "data_end_exits",
    ):
        summary.setdefault(key, 0)
    return trades, equity, summary


def compare_confirmation_timing(five_minute: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    """Measure each 5-minute red signal against its containing hourly bar close.

    This is a confirmation-latency comparison, not a claim that the much coarser
    hourly OHLC must also produce the same crossing.
    """
    rows: list[dict[str, object]] = []
    hour_lookup = {
        row.hour_start: row for row in hourly.sort_values("timestamp", kind="stable").itertuples(index=False)
    }
    for signal in five_minute[five_minute["short_signal"]].itertuples(index=False):
        hour_start = signal.bar_start_time.floor("h")
        hour = hour_lookup.get(hour_start)
        if hour is None or hour.timestamp < signal.timestamp:
            continue
        rows.append({
            "five_minute_confirmation_time": signal.timestamp,
            "hourly_bar_confirmation_time": hour.timestamp,
            "lead_minutes": (hour.timestamp - signal.timestamp).total_seconds() / 60,
            "five_minute_signal_type": signal.short_signal_type,
            "structure_id": int(signal.short_structure_id),
            "hourly_bar_also_has_red_diamond": bool(hour.short_signal),
        })
    return pd.DataFrame(rows)


def sample_bars(bars: pd.DataFrame, minutes: int) -> pd.DataFrame:
    if bars.empty or minutes <= 5:
        return bars.copy()
    return (
        bars.sort_values("timestamp", kind="stable").set_index("timestamp")
        .resample(f"{minutes}min").last().dropna(subset=["close"]).reset_index()
    )


def write_chart(
    path: Path,
    zones: pd.DataFrame,
    five_minute: pd.DataFrame,
    hourly: pd.DataFrame,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    initial_equity_usdt: float,
    chart_sample_minutes: int,
) -> None:
    bars = sample_bars(five_minute, chart_sample_minutes)
    figure = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.035,
        row_heights=[0.64, 0.14, 0.22],
        subplot_titles=("5-minute Pine diamonds + hourly zones/Supertrend", "Open position", "Marked-to-market equity"),
    )
    figure.add_trace(go.Scatter(x=bars["timestamp"], y=bars["close"], mode="lines", name="5m close"), row=1, col=1)
    if not hourly.empty:
        figure.add_trace(
            go.Scatter(x=hourly["timestamp"], y=hourly["supertrend"], mode="lines", name="Hourly adaptive Supertrend", line={"color": "#7b1fa2"}),
            row=1, col=1,
        )
    chart_end = bars["timestamp"].iloc[-1] if not bars.empty else pd.Timestamp.now(tz="UTC")
    for zone in zones.itertuples(index=False):
        is_resistance = zone.zone_type == "resistance"
        figure.add_shape(
            type="rect", x0=zone.created_time, x1=zone.broken_time if pd.notna(zone.broken_time) else chart_end,
            y0=zone.bottom, y1=zone.top,
            fillcolor="rgba(211,47,47,0.11)" if is_resistance else "rgba(32,202,38,0.11)",
            line={"color": "rgba(211,47,47,0.55)" if is_resistance else "rgba(32,202,38,0.55)", "width": 1},
            row=1, col=1,
        )
    reds = five_minute[five_minute["short_signal"]]
    greens = five_minute[five_minute["green_exit_signal"]]
    if not reds.empty:
        figure.add_trace(go.Scatter(
            x=reds["timestamp"], y=reds["high"], mode="markers", name="Red diamond (confirmed)",
            text=reds["short_signal_type"], hovertemplate="%{text}<br>%{x}<extra></extra>",
            marker={"symbol": "diamond", "size": 9, "color": "#e53935"}), row=1, col=1)
    if not greens.empty:
        figure.add_trace(go.Scatter(
            x=greens["timestamp"], y=greens["low"], mode="markers", name="Green diamond (confirmed)",
            text=greens["green_exit_signal_type"], hovertemplate="%{text}<br>%{x}<extra></extra>",
            marker={"symbol": "diamond", "size": 9, "color": "#20a526"}), row=1, col=1)
    if not trades.empty:
        figure.add_trace(go.Scatter(
            x=trades["entry_time"], y=trades["entry_fill_price"], mode="markers", name="Short fill",
            marker={"symbol": "triangle-down", "size": 11, "color": "#b71c1c"}), row=1, col=1)
        styles = {
            "structure_stop": ("Structure stop", "#ef6c00"),
            "adaptive_hourly_supertrend_bullish_flip": ("Hourly ST exit", "#00897b"),
            "data_end": ("Data end", "#546e7a"),
        }
        for reason, (label, color) in styles.items():
            exits = trades[trades["exit_reason"] == reason]
            if not exits.empty:
                figure.add_trace(go.Scatter(
                    x=exits["exit_time"], y=exits["exit_fill_price"], mode="markers", name=label,
                    marker={"symbol": "x", "size": 10, "color": color}), row=1, col=1)
        for trade in trades.itertuples(index=False):
            figure.add_shape(type="line", x0=trade.entry_time, x1=trade.exit_time,
                             y0=trade.stop_price, y1=trade.stop_price,
                             line={"color": "#ef6c00", "dash": "dash", "width": 1}, row=1, col=1)
    if not equity.empty:
        figure.add_trace(go.Scatter(x=equity["timestamp"], y=equity["open_positions"], mode="lines", line_shape="hv", name="Open positions"), row=2, col=1)
        figure.add_trace(go.Scatter(x=equity["timestamp"], y=equity["equity_usdt"], mode="lines", name="Equity"), row=3, col=1)
    figure.add_hline(y=initial_equity_usdt, line_dash="dot", line_color="gray", row=3, col=1)
    figure.update_layout(title="BTCUSDT 5m Pine diamond + hourly adaptive Supertrend short backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Position", dtick=1, row=2, col=1)
    figure.update_yaxes(title_text="USDT", tickformat=",.0f", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def format_profit_factor(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def write_report(
    path: Path,
    args: argparse.Namespace,
    source_summary: dict[str, object],
    five_minute: pd.DataFrame,
    hourly: pd.DataFrame,
    zones: pd.DataFrame,
    timing: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    inputs = "\n".join(f"  - `{item}`" for item in source_summary["input_files"])
    supports = int((zones["zone_type"] == "support").sum()) if not zones.empty else 0
    resistances = int((zones["zone_type"] == "resistance").sum()) if not zones.empty else 0
    average_lead = float(timing["lead_minutes"].mean()) if not timing.empty else np.nan
    median_lead = float(timing["lead_minutes"].median()) if not timing.empty else np.nan
    hourly_reds = int(hourly["short_signal"].sum())
    text = f"""# BTCUSDT 5 分鐘 Pine 菱形＋1 小時 Adaptive Supertrend 空單回測

- 輸入：
{inputs}
- 資料範圍：{source_summary['first_timestamp']} 至 {source_summary['last_timestamp']}；raw aggTrades {source_summary['rows']:,} 筆。
- 已完成 K 棒：5 分鐘 {len(five_minute):,} 根、1 小時 {len(hourly):,} 根；支撐箱 {supports} 個、壓力箱 {resistances} 個。
- 箱體：close pivot {args.pivot_lookback}/{args.pivot_lookback}、signed-volume filter {args.volume_filter_length}、ATR({args.zone_atr_length}) × {args.zone_box_width:g}。
- 進場：5 分鐘已完成 K 的兩種紅菱形；訊號後下一筆 raw aggTrade 做空，同時最多一個 {args.position_btc:g} BTC 部位。
- 出場：持倉後先觀察到小時 Supertrend 空頭，再於空翻多後下一筆成交退出；raw price 結構停損優先。停損為 anchor + {args.stop_atr_buffer:g} × 小時 ATR({args.stop_atr_length})。
- 小時 Adaptive Supertrend：ATR({args.atr_length})、乘數 {args.base_multiplier:g}–{args.min_multiplier:g}、speed lookback {args.speed_lookback}、threshold {args.low_speed:g}–{args.high_speed:g}、smoothing {args.smoothing_span}。
- 成本：單邊手續費 {args.taker_fee_rate * 10_000:g} bps、單邊不利滑價 {args.slippage_bps:g} bps，不計 funding；初始資金 US${args.initial_equity_usdt:,.2f}。

## 確認時間與 TradingView 顯示

Pine 原碼的 `offset=-1` 只把菱形視覺上往前移一根，並不代表當時已可交易。本回測把菱形標在真正完成確認的 5 分鐘 K，並只在之後的 raw trade 成交，沒有未完成 K 或 intrabar 偷看。

5 分鐘紅菱形共 {summary['red_signals']} 個；直接用 1 小時 OHLC 計算的紅菱形共 {hourly_reds} 個。對每個 5 分鐘訊號，以其所在小時 K 的真正收盤作等待時間基準，共比較 {len(timing)} 個；5 分鐘確認平均提早 {average_lead:.2f} 分鐘，中位數 {median_lead:.2f} 分鐘。這是確認延遲比較；由於 5 分鐘與 1 小時 OHLC 的 crossing 路徑不同，不表示每個訊號在 1 小時資料上也一定會出現。

| 訊號／績效 | 數值 |
| --- | ---: |
| Resistance Holds 紅菱形 | {summary['resistance_holds']} |
| Support-as-Resistance 紅菱形 | {summary['support_as_resistance_holds']} |
| Support Holds 綠菱形 | {summary['support_holds']} |
| Resistance-as-Support 綠菱形 | {summary['resistance_as_support_holds']} |
| 紅菱形 / 成交 | {summary['red_signals']} / {summary['filled_entries']} |
| 持倉中或同 tick 忽略 | {summary['ignored_while_occupied']} |
| ATR 尚未完成而略過 | {summary['skipped_missing_stop_atr']} |
| Supertrend 空翻多出場 | {summary['bullish_flip_exits']} |
| 結構停損出場 | {summary['structure_stop_exits']} |
| 資料結束出場 | {summary['data_end_exits']} |
| 交易 / 勝 / 負 | {summary['trades']} / {summary['wins']} / {summary['losses']} |
| 勝率 | {summary['win_rate_percent']:.2f}% |
| Profit factor | {format_profit_factor(summary['profit_factor'])} |
| Raw-price P&L | US${summary['raw_price_pnl_usdt']:,.2f} |
| 滑價成本 | US${summary['slippage_cost_usdt']:,.2f} |
| 手續費 | US${summary['fees_usdt']:,.2f} |
| 淨損益 | US${summary['net_pnl_usdt']:,.2f} |
| 最終權益 | US${summary['final_equity_usdt']:,.2f} |
| 報酬率 | {summary['return_percent']:.2f}% |
| 最大回撤 | US${summary['maximum_drawdown_usdt']:,.2f} |
| 平均持倉 | {summary['average_holding_hours']:.2f} 小時 |
| 市場曝險 | {summary['exposure_percent']:.2f}% |
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", metavar="PATH")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--confirmation-minutes", type=int, choices=(5,), default=5)
    parser.add_argument("--volume-bar-notional", type=float, default=1_000_000,
                        help="Only used by the shared preprocessing cache.")
    parser.add_argument("--max-gap-seconds", type=float, default=60)
    parser.add_argument("--initial-equity-usdt", type=float, default=10_000)
    parser.add_argument("--position-btc", type=float, default=0.01)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-bps", type=float, default=2)
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--zone-atr-length", type=int, default=200)
    parser.add_argument("--zone-box-width", type=float, default=1.0)
    parser.add_argument("--stop-atr-length", type=int, default=20)
    parser.add_argument("--stop-atr-buffer", type=float, default=0.10)
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
    positives = (
        args.confirmation_minutes, args.volume_bar_notional, args.max_gap_seconds,
        args.initial_equity_usdt, args.position_btc, args.pivot_lookback,
        args.volume_filter_length, args.zone_atr_length, args.stop_atr_length,
        args.atr_length, args.base_multiplier, args.min_multiplier,
        args.speed_lookback, args.smoothing_span, args.chart_sample_minutes,
    )
    if min(positives) <= 0:
        parser.error("bar sizes, capital, position size, and indicator lengths must be positive")
    if args.min_multiplier > args.base_multiplier:
        parser.error("--min-multiplier must not exceed --base-multiplier")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must be greater than --low-speed")
    if min(args.taker_fee_rate, args.slippage_bps, args.zone_box_width, args.stop_atr_buffer) < 0:
        parser.error("cost and width parameters must be non-negative")
    if args.refresh_cache and args.no_cache:
        parser.error("--refresh-cache and --no-cache cannot be combined")
    return args


def main() -> None:
    args = parse_args()
    input_paths = resolve_input_paths(args.input)
    args.output_dir = args.output_dir.resolve()
    args.report_dir = args.report_dir.resolve()
    hourly_raw, _unused_volume, source_summary = load_or_build_preprocessing(input_paths, args)
    five_raw = load_or_build_time_bars(input_paths, args)
    hourly, five_minute, zones = build_indicators(hourly_raw, five_raw, args)
    trades, equity, summary = backtest(
        iter_agg_trades(input_paths), five_minute, hourly,
        initial_equity_usdt=args.initial_equity_usdt, position_btc=args.position_btc,
        taker_fee_rate=args.taker_fee_rate, slippage_bps=args.slippage_bps,
        chart_sample_minutes=args.chart_sample_minutes,
    )
    timing = compare_confirmation_timing(five_minute, hourly)
    stem = f"{output_stem(input_paths)}_5m_diamond_hourly_supertrend"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "bars": args.output_dir / f"{stem}_bars.csv",
        "hourly": args.output_dir / f"{stem}_hourly.csv",
        "zones": args.output_dir / f"{stem}_zones.csv",
        "trades": args.output_dir / f"{stem}_trades.csv",
        "equity": args.output_dir / f"{stem}_equity.csv",
        "timing": args.output_dir / f"{stem}_timing_comparison.csv",
        "chart": args.output_dir / f"{stem}.html",
        "report": args.report_dir / f"{stem.lower()}.md",
    }
    five_minute.to_csv(paths["bars"], index=False, encoding="utf-8-sig")
    hourly.to_csv(paths["hourly"], index=False, encoding="utf-8-sig")
    zones.to_csv(paths["zones"], index=False, encoding="utf-8-sig")
    trades.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
    equity.to_csv(paths["equity"], index=False, encoding="utf-8-sig")
    timing.to_csv(paths["timing"], index=False, encoding="utf-8-sig")
    write_chart(paths["chart"], zones, five_minute, hourly, trades, equity,
                args.initial_equity_usdt, args.chart_sample_minutes)
    write_report(paths["report"], args, source_summary, five_minute, hourly, zones, timing, summary)
    print(
        f"hourly_bars={len(hourly)} five_minute_bars={len(five_minute)} "
        f"red_signals={summary['red_signals']} trades={summary['trades']} "
        f"net_pnl_usdt={summary['net_pnl_usdt']:.2f} final_equity_usdt={summary['final_equity_usdt']:.2f}"
    )
    print(f"report={paths['report']}")
    print(f"chart={paths['chart']}")


if __name__ == "__main__":
    main()
