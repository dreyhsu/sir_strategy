#!/usr/bin/env python3
"""Backtest BTCUSDT shorts using hourly Pine S/R and volume-bar Supertrend.

Hourly bars create the Pine-style support/resistance boxes and structure stop.
A completed USDT-notional bar touching active resistance while its adaptive
Supertrend is bearish queues a short for the next raw aggregate trade.  The
trade exits at the structure stop or after a completed bullish Supertrend flip.
"""

from __future__ import annotations

import argparse
from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable

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
    from .backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
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
    from backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from backtest_tmf_hourly_support_long import pine_style_zones


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT_DIR = ROOT / "doc"


@dataclass
class OpenShort:
    signal_time_ms: int
    signal_tick_end_id: int
    entry_tick_id: int
    entry_time_ms: int
    raw_entry_price: float
    entry_fill_price: float
    entry_fee_usdt: float
    entry_supertrend: float
    entry_direction: int
    entry_atr: float
    entry_multiplier: float
    resistance_id: int
    resistance_bottom: float
    resistance_top: float
    resistance_signal_number: int
    hourly_stop_atr: float
    stop_price: float
    lowest_price: float
    highest_price: float


def optional_float(value: object) -> float:
    return np.nan if pd.isna(value) else float(value)


def add_hourly_structure_atr(hourly: pd.DataFrame, length: int) -> pd.DataFrame:
    """Add the completed-hour ATR used by the resistance structure stop."""
    result = hourly.copy().sort_values("tick_end_id", kind="stable").reset_index(drop=True)
    previous_close = result["close"].shift(1)
    true_range = pd.concat(
        [
            result["high"] - result["low"],
            (result["high"] - previous_close).abs(),
            (result["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    result["structure_stop_atr"] = true_range.ewm(
        alpha=1 / length,
        adjust=False,
        min_periods=length,
    ).mean()
    return result


def add_resistance_touch_signals(
    bars: pd.DataFrame,
    hourly: pd.DataFrame,
    zones: pd.DataFrame,
    stop_atr_buffer: float,
    max_signals_per_resistance: int = 3,
) -> pd.DataFrame:
    """Label causal hourly-resistance touches and bearish volume-Supertrend signals."""
    result = bars.copy().sort_values("tick_end_id", kind="stable").reset_index(drop=True)
    result["resistance_id"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["resistance_bottom"] = np.nan
    result["resistance_top"] = np.nan
    result["hourly_stop_atr"] = np.nan
    result["stop_price"] = np.nan
    result["resistance_touch"] = False
    result["resistance_supertrend_short"] = False
    result["resistance_signal_number"] = pd.Series(pd.NA, index=result.index, dtype="Int64")

    hourly_rows = list(
        hourly[["tick_end_id", "structure_stop_atr"]]
        .sort_values("tick_end_id", kind="stable")
        .itertuples(index=False)
    )
    resistances = []
    if not zones.empty:
        resistances = list(
            zones[zones["zone_type"] == "resistance"]
            .sort_values("bottom", kind="stable")
            .itertuples(index=False)
        )
    hourly_index = 0
    current_stop_atr = np.nan
    signal_counts: dict[int, int] = defaultdict(int)
    armed: dict[int, bool] = defaultdict(lambda: True)

    for index, bar in result.iterrows():
        tick_end_id = int(bar["tick_end_id"])
        while hourly_index < len(hourly_rows) and int(hourly_rows[hourly_index].tick_end_id) < tick_end_id:
            value = hourly_rows[hourly_index].structure_stop_atr
            current_stop_atr = np.nan if pd.isna(value) else float(value)
            hourly_index += 1
        result.at[index, "hourly_stop_atr"] = current_stop_atr

        timestamp = bar["timestamp"]
        direction = None if pd.isna(bar["supertrend_direction"]) else int(bar["supertrend_direction"])
        if direction == 1:
            for zone in resistances:
                zone_id = int(zone.zone_id)
                if (
                    zone.created_time < timestamp
                    and (pd.isna(zone.broken_time) or timestamp < zone.broken_time)
                    and signal_counts[zone_id] < max_signals_per_resistance
                ):
                    armed[zone_id] = True

        selected = None
        for zone in resistances:
            if not zone.created_time < timestamp:
                continue
            if pd.notna(zone.broken_time) and not timestamp < zone.broken_time:
                continue
            if float(zone.bottom) <= float(bar["high"]) and float(zone.top) >= float(bar["low"]):
                selected = zone
                break
        if selected is None:
            continue

        result.at[index, "resistance_id"] = int(selected.zone_id)
        result.at[index, "resistance_bottom"] = float(selected.bottom)
        result.at[index, "resistance_top"] = float(selected.top)
        result.at[index, "resistance_touch"] = True
        if not pd.isna(current_stop_atr):
            result.at[index, "stop_price"] = float(selected.top) + stop_atr_buffer * current_stop_atr
        zone_id = int(selected.zone_id)
        if direction == -1 and armed[zone_id] and signal_counts[zone_id] < max_signals_per_resistance:
            signal_counts[zone_id] += 1
            armed[zone_id] = False
            result.at[index, "resistance_supertrend_short"] = True
            result.at[index, "resistance_signal_number"] = signal_counts[zone_id]
    return result


def add_zone_signal_counts(zones: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    """Annotate every Pine box with the number of emitted entry signals."""
    result = zones.copy()
    counts = (
        bars[bars["resistance_supertrend_short"]]
        .groupby("resistance_id", dropna=True)
        .size()
        .to_dict()
    )
    result["signals_emitted"] = [int(counts.get(int(zone_id), 0)) for zone_id in result["zone_id"]]
    return result


def build_indicators(
    hourly: pd.DataFrame,
    volume_bars: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Build hourly Pine zones and adaptive Supertrend signals on volume bars."""
    hourly_with_atr = add_hourly_structure_atr(hourly, args.stop_atr_length)
    zones = pine_style_zones(
        hourly_with_atr,
        args.pivot_lookback,
        args.volume_filter_length,
        args.zone_atr_length,
        args.zone_box_width,
    )
    bars = add_adaptive_supertrend(
        volume_bars,
        args.atr_length,
        args.base_multiplier,
        args.min_multiplier,
        args.speed_lookback,
        args.low_speed,
        args.high_speed,
        args.smoothing_span,
    )
    bars = add_resistance_touch_signals(
        bars,
        hourly_with_atr,
        zones,
        args.stop_atr_buffer,
        args.max_signals_per_resistance,
    )
    zones = add_zone_signal_counts(zones, bars)
    return hourly_with_atr, bars, zones


def close_short(
    position: OpenShort,
    exit_tick_id: int,
    exit_time_ms: int,
    raw_exit_price: float,
    reason: str,
    quantity_btc: float,
    taker_fee_rate: float,
    slippage_bps: float,
    exit_signal_time_ms: int | None = None,
    exit_supertrend: float = np.nan,
    exit_direction: float = np.nan,
) -> tuple[dict[str, object], float]:
    """Close one short using adverse exit slippage and return its net P&L."""
    exit_fill = raw_exit_price * (1 + slippage_bps / 10_000)
    exit_fee = exit_fill * quantity_btc * taker_fee_rate
    position.lowest_price = min(position.lowest_price, raw_exit_price)
    position.highest_price = max(position.highest_price, raw_exit_price)
    raw_price_pnl = (position.raw_entry_price - raw_exit_price) * quantity_btc
    gross = (position.entry_fill_price - exit_fill) * quantity_btc
    net = gross - position.entry_fee_usdt - exit_fee
    record = {
        "signal_time": as_timestamp(position.signal_time_ms),
        "entry_time": as_timestamp(position.entry_time_ms),
        "exit_signal_time": (
            as_timestamp(exit_signal_time_ms) if exit_signal_time_ms is not None else pd.NaT
        ),
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
        "raw_price_pnl_usdt": raw_price_pnl,
        "gross_pnl_usdt": gross,
        "slippage_cost_usdt": raw_price_pnl - gross,
        "net_pnl_usdt": net,
        "mfe_usdt": (position.entry_fill_price - position.lowest_price) * quantity_btc,
        "mae_usdt": (position.entry_fill_price - position.highest_price) * quantity_btc,
        "holding_hours": (exit_time_ms - position.entry_time_ms) / 3_600_000,
        "entry_supertrend": position.entry_supertrend,
        "entry_supertrend_direction": position.entry_direction,
        "entry_atr": position.entry_atr,
        "entry_adaptive_multiplier": position.entry_multiplier,
        "resistance_id": position.resistance_id,
        "resistance_bottom": position.resistance_bottom,
        "resistance_top": position.resistance_top,
        "resistance_signal_number": position.resistance_signal_number,
        "hourly_stop_atr": position.hourly_stop_atr,
        "stop_price": position.stop_price,
        "exit_supertrend": exit_supertrend,
        "exit_supertrend_direction": exit_direction,
        "exit_reason": reason,
    }
    return record, net


def backtest_volume_supertrend_short(
    ticks: Iterable[tuple[int, int, float, float, int]],
    bars: pd.DataFrame,
    *,
    initial_equity_usdt: float = 10_000,
    position_btc: float = 0.01,
    taker_fee_rate: float = 0.0005,
    slippage_bps: float = 2,
    chart_sample_minutes: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Replay raw trades and execute completed volume-bar signals causally."""
    completed_bars = {int(row.tick_end_id): row for row in bars.itertuples(index=False)}
    position: OpenShort | None = None
    pending_entry: object | None = None
    pending_exit: object | None = None
    previous_direction: int | None = None
    current_supertrend = np.nan
    current_direction: int | None = None
    realized = 0.0
    peak_equity = initial_equity_usdt
    minimum_equity = initial_equity_usdt
    max_drawdown = 0.0
    trade_records: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    counters = defaultdict(int)
    exposure_ms = defaultdict(int)
    previous_exposure = 0
    last_timestamp_ms: int | None = None
    last_tick_id: int | None = None
    last_price: float | None = None
    next_sample_ms: int | None = None

    for tick_id, _agg_id, price, _quantity, timestamp_ms in ticks:
        if last_timestamp_ms is not None:
            exposure_ms[previous_exposure] += timestamp_ms - last_timestamp_ms
        last_timestamp_ms = timestamp_ms
        last_tick_id = tick_id
        last_price = price
        executed_event = False
        exited_this_tick = False

        if position is not None and price >= position.stop_price:
            pending_exit = None
            record, trade_net = close_short(
                position,
                tick_id,
                timestamp_ms,
                price,
                "resistance_structure_stop",
                position_btc,
                taker_fee_rate,
                slippage_bps,
                exit_supertrend=current_supertrend,
                exit_direction=(np.nan if current_direction is None else float(current_direction)),
            )
            trade_records.append(record)
            realized += trade_net
            position = None
            counters["structure_stop_exits"] += 1
            executed_event = True
            exited_this_tick = True
        elif pending_exit is not None and position is not None:
            signal = pending_exit
            pending_exit = None
            record, trade_net = close_short(
                position,
                tick_id,
                timestamp_ms,
                price,
                "adaptive_volume_supertrend_bullish_flip",
                position_btc,
                taker_fee_rate,
                slippage_bps,
                exit_signal_time_ms=int(signal.timestamp.value // 1_000_000),
                exit_supertrend=optional_float(signal.supertrend),
                exit_direction=optional_float(signal.supertrend_direction),
            )
            trade_records.append(record)
            realized += trade_net
            position = None
            counters["bullish_flip_exits"] += 1
            executed_event = True
            exited_this_tick = True

        if not exited_this_tick and pending_entry is not None and position is None:
            signal = pending_entry
            pending_entry = None
            if pd.isna(signal.hourly_stop_atr) or pd.isna(signal.stop_price):
                counters["skipped_missing_stop_atr"] += 1
            else:
                entry_fill = price * (1 - slippage_bps / 10_000)
                entry_fee = entry_fill * position_btc * taker_fee_rate
                position = OpenShort(
                    signal_time_ms=int(signal.timestamp.value // 1_000_000),
                    signal_tick_end_id=int(signal.tick_end_id),
                    entry_tick_id=tick_id,
                    entry_time_ms=timestamp_ms,
                    raw_entry_price=price,
                    entry_fill_price=entry_fill,
                    entry_fee_usdt=entry_fee,
                    entry_supertrend=optional_float(signal.supertrend),
                    entry_direction=int(signal.supertrend_direction),
                    entry_atr=optional_float(signal.atr),
                    entry_multiplier=optional_float(signal.adaptive_multiplier),
                    resistance_id=int(signal.resistance_id),
                    resistance_bottom=float(signal.resistance_bottom),
                    resistance_top=float(signal.resistance_top),
                    resistance_signal_number=int(signal.resistance_signal_number),
                    hourly_stop_atr=float(signal.hourly_stop_atr),
                    stop_price=float(signal.stop_price),
                    lowest_price=price,
                    highest_price=price,
                )
                counters["filled_entries"] += 1
                executed_event = True

        if position is not None:
            position.lowest_price = min(position.lowest_price, price)
            position.highest_price = max(position.highest_price, price)

        completed = completed_bars.get(tick_id)
        completed_signal = False
        if completed is not None and not pd.isna(completed.supertrend_direction):
            direction = int(completed.supertrend_direction)
            if direction == -1:
                counters["bearish_bars"] += 1
            if bool(completed.resistance_touch):
                counters["resistance_touch_bars"] += 1
            if bool(completed.resistance_supertrend_short):
                counters["entry_signals"] += 1
                completed_signal = True
                if not exited_this_tick and position is None and pending_entry is None:
                    pending_entry = completed
                else:
                    counters["ignored_while_occupied"] += 1
            if position is not None and previous_direction == -1 and direction == 1:
                pending_exit = completed
                counters["bullish_flip_signals"] += 1
                completed_signal = True
            previous_direction = direction
            current_direction = direction
            current_supertrend = optional_float(completed.supertrend)

        unrealized = 0.0
        if position is not None:
            unrealized = (
                (position.entry_fill_price - price) * position_btc - position.entry_fee_usdt
            )
        equity = initial_equity_usdt + realized + unrealized
        peak_equity = max(peak_equity, equity)
        minimum_equity = min(minimum_equity, equity)
        drawdown = equity - peak_equity
        max_drawdown = min(max_drawdown, drawdown)
        force_sample = executed_event or completed_signal
        if next_sample_ms is None or timestamp_ms >= next_sample_ms or force_sample:
            samples.append(
                {
                    "timestamp": as_timestamp(timestamp_ms),
                    "price": price,
                    "equity_usdt": equity,
                    "realized_usdt": realized,
                    "unrealized_usdt": unrealized,
                    "open_positions": int(position is not None),
                    "drawdown_usdt": drawdown,
                }
            )
            next_sample_ms = (
                (timestamp_ms // (chart_sample_minutes * 60_000) + 1)
                * chart_sample_minutes
                * 60_000
            )
        previous_exposure = int(position is not None)

    pending_entry = None
    pending_exit = None
    if (
        position is not None
        and last_tick_id is not None
        and last_timestamp_ms is not None
        and last_price is not None
    ):
        record, trade_net = close_short(
            position,
            last_tick_id,
            last_timestamp_ms,
            last_price,
            "data_end",
            position_btc,
            taker_fee_rate,
            slippage_bps,
            exit_supertrend=current_supertrend,
            exit_direction=(np.nan if current_direction is None else float(current_direction)),
        )
        trade_records.append(record)
        realized += trade_net
        counters["data_end_exits"] += 1
        position = None
        final_equity = initial_equity_usdt + realized
        peak_equity = max(peak_equity, final_equity)
        minimum_equity = min(minimum_equity, final_equity)
        drawdown = final_equity - peak_equity
        max_drawdown = min(max_drawdown, drawdown)
        samples.append(
            {
                "timestamp": as_timestamp(last_timestamp_ms),
                "price": last_price,
                "equity_usdt": final_equity,
                "realized_usdt": realized,
                "unrealized_usdt": 0.0,
                "open_positions": 0,
                "drawdown_usdt": drawdown,
            }
        )

    trades = pd.DataFrame(trade_records)
    if not trades.empty:
        trades.insert(0, "trade_number", range(1, len(trades) + 1))
        trades["cumulative_net_pnl_usdt"] = trades["net_pnl_usdt"].cumsum()
    samples_frame = pd.DataFrame(samples)
    if not samples_frame.empty:
        samples_frame = samples_frame.drop_duplicates(subset=["timestamp"], keep="last")

    elapsed_ms = sum(exposure_ms.values())
    wins = trades[trades["net_pnl_usdt"] > 0] if not trades.empty else trades
    losses = trades[trades["net_pnl_usdt"] < 0] if not trades.empty else trades
    gross_profit = float(wins["net_pnl_usdt"].sum()) if not wins.empty else 0.0
    gross_loss = float(losses["net_pnl_usdt"].sum()) if not losses.empty else 0.0
    profit_factor: float | None
    if gross_loss < 0:
        profit_factor = gross_profit / abs(gross_loss)
    else:
        profit_factor = None
    summary: dict[str, object] = {
        "bearish_bars": counters["bearish_bars"],
        "resistance_touch_bars": counters["resistance_touch_bars"],
        "entry_signals": counters["entry_signals"],
        "filled_entries": counters["filled_entries"],
        "ignored_while_occupied": counters["ignored_while_occupied"],
        "skipped_missing_stop_atr": counters["skipped_missing_stop_atr"],
        "bullish_flip_signals": counters["bullish_flip_signals"],
        "bullish_flip_exits": counters["bullish_flip_exits"],
        "structure_stop_exits": counters["structure_stop_exits"],
        "data_end_exits": counters["data_end_exits"],
        "trades": len(trades),
        "wins": len(wins),
        "losses": len(losses),
        "win_rate_percent": len(wins) / len(trades) * 100 if len(trades) else 0.0,
        "profit_factor": profit_factor,
        "raw_price_pnl_usdt": float(trades["raw_price_pnl_usdt"].sum()) if not trades.empty else 0.0,
        "gross_pnl_usdt": float(trades["gross_pnl_usdt"].sum()) if not trades.empty else 0.0,
        "slippage_cost_usdt": float(trades["slippage_cost_usdt"].sum()) if not trades.empty else 0.0,
        "fees_usdt": (
            float((trades["entry_fee_usdt"] + trades["exit_fee_usdt"]).sum())
            if not trades.empty else 0.0
        ),
        "net_pnl_usdt": realized,
        "final_equity_usdt": initial_equity_usdt + realized,
        "return_percent": realized / initial_equity_usdt * 100,
        "minimum_equity_usdt": minimum_equity,
        "maximum_drawdown_usdt": -max_drawdown,
        "average_holding_hours": (
            float(trades["holding_hours"].mean()) if not trades.empty else 0.0
        ),
        "exposure_percent": (
            exposure_ms[1] / elapsed_ms * 100 if elapsed_ms else 0.0
        ),
    }
    return trades, samples_frame, summary


def sample_bars_for_chart(bars: pd.DataFrame, minutes: int) -> pd.DataFrame:
    """Keep the last completed volume bar per chart bucket."""
    if bars.empty:
        return bars.copy()
    sampled = (
        bars.sort_values("timestamp", kind="stable")
        .set_index("timestamp")
        .resample(f"{minutes}min")
        .last()
        .dropna(subset=["close"])
        .reset_index()
    )
    return sampled


def write_chart(
    path: Path,
    zones: pd.DataFrame,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    samples: pd.DataFrame,
    initial_equity_usdt: float,
    chart_sample_minutes: int,
) -> None:
    chart_bars = sample_bars_for_chart(bars, chart_sample_minutes)
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.62, 0.16, 0.22],
        subplot_titles=(
            "BTCUSDT notional-volume bars and adaptive Supertrend",
            "Open BTC positions",
            "Marked-to-market account equity",
        ),
    )
    figure.add_trace(
        go.Scatter(x=chart_bars["timestamp"], y=chart_bars["close"], mode="lines", name="Volume-bar close"),
        row=1,
        col=1,
    )
    chart_end = chart_bars["timestamp"].iloc[-1]
    if not zones.empty:
        for zone in zones.itertuples(index=False):
            end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
            is_resistance = zone.zone_type == "resistance"
            figure.add_shape(
                type="rect",
                x0=zone.created_time,
                x1=end,
                y0=zone.bottom,
                y1=zone.top,
                fillcolor=("rgba(211,47,47,0.12)" if is_resistance else "rgba(32,202,38,0.12)"),
                line={
                    "color": ("rgba(211,47,47,0.55)" if is_resistance else "rgba(32,202,38,0.55)"),
                    "width": 1,
                },
                row=1,
                col=1,
            )
    figure.add_trace(
        go.Scatter(
            x=chart_bars["timestamp"],
            y=chart_bars["supertrend"],
            mode="lines",
            name="Adaptive Supertrend",
            line={"color": "#7b1fa2", "width": 1.5},
        ),
        row=1,
        col=1,
    )
    emitted_signals = bars[bars["resistance_supertrend_short"]]
    if not emitted_signals.empty:
        figure.add_trace(
            go.Scatter(
                x=emitted_signals["timestamp"],
                y=emitted_signals["high"],
                mode="markers",
                name="Resistance short signal",
                text=[
                    f"Resistance {int(zone_id)}, signal {int(signal_number)}"
                    for zone_id, signal_number in zip(
                        emitted_signals["resistance_id"],
                        emitted_signals["resistance_signal_number"],
                    )
                ],
                hovertemplate="%{text}<br>%{x}<br>Bar high: %{y:,.2f}<extra></extra>",
                marker={"symbol": "triangle-down-open", "size": 9, "color": "#ad1457"},
            ),
            row=1,
            col=1,
        )
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["entry_time"],
                y=trades["entry_fill_price"],
                mode="markers",
                name="Short entry",
                text=[
                    f"Resistance {int(zone_id)}, signal {int(signal_number)}"
                    for zone_id, signal_number in zip(
                        trades["resistance_id"], trades["resistance_signal_number"]
                    )
                ],
                hovertemplate="%{text}<br>%{x}<br>Fill: %{y:,.2f}<extra></extra>",
                marker={"symbol": "triangle-down", "size": 11, "color": "#d32f2f"},
            ),
            row=1,
            col=1,
        )
        exit_styles = {
            "adaptive_volume_supertrend_bullish_flip": ("Bullish-flip exit", "#00897b"),
            "resistance_structure_stop": ("Structure-stop exit", "#ef6c00"),
            "data_end": ("Data-end exit", "#546e7a"),
        }
        for reason, (label, color) in exit_styles.items():
            exits = trades[trades["exit_reason"] == reason]
            if exits.empty:
                continue
            figure.add_trace(
                go.Scatter(
                    x=exits["exit_time"],
                    y=exits["exit_fill_price"],
                    mode="markers",
                    name=label,
                    marker={"symbol": "x", "size": 10, "color": color},
                ),
                row=1,
                col=1,
            )
    figure.add_trace(
        go.Scatter(
            x=samples["timestamp"],
            y=samples["open_positions"],
            mode="lines",
            line_shape="hv",
            name="Open positions",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["equity_usdt"], mode="lines", name="Account equity"),
        row=3,
        col=1,
    )
    figure.add_hline(y=initial_equity_usdt, line_dash="dot", line_color="gray", row=3, col=1)
    figure.update_layout(title="BTCUSDT volume-bar adaptive Supertrend short backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Positions", dtick=1, row=2, col=1)
    figure.update_yaxes(title_text="USDT", tickformat=",.0f", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def format_profit_factor(value: object) -> str:
    return "n/a" if value is None else f"{float(value):.2f}"


def write_report(
    path: Path,
    args: argparse.Namespace,
    first_summary: dict[str, object],
    bars: pd.DataFrame,
    zones: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    input_files = "\n".join(f"  - `{input_path}`" for input_path in first_summary["input_files"])
    support_count = int((zones["zone_type"] == "support").sum()) if not zones.empty else 0
    resistance_count = int((zones["zone_type"] == "resistance").sum()) if not zones.empty else 0
    resistance_signal_rows = "\n".join(
        f"| {int(zone.zone_id)} | {int(zone.signals_emitted)} |"
        for zone in zones[zones["zone_type"] == "resistance"].itertuples(index=False)
    )
    text = f"""# BTCUSDT hourly S/R + volume-bar adaptive Supertrend short backtest

- Inputs:
{input_files}
- Source rows: {first_summary['rows']:,}; completed hourly bars: {first_summary['hourly_bars']:,}; completed notional-volume bars: {len(bars):,}.
- Period: {first_summary['first_timestamp']} to {first_summary['last_timestamp']}.
- Continuous 24/7 market. Volume bar threshold: US${args.volume_bar_notional:,.0f}; maximum data gap: {args.max_gap_seconds:g} seconds.
- Adaptive Supertrend: ATR({args.atr_length}), multiplier {args.base_multiplier:g} to {args.min_multiplier:g}, speed lookback {args.speed_lookback}, speed range {args.low_speed:g}–{args.high_speed:g}, smoothing {args.smoothing_span}.
- Hourly Pine S/R: close pivot {args.pivot_lookback}/{args.pivot_lookback}, signed-volume filter {args.volume_filter_length}, ATR({args.zone_atr_length}) box width × {args.zone_box_width:g}. Generated {support_count} support and {resistance_count} resistance boxes.
- Entry: an armed hourly resistance emits on the first touching bearish volume-Supertrend bar, then requires a bullish state to re-arm. Maximum {args.max_signals_per_resistance} emitted signals per resistance box; fill on the next raw aggTrade when flat.
- Exit: resistance top + {args.stop_atr_buffer:g} × completed hourly ATR({args.stop_atr_length}) structure stop, or completed volume-bar bearish-to-bullish flip filled on the next raw aggTrade. Open trades close at data end.
- Initial equity: US${args.initial_equity_usdt:,.2f}; position: {args.position_btc:g} BTC.
- Costs: {args.taker_fee_rate * 10_000:g} bps taker fee and {args.slippage_bps:g} bps adverse slippage per side. Funding is excluded.

| Resistance box | Signals emitted |
| ---: | ---: |
{resistance_signal_rows}

| Metric | Value |
| --- | ---: |
| Bearish bars | {summary['bearish_bars']} |
| Resistance-touch bars | {summary['resistance_touch_bars']} |
| Entry signals / fills | {summary['entry_signals']} / {summary['filled_entries']} |
| Signals ignored while occupied | {summary['ignored_while_occupied']} |
| Entries skipped before stop ATR warm-up | {summary['skipped_missing_stop_atr']} |
| Bullish flip signals / exits | {summary['bullish_flip_signals']} / {summary['bullish_flip_exits']} |
| Structure-stop exits | {summary['structure_stop_exits']} |
| Data-end exits | {summary['data_end_exits']} |
| Trades | {summary['trades']} |
| Wins / losses | {summary['wins']} / {summary['losses']} |
| Win rate | {summary['win_rate_percent']:.2f}% |
| Profit factor | {format_profit_factor(summary['profit_factor'])} |
| Raw-price P&L | US${summary['raw_price_pnl_usdt']:,.2f} |
| Slippage cost | US${summary['slippage_cost_usdt']:,.2f} |
| Fees | US${summary['fees_usdt']:,.2f} |
| Net P&L | US${summary['net_pnl_usdt']:,.2f} |
| Final equity | US${summary['final_equity_usdt']:,.2f} |
| Return | {summary['return_percent']:.2f}% |
| Minimum equity | US${summary['minimum_equity_usdt']:,.2f} |
| Maximum drawdown | US${summary['maximum_drawdown_usdt']:,.2f} |
| Average holding time | {summary['average_holding_hours']:.2f} hours |
| Market exposure | {summary['exposure_percent']:.2f}% |
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
            "to BTCUSDT-aggTrades-YYYY-MM.csv files. Defaults to data/btcusdt."
        ),
    )
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--volume-bar-notional", type=float, default=1_000_000)
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
    parser.add_argument(
        "--max-signals-per-resistance",
        type=int,
        choices=(1, 2, 3),
        default=3,
        help="Maximum bearish-cycle signals emitted during each resistance box's active lifetime.",
    )
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
        args.volume_bar_notional,
        args.max_gap_seconds,
        args.initial_equity_usdt,
        args.position_btc,
        args.pivot_lookback,
        args.volume_filter_length,
        args.zone_atr_length,
        args.stop_atr_length,
        args.atr_length,
        args.base_multiplier,
        args.min_multiplier,
        args.speed_lookback,
        args.smoothing_span,
        args.chart_sample_minutes,
    )
    if min(positives) <= 0:
        parser.error("bar size, capital, position size, and indicator lengths must be positive")
    if args.min_multiplier > args.base_multiplier:
        parser.error("--min-multiplier must not exceed --base-multiplier")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must be greater than --low-speed")
    if args.taker_fee_rate < 0 or args.slippage_bps < 0 or args.zone_box_width < 0 or args.stop_atr_buffer < 0:
        parser.error("fees, slippage, box width, and stop buffer must be non-negative")
    if args.refresh_cache and args.no_cache:
        parser.error("--refresh-cache and --no-cache cannot be used together")
    return args


def main() -> None:
    args = parse_args()
    input_paths = resolve_input_paths(args.input)
    args.output_dir = args.output_dir.resolve()
    args.report_dir = args.report_dir.resolve()
    hourly, volume_bars, first_summary = load_or_build_preprocessing(input_paths, args)
    hourly, bars, zones = build_indicators(hourly, volume_bars, args)
    trades, samples, summary = backtest_volume_supertrend_short(
        iter_agg_trades(input_paths),
        bars,
        initial_equity_usdt=args.initial_equity_usdt,
        position_btc=args.position_btc,
        taker_fee_rate=args.taker_fee_rate,
        slippage_bps=args.slippage_bps,
        chart_sample_minutes=args.chart_sample_minutes,
    )
    stem = output_stem(input_paths)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    bars_path = args.output_dir / f"{stem}_volume_supertrend_bars.csv"
    zones_path = args.output_dir / f"{stem}_hourly_pine_zones.csv"
    trades_path = args.output_dir / f"{stem}_volume_supertrend_short_trades.csv"
    equity_path = args.output_dir / f"{stem}_volume_supertrend_equity_samples.csv"
    chart_path = args.output_dir / f"{stem}_volume_supertrend_short.html"
    report_path = args.report_dir / f"{stem.lower()}_volume_supertrend_short.md"
    bars.to_csv(bars_path, index=False, encoding="utf-8-sig")
    zones.to_csv(zones_path, index=False, encoding="utf-8-sig")
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")
    samples.to_csv(equity_path, index=False, encoding="utf-8-sig")
    write_chart(
        chart_path,
        zones,
        bars,
        trades,
        samples,
        args.initial_equity_usdt,
        args.chart_sample_minutes,
    )
    write_report(report_path, args, first_summary, bars, zones, summary)
    print(
        f"hourly_bars={len(hourly)} zones={len(zones)} volume_bars={len(bars)} trades={summary['trades']} "
        f"net_pnl_usdt={summary['net_pnl_usdt']:.2f} "
        f"final_equity_usdt={summary['final_equity_usdt']:.2f}"
    )
    print(f"report={report_path}")
    print(f"chart={chart_path}")


if __name__ == "__main__":
    main()
