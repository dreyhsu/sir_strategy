#!/usr/bin/env python
"""Backtest the BTCUSDT hourly-resistance / 3-minute UT Bot short strategy per month.

Reads the committed 1h and 3m bar CSVs produced by ``preprocess_btcusdt_bars.py``
(``data/btcusdt_bars/BTCUSDT_YYYY-MM_{1h,3m}.csv``) rather than raw ticks, so the
huge aggTrades files are only touched once, on the machine that downloaded them.

Each calendar month is backtested on its own. Indicators — especially the slow
1-hour support/resistance zones — are warmed with the preceding month(s) of bars,
then only the target month's 3-minute bars are simulated. January cannot be warmed
(no prior month) and is therefore reported as warm-up only / skipped.

BTCUSDT trades continuously (24/7); every bar is ``session_id = "continuous"``.
Costs follow the Binance-perp model of the other BTC scripts: per-side slippage in
basis points plus a taker fee, with P&L reported in USDT for a fixed BTC size.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .backtest_tmf_hourly_diamond_short import add_pine_diamond_signals, pine_atr
    from .backtest_tmf_0923_hourly_resistance_1m_short import add_adjust_supertrend, adjusted_resistance_top
    from .backtest_tmf_hourly_resistance_utbot_3m_short import (
        Position,
        add_hourly_strategy_features,
        add_ut_bot_state,
        attach_hourly_features,
    )
except ImportError:
    from backtest_tmf_hourly_diamond_short import add_pine_diamond_signals, pine_atr
    from backtest_tmf_0923_hourly_resistance_1m_short import add_adjust_supertrend, adjusted_resistance_top
    from backtest_tmf_hourly_resistance_utbot_3m_short import (
        Position,
        add_hourly_strategy_features,
        add_ut_bot_state,
        attach_hourly_features,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BARS_DIR = ROOT / "data" / "btcusdt_bars"
DEFAULT_OUTPUT_DIR = ROOT / "btcusdt_tick"
DEFAULT_DOC_DIR = ROOT / "doc"
DEFAULT_START_MONTH = "2026-02"
DEFAULT_END_MONTH = "2026-08"


TRADE_COLUMNS = [
    "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
    "entry_type", "zone_id", "zone_version", "resistance_bottom", "resistance_top",
    "raw_entry_price", "entry_price", "exit_price", "initial_stop", "initial_risk", "atr_at_entry",
    "one_r_time", "trailing_stop_at_exit", "gross_points", "net_points",
    "entry_fee_usdt", "exit_fee_usdt", "gross_usdt", "net_usdt",
    "gross_r", "net_r", "mfe_points", "mae_points", "exit_reason", "cross_session",
    "cumulative_gross_usdt", "cumulative_net_usdt", "gross_drawdown_usdt", "net_drawdown_usdt",
]


def parse_month(text: str) -> str:
    try:
        parsed = pd.Period(text, freq="M")
    except (ValueError, TypeError) as error:
        raise argparse.ArgumentTypeError(f"invalid month {text!r}; expected YYYY-MM") from error
    return f"{parsed.year:04d}-{parsed.month:02d}"


def month_range(start_month: str, end_month: str) -> list[str]:
    start, end = pd.Period(start_month, freq="M"), pd.Period(end_month, freq="M")
    if end < start:
        raise ValueError("--end-month must be on or after --start-month")
    return [f"{p.year:04d}-{p.month:02d}" for p in pd.period_range(start, end, freq="M")]


def load_bars(bars_dir: Path, month: str, timeframe: str) -> pd.DataFrame:
    path = bars_dir / f"BTCUSDT_{month}_{timeframe}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"missing bar file: {path}")
    time_columns = ["timestamp", "hour_start" if timeframe == "1h" else "minute_start"]
    frame = pd.read_csv(path)
    for column in time_columns:
        frame[column] = pd.to_datetime(frame[column], utc=True, format="ISO8601")
    return frame


def load_span(bars_dir: Path, months: list[str], timeframe: str) -> pd.DataFrame:
    frames = [load_bars(bars_dir, month, timeframe) for month in months]
    return pd.concat(frames, ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)


def _trade_record(
    position: Position,
    bar: pd.Series,
    exit_time: pd.Timestamp,
    raw_exit_price: float,
    exit_reason: str,
    slippage_bps: float,
    taker_fee_rate: float,
    position_btc: float,
) -> dict[str, object]:
    slip = slippage_bps / 10_000.0
    exit_fill = raw_exit_price * (1 + slip)
    entry_fee = position.entry_price * position_btc * taker_fee_rate
    exit_fee = exit_fill * position_btc * taker_fee_rate
    gross_points = position.raw_entry_price - raw_exit_price
    net_points = position.entry_price - exit_fill
    gross_usdt = gross_points * position_btc
    net_usdt = net_points * position_btc - entry_fee - exit_fee
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
        "exit_price": exit_fill,
        "initial_stop": position.initial_stop,
        "initial_risk": position.initial_risk,
        "atr_at_entry": position.atr_at_entry,
        "one_r_time": position.one_r_time,
        "trailing_stop_at_exit": position.trailing_stop,
        "gross_points": gross_points,
        "net_points": net_points,
        "entry_fee_usdt": entry_fee,
        "exit_fee_usdt": exit_fee,
        "gross_usdt": gross_usdt,
        "net_usdt": net_usdt,
        "gross_r": gross_points / position.initial_risk,
        "net_r": net_points / position.initial_risk,
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
    slippage_bps: float = 1.0,
    taker_fee_rate: float = 0.0004,
    position_btc: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Short-only state machine ported from the TMF UT Bot 3m strategy.

    Identical entry/exit logic; only the fill/cost accounting is Binance-perp
    (slippage bps + taker fee, entry fill raised, exit fill raised).
    """
    if min(initial_stop_atr, trailing_atr, breakout_invalidate_atr, approach_atr, max_entry_below_atr, slippage_bps, taker_fee_rate, position_btc) < 0:
        raise ValueError("ATR multipliers, slippage, fee, and size must be non-negative")
    if stop_swing_lookback < 1:
        raise ValueError("stop_swing_lookback must be positive")
    if not 0 <= top_adjust_ratio <= 1:
        raise ValueError("top_adjust_ratio must be between 0 and 1")
    if reentry_timeout_minutes < 1:
        raise ValueError("reentry_timeout_minutes must be positive")

    slip = slippage_bps / 10_000.0
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
        return _trade_record(pos, bar, exit_time, raw_exit, reason, slippage_bps, taker_fee_rate, position_btc)

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
                entry_fill = raw_entry * (1 - slip)
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
                    position.breakeven_stop = (
                        position.entry_price * (1 - taker_fee_rate) / ((1 + taker_fee_rate) * (1 + slip))
                    )
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
        trades.append(record(position, last, pd.Timestamp(last["timestamp"]), raw_exit, "data_end"))
    if zone_id is not None and zone_start is not None:
        close_zone_segment(pd.Timestamp(frame.iloc[-1]["timestamp"]))

    if not trades:
        trade_frame = pd.DataFrame(columns=TRADE_COLUMNS)
    else:
        trade_frame = pd.DataFrame(trades)
        trade_frame.insert(0, "trade_number", range(1, len(trade_frame) + 1))
        trade_frame["cumulative_gross_usdt"] = trade_frame["gross_usdt"].cumsum()
        trade_frame["cumulative_net_usdt"] = trade_frame["net_usdt"].cumsum()
        gross_peak = np.maximum.accumulate(np.r_[0.0, trade_frame["cumulative_gross_usdt"].to_numpy()])[1:]
        net_peak = np.maximum.accumulate(np.r_[0.0, trade_frame["cumulative_net_usdt"].to_numpy()])[1:]
        trade_frame["gross_drawdown_usdt"] = trade_frame["cumulative_gross_usdt"] - gross_peak
        trade_frame["net_drawdown_usdt"] = trade_frame["cumulative_net_usdt"] - net_peak
        trade_frame = trade_frame.reindex(columns=TRADE_COLUMNS)
    return trade_frame, frame, pd.DataFrame(zone_segments)


def performance_summary(trades: pd.DataFrame) -> dict[str, object]:
    if trades.empty:
        return {"trades": 0}
    winners = trades[trades["net_usdt"] > 0]
    losers = trades[trades["net_usdt"] < 0]
    gross_profit = float(winners["net_usdt"].sum())
    gross_loss = float(losers["net_usdt"].sum())
    return {
        "trades": len(trades),
        "wins": len(winners),
        "losses": len(losers),
        "breakeven": int((trades["net_usdt"] == 0).sum()),
        "win_rate": len(winners) / len(trades) * 100,
        "gross_usdt": float(trades["gross_usdt"].sum()),
        "net_usdt": float(trades["net_usdt"].sum()),
        "total_fees_usdt": float((trades["entry_fee_usdt"] + trades["exit_fee_usdt"]).sum()),
        "profit_factor": "n/a" if gross_loss == 0 else f"{gross_profit / abs(gross_loss):.2f}",
        "average_net_usdt": float(trades["net_usdt"].mean()),
        "max_net_drawdown_usdt": float(trades["net_drawdown_usdt"].min()),
    }


def write_markdown_report(
    path: Path,
    args: argparse.Namespace,
    month: str,
    warmup_months: list[str],
    hourly_rows: int,
    bar_rows: int,
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
            f"{row.exit_time:%Y-%m-%d %H:%M} @ {row.exit_price:.1f} | {row.net_usdt:.2f} | "
            f"{row.net_r:.2f} | {row.exit_reason} |"
            for row in trades.itertuples(index=False)
        )
    exit_counts = trades["exit_reason"].value_counts() if not trades.empty else pd.Series(dtype=int)
    exit_lines = "\n".join(f"- `{name}`: {count}" for name, count in exit_counts.items()) or "- no trades"
    warmup_text = ", ".join(warmup_months) if warmup_months else "none"
    text = f"""# BTCUSDT Hourly-Resistance + 3m UT Bot Short — {month}

## Data & Setup

- Backtest month: `{month}` (UTC); warm-up months: {warmup_text}.
- Hourly bars in span: {hourly_rows:,}; simulated 3m bars (target month): {bar_rows:,}.
- Costs: slippage `{args.slippage_bps:g}` bps/side, taker fee `{args.taker_fee_rate:.4%}`, size `{args.position_btc:g}` BTC.
- Pine resistance: close pivot `{args.pivot_lookback}/{args.pivot_lookback}`, volume filter `{args.volume_filter_length}`, ATR({args.box_atr_length}) × `{args.box_width:g}`.
- Entry: 3m UT Bot(a={args.ut_sensitivity:g}, ATR={args.ut_atr_period}) SELL with close inside the zone; short on next 3m open.
- Initial stop: min(zone top, recent {args.stop_swing_lookback}-bar swing high) + `{args.initial_stop_atr:g} × hourly ATR({args.risk_atr_length})` — anchored to the rejection high, not just the box top.
- Downside-exit entries only when the close is within `{args.max_entry_below_atr:g} × hourly ATR({args.risk_atr_length})` below the zone bottom (no shorting far under the zone).
- Re-entry only after an initial stop; break above top then a UT Bot SELL back inside the zone within `{args.reentry_timeout_minutes}` min.
- Profit lock: once price trades below the zone bottom OR the trade reaches 1R, the stop ratchets to break-even net of round-trip fees (`breakeven_lock`), so a profitable short can't turn into a net loss.
- Resistance retired (no more shorts) once a 3m close clears the zone top by more than `{args.breakout_invalidate_atr:g} × hourly ATR({args.risk_atr_length})` — a full breakout, role reversal to support.
- Trend filter: no new shorts while the hourly SMA({args.trend_sma_length}) is rising faster than `{args.max_uptrend_slope:g}%` over `{args.trend_slope_hours}h` (stand aside in strong uptrends).
- Approach band: price counts as reaching the zone when the high comes within `{args.approach_atr:g} × hourly ATR({args.risk_atr_length})` of the bottom (captures rejections just under resistance).
- Adjust Supertrend dynamic multiplier `{args.base_multiplier:g}–{args.minimum_multiplier:g}`; short-confirmed + 1R reached enables `{args.trailing_atr:g} × ATR({args.risk_atr_length})` trailing.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Pine resistance IDs used | {int(zones['zone_id'].nunique()) if not zones.empty else 0} |
| Dynamic top versions | {len(zones)} |
| Top adjustments | {int(bars['top_adjusted'].sum())} |
| Zones invalidated (full breakout) | {int(bars.loc[bars['zone_invalidated'], 'active_zone_id'].nunique())} |
| Initial-entry signals | {int((bars['entry_signal_type'] == 'initial_entry').sum())} |
| Downside-exit initial signals | {int((bars['entry_signal_type'] == 'initial_entry_after_downside_exit').sum())} |
| Re-entry signals | {int((bars['entry_signal_type'] == 'reentry_after_initial_stop').sum())} |
| UT Bot SELL total | {int(bars['ut_sell_signal'].sum())} |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | {metric('trades')} |
| Wins / Losses / Breakeven | {metric('wins')} / {metric('losses')} / {metric('breakeven')} |
| Win rate | {float(metric('win_rate')):.1f}% |
| Gross P&L | {float(metric('gross_usdt')):,.2f} USDT |
| Net P&L after costs | {float(metric('net_usdt')):,.2f} USDT |
| Total fees | {float(metric('total_fees_usdt')):,.2f} USDT |
| Net profit factor | {metric('profit_factor', 'n/a')} |
| Average net P&L | {float(metric('average_net_usdt')):,.2f} USDT |
| Maximum net drawdown | {float(metric('max_net_drawdown_usdt')):,.2f} USDT |

## Exit Reasons

{exit_lines}

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
{rows}

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_html_report(
    path: Path,
    month: str,
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
            "Closed-trade net equity (USDT)",
            "Trade ledger",
        ),
    )
    figure.add_trace(
        go.Candlestick(
            x=hourly["timestamp"], open=hourly["open"], high=hourly["high"], low=hourly["low"],
            close=hourly["close"], name="BTCUSDT hourly",
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
                x=trades["exit_time"], y=trades["cumulative_net_usdt"], mode="lines+markers",
                name="Net cumulative P&L", line={"color": "#3949ab", "width": 2},
                fill="tozeroy", fillcolor="rgba(57,73,171,0.10)",
            ), row=3, col=1,
        )
        table_values = [
            trades["trade_number"].tolist(), trades["entry_type"].tolist(),
            trades["entry_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["exit_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["net_usdt"].map(lambda value: f"{value:.2f}").tolist(),
            trades["net_r"].map(lambda value: f"{value:.2f}").tolist(), trades["exit_reason"].tolist(),
        ]
    else:
        table_values = [["-"], ["No trade"], ["-"], ["-"], ["-"], ["-"], ["-"]]
    figure.add_trace(
        go.Table(
            header={
                "values": ["#", "Type", "Entry", "Exit", "Net USDT", "Net R", "Exit reason"],
                "fill_color": "#263238", "font": {"color": "white"}, "align": "left",
            },
            cells={"values": table_values, "fill_color": "#f7f9fb", "align": "left", "height": 25},
        ), row=4, col=1,
    )
    title = (
        f"BTCUSDT {month} UT Bot 3m Short | Trades {metric('trades')} · "
        f"Win rate {float(metric('win_rate')):.1f}% · Net {float(metric('net_usdt')):,.0f} USDT · "
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
    figure.update_yaxes(title_text="Net USDT", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True, full_html=True)


def run_month(month: str, args: argparse.Namespace) -> dict[str, object]:
    span_months = month_range(
        f"{(pd.Period(month, freq='M') - args.warmup_months)}", month
    ) if args.warmup_months > 0 else [month]
    warmup_months = span_months[:-1]

    hourly_raw = load_span(args.bars_dir, span_months, "1h")
    hourly = add_hourly_strategy_features(
        hourly_raw, args.pivot_lookback, args.volume_filter_length, args.box_atr_length,
        args.box_width, args.risk_atr_length, args.adjust_atr_length,
        args.speed_lookback, args.speed_smoothing, args.base_multiplier,
        args.minimum_multiplier, args.low_speed, args.high_speed,
    )
    hourly = hourly.sort_values("timestamp", kind="stable").reset_index(drop=True)
    trend_sma = hourly["close"].rolling(args.trend_sma_length).mean()
    hourly["uptrend_slope"] = (trend_sma / trend_sma.shift(args.trend_slope_hours) - 1.0) * 100.0
    bars = load_span(args.bars_dir, span_months, "3m")
    bars = add_ut_bot_state(bars, sensitivity=args.ut_sensitivity, atr_period=args.ut_atr_period)
    bars = attach_hourly_features(bars, hourly)
    bars["uptrend_slope"] = bars["hourly_confirmation_time"].map(
        hourly.set_index("timestamp")["uptrend_slope"]
    )

    month_period = pd.Period(month, freq="M")
    month_start = pd.Timestamp(month_period.start_time, tz="UTC")
    month_end = pd.Timestamp(month_period.end_time, tz="UTC")
    month_mask = (bars["timestamp"] >= month_start) & (bars["timestamp"] <= month_end)
    month_bars = bars[month_mask].reset_index(drop=True)
    if month_bars.empty:
        raise ValueError(f"no 3m bars fall inside {month}")

    trades, bar_state, zone_segments = backtest_strategy(
        month_bars, args.initial_stop_atr, args.trailing_atr, args.top_adjust_ratio,
        args.reentry_timeout_minutes, args.breakout_invalidate_atr, args.max_uptrend_slope,
        args.approach_atr, args.max_entry_below_atr, args.stop_swing_lookback,
        args.slippage_bps, args.taker_fee_rate, args.position_btc,
    )
    summary = performance_summary(trades)
    hourly_month = hourly[(hourly["timestamp"] >= month_start) & (hourly["timestamp"] <= month_end)]

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"BTCUSDT_{month}_utbot3m"
    hourly.to_csv(args.output_dir / f"{stem}_hourly.csv", index=False, encoding="utf-8-sig")
    bar_state.to_csv(args.output_dir / f"{stem}_bar_state.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(args.output_dir / f"{stem}_trades.csv", index=False, encoding="utf-8-sig")
    zone_segments.to_csv(args.output_dir / f"{stem}_dynamic_zones.csv", index=False, encoding="utf-8-sig")
    write_markdown_report(
        args.doc_dir / f"btcusdt_{month.replace('-', '')}_utbot3m_backtest.md",
        args, month, warmup_months, len(hourly), len(month_bars),
        bar_state, trades, zone_segments, summary,
    )
    write_html_report(
        args.output_dir / f"{stem}_backtest.html",
        month, hourly_month, bar_state, trades, zone_segments, summary,
    )
    print(
        f"{month}: warmup={warmup_months or 'none'} hourly={len(hourly)} bars={len(month_bars)} "
        f"trades={summary['trades']} net_usdt={float(summary.get('net_usdt', 0)):,.2f}"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest the BTCUSDT hourly-resistance / 3-minute UT Bot short strategy per month.")
    parser.add_argument("--bars-dir", type=Path, default=DEFAULT_BARS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-dir", type=Path, default=DEFAULT_DOC_DIR)
    parser.add_argument("--start-month", type=parse_month, default=DEFAULT_START_MONTH)
    parser.add_argument("--end-month", type=parse_month, default=DEFAULT_END_MONTH)
    parser.add_argument("--warmup-months", type=int, default=1)
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
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0004)
    parser.add_argument("--position-btc", type=float, default=1.0)
    args = parser.parse_args()
    if pd.Period(args.end_month, freq="M") < pd.Period(args.start_month, freq="M"):
        parser.error("--end-month must be on or after --start-month")
    if args.warmup_months < 0:
        parser.error("--warmup-months must be non-negative")
    positive_lengths = (
        args.pivot_lookback, args.volume_filter_length, args.box_atr_length, args.risk_atr_length,
        args.adjust_atr_length, args.speed_lookback, args.speed_smoothing, args.ut_atr_period,
        args.trend_sma_length, args.trend_slope_hours, args.stop_swing_lookback,
    )
    if min(positive_lengths) < 1:
        parser.error("all lengths must be positive")
    if args.ut_sensitivity <= 0:
        parser.error("--ut-sensitivity must be positive")
    if min(args.box_width, args.initial_stop_atr, args.trailing_atr, args.breakout_invalidate_atr, args.approach_atr, args.max_entry_below_atr, args.slippage_bps, args.taker_fee_rate, args.position_btc) < 0:
        parser.error("width, ATR multipliers, slippage, fee, and size must be non-negative")
    if not 0 <= args.top_adjust_ratio <= 1:
        parser.error("--top-adjust-ratio must be between 0 and 1")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must exceed --low-speed")
    if args.reentry_timeout_minutes < 1:
        parser.error("--reentry-timeout-minutes must be positive")
    args.bars_dir = args.bars_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    args.doc_dir = args.doc_dir.resolve()
    return args


def main() -> None:
    args = parse_args()
    months = month_range(args.start_month, args.end_month)
    for month in months:
        run_month(month, args)


if __name__ == "__main__":
    main()
