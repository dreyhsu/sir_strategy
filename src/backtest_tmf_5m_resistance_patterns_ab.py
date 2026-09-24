#!/usr/bin/env python
"""Tick-ordered TMF short backtest for 5-minute resistance patterns A and B."""

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
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones, session_anchor
except ImportError:
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones, session_anchor


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data" / "txf"
OUTPUT_DIR = ROOT / "txf_tick"
DOC_DIR = ROOT / "doc"
DEFAULT_START = date(2026, 8, 5)
DEFAULT_END = date(2026, 9, 15)
OUTPUT_PERIOD = "2026-08-05_to_2026-09-15"
DEFAULT_CONTRACT_TRADES = OUTPUT_DIR / f"TMF_202609_5m_resistance_patterns_ab_contracts_{OUTPUT_PERIOD}.csv"
DEFAULT_GROUP_TRADES = OUTPUT_DIR / f"TMF_202609_5m_resistance_patterns_ab_groups_{OUTPUT_PERIOD}.csv"
DEFAULT_CHART = OUTPUT_DIR / f"TMF_202609_5m_resistance_patterns_ab_{OUTPUT_PERIOD}.html"
DEFAULT_REPORT = DOC_DIR / f"tmf_202609_5m_resistance_patterns_ab_{OUTPUT_PERIOD}.md"


@dataclass
class ShortPosition:
    trade_id: int
    pattern_type: str
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    raw_entry_price: float
    entry_fill_price: float
    signal_tick_end_id: int
    resistance_id: int
    resistance_low: float
    resistance_high: float
    initial_stop: float
    target_price: float
    risk_points: float
    h1: float
    l1: float
    h2: float
    strongest_red_time: pd.Timestamp | None
    strongest_red_low: float
    strongest_red_body: float
    lowest_price: float
    highest_price: float


TRADE_COLUMNS = [
    "trade_number", "group_id", "slot", "pattern_type", "signal_time", "entry_time", "exit_time",
    "entry_session", "exit_session", "raw_entry_price", "entry_fill_price", "raw_exit_price",
    "exit_fill_price", "signal_tick_end_id", "resistance_id", "resistance_low", "resistance_high",
    "h1", "l1", "h2", "strongest_red_time", "strongest_red_low", "strongest_red_body",
    "initial_stop", "target_price", "risk_points", "gross_points", "net_points", "gross_ntd",
    "net_ntd", "r_multiple", "mfe_points", "mae_points", "holding_hours", "exit_reason",
    "cross_session", "cumulative_net_ntd",
]

GROUP_COLUMNS = [
    "group_id", "contract_count", "pattern_type", "first_entry_time", "last_entry_time", "exit_time",
    "entry_session", "exit_session", "average_raw_entry_price", "average_entry_fill_price",
    "raw_exit_price", "exit_fill_price", "resistance_ids", "gross_contract_points",
    "net_contract_points", "gross_ntd", "net_ntd", "holding_hours", "exit_reason", "cross_session",
    "cumulative_net_ntd",
]


def prepare_ticks(ticks: pd.DataFrame) -> pd.DataFrame:
    """Preserve exchange source order while assigning stable event ids."""
    ordering = [column for column in ("timestamp", "source_file", "source_sequence") if column in ticks.columns]
    result = ticks.sort_values(ordering, kind="stable").reset_index(drop=True)
    result["tick_id"] = np.arange(len(result), dtype=np.int64)
    return result


def build_five_minute_bars(ticks: pd.DataFrame) -> pd.DataFrame:
    """Build causal, session-anchored 5-minute OHLCV bars from ordered ticks."""
    records: list[dict[str, object]] = []
    for session_id, session_ticks in ticks.groupby("session_id", sort=False):
        frame = session_ticks.sort_values("tick_id", kind="stable").copy()
        anchor = session_anchor(str(session_id))
        elapsed = (frame["timestamp"] - anchor).dt.total_seconds()
        frame["bar_start"] = anchor + pd.to_timedelta((elapsed // 300).astype(int) * 300, unit="s")
        last_timestamp = frame["timestamp"].iloc[-1]
        session_end = anchor + pd.Timedelta(hours=5 if str(session_id).endswith(" day") else 14)
        for start, group in frame.groupby("bar_start", sort=True):
            end = start + pd.Timedelta(minutes=5)
            # A later tick proves an ordinary bucket complete.  The official
            # day/night close proves the final bucket complete without a tick
            # stamped exactly at the boundary.
            if end > last_timestamp and end != session_end:
                continue
            records.append(
                {
                    "bar_start": start,
                    "timestamp": end,
                    "open": float(group["price"].iloc[0]),
                    "high": float(group["price"].max()),
                    "low": float(group["price"].min()),
                    "close": float(group["price"].iloc[-1]),
                    "volume": float(group["quantity"].sum()),
                    "tick_start_id": int(group["tick_id"].iloc[0]),
                    "tick_end_id": int(group["tick_id"].iloc[-1]),
                    "session_id": session_id,
                    "session_type": group["session_type"].iloc[0],
                    "session_date": group["session_date"].iloc[0],
                }
            )
    columns = [
        "bar_start", "timestamp", "open", "high", "low", "close", "volume", "tick_start_id",
        "tick_end_id", "session_id", "session_type", "session_date",
    ]
    if not records:
        return pd.DataFrame(columns=columns)
    return pd.DataFrame(records, columns=columns).sort_values("timestamp", kind="stable").reset_index(drop=True)


def _zone_available(zone: object, bar_start: pd.Timestamp) -> bool:
    return bool(
        zone.created_time < bar_start
        and (pd.isna(zone.broken_time) or bar_start < zone.broken_time)
    )


def _strict_pivot(frame: pd.DataFrame, candidate: int, strength: int, column: str, high: bool) -> bool:
    if candidate - strength < 0 or candidate + strength >= len(frame):
        return False
    value = float(frame.iloc[candidate][column])
    neighbours = pd.concat(
        [
            frame[column].iloc[candidate - strength : candidate],
            frame[column].iloc[candidate + 1 : candidate + strength + 1],
        ]
    )
    return bool((value > neighbours).all()) if high else bool((value < neighbours).all())


def _strongest_red(
    frame: pd.DataFrame, current_index: int, lookback: int, mode: str
) -> pd.Series | None:
    if current_index < lookback:
        return None
    previous = frame.iloc[current_index - lookback : current_index].copy()
    previous["red_body"] = previous["close"] - previous["open"]
    bullish = previous[previous["red_body"] > 0].copy()
    if bullish.empty:
        return None
    if mode == "body_percent":
        bullish["red_score"] = bullish["red_body"] / bullish["open"]
    else:
        bullish["red_score"] = bullish["red_body"]
    return bullish.loc[bullish["red_score"].idxmax()]


def add_resistance_pattern_signals(
    bars: pd.DataFrame,
    zones: pd.DataFrame,
    strongest_red_lookback: int = 5,
    strongest_red_mode: str = "body",
    pivot_strength: int = 2,
    failure_window_bars: int = 3,
    breakout_points: float = 5.0,
    lower_high_min_difference: float = 5.0,
    stop_buffer_points: float = 5.0,
    pattern_b_window_bars: int = 12,
) -> pd.DataFrame:
    """Add causal Pattern A/B short signals to completed 5-minute bars."""
    if strongest_red_mode not in {"body", "body_percent"}:
        raise ValueError("strongest_red_mode must be 'body' or 'body_percent'")
    result = bars.copy()
    defaults: dict[str, object] = {
        "short_signal": False,
        "resistance_reversal": False,
        "pattern_type": pd.NA,
        "zone_id": pd.NA,
        "resistance_low": np.nan,
        "resistance_high": np.nan,
        "initial_stop": np.nan,
        "h1": np.nan,
        "l1": np.nan,
        "h2": np.nan,
        "strongest_red_time": pd.NaT,
        "strongest_red_low": np.nan,
        "strongest_red_body": np.nan,
    }
    for column, default in defaults.items():
        result[column] = default
    if result.empty or zones.empty:
        return result
    resistances = list(zones[zones["zone_type"] == "resistance"].itertuples(index=False))

    for _, indices in result.groupby("session_id", sort=False).groups.items():
        session = result.loc[list(indices)].sort_values("timestamp", kind="stable")
        global_indices = session.index.to_list()
        local = session.reset_index(drop=True)
        pattern_a: dict[int, dict[str, object]] = {}
        pattern_b: dict[int, dict[str, object]] = {}

        for i, bar in local.iterrows():
            active = {
                int(zone.zone_id): zone
                for zone in resistances
                if _zone_available(zone, bar["bar_start"])
            }
            pattern_a = {zone_id: state for zone_id, state in pattern_a.items() if zone_id in active}
            pattern_b = {zone_id: state for zone_id, state in pattern_b.items() if zone_id in active}
            touched = [zone for zone in active.values() if float(bar["high"]) >= float(zone.bottom)]
            selected = max(touched, key=lambda zone: (zone.created_time, int(zone.zone_id))) if touched else None

            if selected is not None:
                zone_id = int(selected.zone_id)
                if zone_id not in pattern_b:
                    pattern_b[zone_id] = {"start": i, "stage": 0, "h1": np.nan, "h1_i": -1,
                                                  "l1": np.nan, "l1_i": -1, "h2": np.nan, "h2_i": -1}
                if zone_id not in pattern_a and float(bar["high"]) > float(selected.top) + breakout_points:
                    pattern_a[zone_id] = {"start": i, "highest": float(bar["high"])}

            a_candidates: list[dict[str, object]] = []
            for zone_id, state in list(pattern_a.items()):
                zone = active[zone_id]
                age = i - int(state["start"])
                if age >= failure_window_bars:
                    del pattern_a[zone_id]
                    # An expired setup may begin again on this same bar.
                    if float(bar["high"]) > float(zone.top) + breakout_points:
                        state = {"start": i, "highest": float(bar["high"])}
                        pattern_a[zone_id] = state
                        age = 0
                    else:
                        continue
                state["highest"] = max(float(state["highest"]), float(bar["high"]))
                strongest = _strongest_red(local, i, strongest_red_lookback, strongest_red_mode)
                if strongest is not None and float(bar["close"]) < float(zone.top) and float(bar["close"]) < float(strongest["low"]):
                    a_candidates.append(
                        {
                            "pattern_type": "A", "zone": zone,
                            "initial_stop": float(state["highest"]) + stop_buffer_points,
                            "h1": np.nan, "l1": np.nan, "h2": np.nan,
                            "strongest_red_time": strongest["timestamp"],
                            "strongest_red_low": float(strongest["low"]),
                            "strongest_red_body": float(strongest["red_body"]),
                        }
                    )
                    del pattern_a[zone_id]

            b_candidates: list[dict[str, object]] = []
            for zone_id, state in list(pattern_b.items()):
                zone = active[zone_id]
                age = i - int(state["start"])
                if age >= pattern_b_window_bars:
                    del pattern_b[zone_id]
                    if selected is not None and int(selected.zone_id) == zone_id:
                        pattern_b[zone_id] = {"start": i, "stage": 0, "h1": np.nan, "h1_i": -1,
                                              "l1": np.nan, "l1_i": -1, "h2": np.nan, "h2_i": -1}
                    continue
                candidate = i - pivot_strength
                if candidate >= int(state["start"]):
                    if int(state["stage"]) == 0 and _strict_pivot(local, candidate, pivot_strength, "high", True):
                        state.update({"stage": 1, "h1": float(local.iloc[candidate]["high"]), "h1_i": candidate})
                    elif (
                        int(state["stage"]) == 1
                        and candidate > int(state["h1_i"])
                        and _strict_pivot(local, candidate, pivot_strength, "low", False)
                    ):
                        state.update({"stage": 2, "l1": float(local.iloc[candidate]["low"]), "l1_i": candidate})
                    elif (
                        int(state["stage"]) == 2
                        and candidate > int(state["l1_i"])
                        and _strict_pivot(local, candidate, pivot_strength, "high", True)
                    ):
                        h2 = float(local.iloc[candidate]["high"])
                        if h2 < float(state["h1"]) and float(state["h1"]) - h2 >= lower_high_min_difference:
                            state.update({"stage": 3, "h2": h2, "h2_i": candidate})
                if int(state["stage"]) == 3 and float(bar["close"]) < float(state["l1"]):
                    b_candidates.append(
                        {
                            "pattern_type": "B", "zone": zone,
                            "initial_stop": float(state["h2"]) + stop_buffer_points,
                            "h1": float(state["h1"]), "l1": float(state["l1"]), "h2": float(state["h2"]),
                            "strongest_red_time": pd.NaT, "strongest_red_low": np.nan,
                            "strongest_red_body": np.nan,
                        }
                    )
                    del pattern_b[zone_id]

            candidates = a_candidates or b_candidates
            if candidates:
                chosen = max(candidates, key=lambda item: (item["zone"].created_time, int(item["zone"].zone_id)))
                output_index = global_indices[i]
                zone = chosen["zone"]
                values = {
                    "short_signal": True,
                    "resistance_reversal": True,
                    "pattern_type": chosen["pattern_type"],
                    "zone_id": int(zone.zone_id),
                    "resistance_low": float(zone.bottom),
                    "resistance_high": float(zone.top),
                    "initial_stop": float(chosen["initial_stop"]),
                    "h1": chosen["h1"], "l1": chosen["l1"], "h2": chosen["h2"],
                    "strongest_red_time": chosen["strongest_red_time"],
                    "strongest_red_low": chosen["strongest_red_low"],
                    "strongest_red_body": chosen["strongest_red_body"],
                }
                for column, value in values.items():
                    result.at[output_index, column] = value
    return result


def _complete_trade(
    position: ShortPosition,
    tick: object,
    reason: str,
    slippage_points: float,
    point_value_ntd: float,
) -> dict[str, object]:
    raw_exit = float(tick.price)
    exit_fill = raw_exit + slippage_points
    lowest_price = min(position.lowest_price, raw_exit)
    highest_price = max(position.highest_price, raw_exit)
    gross_points = position.raw_entry_price - raw_exit
    net_points = position.entry_fill_price - exit_fill
    return {
        "group_id": position.trade_id, "slot": 1, "pattern_type": position.pattern_type,
        "signal_time": position.signal_time, "entry_time": position.entry_time, "exit_time": tick.timestamp,
        "entry_session": position.entry_session, "exit_session": tick.session_id,
        "raw_entry_price": position.raw_entry_price, "entry_fill_price": position.entry_fill_price,
        "raw_exit_price": raw_exit, "exit_fill_price": exit_fill,
        "signal_tick_end_id": position.signal_tick_end_id, "resistance_id": position.resistance_id,
        "resistance_low": position.resistance_low, "resistance_high": position.resistance_high,
        "h1": position.h1, "l1": position.l1, "h2": position.h2,
        "strongest_red_time": position.strongest_red_time, "strongest_red_low": position.strongest_red_low,
        "strongest_red_body": position.strongest_red_body, "initial_stop": position.initial_stop,
        "target_price": position.target_price, "risk_points": position.risk_points,
        "gross_points": gross_points, "net_points": net_points,
        "gross_ntd": gross_points * point_value_ntd, "net_ntd": net_points * point_value_ntd,
        "r_multiple": net_points / position.risk_points if position.risk_points > 0 else np.nan,
        "mfe_points": position.entry_fill_price - lowest_price,
        "mae_points": position.entry_fill_price - highest_price,
        "holding_hours": (tick.timestamp - position.entry_time).total_seconds() / 3600,
        "exit_reason": reason, "cross_session": position.entry_session != tick.session_id,
    }


def backtest_single_position_short(
    ticks: pd.DataFrame,
    signal_bars: pd.DataFrame,
    initial_capital_ntd: float = 400_000.0,
    point_value_ntd: float = 10.0,
    slippage_points: float = 2.0,
    risk_reward: float = 2.0,
    chart_sample_minutes: int = 5,
    show_progress: bool = False,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Fill at the next 5-minute open and manage one short position tick-by-tick."""
    ordered_ticks = ticks.sort_values("tick_id", kind="stable").reset_index(drop=True)
    events = list(signal_bars.sort_values("timestamp", kind="stable").itertuples(index=False))
    event_index = 0
    pending_entry: object | None = None
    pending_exit: str | None = None
    position: ShortPosition | None = None
    records: list[dict[str, object]] = []
    samples: list[dict[str, object]] = []
    counters = {
        "signals_a": 0, "signals_b": 0, "filled_entries": 0, "ignored_while_occupied": 0,
        "canceled_session": 0, "canceled_stop_breached": 0, "stop_exits": 0, "target_exits": 0,
        "resistance_reclaim_exits": 0, "data_end_exits": 0,
    }
    realized = 0.0
    peak_equity = minimum_equity = initial_capital_ntd
    maximum_drawdown = maximum_drawdown_percent = 0.0
    exposure_seconds = {0: 0.0, 1: 0.0}
    previous_time: pd.Timestamp | None = None
    previous_exposure = 0
    sample_delta = pd.Timedelta(minutes=chart_sample_minutes)
    next_sample_time: pd.Timestamp | None = None
    last_tick: object | None = None
    next_trade_id = 0
    started = time.monotonic()
    step = max(1, len(ordered_ticks) // (100 if sys.stderr.isatty() else 20))

    for number, tick in enumerate(ordered_ticks.itertuples(index=False), start=1):
        last_tick = tick
        if show_progress and (number == 1 or number % step == 0 or number == len(ordered_ticks)):
            elapsed = time.monotonic() - started
            percent = number / len(ordered_ticks) * 100 if len(ordered_ticks) else 100.0
            eta = elapsed * (len(ordered_ticks) - number) / number if number else 0.0
            print(f"Backtest ticks: {percent:5.1f}% ({number:,}/{len(ordered_ticks):,}) elapsed {elapsed:,.0f}s, ETA {eta:,.0f}s", file=sys.stderr, flush=True)
        if previous_time is not None:
            exposure_seconds[previous_exposure] += max(0.0, (tick.timestamp - previous_time).total_seconds())
        previous_time = tick.timestamp

        while event_index < len(events) and events[event_index].timestamp <= tick.timestamp:
            bar = events[event_index]
            event_index += 1
            if position is not None and bar.timestamp > position.entry_time and float(bar.close) > position.resistance_high:
                pending_exit = "resistance_reclaimed"
            if bool(bar.short_signal):
                key = "signals_a" if str(bar.pattern_type) == "A" else "signals_b"
                counters[key] += 1
                if position is not None or pending_entry is not None or pending_exit is not None:
                    counters["ignored_while_occupied"] += 1
                else:
                    pending_entry = bar

        exited_this_tick = False
        if position is not None and pending_exit is not None:
            record = _complete_trade(position, tick, pending_exit, slippage_points, point_value_ntd)
            records.append(record)
            realized += float(record["net_ntd"])
            counters["resistance_reclaim_exits"] += 1
            position = None
            pending_exit = None
            exited_this_tick = True

        if not exited_this_tick and position is None and pending_entry is not None:
            signal = pending_entry
            pending_entry = None
            if tick.session_id != signal.session_id:
                counters["canceled_session"] += 1
            elif float(tick.price) >= float(signal.initial_stop):
                counters["canceled_stop_breached"] += 1
            else:
                next_trade_id += 1
                raw_entry = float(tick.price)
                risk = float(signal.initial_stop) - raw_entry
                position = ShortPosition(
                    trade_id=next_trade_id, pattern_type=str(signal.pattern_type), signal_time=signal.timestamp,
                    entry_time=tick.timestamp, entry_session=tick.session_id, raw_entry_price=raw_entry,
                    entry_fill_price=raw_entry - slippage_points, signal_tick_end_id=int(signal.tick_end_id),
                    resistance_id=int(signal.zone_id), resistance_low=float(signal.resistance_low),
                    resistance_high=float(signal.resistance_high), initial_stop=float(signal.initial_stop),
                    target_price=raw_entry - risk_reward * risk, risk_points=risk,
                    h1=float(signal.h1), l1=float(signal.l1), h2=float(signal.h2),
                    strongest_red_time=None if pd.isna(signal.strongest_red_time) else signal.strongest_red_time,
                    strongest_red_low=float(signal.strongest_red_low),
                    strongest_red_body=float(signal.strongest_red_body), lowest_price=raw_entry, highest_price=raw_entry,
                )
                counters["filled_entries"] += 1

        price = float(tick.price)
        if position is not None:
            position.lowest_price = min(position.lowest_price, price)
            position.highest_price = max(position.highest_price, price)
            reason = None
            if price >= position.initial_stop:
                reason = "initial_structure_stop"
                counters["stop_exits"] += 1
            elif price <= position.target_price:
                reason = "risk_reward_target"
                counters["target_exits"] += 1
            if reason is not None:
                record = _complete_trade(position, tick, reason, slippage_points, point_value_ntd)
                records.append(record)
                realized += float(record["net_ntd"])
                position = None
                exited_this_tick = True

        unrealized = (position.entry_fill_price - price) * point_value_ntd if position is not None else 0.0
        equity = initial_capital_ntd + realized + unrealized
        peak_equity = max(peak_equity, equity)
        minimum_equity = min(minimum_equity, equity)
        maximum_drawdown = min(maximum_drawdown, equity - peak_equity)
        maximum_drawdown_percent = max(
            maximum_drawdown_percent, (peak_equity - equity) / peak_equity * 100 if peak_equity else 0.0
        )
        if next_sample_time is None or tick.timestamp >= next_sample_time or exited_this_tick:
            samples.append(
                {"timestamp": tick.timestamp, "price": price, "equity_ntd": equity,
                 "realized_ntd": realized, "unrealized_ntd": unrealized,
                 "open_positions": int(position is not None), "drawdown_ntd": equity - peak_equity}
            )
            next_sample_time = tick.timestamp.floor(f"{chart_sample_minutes}min") + sample_delta
        previous_exposure = int(position is not None)

    if position is not None and last_tick is not None:
        record = _complete_trade(position, last_tick, "data_end", slippage_points, point_value_ntd)
        records.append(record)
        realized += float(record["net_ntd"])
        counters["data_end_exits"] += 1
        final_equity = initial_capital_ntd + realized
        peak_equity = max(peak_equity, final_equity)
        minimum_equity = min(minimum_equity, final_equity)
        maximum_drawdown = min(maximum_drawdown, final_equity - peak_equity)
        maximum_drawdown_percent = max(
            maximum_drawdown_percent,
            (peak_equity - final_equity) / peak_equity * 100 if peak_equity else 0.0,
        )
        samples.append(
            {"timestamp": last_tick.timestamp, "price": float(last_tick.price), "equity_ntd": final_equity,
             "realized_ntd": realized, "unrealized_ntd": 0.0, "open_positions": 0,
             "drawdown_ntd": final_equity - peak_equity}
        )

    trades = pd.DataFrame(records)
    if trades.empty:
        trades = pd.DataFrame(columns=TRADE_COLUMNS)
    else:
        trades.insert(0, "trade_number", range(1, len(trades) + 1))
        trades["cumulative_net_ntd"] = trades["net_ntd"].cumsum()
        trades = trades.reindex(columns=TRADE_COLUMNS)
    groups = pd.DataFrame(columns=GROUP_COLUMNS)
    if not trades.empty:
        groups = pd.DataFrame(
            {
                "group_id": trades["group_id"], "contract_count": 1, "pattern_type": trades["pattern_type"],
                "first_entry_time": trades["entry_time"], "last_entry_time": trades["entry_time"],
                "exit_time": trades["exit_time"], "entry_session": trades["entry_session"],
                "exit_session": trades["exit_session"], "average_raw_entry_price": trades["raw_entry_price"],
                "average_entry_fill_price": trades["entry_fill_price"], "raw_exit_price": trades["raw_exit_price"],
                "exit_fill_price": trades["exit_fill_price"], "resistance_ids": trades["resistance_id"].astype(str),
                "gross_contract_points": trades["gross_points"], "net_contract_points": trades["net_points"],
                "gross_ntd": trades["gross_ntd"], "net_ntd": trades["net_ntd"],
                "holding_hours": trades["holding_hours"], "exit_reason": trades["exit_reason"],
                "cross_session": trades["cross_session"], "cumulative_net_ntd": trades["cumulative_net_ntd"],
            }
        ).reindex(columns=GROUP_COLUMNS)
    sample_frame = pd.DataFrame(samples).drop_duplicates(subset=["timestamp"], keep="last")
    wins = trades[trades["net_ntd"] > 0]
    losses = trades[trades["net_ntd"] < 0]
    profit_factor = (
        float(wins["net_ntd"].sum()) / abs(float(losses["net_ntd"].sum()))
        if not losses.empty else float("inf") if not wins.empty else 0.0
    )
    elapsed_seconds = sum(exposure_seconds.values())
    summary: dict[str, object] = {
        **counters, "signals": counters["signals_a"] + counters["signals_b"], "contract_trades": len(trades),
        "groups": len(groups), "winning_contracts": len(wins), "losing_contracts": len(losses),
        "winning_groups": len(wins), "losing_groups": len(losses),
        "contract_win_rate_percent": len(wins) / len(trades) * 100 if len(trades) else 0.0,
        "group_win_rate_percent": len(wins) / len(trades) * 100 if len(trades) else 0.0,
        "group_profit_factor": profit_factor,
        "gross_ntd": float(trades["gross_ntd"].sum()) if not trades.empty else 0.0,
        "net_ntd": realized, "initial_equity_ntd": initial_capital_ntd,
        "final_equity_ntd": initial_capital_ntd + realized,
        "return_percent": realized / initial_capital_ntd * 100,
        "minimum_equity_ntd": minimum_equity, "maximum_drawdown_ntd": max(0.0, -maximum_drawdown),
        "maximum_drawdown_percent": maximum_drawdown_percent, "peak_positions": int(not trades.empty),
        "exposure_hours": {key: value / 3600 for key, value in exposure_seconds.items()},
        "exposure_percent": {key: value / elapsed_seconds * 100 if elapsed_seconds else 0.0
                             for key, value in exposure_seconds.items()},
    }
    return trades, groups, sample_frame, summary


def write_report(
    path: Path, args: argparse.Namespace, sources: list[Path], ticks: pd.DataFrame, hourly: pd.DataFrame,
    bars: pd.DataFrame, trades: pd.DataFrame, groups: pd.DataFrame, summary: dict[str, object],
) -> None:
    rows = "| - | - | - | - | - | - | No trade |"
    if not groups.empty:
        rows = "\n".join(
            f"| {row.group_id} | {row.pattern_type} | {row.first_entry_time:%Y-%m-%d %H:%M:%S} | "
            f"{row.exit_time:%Y-%m-%d %H:%M:%S} | {row.average_entry_fill_price:.1f} | "
            f"{row.net_ntd:,.0f} | {row.exit_reason} |" for row in groups.itertuples(index=False)
        )
    profit_factor = summary["group_profit_factor"]
    profit_factor_text = "∞" if np.isinf(profit_factor) else f"{profit_factor:.2f}"
    exposure_hours = summary["exposure_hours"]
    exposure_percent = summary["exposure_percent"]
    text = f"""# {args.product} {args.contract_month}：5M 壓力區型態 A／B 空單回測

## 資料與設定

- 日期：`{args.start_date}` 至 `{args.end_date}`；來源檔 {len(sources)} 個、有效 tick {len(ticks):,} 筆、5 分 K {len(bars):,} 根、60 分 K {len(hourly):,} 根。
- 起始權益：NT${args.initial_capital_ntd:,.0f}；每點 NT${args.point_value_ntd:g}；同時最多一口。
- 進出場每邊 {args.slippage_points:g} 點不利滑價；未計手續費與期交稅。

## 交易規則

- 型態 A：突破壓力上緣 {args.breakout_points:g} 點後，在含突破棒的 {args.failure_window_bars} 根內收回箱內，並跌破前 {args.strongest_red_lookback} 根最強紅 K 低點。
- 最強紅 K 模式：`{args.strongest_red_mode}`；型態 A 停損為突破過程最高價加 {args.stop_buffer_points:g} 點。
- 型態 B：進入壓力區後 {args.pattern_b_window_bars} 根內，以左右 {args.pivot_strength} 根確認 H1/L1/H2，H2 至少低 {args.lower_high_min_difference:g} 點，再收破 L1。
- 下一根 5M 第一筆 tick 進場；停利為 {args.risk_reward:g}R；5M 收盤站回壓力上緣則下一根開盤退出。

## 帳戶結果

| Metric | Value |
| --- | ---: |
| Pattern A / B signals | {summary['signals_a']} / {summary['signals_b']} |
| Valid signals / filled entries | {summary['signals']} / {summary['filled_entries']} |
| Ignored while occupied | {summary['ignored_while_occupied']} |
| Canceled at session / stop breached | {summary['canceled_session']} / {summary['canceled_stop_breached']} |
| Contract trades / groups | {summary['contract_trades']} / {summary['groups']} |
| Winning / losing trades | {summary['winning_contracts']} / {summary['losing_contracts']} |
| Win rate / profit factor | {summary['contract_win_rate_percent']:.1f}% / {profit_factor_text} |
| Gross P&L | NT${summary['gross_ntd']:,.0f} |
| Net P&L after slippage | NT${summary['net_ntd']:,.0f} |
| Final equity | NT${summary['final_equity_ntd']:,.0f} |
| Return | {summary['return_percent']:.2f}% |
| Minimum tick-level equity | NT${summary['minimum_equity_ntd']:,.0f} |
| Maximum tick-level drawdown | NT${summary['maximum_drawdown_ntd']:,.0f} ({summary['maximum_drawdown_percent']:.2f}%) |
| Stop / target / reclaim exits | {summary['stop_exits']} / {summary['target_exits']} / {summary['resistance_reclaim_exits']} |
| Flat exposure | {exposure_hours.get(0, 0):.1f} h ({exposure_percent.get(0, 0):.1f}%) |
| One-contract exposure | {exposure_hours.get(1, 0):.1f} h ({exposure_percent.get(1, 0):.1f}%) |

## Group Ledger

| Group | Pattern | Entry | Exit | Fill | Net NTD | Exit reason |
|---:|---|---|---|---:|---:|---|
{rows}

## 風險說明

NT${args.initial_capital_ntd:,.0f} 僅作為權益基準；回測不會因權益或保證金不足自動平倉。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_chart(
    path: Path, zones: pd.DataFrame, trades: pd.DataFrame, samples: pd.DataFrame, initial_capital_ntd: float,
) -> None:
    figure = make_subplots(
        rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.035, row_heights=[0.62, 0.16, 0.22],
        subplot_titles=("Sampled tick price and A/B entries", "Open TMF contracts", "Marked-to-market equity"),
    )
    if not samples.empty:
        figure.add_trace(go.Scatter(x=samples["timestamp"], y=samples["price"], mode="lines", name="Tick price"), row=1, col=1)
        chart_end = samples["timestamp"].iloc[-1]
        for zone in zones[zones["zone_type"] == "resistance"].itertuples(index=False) if not zones.empty else []:
            end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
            figure.add_shape(type="rect", x0=zone.created_time, x1=end, y0=zone.bottom, y1=zone.top,
                             fillcolor="rgba(211,47,47,0.12)", line={"color": "rgba(211,47,47,0.55)"}, row=1, col=1)
        if not trades.empty:
            colors = trades["pattern_type"].map({"A": "#6a1b9a", "B": "#ef6c00"})
            figure.add_trace(go.Scatter(x=trades["entry_time"], y=trades["entry_fill_price"], mode="markers",
                                        name="Short entry", marker={"symbol": "triangle-down", "size": 12, "color": colors},
                                        text=trades["pattern_type"]), row=1, col=1)
            figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["exit_fill_price"], mode="markers",
                                        name="Exit", marker={"symbol": "x", "size": 10, "color": "#00897b"},
                                        text=trades["exit_reason"]), row=1, col=1)
        figure.add_trace(go.Scatter(x=samples["timestamp"], y=samples["open_positions"], mode="lines",
                                    line_shape="hv", name="Open contracts"), row=2, col=1)
        figure.add_trace(go.Scatter(x=samples["timestamp"], y=samples["equity_ntd"], mode="lines",
                                    name="Account equity"), row=3, col=1)
    figure.add_hline(y=initial_capital_ntd, line_dash="dot", line_color="gray", row=3, col=1)
    figure.update_layout(title="TMF 5M Resistance Patterns A/B Short Backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Contracts", dtick=1, row=2, col=1)
    figure.update_yaxes(title_text="NTD", tickformat=",.0f", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest TMF 5-minute resistance patterns A and B.")
    parser.add_argument("--input-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START)
    parser.add_argument("--end-date", type=parse_date, default=DEFAULT_END)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--initial-capital-ntd", type=float, default=400_000)
    parser.add_argument("--point-value-ntd", type=float, default=10)
    parser.add_argument("--slippage-points", type=float, default=2)
    parser.add_argument("--strongest-red-lookback", type=int, choices=[3, 5, 8, 10], default=5)
    parser.add_argument("--strongest-red-mode", choices=["body", "body_percent"], default="body")
    parser.add_argument("--pivot-strength", type=int, choices=[2, 3, 4], default=2)
    parser.add_argument("--failure-window-bars", type=int, choices=[1, 2, 3, 4], default=3)
    parser.add_argument("--breakout-points", type=float, choices=[0, 5, 10], default=5)
    parser.add_argument("--lower-high-min-difference", type=float, choices=[0, 5, 10, 15], default=5)
    parser.add_argument("--stop-buffer-points", type=float, default=5)
    parser.add_argument("--risk-reward", type=float, choices=[1, 1.5, 2, 3], default=2)
    parser.add_argument("--pattern-b-window-bars", type=int, default=12)
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--zone-atr-length", type=int, default=20)
    parser.add_argument("--zone-box-width", type=float, default=1.0)
    parser.add_argument("--chart-sample-minutes", type=int, default=5)
    parser.add_argument("--contract-trades-output", type=Path, default=DEFAULT_CONTRACT_TRADES)
    parser.add_argument("--group-trades-output", type=Path, default=DEFAULT_GROUP_TRADES)
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--no-progress", action="store_true")
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    if min(args.initial_capital_ntd, args.point_value_ntd, args.strongest_red_lookback,
           args.pivot_strength, args.failure_window_bars, args.pattern_b_window_bars,
           args.pivot_lookback, args.volume_filter_length, args.zone_atr_length,
           args.chart_sample_minutes) <= 0:
        parser.error("capital, point value, windows, and lookbacks must be positive")
    if min(args.slippage_points, args.breakout_points, args.lower_high_min_difference,
           args.stop_buffer_points, args.zone_box_width) < 0:
        parser.error("slippage, price buffers, and zone width must be non-negative")
    return args


def main() -> None:
    args = parse_args()
    progress = not args.no_progress

    def stage(number: int, message: str) -> None:
        if progress:
            print(f"[{number}/8] {message}", file=sys.stderr, flush=True)

    stage(1, "Finding daily source files...")
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    stage(2, f"Loading and filtering {len(sources)} daily files...")
    ticks = prepare_ticks(add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip())))
    stage(3, "Building hourly bars and Pine-style zones...")
    hourly = build_hourly_bars(ticks)
    zones = pine_style_zones(hourly, args.pivot_lookback, args.volume_filter_length,
                             args.zone_atr_length, args.zone_box_width)
    stage(4, "Building session-anchored 5-minute bars...")
    bars = build_five_minute_bars(ticks)
    stage(5, f"Detecting patterns in {len(bars):,} completed bars...")
    bars = add_resistance_pattern_signals(
        bars, zones, args.strongest_red_lookback, args.strongest_red_mode, args.pivot_strength,
        args.failure_window_bars, args.breakout_points, args.lower_high_min_difference,
        args.stop_buffer_points, args.pattern_b_window_bars,
    )
    stage(6, f"Running tick backtest across {len(ticks):,} ticks...")
    trades, groups, samples, summary = backtest_single_position_short(
        ticks, bars, args.initial_capital_ntd, args.point_value_ntd, args.slippage_points,
        args.risk_reward, args.chart_sample_minutes, progress,
    )
    stage(7, "Writing trade files and report...")
    for output in (args.contract_trades_output, args.group_trades_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.contract_trades_output, index=False, encoding="utf-8-sig")
    groups.to_csv(args.group_trades_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, args, sources, ticks, hourly, bars, trades, groups, summary)
    stage(8, "Writing interactive chart...")
    write_chart(args.chart_output, zones, trades, samples, args.initial_capital_ntd)
    print(f"ticks={len(ticks)} hourly_bars={len(hourly)} five_minute_bars={len(bars)} signals={summary['signals']}")
    print(f"trades={summary['contract_trades']} net_ntd={summary['net_ntd']:.0f} final_equity_ntd={summary['final_equity_ntd']:.0f}")
    print(f"report={args.report_output}")
    print(f"chart={args.chart_output}")


if __name__ == "__main__":
    main()
