#!/usr/bin/env python
"""Backtest the TMF hourly-resistance / 3-minute UT Bot short strategy."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_diamond_short import add_pine_diamond_signals, pine_atr
    from .backtest_tmf_hourly_support_long import build_hourly_bars
    from .backtest_tmf_0923_hourly_resistance_1m_short import (
        add_adjust_supertrend,
        adjusted_resistance_top,
    )
except ImportError:
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_diamond_short import add_pine_diamond_signals, pine_atr
    from backtest_tmf_hourly_support_long import build_hourly_bars
    from backtest_tmf_0923_hourly_resistance_1m_short import (
        add_adjust_supertrend,
        adjusted_resistance_top,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "txf"
DEFAULT_OUTPUT_DIR = ROOT / "txf_tick"
DEFAULT_DOC_DIR = ROOT / "doc"
DEFAULT_START = date(2026, 8, 5)
DEFAULT_END = date(2026, 9, 29)
DEFAULT_PERIOD = "2026-08-05_to_2026-09-29"
BAR_MINUTES = 3


@dataclass
class Position:
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    entry_type: str
    zone_id: int
    zone_version: int
    resistance_bottom: float
    resistance_top: float
    raw_entry_price: float
    entry_price: float
    initial_stop: float
    initial_risk: float
    atr_at_entry: float
    supertrend_confirmed: bool
    last_supertrend_direction: int | None
    lowest_price: float
    highest_price: float
    reached_one_r: bool = False
    one_r_time: pd.Timestamp | None = None
    trailing_stop: float | None = None
    profit_locked: bool = False
    breakeven_stop: float | None = None


TRADE_COLUMNS = [
    "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
    "entry_type", "zone_id", "zone_version", "resistance_bottom", "resistance_top",
    "raw_entry_price", "entry_price", "exit_price", "initial_stop", "initial_risk", "atr_at_entry",
    "one_r_time", "trailing_stop_at_exit", "gross_points", "slippage_points", "net_points",
    "gross_r", "net_r", "mfe_points", "mae_points", "exit_reason", "cross_session",
    "cumulative_gross_points", "cumulative_net_points", "gross_drawdown_points", "net_drawdown_points",
]


def build_three_minute_bars(ticks: pd.DataFrame, bar_minutes: int = BAR_MINUTES) -> pd.DataFrame:
    """Build 3-minute OHLCV bars aligned to each session's starting timestamp.

    Bars anchor to the first tick of each session (day session 08:45, night session
    15:00). Idle 3-minute slots are dropped, matching the 1-minute variant which
    also does not fill inactive minutes.
    """
    if bar_minutes < 1:
        raise ValueError("bar_minutes must be positive")
    frame = ticks.copy().sort_values("timestamp", kind="stable")
    session_anchor = frame.groupby("session_id", sort=False)["timestamp"].transform("min")
    elapsed_seconds = (frame["timestamp"] - session_anchor).dt.total_seconds()
    bucket_index = (elapsed_seconds // (bar_minutes * 60)).astype("int64")
    frame["bar_start"] = session_anchor + pd.to_timedelta(bucket_index * bar_minutes * 60, unit="s")
    grouped = frame.groupby(["session_id", "bar_start"], sort=True, observed=True)
    result = grouped.agg(
        timestamp=("timestamp", "last"),
        open=("price", "first"),
        high=("price", "max"),
        low=("price", "min"),
        close=("price", "last"),
        volume=("quantity", "sum"),
    ).reset_index()
    result = result.rename(columns={"bar_start": "minute_start"})  # reuse column name for downstream code
    return result.sort_values("timestamp", kind="stable").reset_index(drop=True)


def add_ut_bot_state(
    bars: pd.DataFrame,
    sensitivity: float = 2.0,
    atr_period: int = 10,
) -> pd.DataFrame:
    """Iteratively compute the UT Bot ATR trailing stop and SELL/BUY signals.

    Matches Pine v4 `UT Bot Alerts` (Yo_adriiiiaan / QuantNomad) with
    src = close and heikin-ashi disabled.
    """
    if sensitivity <= 0:
        raise ValueError("sensitivity must be positive")
    if atr_period < 1:
        raise ValueError("atr_period must be positive")

    result = bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    atr = pine_atr(result, atr_period)
    n_loss = sensitivity * atr

    stops = np.full(len(result), np.nan)
    directions = np.full(len(result), np.nan)  # +1 long, -1 short
    sells = np.zeros(len(result), dtype=bool)
    buys = np.zeros(len(result), dtype=bool)

    for index in range(len(result)):
        if pd.isna(n_loss.iloc[index]):
            continue
        src = float(result.at[index, "close"])
        if index == 0 or pd.isna(stops[index - 1]):
            # Initialise below price; matches Pine's first non-na behaviour.
            stops[index] = src - float(n_loss.iloc[index])
            directions[index] = 1
            continue
        prev_stop = stops[index - 1]
        prev_src = float(result.at[index - 1, "close"])
        loss = float(n_loss.iloc[index])
        if src > prev_stop and prev_src > prev_stop:
            new_stop = max(prev_stop, src - loss)
        elif src < prev_stop and prev_src < prev_stop:
            new_stop = min(prev_stop, src + loss)
        elif src > prev_stop:
            new_stop = src - loss
        else:
            new_stop = src + loss
        stops[index] = new_stop
        if prev_src < prev_stop and src > prev_stop:
            directions[index] = 1
            buys[index] = True
        elif prev_src > prev_stop and src < prev_stop:
            directions[index] = -1
            sells[index] = True
        else:
            directions[index] = directions[index - 1] if not pd.isna(directions[index - 1]) else np.nan

    result["ut_atr"] = atr
    result["ut_trailing_stop"] = stops
    result["ut_direction"] = directions
    result["ut_sell_signal"] = sells
    result["ut_buy_signal"] = buys
    return result


def add_hourly_strategy_features(
    hourly: pd.DataFrame,
    pivot_lookback: int,
    volume_filter_length: int,
    box_atr_length: int,
    box_width: float,
    risk_atr_length: int,
    adjust_atr_length: int,
    speed_lookback: int,
    speed_smoothing: int,
    base_multiplier: float,
    minimum_multiplier: float,
    low_speed: float,
    high_speed: float,
) -> pd.DataFrame:
    result = add_pine_diamond_signals(
        hourly,
        lookback=pivot_lookback,
        volume_length=volume_filter_length,
        atr_length=box_atr_length,
        box_width=box_width,
    )
    result["risk_atr"] = pine_atr(result, risk_atr_length)
    return add_adjust_supertrend(
        result,
        atr_length=adjust_atr_length,
        speed_lookback=speed_lookback,
        speed_smoothing=speed_smoothing,
        base_multiplier=base_multiplier,
        minimum_multiplier=minimum_multiplier,
        low_speed=low_speed,
        high_speed=high_speed,
    )


def attach_hourly_features(bars: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    columns = [
        "timestamp", "resistance_id", "resistance_bottom", "resistance_top", "risk_atr",
        "adjust_atr", "raw_price_speed", "price_speed", "speed_score",
        "adjust_multiplier", "adjusted_atr_distance", "adjust_supertrend", "adjust_supertrend_direction",
    ]
    right = hourly[columns].rename(columns={"timestamp": "hourly_confirmation_time"})
    return pd.merge_asof(
        bars.sort_values("timestamp", kind="stable"),
        right.sort_values("hourly_confirmation_time", kind="stable"),
        left_on="timestamp",
        right_on="hourly_confirmation_time",
        direction="backward",
        allow_exact_matches=False,
    )


def _trade_record(
    position: Position,
    bar: pd.Series,
    exit_time: pd.Timestamp,
    raw_exit_price: float,
    exit_reason: str,
    slippage_per_side: float,
) -> dict[str, object]:
    exit_price = raw_exit_price + slippage_per_side
    gross = position.raw_entry_price - raw_exit_price
    net = position.entry_price - exit_price
    return {
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": exit_time,
        "entry_session": position.entry_session,
        "exit_session": str(bar["session_id"]),
        "entry_type": position.entry_type,
        "zone_id": position.zone_id,
        "zone_version": position.zone_version,
        "resistance_bottom": position.resistance_bottom,
        "resistance_top": position.resistance_top,
        "raw_entry_price": position.raw_entry_price,
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "initial_stop": position.initial_stop,
        "initial_risk": position.initial_risk,
        "atr_at_entry": position.atr_at_entry,
        "one_r_time": position.one_r_time,
        "trailing_stop_at_exit": position.trailing_stop,
        "gross_points": gross,
        "slippage_points": 2 * slippage_per_side,
        "net_points": net,
        "gross_r": gross / position.initial_risk,
        "net_r": net / position.initial_risk,
        "mfe_points": position.entry_price - position.lowest_price,
        "mae_points": position.entry_price - position.highest_price,
        "exit_reason": exit_reason,
        "cross_session": position.entry_session != str(bar["session_id"]),
    }


def backtest_strategy(
    bar_frame: pd.DataFrame,
    initial_stop_atr: float = 0.5,
    trailing_atr: float = 3.0,
    top_adjust_ratio: float = 0.5,
    reentry_timeout_minutes: int = 15,
    breakout_invalidate_atr: float = 1.5,
    max_uptrend_slope: float = 0.5,
    approach_atr: float = 0.25,
    max_entry_below_atr: float = 1.5,
    stop_swing_lookback: int = 20,
    slippage_per_side: float = 2.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if min(initial_stop_atr, trailing_atr, breakout_invalidate_atr, approach_atr, max_entry_below_atr, slippage_per_side) < 0:
        raise ValueError("ATR multipliers and slippage must be non-negative")
    if stop_swing_lookback < 1:
        raise ValueError("stop_swing_lookback must be positive")
    if not 0 <= top_adjust_ratio <= 1:
        raise ValueError("top_adjust_ratio must be between 0 and 1")
    if reentry_timeout_minutes < 1:
        raise ValueError("reentry_timeout_minutes must be positive")

    frame = bar_frame.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    frame["recent_high"] = frame["high"].rolling(stop_swing_lookback, min_periods=1).max()
    for column, default in (
        ("active_zone_id", pd.NA), ("zone_version", pd.NA), ("dynamic_resistance_bottom", np.nan),
        ("dynamic_resistance_top", np.nan), ("entry_signal", False), ("entry_signal_type", None),
        ("top_adjusted", False), ("breakout_peak", np.nan), ("breakout_deadline", pd.NaT),
        ("zone_invalidated", False),
    ):
        frame[column] = default
    frame["active_zone_id"] = frame["active_zone_id"].astype("Int64")
    frame["zone_version"] = frame["zone_version"].astype("Int64")
    frame["breakout_deadline"] = frame["breakout_deadline"].astype(object)

    trades: list[dict[str, object]] = []
    zone_segments: list[dict[str, object]] = []
    position: Position | None = None
    pending_entry: dict[str, object] | None = None
    reentry_armed = False
    reentry_zone_id: int | None = None
    reentry_block_until_index = -1
    zone_id: int | None = None
    zone_version = 0
    zone_bottom = np.nan
    zone_top = np.nan
    zone_start: pd.Timestamp | None = None
    breakout_armed = False
    breakout_peak = np.nan
    breakout_start_time: pd.Timestamp | None = None
    breakout_expired = False
    zone_had_initial_entry = False
    zone_downside_exit_seen = False
    zone_price_touched = False
    zone_invalidated = False

    def close_zone_segment(end_time: pd.Timestamp) -> None:
        if zone_id is not None and zone_start is not None:
            zone_segments.append(
                {
                    "zone_id": zone_id,
                    "zone_version": zone_version,
                    "start_time": zone_start,
                    "end_time": end_time,
                    "resistance_bottom": zone_bottom,
                    "resistance_top": zone_top,
                }
            )

    def record(pos: Position, bar: pd.Series, exit_time: pd.Timestamp, raw_exit: float, reason: str) -> dict[str, object]:
        return _trade_record(pos, bar, exit_time, raw_exit, reason, slippage_per_side)

    for index, bar in frame.iterrows():
        timestamp = pd.Timestamp(bar["timestamp"])
        bar_start = pd.Timestamp(bar["minute_start"])
        source_zone_id = None if pd.isna(bar["resistance_id"]) else int(bar["resistance_id"])
        if source_zone_id is not None and source_zone_id != zone_id:
            close_zone_segment(timestamp)
            zone_id = source_zone_id
            zone_version = 1
            zone_bottom = float(bar["resistance_bottom"])
            zone_top = float(bar["resistance_top"])
            zone_start = timestamp
            breakout_armed = False
            breakout_peak = np.nan
            breakout_start_time = None
            breakout_expired = False
            reentry_armed = False
            reentry_zone_id = None
            pending_entry = None
            zone_had_initial_entry = False
            zone_downside_exit_seen = False
            zone_price_touched = False
            zone_invalidated = False

        occupied_at_open = position is not None
        stopped_this_bar = False
        raw_open = float(bar["open"])
        current_direction = None if pd.isna(bar["adjust_supertrend_direction"]) else int(bar["adjust_supertrend_direction"])

        if position is not None:
            trailing = position.trailing_stop if position.trailing_stop is not None else np.inf
            breakeven = position.breakeven_stop if position.breakeven_stop is not None else np.inf
            active_stop = min(position.initial_stop, trailing, breakeven)
            if raw_open >= active_stop:
                if position.profit_locked and breakeven <= trailing and breakeven <= position.initial_stop:
                    reason = "breakeven_lock_gap"
                elif position.trailing_stop is not None and active_stop < position.initial_stop:
                    reason = "atr_trailing_stop_gap"
                else:
                    reason = "initial_stop_gap"
                position.highest_price = max(position.highest_price, raw_open)
                trades.append(record(position, bar, bar_start, raw_open, reason))
                if reason == "initial_stop_gap":
                    reentry_armed, reentry_zone_id, reentry_block_until_index = True, position.zone_id, index
                else:
                    breakout_armed = False
                    breakout_peak = np.nan
                    breakout_start_time = None
                    breakout_expired = False
                position = None
                stopped_this_bar = True
            elif (
                position.supertrend_confirmed
                and position.last_supertrend_direction == -1
                and current_direction == 1
            ):
                position.lowest_price = min(position.lowest_price, raw_open)
                position.highest_price = max(position.highest_price, raw_open)
                trades.append(record(position, bar, bar_start, raw_open, "adjust_supertrend_bullish_flip"))
                position = None
                breakout_armed = False
                breakout_peak = np.nan
                breakout_start_time = None
                breakout_expired = False

        if position is None and not occupied_at_open and pending_entry is not None:
            if str(bar["session_id"]) == str(pending_entry["session_id"]):
                raw_entry = raw_open
                entry_fill = raw_entry - slippage_per_side
                entry_top = float(pending_entry.get("adjusted_resistance_top", pending_entry["resistance_top"]))
                stop_ref = entry_top
                swing_high = float(pending_entry.get("swing_high", np.nan))
                if pd.notna(swing_high) and entry_fill < swing_high < entry_top:
                    stop_ref = swing_high
                initial_stop = stop_ref + initial_stop_atr * float(pending_entry["risk_atr"])
                initial_risk = initial_stop - entry_fill
                if initial_risk > 0 and entry_fill < initial_stop:
                    entry_zone_version = int(pending_entry["zone_version"])
                    if (
                        pending_entry["entry_type"] == "reentry_after_initial_stop"
                        and zone_id == int(pending_entry["zone_id"])
                        and entry_top > zone_top
                    ):
                        close_zone_segment(bar_start)
                        zone_top = entry_top
                        zone_version += 1
                        zone_start = bar_start
                        entry_zone_version = zone_version
                        frame.at[index, "top_adjusted"] = True
                    confirmed = current_direction == -1
                    position = Position(
                        signal_time=pd.Timestamp(pending_entry["signal_time"]),
                        entry_time=bar_start,
                        entry_session=str(bar["session_id"]),
                        entry_type=str(pending_entry["entry_type"]),
                        zone_id=int(pending_entry["zone_id"]),
                        zone_version=entry_zone_version,
                        resistance_bottom=float(pending_entry["resistance_bottom"]),
                        resistance_top=entry_top,
                        raw_entry_price=raw_entry,
                        entry_price=entry_fill,
                        initial_stop=initial_stop,
                        initial_risk=initial_risk,
                        atr_at_entry=float(pending_entry["risk_atr"]),
                        supertrend_confirmed=confirmed,
                        last_supertrend_direction=current_direction,
                        lowest_price=entry_fill,
                        highest_price=entry_fill,
                    )
                    if pending_entry["entry_type"] == "reentry_after_initial_stop":
                        breakout_armed = False
                        breakout_peak = np.nan
                        breakout_start_time = None
                        breakout_expired = False
            pending_entry = None

        if position is not None:
            if current_direction == -1:
                position.supertrend_confirmed = True
            if current_direction is not None:
                position.last_supertrend_direction = current_direction
            trailing = position.trailing_stop if position.trailing_stop is not None else np.inf
            breakeven = position.breakeven_stop if position.breakeven_stop is not None else np.inf
            active_stop = min(position.initial_stop, trailing, breakeven)
            if float(bar["high"]) >= active_stop:
                if position.profit_locked and breakeven <= trailing and breakeven <= position.initial_stop:
                    reason = "breakeven_lock"
                elif position.trailing_stop is not None and active_stop < position.initial_stop:
                    reason = "atr_trailing_stop"
                else:
                    reason = "initial_stop"
                position.highest_price = max(position.highest_price, active_stop)
                trades.append(record(position, bar, timestamp, active_stop, reason))
                if reason == "initial_stop":
                    reentry_armed, reentry_zone_id, reentry_block_until_index = True, position.zone_id, index
                else:
                    breakout_armed = False
                    breakout_peak = np.nan
                    breakout_start_time = None
                    breakout_expired = False
                position = None
                stopped_this_bar = True
            else:
                position.lowest_price = min(position.lowest_price, float(bar["low"]))
                position.highest_price = max(position.highest_price, float(bar["high"]))
                if not position.profit_locked and (
                    (position.entry_price >= position.resistance_bottom and position.lowest_price < position.resistance_bottom)
                    or position.entry_price - position.lowest_price >= position.initial_risk
                ):
                    position.profit_locked = True
                    position.breakeven_stop = position.entry_price - slippage_per_side
                if not position.reached_one_r and position.entry_price - position.lowest_price >= position.initial_risk:
                    position.reached_one_r = True
                    position.one_r_time = timestamp
                if position.reached_one_r and position.supertrend_confirmed and pd.notna(bar["risk_atr"]):
                    candidate = position.lowest_price + trailing_atr * float(bar["risk_atr"])
                    position.trailing_stop = (
                        candidate if position.trailing_stop is None else min(position.trailing_stop, candidate)
                    )

        if zone_id is not None:
            if (
                breakout_armed
                and breakout_start_time is not None
                and bar_start > breakout_start_time + pd.Timedelta(minutes=reentry_timeout_minutes)
            ):
                breakout_armed = False
                breakout_peak = np.nan
                breakout_start_time = None
                breakout_expired = True
                if reentry_armed:
                    reentry_armed = False
                    reentry_zone_id = None
            if breakout_expired and zone_bottom <= float(bar["close"]) <= zone_top:
                breakout_expired = False
                if reentry_armed:
                    reentry_armed = False
                    reentry_zone_id = None
            if (
                not breakout_armed
                and not breakout_expired
                and (position is not None or reentry_armed)
                and float(bar["high"]) > zone_top
            ):
                breakout_armed = True
                breakout_peak = float(bar["high"])
                breakout_start_time = bar_start
            elif breakout_armed and float(bar["high"]) > zone_top:
                breakout_peak = max(float(breakout_peak), float(bar["high"]))

        if zone_id is not None and not zone_invalidated and pd.notna(bar["risk_atr"]):
            if float(bar["close"]) > zone_top + breakout_invalidate_atr * float(bar["risk_atr"]):
                zone_invalidated = True
                reentry_armed = False
                reentry_zone_id = None
                breakout_armed = False
                breakout_peak = np.nan
                breakout_start_time = None
                breakout_expired = False
                pending_entry = None

        if zone_id is not None and not zone_had_initial_entry:
            approach_band = approach_atr * float(bar["risk_atr"]) if pd.notna(bar["risk_atr"]) else 0.0
            if not zone_price_touched and float(bar["high"]) >= zone_bottom - approach_band:
                zone_price_touched = True
            if zone_price_touched and float(bar["close"]) < zone_bottom:
                zone_downside_exit_seen = True

        if (
            position is None
            and pending_entry is None
            and not occupied_at_open
            and not stopped_this_bar
            and zone_id is not None
            and not zone_invalidated
            and pd.notna(bar["risk_atr"])
            and (pd.isna(bar["uptrend_slope"]) or float(bar["uptrend_slope"]) <= max_uptrend_slope)
            and index < len(frame) - 1
            and bool(bar["ut_sell_signal"])
        ):
            bar_close = float(bar["close"])
            in_zone = zone_bottom <= bar_close <= zone_top
            entry_type: str | None = None
            if (
                reentry_armed
                and reentry_zone_id == zone_id
                and index > reentry_block_until_index
                and breakout_armed
                and breakout_start_time is not None
                and bar_start <= breakout_start_time + pd.Timedelta(minutes=reentry_timeout_minutes)
                and in_zone
            ):
                entry_type = "reentry_after_initial_stop"
            elif not reentry_armed:
                if in_zone:
                    entry_type = "initial_entry"
                elif (
                    zone_downside_exit_seen
                    and not zone_had_initial_entry
                    and bar_close >= zone_bottom - max_entry_below_atr * float(bar["risk_atr"])
                ):
                    entry_type = "initial_entry_after_downside_exit"
            if entry_type is not None:
                frame.at[index, "entry_signal"] = True
                frame.at[index, "entry_signal_type"] = entry_type
                pending_entry = {
                    "signal_time": timestamp,
                    "session_id": str(bar["session_id"]),
                    "entry_type": entry_type,
                    "zone_id": zone_id,
                    "zone_version": zone_version,
                    "resistance_bottom": zone_bottom,
                    "resistance_top": zone_top,
                    "risk_atr": float(bar["risk_atr"]),
                    "swing_high": float(bar["recent_high"]),
                }
                if entry_type == "reentry_after_initial_stop":
                    pending_entry["adjusted_resistance_top"] = adjusted_resistance_top(
                        zone_top, float(breakout_peak), top_adjust_ratio
                    )
                    reentry_armed = False
                    reentry_zone_id = None
                elif entry_type in ("initial_entry", "initial_entry_after_downside_exit"):
                    zone_had_initial_entry = True

        if zone_id is not None:
            frame.at[index, "active_zone_id"] = zone_id
            frame.at[index, "zone_version"] = zone_version
            frame.at[index, "dynamic_resistance_bottom"] = zone_bottom
            frame.at[index, "dynamic_resistance_top"] = zone_top
            frame.at[index, "zone_invalidated"] = zone_invalidated
            if breakout_armed:
                frame.at[index, "breakout_peak"] = breakout_peak
                frame.at[index, "breakout_deadline"] = (
                    breakout_start_time + pd.Timedelta(minutes=reentry_timeout_minutes)
                    if breakout_start_time is not None else pd.NaT
                )

    if position is not None:
        last = frame.iloc[-1]
        raw_exit = float(last["close"])
        position.lowest_price = min(position.lowest_price, float(last["low"]))
        position.highest_price = max(position.highest_price, float(last["high"]))
        trades.append(
            _trade_record(position, last, pd.Timestamp(last["timestamp"]), raw_exit, "data_end", slippage_per_side)
        )
    if zone_id is not None and zone_start is not None:
        close_zone_segment(pd.Timestamp(frame.iloc[-1]["timestamp"]))

    if not trades:
        trade_frame = pd.DataFrame(columns=TRADE_COLUMNS)
    else:
        trade_frame = pd.DataFrame(trades)
        trade_frame.insert(0, "trade_number", range(1, len(trade_frame) + 1))
        trade_frame["cumulative_gross_points"] = trade_frame["gross_points"].cumsum()
        trade_frame["cumulative_net_points"] = trade_frame["net_points"].cumsum()
        gross_peak = np.maximum.accumulate(np.r_[0.0, trade_frame["cumulative_gross_points"].to_numpy()])[1:]
        net_peak = np.maximum.accumulate(np.r_[0.0, trade_frame["cumulative_net_points"].to_numpy()])[1:]
        trade_frame["gross_drawdown_points"] = trade_frame["cumulative_gross_points"] - gross_peak
        trade_frame["net_drawdown_points"] = trade_frame["cumulative_net_points"] - net_peak
        trade_frame = trade_frame.reindex(columns=TRADE_COLUMNS)
    return trade_frame, frame, pd.DataFrame(zone_segments)


def performance_summary(trades: pd.DataFrame) -> dict[str, object]:
    if trades.empty:
        return {"trades": 0}
    winners = trades[trades["net_points"] > 0]
    losers = trades[trades["net_points"] < 0]
    gross_profit = float(winners["net_points"].sum())
    gross_loss = float(losers["net_points"].sum())
    return {
        "trades": len(trades),
        "wins": len(winners),
        "losses": len(losers),
        "breakeven": int((trades["net_points"] == 0).sum()),
        "win_rate": len(winners) / len(trades) * 100,
        "gross_points": float(trades["gross_points"].sum()),
        "net_points": float(trades["net_points"].sum()),
        "net_twd": float(trades["net_points"].sum()) * 10,
        "profit_factor": "n/a" if gross_loss == 0 else f"{gross_profit / abs(gross_loss):.2f}",
        "average_net_points": float(trades["net_points"].mean()),
        "max_net_drawdown": float(trades["net_drawdown_points"].min()),
    }


def write_markdown_report(
    path: Path,
    args: argparse.Namespace,
    source_count: int,
    tick_count: int,
    hourly: pd.DataFrame,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    zones: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    metric = lambda name, default=0: summary.get(name, default)
    rows = "| - | - | - | - | - | - | No trade |"
    if not trades.empty:
        rows = "\n".join(
            f"| {row.trade_number} | {row.entry_type} | {row.entry_time:%Y-%m-%d %H:%M} @ {row.entry_price:.1f} | "
            f"{row.exit_time:%Y-%m-%d %H:%M} @ {row.exit_price:.1f} | {row.net_points:.1f} | "
            f"{row.net_r:.2f} | {row.exit_reason} |"
            for row in trades.itertuples(index=False)
        )
    exit_counts = trades["exit_reason"].value_counts() if not trades.empty else pd.Series(dtype=int)
    exit_lines = "\n".join(f"- `{name}`：{count}" for name, count in exit_counts.items()) or "- 無交易"
    text = f"""# TMF 一小時壓力區＋三分 K UT Bot 純空策略回測

## 資料與設定

- 期間：`{args.start_date}` 至 `{args.end_date}`；來源 {source_count} 檔、有效 tick {tick_count:,} 筆。
- 一小時 K：{len(hourly):,} 根；有成交的三分 K：{len(bars):,} 根。
- 商品／合約：`{args.product} / {args.contract_month}`；每邊滑價 `{args.slippage_per_side:g}` 點。
- Pine 壓力區：close pivot `{args.pivot_lookback}/{args.pivot_lookback}`、volume filter `{args.volume_filter_length}`、ATR({args.box_atr_length}) × `{args.box_width:g}`。
- 首次進場：3m UT Bot(a={args.ut_sensitivity:g}, ATR={args.ut_atr_period}) 出現 SELL 且該 3m close 位於壓力區內；下一根 3m open 放空。
- 初始停損：min(進場上蓋, 最近 {args.stop_swing_lookback} 根擺盪高) 加 `{args.initial_stop_atr:g} × 一小時 ATR({args.risk_atr_length})`——錨定拒絕高點，不只是箱頂。
- 跌破區進場：close 需在區底下方 `{args.max_entry_below_atr:g} × 一小時 ATR({args.risk_atr_length})` 以內（不追過低放空）。
- 只有 initial stop 啟動再進場；突破原上蓋後，必須在 `{args.reentry_timeout_minutes}` 分鐘內再次出現 UT Bot SELL 且 close 回到原壓力區。
- 回區訊號後於下一根 3m open 再進場；成交後才把上蓋向突破最高價移動 `{args.top_adjust_ratio:.0%}`，並用新上蓋計算該筆停損。
- 保本鎖利：一旦價格跌破區底或達到 1R，停損收斂到扣除來回滑價後的保本價（`breakeven_lock`），獲利單不再翻成淨虧。
- 壓力區失效（不再放空）：3m close 收在上蓋上方超過 `{args.breakout_invalidate_atr:g} × 一小時 ATR({args.risk_atr_length})`——完整突破、角色反轉為支撐。
- 趨勢濾網：當一小時 SMA({args.trend_sma_length}) 在 `{args.trend_slope_hours}h` 內上升超過 `{args.max_uptrend_slope:g}%` 時不開新空單（強多頭時觀望）。
- 靠近帶：高點來到區底下方 `{args.approach_atr:g} × 一小時 ATR({args.risk_atr_length})` 內即視為觸及壓力（捕捉壓力下方的拒絕）。
- Adjust Supertrend：ATR 正規化價格速度動態 multiplier `{args.base_multiplier:g}–{args.minimum_multiplier:g}`；空頭確認且曾達 1R 後啟用 `{args.trailing_atr:g} × ATR({args.risk_atr_length})` trailing。

## 訊號與結構

| 項目 | 數量 |
| --- | ---: |
| Pine resistance IDs used | {int(zones['zone_id'].nunique()) if not zones.empty else 0} |
| Dynamic top versions | {len(zones)} |
| Top adjustments | {int(bars['top_adjusted'].sum())} |
| Zones invalidated (full breakout) | {int(bars.loc[bars['zone_invalidated'], 'active_zone_id'].nunique())} |
| Initial-entry signals | {int((bars['entry_signal_type'] == 'initial_entry').sum())} |
| Downside-exit initial signals | {int((bars['entry_signal_type'] == 'initial_entry_after_downside_exit').sum())} |
| Re-entry signals | {int((bars['entry_signal_type'] == 'reentry_after_initial_stop').sum())} |
| UT Bot SELL total | {int(bars['ut_sell_signal'].sum())} |

## 績效

| 指標 | 結果 |
| --- | ---: |
| Trades | {metric('trades')} |
| Wins / Losses / Breakeven | {metric('wins')} / {metric('losses')} / {metric('breakeven')} |
| Win rate | {float(metric('win_rate')):.1f}% |
| Gross P&L | {float(metric('gross_points')):.1f} points |
| Net P&L after slippage | {float(metric('net_points')):.1f} points |
| Net P&L, 1 TMF contract | NT${float(metric('net_twd')):,.0f} |
| Net profit factor | {metric('profit_factor', 'n/a')} |
| Average net P&L | {float(metric('average_net_points')):.1f} points |
| Maximum net drawdown | {float(metric('max_net_drawdown')):.1f} points |

## 出場原因

{exit_lines}

## 交易明細

| # | Entry type | Entry | Exit | Net | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
{rows}

## 限制

- 3m OHLC 無法還原分鐘內 high/low 先後；既有停損優先，新 trailing stop 僅從下一根 3m 生效。
- 只使用事件當下已完成的資料；pivot 的歷史回畫及 Pine `offset=-1` 不用於交易。
- 淨損益包含每邊固定滑價，但未扣手續費、期交稅、買賣價差與排隊成交影響。
- UT Bot 狀態機從資料最早段開始遞推，靠近資料起點的訊號受 warm-up 影響。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_html_report(
    path: Path,
    args: argparse.Namespace,
    hourly: pd.DataFrame,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    zones: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    metric = lambda name, default=0: summary.get(name, default)
    figure = make_subplots(
        rows=4, cols=1, shared_xaxes=False, vertical_spacing=0.045,
        row_heights=[0.55, 0.14, 0.13, 0.18],
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=(
            "Hourly Pine resistance, dynamic caps, and trades",
            "UT Bot trailing stop (3m)",
            "Closed-trade net equity",
            "Trade ledger",
        ),
    )
    figure.add_trace(
        go.Candlestick(
            x=hourly["timestamp"], open=hourly["open"], high=hourly["high"], low=hourly["low"],
            close=hourly["close"], name="TMF hourly",
        ), row=1, col=1,
    )
    if not zones.empty:
        for zone in zones.itertuples(index=False):
            figure.add_shape(
                type="rect", x0=zone.start_time, x1=zone.end_time,
                y0=zone.resistance_bottom, y1=zone.resistance_top,
                fillcolor="rgba(229,57,53,0.10)", line={"color": "rgba(229,57,53,0.65)", "width": 1},
                layer="below", row=1, col=1,
            )
    adjustments = bars[bars["top_adjusted"]]
    if not adjustments.empty:
        figure.add_trace(
            go.Scatter(
                x=adjustments["timestamp"], y=adjustments["dynamic_resistance_top"], mode="markers",
                name="Dynamic top raised", marker={"symbol": "diamond", "size": 10, "color": "#ef6c00"},
                hovertemplate="Top raised<br>%{x}<br>New top %{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["entry_time"], y=trades["raw_entry_price"], mode="markers", name="Short entry",
                marker={"symbol": "triangle-down", "size": 13, "color": "#6a1b9a"}, text=trades["entry_type"],
                hovertemplate="%{text}<br>%{x}<br>Raw %{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit",
                marker={"symbol": "x", "size": 11, "color": "#00897b"}, text=trades["exit_reason"],
                hovertemplate="%{text}<br>%{x}<br>Fill %{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
    figure.add_trace(
        go.Scatter(
            x=bars["timestamp"], y=bars["ut_trailing_stop"], mode="lines",
            name="UT Bot trailing stop", line={"color": "#1565c0"},
        ), row=2, col=1,
    )
    sell_bars = bars[bars["ut_sell_signal"]]
    if not sell_bars.empty:
        figure.add_trace(
            go.Scatter(
                x=sell_bars["timestamp"], y=sell_bars["close"], mode="markers",
                name="UT Bot SELL", marker={"symbol": "triangle-down", "size": 8, "color": "#e53935"},
            ), row=2, col=1,
        )
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["cumulative_net_points"], mode="lines+markers",
                name="Net cumulative P&L", line={"color": "#3949ab", "width": 2},
                fill="tozeroy", fillcolor="rgba(57,73,171,0.10)",
            ), row=3, col=1,
        )
        table_values = [
            trades["trade_number"].tolist(), trades["entry_type"].tolist(),
            trades["entry_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["exit_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["net_points"].map(lambda value: f"{value:.1f}").tolist(),
            trades["net_r"].map(lambda value: f"{value:.2f}").tolist(), trades["exit_reason"].tolist(),
        ]
    else:
        table_values = [["-"], ["No trade"], ["-"], ["-"], ["-"], ["-"], ["-"]]
    figure.add_trace(
        go.Table(
            header={
                "values": ["#", "Type", "Entry", "Exit", "Net pts", "Net R", "Exit reason"],
                "fill_color": "#263238", "font": {"color": "white"}, "align": "left",
            },
            cells={"values": table_values, "fill_color": "#f7f9fb", "align": "left", "height": 25},
        ), row=4, col=1,
    )
    title = (
        f"TMF {args.contract_month} UT Bot 3m Strategy | Trades {metric('trades')} · "
        f"Win rate {float(metric('win_rate')):.1f}% · Net {float(metric('net_points')):,.1f} pts · "
        f"PF {metric('profit_factor', 'n/a')}"
    )
    figure.update_layout(
        title={"text": title, "x": 0.5}, template="plotly_white", height=1250,
        hovermode="x unified", legend={"orientation": "h", "y": 1.02, "x": 0},
        margin={"l": 65, "r": 35, "t": 105, "b": 35},
    )
    figure.update_xaxes(rangeslider_visible=False, row=1, col=1)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="UT Bot stop", row=2, col=1)
    figure.update_yaxes(title_text="Net points", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True, full_html=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest the TMF hourly-resistance / 3-minute UT Bot short strategy.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START)
    parser.add_argument("--end-date", type=parse_date, default=DEFAULT_END)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
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
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_utbot3m_hourly_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--bar-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_utbot3m_bar_state_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--trades-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_utbot3m_trades_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--zones-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_utbot3m_dynamic_zones_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--report-output", type=Path,
        default=DEFAULT_DOC_DIR / f"tmf_202609_utbot3m_backtest_{DEFAULT_PERIOD}.md",
    )
    parser.add_argument(
        "--html-output", type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_utbot3m_backtest_{DEFAULT_PERIOD}.html",
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
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    ticks = add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip()))
    hourly = add_hourly_strategy_features(
        build_hourly_bars(ticks), args.pivot_lookback, args.volume_filter_length, args.box_atr_length,
        args.box_width, args.risk_atr_length, args.adjust_atr_length,
        args.speed_lookback, args.speed_smoothing, args.base_multiplier,
        args.minimum_multiplier, args.low_speed, args.high_speed,
    )
    hourly = hourly.sort_values("timestamp", kind="stable").reset_index(drop=True)
    trend_sma = hourly["close"].rolling(args.trend_sma_length).mean()
    hourly["uptrend_slope"] = (trend_sma / trend_sma.shift(args.trend_slope_hours) - 1.0) * 100.0
    bars = build_three_minute_bars(ticks)
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
    write_markdown_report(
        args.report_output, args, len(sources), len(ticks), hourly, bar_state, trades, zone_segments, summary
    )
    write_html_report(args.html_output, args, hourly, bar_state, trades, zone_segments, summary)
    print(
        f"ticks={len(ticks)} hourly={len(hourly)} bars={len(bar_state)} "
        f"trades={summary['trades']} net_points={float(summary.get('net_points', 0)):.1f}"
    )
    print(f"report={args.report_output}")
    print(f"html={args.html_output}")


if __name__ == "__main__":
    main()
