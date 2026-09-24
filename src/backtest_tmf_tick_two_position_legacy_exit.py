#!/usr/bin/env python
"""Tick-ordered TMF short backtest with two entries and a shared legacy exit."""

from __future__ import annotations

import argparse
import sys
import time
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from .backtest_tmf_adaptive_hourly_resistance_short_ab import build_session_volume_bars
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_resistance_short import assign_resistance_entries
    from .backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones, zone_active
except ImportError:
    from backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from backtest_tmf_adaptive_hourly_resistance_short_ab import build_session_volume_bars
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_resistance_short import assign_resistance_entries
    from backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones, zone_active


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "txf"
OUTPUT_DIR = ROOT / "txf_tick"
DOC_DIR = ROOT / "doc"
DEFAULT_START = date(2026, 8, 5)
DEFAULT_END = date(2026, 9, 15)
OUTPUT_PERIOD = "2026-08-05_to_2026-09-15"
DEFAULT_CONTRACT_TRADES = OUTPUT_DIR / f"TMF_202609_tick_two_position_contracts_{OUTPUT_PERIOD}.csv"
DEFAULT_GROUP_TRADES = OUTPUT_DIR / f"TMF_202609_tick_two_position_groups_{OUTPUT_PERIOD}.csv"
DEFAULT_CHART = OUTPUT_DIR / f"TMF_202609_tick_two_position_legacy_exit_{OUTPUT_PERIOD}.html"
DEFAULT_REPORT = DOC_DIR / f"tmf_202609_tick_two_position_legacy_exit_{OUTPUT_PERIOD}.md"


@dataclass
class OpenLot:
    group_id: int
    slot: int
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    raw_entry_price: float
    entry_fill_price: float
    entry_layer: str
    signal_tick_end_id: int
    signal_open: float
    signal_high: float
    signal_low: float
    signal_close: float
    signal_volume: float
    signal_close_position: float
    resistance_id: int
    resistance_bottom: float
    resistance_top: float
    lowest_price: float
    highest_price: float
    signal_type: str = "resistance_reversal"
    zone_type: str = "resistance"
    zone_bottom: float = np.nan
    zone_top: float = np.nan
    initial_stop: float = np.nan
    target_price: float = np.nan
    risk_points: float = np.nan


CONTRACT_COLUMNS = [
    "trade_number", "group_id", "slot", "signal_time", "entry_time", "exit_time", "entry_session",
    "exit_session", "raw_entry_price", "entry_fill_price", "raw_exit_price", "exit_fill_price",
    "entry_layer", "signal_tick_end_id", "signal_open", "signal_high", "signal_low", "signal_close", "signal_volume",
    "signal_close_position", "resistance_id", "resistance_bottom", "resistance_top", "gross_points", "net_points", "gross_ntd",
    "net_ntd", "mfe_points", "mae_points", "holding_hours", "exit_reason", "cross_session", "signal_type",
    "zone_type", "zone_bottom", "zone_top", "initial_stop", "target_price", "risk_points", "r_multiple",
    "scale_in_time",
    "cumulative_net_ntd",
]

GROUP_COLUMNS = [
    "group_id", "contract_count", "first_entry_time", "last_entry_time", "exit_time", "entry_session",
    "exit_session", "average_raw_entry_price", "average_entry_fill_price", "raw_exit_price", "exit_fill_price",
    "resistance_ids", "gross_contract_points", "net_contract_points", "gross_ntd", "net_ntd",
    "holding_hours", "exit_reason", "cross_session", "cumulative_net_ntd",
]


def prepare_ticks(ticks: pd.DataFrame) -> pd.DataFrame:
    """Assign a stable event id after filtering ticks into valid trading sessions."""
    ordering = [column for column in ("timestamp", "source_file", "source_sequence") if column in ticks.columns]
    result = ticks.sort_values(ordering, kind="stable").reset_index(drop=True)
    result["tick_id"] = np.arange(len(result), dtype=np.int64)
    return result


def add_optimized_layer_signals(
    bars: pd.DataFrame,
    hourly: pd.DataFrame,
    zones: pd.DataFrame,
    close_position_max: float,
    breakout_buffer_atr: float = 0.10,
    rejection_timeout_bars: int = 3,
) -> pd.DataFrame:
    """Create causal Early, Balanced, and Conservative resistance entries.

    A completed hourly bar first arms a touched resistance. Early is the first
    bearish bottom-close volume bar after that confirmation. Balanced requires
    a later completed hour to set a higher test high and then a lower-high
    bearish volume bar. Conservative is the next bearish bottom-close bar that
    closes below the resistance floor.
    """
    result = bars.copy()
    price_range = (result["high"] - result["low"]).replace(0, np.nan)
    result["close_position"] = (result["close"] - result["low"]) / price_range
    result["bearish_rejection"] = (
        (result["close"] < result["open"])
        & (result["close_position"] <= close_position_max)
    )
    result = assign_resistance_entries(result, zones)
    for column, default in {
        "signal_type": pd.NA, "zone_type": pd.NA, "zone_id": pd.NA,
        "zone_bottom": np.nan, "zone_top": np.nan, "breakout_confirmed": False,
        "rejection_low": np.nan, "rejection_high": np.nan,
    }.items():
        result[column] = default
    result["entry_layer"] = pd.NA
    result["resistance_reversal"] = False
    resistances = zones[zones["zone_type"] == "resistance"] if not zones.empty else zones
    supports = zones[zones["zone_type"] == "support"] if not zones.empty else zones

    for session_id, session_bars in result.groupby("session_id", sort=False):
        session_hourly = hourly[hourly["session_id"] == session_id].sort_values("timestamp", kind="stable")
        hourly_rows = list(session_hourly.itertuples(index=False))
        hourly_index = -1
        setup: dict[str, object] | None = None
        pending_rejections: list[dict[str, object]] = []
        previous_close: float | None = None
        support_signalled: set[int] = set()

        for index, bar in session_bars.sort_values("tick_end_id", kind="stable").iterrows():
            while hourly_index + 1 < len(hourly_rows) and hourly_rows[hourly_index + 1].timestamp < bar["timestamp"]:
                hourly_index += 1
                hour = hourly_rows[hourly_index]
                candidates = resistances[
                    resistances.apply(lambda zone: zone_active(zone, hour.timestamp), axis=1)
                    & (resistances["bottom"] <= float(hour.high))
                    & (resistances["top"] >= float(hour.low))
                ]
                if candidates.empty:
                    continue
                selected = candidates.sort_values("bottom").iloc[0]
                resistance_id = int(selected["zone_id"])
                if setup is None or int(setup["resistance_id"]) != resistance_id:
                    setup = {
                        "resistance_id": resistance_id,
                        "peak_high": float(hour.high),
                        "stage": 0,
                        "balanced_armed": False,
                    }
                else:
                    previous_peak = float(setup["peak_high"])
                    if int(setup["stage"]) >= 1 and float(hour.high) > previous_peak:
                        setup["balanced_armed"] = True
                    setup["peak_high"] = max(previous_peak, float(hour.high))

            # A bearish resistance touch becomes a rejection candidate.  Entry
            # requires a later completed volume bar to break its low.
            if not pd.isna(bar["resistance_id"]):
                rid = int(bar["resistance_id"])
                pending_rejections.append({
                    "zone_id": rid, "bottom": float(bar["resistance_bottom"]),
                    "top": float(bar["resistance_top"]), "low": float(bar["low"]),
                    "high": float(bar["high"]), "age": 0,
                })

            # hourly_index already identifies the latest completed hour.  Do
            # not rescan every earlier hourly row for every volume bar.
            atr_value = np.nan
            if hourly_index >= 0 and hasattr(hourly_rows[hourly_index], "atr"):
                atr_value = float(hourly_rows[hourly_index].atr)
            buffer = 0.0 if pd.isna(atr_value) else breakout_buffer_atr * atr_value

            # Confirm a rejection only once, and expire stale candidates.
            confirmed = None
            for rejection in pending_rejections:
                rejection["age"] = int(rejection["age"]) + 1
                if float(bar["close"]) < float(rejection["low"]) - buffer:
                    confirmed = rejection
                    break
            pending_rejections = [r for r in pending_rejections if int(r["age"]) <= rejection_timeout_bars]
            if confirmed is not None:
                result.at[index, "entry_layer"] = "confirmed_reversal"
                result.at[index, "resistance_reversal"] = True
                result.at[index, "signal_type"] = "resistance_reversal"
                result.at[index, "zone_type"] = "resistance"
                result.at[index, "zone_id"] = int(confirmed["zone_id"])
                result.at[index, "zone_bottom"] = float(confirmed["bottom"])
                result.at[index, "zone_top"] = float(confirmed["top"])
                result.at[index, "rejection_low"] = float(confirmed["low"])
                result.at[index, "rejection_high"] = float(confirmed["high"])
                pending_rejections = [r for r in pending_rejections if r is not confirmed]

            # A support breakdown is a close-through event, not a touch.
            if previous_close is not None and not supports.empty:
                candidates = supports[
                    (supports["created_time"] < bar["timestamp"])
                    & (supports["top"] >= float(bar["low"]))
                    & (supports["bottom"] <= float(bar["high"]))
                    & (supports["broken_time"].isna() | (bar["timestamp"] <= supports["broken_time"]))
                ]
                if not candidates.empty:
                    selected = candidates.sort_values("top", ascending=False).iloc[0]
                    sid = int(selected["zone_id"])
                    atr_buffer = 0.0 if pd.isna(atr_value) else breakout_buffer_atr * atr_value
                    if (
                        sid not in support_signalled
                        and previous_close >= float(selected["bottom"])
                        and float(bar["close"]) < float(selected["bottom"]) - atr_buffer
                        and bool(bar["bearish_rejection"])
                    ):
                        support_signalled.add(sid)
                        result.at[index, "entry_layer"] = "breakdown"
                        result.at[index, "resistance_reversal"] = True
                        result.at[index, "signal_type"] = "support_breakdown"
                        result.at[index, "zone_type"] = "support"
                        result.at[index, "zone_id"] = sid
                        result.at[index, "zone_bottom"] = float(selected["bottom"])
                        result.at[index, "zone_top"] = float(selected["top"])
                        result.at[index, "breakout_confirmed"] = True
                        result.at[index, "rejection_low"] = float(bar["low"])
                        result.at[index, "rejection_high"] = float(bar["high"])
            previous_close = float(bar["close"])

    return result


def _close_group(
    positions: list[OpenLot],
    tick: object,
    reason: str,
    slippage_points: float,
    point_value_ntd: float,
) -> tuple[list[dict[str, object]], dict[str, object], float]:
    raw_exit = float(tick.price)
    exit_fill = raw_exit + slippage_points
    contract_records: list[dict[str, object]] = []
    for lot in positions:
        lot.lowest_price = min(lot.lowest_price, raw_exit)
        lot.highest_price = max(lot.highest_price, raw_exit)
        gross_points = lot.raw_entry_price - raw_exit
        net_points = lot.entry_fill_price - exit_fill
        contract_records.append(
            {
                "group_id": lot.group_id,
                "slot": lot.slot,
                "signal_time": lot.signal_time,
                "entry_time": lot.entry_time,
                "exit_time": tick.timestamp,
                "entry_session": lot.entry_session,
                "exit_session": tick.session_id,
                "raw_entry_price": lot.raw_entry_price,
                "entry_fill_price": lot.entry_fill_price,
                "raw_exit_price": raw_exit,
                "exit_fill_price": exit_fill,
                "entry_layer": lot.entry_layer,
                "signal_tick_end_id": lot.signal_tick_end_id,
                "signal_open": lot.signal_open,
                "signal_high": lot.signal_high,
                "signal_low": lot.signal_low,
                "signal_close": lot.signal_close,
                "signal_volume": lot.signal_volume,
                "signal_close_position": lot.signal_close_position,
                "resistance_id": lot.resistance_id,
                "resistance_bottom": lot.resistance_bottom,
                "resistance_top": lot.resistance_top,
                "gross_points": gross_points,
                "net_points": net_points,
                "gross_ntd": gross_points * point_value_ntd,
                "net_ntd": net_points * point_value_ntd,
                "mfe_points": lot.entry_fill_price - lot.lowest_price,
                "mae_points": lot.entry_fill_price - lot.highest_price,
                "holding_hours": (tick.timestamp - lot.entry_time).total_seconds() / 3600,
                "exit_reason": reason,
                "cross_session": lot.entry_session != tick.session_id,
                "signal_type": lot.signal_type,
                "zone_type": lot.zone_type,
                "zone_bottom": lot.zone_bottom,
                "zone_top": lot.zone_top,
                "initial_stop": lot.initial_stop,
                "target_price": lot.target_price,
                "risk_points": lot.risk_points,
                "r_multiple": net_points / lot.risk_points if lot.risk_points > 0 else np.nan,
                "scale_in_time": pd.NaT,
            }
        )

    first = min(positions, key=lambda lot: lot.entry_time)
    group_net_ntd = float(sum(record["net_ntd"] for record in contract_records))
    group_record = {
        "group_id": first.group_id,
        "contract_count": len(positions),
        "first_entry_time": min(lot.entry_time for lot in positions),
        "last_entry_time": max(lot.entry_time for lot in positions),
        "exit_time": tick.timestamp,
        "entry_session": first.entry_session,
        "exit_session": tick.session_id,
        "average_raw_entry_price": float(np.mean([lot.raw_entry_price for lot in positions])),
        "average_entry_fill_price": float(np.mean([lot.entry_fill_price for lot in positions])),
        "raw_exit_price": raw_exit,
        "exit_fill_price": exit_fill,
        "resistance_ids": ",".join(str(lot.resistance_id) for lot in positions),
        "gross_contract_points": float(sum(record["gross_points"] for record in contract_records)),
        "net_contract_points": float(sum(record["net_points"] for record in contract_records)),
        "gross_ntd": float(sum(record["gross_ntd"] for record in contract_records)),
        "net_ntd": group_net_ntd,
        "holding_hours": (tick.timestamp - first.entry_time).total_seconds() / 3600,
        "exit_reason": reason,
        "cross_session": first.entry_session != tick.session_id,
    }
    return contract_records, group_record, group_net_ntd


def backtest_two_position_short(
    ticks: pd.DataFrame,
    signal_bars: pd.DataFrame,
    hourly: pd.DataFrame,
    initial_capital_ntd: float = 400_000.0,
    max_positions: int = 2,
    point_value_ntd: float = 10.0,
    slippage_points: float = 2.0,
    chart_sample_minutes: int = 5,
    stop_buffer_atr: float = 0.25,
    trail_atr_multiplier: float = 1.0,
    scale_in_min_r: float = 0.5,
    confirmation_timeout_hours: float = 12.0,
    maximum_holding_hours: float = 24.0,
    show_progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Run tick fills, two-lot scaling, a shared Supertrend exit, and account MTM."""
    if initial_capital_ntd <= 0 or max_positions < 1 or point_value_ntd <= 0:
        raise ValueError("capital, max positions, and point value must be positive")
    if slippage_points < 0 or chart_sample_minutes < 1:
        raise ValueError("slippage must be non-negative and chart sampling must be positive")

    ordered_ticks = ticks.sort_values("tick_id", kind="stable").reset_index(drop=True)
    completed_bars = {int(row.tick_end_id): row for row in signal_bars.itertuples(index=False)}
    hourly_columns = ["timestamp", "supertrend_direction"]
    if "atr" in hourly.columns:
        hourly_columns.append("atr")
    hourly_rows = list(
        hourly[hourly_columns]
        .sort_values("timestamp", kind="stable")
        .itertuples(index=False)
    )
    hourly_index = -1
    current_direction: int | None = None
    current_atr = np.nan
    group_last_direction: int | None = None
    group_seen_bearish = False
    next_group_id = 0
    positions: list[OpenLot] = []
    pending_entry: object | None = None
    pending_scale_in: object | None = None
    contract_records: list[dict[str, object]] = []
    group_records: list[dict[str, object]] = []
    equity_samples: list[dict[str, object]] = []
    realized_ntd = 0.0
    peak_equity = initial_capital_ntd
    minimum_equity = initial_capital_ntd
    maximum_drawdown = 0.0
    maximum_drawdown_percent = 0.0
    peak_positions = 0
    signals = filled_entries = ignored_at_capacity = canceled_session = 0
    previous_time: pd.Timestamp | None = None
    previous_exposure = 0
    exposure_seconds = {count: 0.0 for count in range(max_positions + 1)}
    sample_delta = pd.Timedelta(minutes=chart_sample_minutes)
    next_sample_time: pd.Timestamp | None = None
    last_tick: object | None = None

    total_ticks = len(ordered_ticks)
    progress_started = time.monotonic()
    progress_step = max(1, total_ticks // (100 if sys.stderr.isatty() else 20))

    for tick_number, tick in enumerate(ordered_ticks.itertuples(index=False), start=1):
        report_interval = tick_number % progress_step == 0 and tick_number / total_ticks < 0.995
        if show_progress and (tick_number == 1 or report_interval or tick_number == total_ticks):
            elapsed = time.monotonic() - progress_started
            percent = tick_number / total_ticks * 100 if total_ticks else 100.0
            if tick_number == 1:
                message = f"Backtest ticks: {percent:5.1f}% ({tick_number:,}/{total_ticks:,})"
            else:
                eta = elapsed * (total_ticks - tick_number) / tick_number
                message = (
                    f"Backtest ticks: {percent:5.1f}% ({tick_number:,}/{total_ticks:,}) "
                    f"elapsed {elapsed:,.0f}s, ETA {eta:,.0f}s"
                )
            print(message, file=sys.stderr, flush=True)
        last_tick = tick
        if previous_time is not None:
            elapsed = max(0.0, (tick.timestamp - previous_time).total_seconds())
            exposure_seconds[previous_exposure] += elapsed
        previous_time = tick.timestamp

        bullish_flip = False
        while hourly_index + 1 < len(hourly_rows) and hourly_rows[hourly_index + 1].timestamp < tick.timestamp:
            hourly_index += 1
            hourly_row = hourly_rows[hourly_index]
            direction_value = hourly_row.supertrend_direction
            new_direction = None if pd.isna(direction_value) else int(direction_value)
            atr_value = getattr(hourly_row, "atr", np.nan)
            current_atr = np.nan if pd.isna(atr_value) else float(atr_value)
            if positions and new_direction is not None:
                if new_direction == -1:
                    group_seen_bearish = True
                if group_seen_bearish and group_last_direction == -1 and new_direction == 1:
                    bullish_flip = True
                group_last_direction = new_direction
            current_direction = new_direction

        exited_this_tick = False
        if positions and bullish_flip:
            records, group_record, group_net = _close_group(
                positions, tick, "adaptive_hourly_supertrend_bullish_flip", slippage_points, point_value_ntd
            )
            contract_records.extend(records)
            group_records.append(group_record)
            realized_ntd += group_net
            positions = []
            pending_entry = None
            pending_scale_in = None
            group_last_direction = None
            group_seen_bearish = False
            exited_this_tick = True

        if not exited_this_tick and pending_entry is not None:
            signal = pending_entry
            pending_entry = None
            if tick.session_id == signal.session_id and len(positions) < max_positions and current_direction == -1:
                if not positions:
                    next_group_id += 1
                    group_last_direction = current_direction
                    group_seen_bearish = current_direction == -1
                raw_entry = float(tick.price)
                atr = 0.0 if pd.isna(current_atr) else current_atr
                signal_type = str(getattr(signal, "signal_type", "resistance_reversal"))
                zone_type = str(getattr(signal, "zone_type", "resistance"))
                zone_bottom = float(getattr(signal, "zone_bottom", getattr(signal, "resistance_bottom", np.nan)))
                zone_top = float(getattr(signal, "zone_top", getattr(signal, "resistance_top", np.nan)))
                signal_high = float(signal.high)
                if signal_type == "support_breakdown":
                    initial_stop = max(signal_high, zone_bottom) + stop_buffer_atr * atr
                else:
                    initial_stop = max(signal_high, zone_top) + stop_buffer_atr * atr
                risk_points = max(0.0, initial_stop - raw_entry)
                target_price = np.nan
                if risk_points > 0:
                    target_price = raw_entry - risk_points
                positions.append(
                    OpenLot(
                        group_id=next_group_id,
                        slot=len(positions) + 1,
                        signal_time=signal.timestamp,
                        entry_time=tick.timestamp,
                        entry_session=tick.session_id,
                        raw_entry_price=raw_entry,
                        entry_fill_price=raw_entry - slippage_points,
                        entry_layer=str(getattr(signal, "entry_layer", "legacy")),
                        signal_tick_end_id=int(signal.tick_end_id),
                        signal_open=float(signal.open),
                        signal_high=float(signal.high),
                        signal_low=float(signal.low),
                        signal_close=float(signal.close),
                        signal_volume=float(signal.volume),
                        signal_close_position=float(signal.close_position),
                        resistance_id=int(getattr(signal, "zone_id", getattr(signal, "resistance_id", -1))),
                        resistance_bottom=zone_bottom,
                        resistance_top=zone_top,
                        lowest_price=raw_entry,
                        highest_price=raw_entry,
                        signal_type=signal_type,
                        zone_type=zone_type,
                        zone_bottom=zone_bottom,
                        zone_top=zone_top,
                        initial_stop=initial_stop,
                        target_price=target_price,
                        risk_points=risk_points,
                )
                )
                filled_entries += 1
                peak_positions = max(peak_positions, len(positions))
            else:
                canceled_session += 1

        # Scale in only after the first lot has achieved the configured R and
        # a fresh signal confirms a failed retest of the same zone.
        if not exited_this_tick and pending_scale_in is not None and len(positions) == 1:
            signal = pending_scale_in
            pending_scale_in = None
            first = positions[0]
            favorable_r = (first.entry_fill_price - float(tick.price)) / first.risk_points if first.risk_points > 0 else 0.0
            if tick.session_id == signal.session_id and favorable_r >= scale_in_min_r:
                raw_entry = float(tick.price)
                positions.append(OpenLot(
                    group_id=first.group_id, slot=2, signal_time=signal.timestamp,
                    entry_time=tick.timestamp, entry_session=tick.session_id,
                    raw_entry_price=raw_entry, entry_fill_price=raw_entry - slippage_points,
                    entry_layer=str(getattr(signal, "entry_layer", "scale_in")),
                    signal_tick_end_id=int(signal.tick_end_id), signal_open=float(signal.open),
                    signal_high=float(signal.high), signal_low=float(signal.low), signal_close=float(signal.close),
                    signal_volume=float(signal.volume), signal_close_position=float(signal.close_position),
                    resistance_id=int(getattr(signal, "zone_id", getattr(signal, "resistance_id", -1))),
                    resistance_bottom=float(getattr(signal, "zone_bottom", getattr(signal, "resistance_bottom", np.nan))),
                    resistance_top=float(getattr(signal, "zone_top", getattr(signal, "resistance_top", np.nan))),
                    lowest_price=raw_entry, highest_price=raw_entry,
                    signal_type=str(getattr(signal, "signal_type", first.signal_type)), zone_type=first.zone_type,
                    zone_bottom=first.zone_bottom, zone_top=first.zone_top,
                    initial_stop=first.initial_stop, target_price=first.target_price,
                    risk_points=first.risk_points,
                ))
                filled_entries += 1

        price = float(tick.price)
        for lot in positions:
            lot.lowest_price = min(lot.lowest_price, price)
            lot.highest_price = max(lot.highest_price, price)

        if positions:
            first = positions[0]
            if not pd.isna(current_atr):
                for lot in positions:
                    if lot.risk_points > 0 and lot.lowest_price <= lot.entry_fill_price - scale_in_min_r * lot.risk_points:
                        trail = lot.lowest_price + trail_atr_multiplier * current_atr
                        lot.initial_stop = min(lot.initial_stop, trail)
            stop_hit = any(price >= lot.initial_stop for lot in positions if not pd.isna(lot.initial_stop))
            target_hit = len(positions) >= 1 and not pd.isna(first.target_price) and price <= first.target_price
            timeout = tick.timestamp - first.entry_time >= pd.Timedelta(hours=maximum_holding_hours)
            no_confirmation = (
                tick.timestamp - first.entry_time >= pd.Timedelta(hours=confirmation_timeout_hours)
                and first.lowest_price > first.entry_fill_price - scale_in_min_r * first.risk_points
            )
            if stop_hit:
                records, group_record, group_net = _close_group(positions, tick, "initial_structure_stop", slippage_points, point_value_ntd)
                contract_records.extend(records); group_records.append(group_record); realized_ntd += group_net
                positions = []; pending_entry = None; pending_scale_in = None; exited_this_tick = True
            elif target_hit and len(positions) == 1:
                records, group_record, group_net = _close_group(positions, tick, "one_r_target", slippage_points, point_value_ntd)
                contract_records.extend(records); group_records.append(group_record); realized_ntd += group_net
                positions = []; pending_entry = None; pending_scale_in = None; exited_this_tick = True
            elif timeout:
                records, group_record, group_net = _close_group(positions, tick, "maximum_holding_time", slippage_points, point_value_ntd)
                contract_records.extend(records); group_records.append(group_record); realized_ntd += group_net
                positions = []; pending_entry = None; pending_scale_in = None; exited_this_tick = True
            elif no_confirmation:
                records, group_record, group_net = _close_group(positions, tick, "confirmation_timeout", slippage_points, point_value_ntd)
                contract_records.extend(records); group_records.append(group_record); realized_ntd += group_net
                positions = []; pending_entry = None; pending_scale_in = None; exited_this_tick = True

        completed_bar = completed_bars.get(int(tick.tick_id))
        if completed_bar is not None and bool(completed_bar.resistance_reversal):
            signals += 1
            if exited_this_tick:
                pass
            elif len(positions) >= max_positions:
                ignored_at_capacity += 1
            elif pending_entry is None:
                same_zone = (
                    len(positions) == 1
                    and not pd.isna(getattr(completed_bar, "zone_id", np.nan))
                    and int(completed_bar.zone_id) == positions[0].resistance_id
                )
                if same_zone:
                    pending_scale_in = completed_bar
                elif not positions:
                    pending_entry = completed_bar
                else:
                    ignored_at_capacity += 1

        unrealized_ntd = sum((lot.entry_fill_price - price) * point_value_ntd for lot in positions)
        equity = initial_capital_ntd + realized_ntd + unrealized_ntd
        peak_equity = max(peak_equity, equity)
        minimum_equity = min(minimum_equity, equity)
        maximum_drawdown = min(maximum_drawdown, equity - peak_equity)
        maximum_drawdown_percent = max(
            maximum_drawdown_percent, (peak_equity - equity) / peak_equity * 100 if peak_equity else 0.0
        )

        force_sample = exited_this_tick or completed_bar is not None and bool(completed_bar.resistance_reversal)
        if next_sample_time is None or tick.timestamp >= next_sample_time or force_sample:
            equity_samples.append(
                {
                    "timestamp": tick.timestamp,
                    "price": price,
                    "equity_ntd": equity,
                    "realized_ntd": realized_ntd,
                    "unrealized_ntd": unrealized_ntd,
                    "open_positions": len(positions),
                    "drawdown_ntd": equity - peak_equity,
                }
            )
            next_sample_time = tick.timestamp.floor(f"{chart_sample_minutes}min") + sample_delta
        previous_exposure = len(positions)

    if positions and last_tick is not None:
        records, group_record, group_net = _close_group(
            positions, last_tick, "data_end", slippage_points, point_value_ntd
        )
        contract_records.extend(records)
        group_records.append(group_record)
        realized_ntd += group_net
        positions = []
        final_equity = initial_capital_ntd + realized_ntd
        peak_equity = max(peak_equity, final_equity)
        minimum_equity = min(minimum_equity, final_equity)
        maximum_drawdown = min(maximum_drawdown, final_equity - peak_equity)
        maximum_drawdown_percent = max(
            maximum_drawdown_percent,
            (peak_equity - final_equity) / peak_equity * 100 if peak_equity else 0.0,
        )
        equity_samples.append(
            {
                "timestamp": last_tick.timestamp,
                "price": float(last_tick.price),
                "equity_ntd": final_equity,
                "realized_ntd": realized_ntd,
                "unrealized_ntd": 0.0,
                "open_positions": 0,
                "drawdown_ntd": final_equity - peak_equity,
            }
        )

    contracts = pd.DataFrame(contract_records)
    if contracts.empty:
        contracts = pd.DataFrame(columns=CONTRACT_COLUMNS)
    else:
        contracts.insert(0, "trade_number", range(1, len(contracts) + 1))
        contracts["cumulative_net_ntd"] = contracts["net_ntd"].cumsum()
        contracts = contracts.reindex(columns=CONTRACT_COLUMNS)
    groups = pd.DataFrame(group_records)
    if groups.empty:
        groups = pd.DataFrame(columns=GROUP_COLUMNS)
    else:
        groups["cumulative_net_ntd"] = groups["net_ntd"].cumsum()
        groups = groups.reindex(columns=GROUP_COLUMNS)
    samples = pd.DataFrame(equity_samples).drop_duplicates(subset=["timestamp"], keep="last")

    final_equity = initial_capital_ntd + realized_ntd
    elapsed_seconds = sum(exposure_seconds.values())
    summary: dict[str, object] = {
        "signals": signals,
        "filled_entries": filled_entries,
        "ignored_at_capacity": ignored_at_capacity,
        "canceled_session": canceled_session,
        "contract_trades": len(contracts),
        "groups": len(groups),
        "winning_contracts": int((contracts["net_ntd"] > 0).sum()) if not contracts.empty else 0,
        "losing_contracts": int((contracts["net_ntd"] < 0).sum()) if not contracts.empty else 0,
        "winning_groups": int((groups["net_ntd"] > 0).sum()) if not groups.empty else 0,
        "losing_groups": int((groups["net_ntd"] < 0).sum()) if not groups.empty else 0,
        "gross_ntd": float(contracts["gross_ntd"].sum()) if not contracts.empty else 0.0,
        "net_ntd": realized_ntd,
        "contract_win_rate_percent": (
            float((contracts["net_ntd"] > 0).mean() * 100) if not contracts.empty else 0.0
        ),
        "group_win_rate_percent": float((groups["net_ntd"] > 0).mean() * 100) if not groups.empty else 0.0,
        "group_profit_factor": (
            float(groups.loc[groups["net_ntd"] > 0, "net_ntd"].sum())
            / abs(float(groups.loc[groups["net_ntd"] < 0, "net_ntd"].sum()))
            if not groups.empty and float(groups.loc[groups["net_ntd"] < 0, "net_ntd"].sum()) < 0
            else float("inf") if not groups.empty and bool((groups["net_ntd"] > 0).any()) else 0.0
        ),
        "initial_equity_ntd": initial_capital_ntd,
        "final_equity_ntd": final_equity,
        "return_percent": (final_equity / initial_capital_ntd - 1) * 100,
        "minimum_equity_ntd": minimum_equity,
        "maximum_drawdown_ntd": -maximum_drawdown,
        "maximum_drawdown_percent": maximum_drawdown_percent,
        "peak_positions": peak_positions,
        "exposure_hours": {count: seconds / 3600 for count, seconds in exposure_seconds.items()},
        "exposure_percent": {
            count: (seconds / elapsed_seconds * 100 if elapsed_seconds else 0.0)
            for count, seconds in exposure_seconds.items()
        },
    }
    return contracts, groups, samples, summary


def write_report(
    path: Path,
    args: argparse.Namespace,
    sources: list[Path],
    ticks: pd.DataFrame,
    hourly: pd.DataFrame,
    signal_bars: pd.DataFrame,
    contracts: pd.DataFrame,
    groups: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    group_rows = "| - | - | - | - | - | - | No trade |"
    if not groups.empty:
        group_rows = "\n".join(
            f"| {row.group_id} | {row.contract_count} | {row.first_entry_time:%Y-%m-%d %H:%M:%S} | "
            f"{row.exit_time:%Y-%m-%d %H:%M:%S} | {row.average_entry_fill_price:.1f} | "
            f"{row.net_ntd:,.0f} | {row.exit_reason} |"
            for row in groups.itertuples(index=False)
        )
    exposure_hours = summary["exposure_hours"]
    exposure_percent = summary["exposure_percent"]
    profit_factor = summary["group_profit_factor"]
    profit_factor_text = "∞" if np.isinf(profit_factor) else f"{profit_factor:.2f}"
    text = f"""# {args.product} {args.contract_month}：Tick 兩口空單＋Legacy Supertrend 出場回測

## 資料與設定

- 日期：`{args.start_date}` 至 `{args.end_date}`；來源檔 {len(sources)} 個、有效 tick {len(ticks):,} 筆、60 分 K {len(hourly):,} 根。
- 起始權益：NT${args.initial_capital_ntd:,.0f}；TMF 每點 NT${args.point_value_ntd:g}；最多同時 {args.max_positions} 口。
- 進出場每邊使用 {args.slippage_points:g} 點不利滑價；未計手續費與期交稅；不模擬追繳或強制平倉。
- 2,000 口量 K 每個日／夜盤重新累積，時段尾端不足量直接丟棄。

## 交易規則

- 60 分鐘 K 建立支撐／壓力箱；2,000 口量 K 判定訊號，訊號完成後同交易時段下一筆 tick 放空。
- 壓力反轉需先形成收黑 rejection K，再由後續量 K 跌破 rejection 低點；支撐跌破需收盤有效跌破箱底。
- 只在 60 分鐘 Supertrend 為空頭時進場；首口確認後，同箱體回測失敗且至少達 {args.scale_in_min_r:.1f}R 才允許第二口。
- 使用箱體失效位置加 {args.stop_buffer_atr:g} ATR 初始停損，並在達到確認獲利後使用 {args.trail_atr_multiplier:g} ATR 移動停損。
- 首口以 1R 目標出場；另設 {args.confirmation_timeout_hours:g} 小時確認逾時與 {args.maximum_holding_hours:g} 小時最大持倉時間。
- 60 分狀態只在其完成時間嚴格早於當前 tick 時使用，保留同秒成交的原始列順序。

## 帳戶結果

| Metric | Value |
| --- | ---: |
| Valid signals / filled entries | {summary['signals']} / {summary['filled_entries']} |
| Ignored at two-contract capacity | {summary['ignored_at_capacity']} |
| Contract trades / position groups | {summary['contract_trades']} / {summary['groups']} |
| Winning / losing contracts | {summary['winning_contracts']} / {summary['losing_contracts']} |
| Winning / losing groups | {summary['winning_groups']} / {summary['losing_groups']} |
| Contract / group win rate | {summary['contract_win_rate_percent']:.1f}% / {summary['group_win_rate_percent']:.1f}% |
| Group profit factor | {profit_factor_text} |
| Gross P&L | NT${summary['gross_ntd']:,.0f} |
| Net P&L after slippage | NT${summary['net_ntd']:,.0f} |
| Final equity | NT${summary['final_equity_ntd']:,.0f} |
| Return | {summary['return_percent']:.2f}% |
| Minimum tick-level equity | NT${summary['minimum_equity_ntd']:,.0f} |
| Maximum tick-level drawdown | NT${summary['maximum_drawdown_ntd']:,.0f} ({summary['maximum_drawdown_percent']:.2f}%) |
| Peak open contracts | {summary['peak_positions']} |
| Flat exposure | {exposure_hours.get(0, 0):.1f} h ({exposure_percent.get(0, 0):.1f}%) |
| One-contract exposure | {exposure_hours.get(1, 0):.1f} h ({exposure_percent.get(1, 0):.1f}%) |
| Two-contract exposure | {exposure_hours.get(2, 0):.1f} h ({exposure_percent.get(2, 0):.1f}%) |

## Group Ledger

| Group | Lots | First entry | Exit | Average fill | Net NTD | Exit reason |
|---:|---:|---|---|---:|---:|---|
{group_rows}

## 風險說明

NT$400,000 僅作為權益基準；回測不會因權益或保證金不足自動平倉。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_chart(
    path: Path,
    zones: pd.DataFrame,
    contracts: pd.DataFrame,
    samples: pd.DataFrame,
    initial_capital_ntd: float,
) -> None:
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.62, 0.16, 0.22],
        subplot_titles=("Sampled tick price and entries", "Open TMF contracts", "Marked-to-market account equity"),
    )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["price"], mode="lines", name="Tick price (sampled)"), row=1, col=1
    )
    chart_end = samples["timestamp"].iloc[-1]
    if not zones.empty:
        for zone in zones[zones["zone_type"] == "resistance"].itertuples(index=False):
            end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
            figure.add_shape(
                type="rect", x0=zone.created_time, x1=end, y0=zone.bottom, y1=zone.top,
                fillcolor="rgba(211,47,47,0.12)", line={"color": "rgba(211,47,47,0.55)", "width": 1}, row=1, col=1,
            )
    if not contracts.empty:
        common_exits = contracts.drop_duplicates(subset=["group_id"], keep="last")
        figure.add_trace(
            go.Scatter(
                x=contracts["entry_time"], y=contracts["entry_fill_price"], mode="markers", name="Short entry",
                marker={"symbol": "triangle-down", "size": 12, "color": "#6a1b9a"},
                text=[f"Group {g}, slot {s}" for g, s in zip(contracts["group_id"], contracts["slot"])],
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=common_exits["exit_time"], y=common_exits["exit_fill_price"], mode="markers", name="Shared exit",
                marker={"symbol": "x", "size": 10, "color": "#00897b"}, text=common_exits["exit_reason"],
            ), row=1, col=1,
        )
    figure.add_trace(
        go.Scatter(
            x=samples["timestamp"], y=samples["open_positions"], mode="lines", line_shape="hv", name="Open contracts"
        ), row=2, col=1,
    )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["equity_ntd"], mode="lines", name="Account equity"), row=3, col=1
    )
    figure.add_hline(y=initial_capital_ntd, line_dash="dot", line_color="gray", row=3, col=1)
    figure.update_layout(title="TMF Tick-Level Two-Position Short Backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Contracts", dtick=1, row=2, col=1)
    figure.update_yaxes(title_text="NTD", tickformat=",.0f", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest two TMF tick entries with a shared legacy Supertrend exit.")
    parser.add_argument("--input-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START)
    parser.add_argument("--end-date", type=parse_date, default=DEFAULT_END)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--initial-capital-ntd", type=float, default=400_000)
    parser.add_argument("--max-positions", type=int, default=2)
    parser.add_argument("--point-value-ntd", type=float, default=10)
    parser.add_argument("--slippage-points", type=float, default=2)
    parser.add_argument("--volume-bar-size", type=float, default=2000)
    parser.add_argument("--tick-lookback", type=int, default=5)
    parser.add_argument("--close-position-max", type=float, default=0.35)
    parser.add_argument("--breakout-buffer-atr", type=float, default=0.10)
    parser.add_argument("--stop-buffer-atr", type=float, default=0.25)
    parser.add_argument("--rejection-timeout-bars", type=int, default=3)
    parser.add_argument("--scale-in-min-r", type=float, default=0.5)
    parser.add_argument("--trail-atr-multiplier", type=float, default=1.0)
    parser.add_argument("--confirmation-timeout-hours", type=float, default=12.0)
    parser.add_argument("--maximum-holding-hours", type=float, default=24.0)
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--zone-atr-length", type=int, default=20)
    parser.add_argument("--zone-box-width", type=float, default=1.0)
    parser.add_argument("--atr-length", type=int, default=10)
    parser.add_argument("--base-multiplier", type=float, default=3.0)
    parser.add_argument("--min-multiplier", type=float, default=0.8)
    parser.add_argument("--speed-lookback", type=int, default=2)
    parser.add_argument("--low-speed", type=float, default=0.25)
    parser.add_argument("--high-speed", type=float, default=0.8)
    parser.add_argument("--smoothing-span", type=int, default=2)
    parser.add_argument("--chart-sample-minutes", type=int, default=5)
    parser.add_argument("--contract-trades-output", type=Path, default=DEFAULT_CONTRACT_TRADES)
    parser.add_argument("--group-trades-output", type=Path, default=DEFAULT_GROUP_TRADES)
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument(
        "--no-progress", action="store_true",
        help="Hide stage messages and tick-loop percentage/ETA output.",
    )
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    positive = (
        args.initial_capital_ntd, args.max_positions, args.point_value_ntd, args.volume_bar_size,
        args.tick_lookback, args.pivot_lookback, args.volume_filter_length, args.zone_atr_length,
        args.atr_length, args.speed_lookback, args.smoothing_span, args.chart_sample_minutes,
    )
    if min(positive) <= 0:
        parser.error("capital, position count, bar sizes, and lookbacks must be positive")
    if args.slippage_points < 0 or args.zone_box_width < 0:
        parser.error("slippage and zone width must be non-negative")
    if min(args.breakout_buffer_atr, args.stop_buffer_atr, args.scale_in_min_r,
           args.trail_atr_multiplier, args.confirmation_timeout_hours,
           args.maximum_holding_hours) <= 0 or args.rejection_timeout_bars < 1:
        parser.error("risk buffers, timeouts, and scale-in thresholds must be positive")
    if not 0 < args.close_position_max <= 1:
        parser.error("--close-position-max must be in (0, 1]")
    if not 0 < args.min_multiplier <= args.base_multiplier:
        parser.error("--min-multiplier must be positive and no greater than --base-multiplier")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must be greater than --low-speed")
    return args


def main() -> None:
    args = parse_args()
    show_progress = not args.no_progress

    def stage(number: int, message: str) -> None:
        if show_progress:
            print(f"[{number}/8] {message}", file=sys.stderr, flush=True)

    stage(1, "Finding daily source files...")
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    stage(2, f"Loading and filtering {len(sources)} daily files...")
    ticks = prepare_ticks(add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip())))
    stage(3, f"Building hourly bars from {len(ticks):,} ticks...")
    hourly = build_hourly_bars(ticks)
    hourly = add_adaptive_supertrend(
        hourly, args.atr_length, args.base_multiplier, args.min_multiplier, args.speed_lookback,
        args.low_speed, args.high_speed, args.smoothing_span,
    )
    zones = pine_style_zones(
        hourly, args.pivot_lookback, args.volume_filter_length, args.zone_atr_length, args.zone_box_width
    )
    stage(4, "Building session volume bars...")
    signal_bars = build_session_volume_bars(ticks, args.volume_bar_size)
    stage(5, f"Detecting signals in {len(signal_bars):,} volume bars...")
    signal_bars = add_optimized_layer_signals(
        signal_bars, hourly, zones, args.close_position_max,
        args.breakout_buffer_atr, args.rejection_timeout_bars,
    )
    stage(6, f"Running tick backtest across {len(ticks):,} ticks...")
    contracts, groups, samples, summary = backtest_two_position_short(
        ticks, signal_bars, hourly, args.initial_capital_ntd, args.max_positions, args.point_value_ntd,
        args.slippage_points, args.chart_sample_minutes,
        args.stop_buffer_atr, args.trail_atr_multiplier, args.scale_in_min_r,
        args.confirmation_timeout_hours, args.maximum_holding_hours,
        show_progress=show_progress,
    )
    stage(7, "Writing trade files and report...")
    for output in (args.contract_trades_output, args.group_trades_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    contracts.to_csv(args.contract_trades_output, index=False, encoding="utf-8-sig")
    groups.to_csv(args.group_trades_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, args, sources, ticks, hourly, signal_bars, contracts, groups, summary)
    stage(8, "Writing interactive chart...")
    write_chart(args.chart_output, zones, contracts, samples, args.initial_capital_ntd)
    print(
        f"ticks={len(ticks)} hourly_bars={len(hourly)} volume_bars={len(signal_bars)} "
        f"signals={summary['signals']} filled_entries={summary['filled_entries']}"
    )
    print(
        f"contracts={summary['contract_trades']} groups={summary['groups']} "
        f"net_ntd={summary['net_ntd']:.0f} final_equity_ntd={summary['final_equity_ntd']:.0f}"
    )
    print(f"report={args.report_output}")
    print(f"chart={args.chart_output}")


if __name__ == "__main__":
    main()
