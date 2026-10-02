#!/usr/bin/env python
"""Backtest the BTCUSDT 1h-trend / 15m MACD-pullback downtrend-line breakout LONG strategy.

Long-only. The setup combines a slow **1-hour trend filter** with a fast **15-minute
MACD pullback + downtrend-line breakout** trigger:

1. Trend filter: the last *closed* hourly close is above its MA(20) **and** the most recent
   7 fifteen-minute closes are all above that (last closed) 1h MA(20).  BTCUSDT trades
   continuously (24/7), so the TXF-style "08:45 day-session" hourly alignment does not apply —
   the committed UTC ``:00``-anchored 1h bars are used as-is.
2. Pullback (15m, state 1): MACD(12,26,9) ``DIF`` crosses below the zero axis.  ``H1`` is
   the swing high of the rally that preceded the pullback.
3. Armed (15m, state 2): a golden cross *below* the zero axis (``DIF`` crosses above
   ``DEA`` with both < 0).  A downtrend line is drawn through ``H1`` and ``H2`` — the most
   recent *confirmed* swing high after ``H1`` that is lower than ``H1``.
4. Entry: while armed, a 15m close above ``line + buffer`` fires; the long is filled on the
   **next** 15m open.
5. Exits: initial stop = nearer of (pullback low, entry − 1.5×ATR15m) = 1R; take-profit is
   either a fixed 2R target or a trailing 15m-swing-low stop (``--exit-mode``); a close of the
   last 1h bar back below MA20 forces an exit; and a time stop closes trades that make no
   meaningful progress within ``--time-stop-bars`` bars.

No look-ahead: every signal reads only closed-bar data, fills happen on the next bar's open,
swing-high/low pivots are consumed only once confirmed (pivot index + k bars), and each 15m
bar sees only the previously-closed 1h bar.  Every drawn trend line is rendered on the HTML.

Reads the committed 1h and 15m bar CSVs produced by ``preprocess_btcusdt_bars.py``
(``data/btcusdt_bars/BTCUSDT_YYYY-MM_{1h,15m}.csv``).  Each calendar month is backtested on
its own; indicators are warmed with the preceding month(s).  Costs follow the Binance-perp
model of the sibling BTC scripts: per-side slippage in basis points plus a taker fee, with
P&L reported in USDT for a fixed BTC size.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .backtest_tmf_hourly_diamond_short import pine_atr
except ImportError:
    from backtest_tmf_hourly_diamond_short import pine_atr


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BARS_DIR = ROOT / "data" / "btcusdt_bars"
DEFAULT_OUTPUT_DIR = ROOT / "btcusdt_tick"
DEFAULT_DOC_DIR = ROOT / "doc"
DEFAULT_START_MONTH = "2026-02"
DEFAULT_END_MONTH = "2026-08"
EXIT_MODES = ("fixed_2r", "trailing_swinglow")


@dataclass
class Position:
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    entry_type: str
    entry_index: int
    h1_time: pd.Timestamp
    h2_time: pd.Timestamp
    line_slope: float
    raw_entry_price: float
    entry_price: float
    initial_stop: float
    initial_risk: float
    atr_at_entry: float
    target_price: float
    pullback_low: float
    lowest_price: float
    highest_price: float
    reached_one_r: bool = False
    one_r_time: pd.Timestamp | None = None
    trailing_stop: float | None = None


TRADE_COLUMNS = [
    "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
    "entry_type", "h1_time", "h2_time", "line_slope",
    "raw_entry_price", "entry_price", "exit_price", "initial_stop", "initial_risk", "atr_at_entry",
    "target_price", "one_r_time", "trailing_stop_at_exit", "gross_points", "net_points",
    "entry_fee_usdt", "exit_fee_usdt", "gross_usdt", "net_usdt",
    "gross_r", "net_r", "mfe_points", "mae_points", "exit_reason", "cross_session",
    "cumulative_gross_usdt", "cumulative_net_usdt", "gross_drawdown_usdt", "net_drawdown_usdt",
]

TRENDLINE_COLUMNS = [
    "h1_time", "h1_price", "h2_time", "h2_price", "slope",
    "start_time", "end_time", "end_price", "status",
]


# --------------------------------------------------------------------------------------
# Data loading
# --------------------------------------------------------------------------------------
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


# --------------------------------------------------------------------------------------
# Indicators (causal / no look-ahead)
# --------------------------------------------------------------------------------------
def macd(close: pd.Series, fast: int, slow: int, signal: int) -> tuple[pd.Series, pd.Series]:
    """Return (DIF, DEA).  DIF = EMA(fast) - EMA(slow); DEA = EMA(signal) of DIF.

    ``pandas.ewm`` is strictly causal — the value at bar *i* uses only closes up to and
    including *i* — so this never peeks at future bars.
    """
    ema_fast = close.ewm(span=fast, adjust=False).mean()
    ema_slow = close.ewm(span=slow, adjust=False).mean()
    dif = ema_fast - ema_slow
    dea = dif.ewm(span=signal, adjust=False).mean()
    return dif, dea


def swing_high_flags(high: np.ndarray, k: int) -> np.ndarray:
    """Boolean array: bar *i* is a swing high when its high is the strict maximum of the
    window ``[i-k, i+k]``.  A pivot is only *confirmable* k bars later (at ``i+k``)."""
    n = len(high)
    flags = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        center = high[i]
        if center == np.nanmax(high[i - k : i + k + 1]) and np.sum(high[i - k : i + k + 1] == center) == 1:
            flags[i] = True
    return flags


def swing_low_flags(low: np.ndarray, k: int) -> np.ndarray:
    """Boolean array: bar *i* is a swing low when its low is the strict minimum of the
    window ``[i-k, i+k]`` (confirmable k bars later)."""
    n = len(low)
    flags = np.zeros(n, dtype=bool)
    for i in range(k, n - k):
        center = low[i]
        if center == np.nanmin(low[i - k : i + k + 1]) and np.sum(low[i - k : i + k + 1] == center) == 1:
            flags[i] = True
    return flags


def add_15m_features(
    bars: pd.DataFrame, fast: int, slow: int, signal: int, atr_length: int, swing_k: int
) -> pd.DataFrame:
    frame = bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    dif, dea = macd(frame["close"], fast, slow, signal)
    frame["dif"] = dif
    frame["dea"] = dea
    frame["atr15"] = pine_atr(frame, atr_length)
    prev_dif = frame["dif"].shift(1)
    prev_dea = frame["dea"].shift(1)
    frame["cross_below_zero"] = (frame["dif"] < 0) & (prev_dif >= 0)
    frame["cross_above_zero"] = (frame["dif"] >= 0) & (prev_dif < 0)
    frame["golden_cross_below"] = (
        (frame["dif"] > frame["dea"]) & (prev_dif <= prev_dea) & (frame["dif"] < 0) & (frame["dea"] < 0)
    )
    frame["death_cross_below"] = (
        (frame["dif"] < frame["dea"]) & (prev_dif >= prev_dea) & (frame["dif"] < 0) & (frame["dea"] < 0)
    )
    frame["is_swing_high"] = swing_high_flags(frame["high"].to_numpy(dtype=float), swing_k)
    frame["is_swing_low"] = swing_low_flags(frame["low"].to_numpy(dtype=float), swing_k)
    return frame


def add_hourly_features(hourly: pd.DataFrame, ma_length: int, atr_length: int) -> pd.DataFrame:
    frame = hourly.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    ma = frame["close"].rolling(ma_length).mean()
    frame["hourly_ma"] = ma
    frame["hourly_atr"] = pine_atr(frame, atr_length)
    frame["hourly_trend_invalidated"] = frame["close"] < ma
    return frame


def attach_hourly_features(bars: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    """Merge the last *closed* hourly bar's state onto each 15m bar (strictly-before merge)."""
    columns = ["timestamp", "close", "hourly_ma", "hourly_atr", "hourly_trend_invalidated"]
    right = hourly[columns].rename(columns={"timestamp": "hourly_confirmation_time", "close": "hourly_close"})
    return pd.merge_asof(
        bars.sort_values("timestamp", kind="stable"),
        right.sort_values("hourly_confirmation_time", kind="stable"),
        left_on="timestamp",
        right_on="hourly_confirmation_time",
        direction="backward",
        allow_exact_matches=False,
    )


def add_trend_filter(bars: pd.DataFrame, bars_above_window: int) -> pd.DataFrame:
    """Compute the per-15m long trend filter (requires attached hourly features).

    The setup is allowed only when the last *closed* 1h close is above its MA, **and** the
    most recent ``bars_above_window`` 15m closes are all above the (last closed) 1h MA.  Both
    legs read only closed-bar data, so the filter is free of look-ahead.
    """
    frame = bars.copy()
    above = frame["close"] > frame["hourly_ma"]
    consecutive = above.rolling(bars_above_window, min_periods=bars_above_window).sum()
    frame["bar_above_hourly_ma"] = above
    frame["hourly_trend_ok"] = (frame["hourly_close"] > frame["hourly_ma"]) & (consecutive >= bars_above_window)
    return frame


# --------------------------------------------------------------------------------------
# Trade accounting (long)
# --------------------------------------------------------------------------------------
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
    exit_fill = raw_exit_price * (1 - slip)  # long exit is a sell → filled lower
    entry_fee = position.entry_price * position_btc * taker_fee_rate
    exit_fee = exit_fill * position_btc * taker_fee_rate
    gross_points = raw_exit_price - position.raw_entry_price
    net_points = exit_fill - position.entry_price
    gross_usdt = gross_points * position_btc
    net_usdt = net_points * position_btc - entry_fee - exit_fee
    return {
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": exit_time,
        "entry_session": position.entry_session,
        "exit_session": str(bar["session_id"]),
        "entry_type": position.entry_type,
        "h1_time": position.h1_time,
        "h2_time": position.h2_time,
        "line_slope": position.line_slope,
        "raw_entry_price": position.raw_entry_price,
        "entry_price": position.entry_price,
        "exit_price": exit_fill,
        "initial_stop": position.initial_stop,
        "initial_risk": position.initial_risk,
        "atr_at_entry": position.atr_at_entry,
        "target_price": position.target_price,
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
        "mfe_points": position.highest_price - position.entry_price,
        "mae_points": position.lowest_price - position.entry_price,
        "exit_reason": exit_reason,
        "cross_session": position.entry_session != str(bar["session_id"]),
    }


# --------------------------------------------------------------------------------------
# Backtest state machine
# --------------------------------------------------------------------------------------
def backtest_strategy(
    bar_frame: pd.DataFrame,
    exit_mode: str = "fixed_2r",
    swing_k: int = 2,
    slope_atr_max: float = -0.03,
    min_h1_distance: int = 6,
    max_h1_distance: int = 40,
    buffer_atr: float = 0.15,
    disarm_bars: int = 20,
    stop_atr: float = 1.5,
    target_r: float = 2.0,
    time_stop_bars: int = 24,
    pullback_depth_atr: float = 0.0,
    slippage_bps: float = 1.0,
    taker_fee_rate: float = 0.0004,
    position_btc: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if exit_mode not in EXIT_MODES:
        raise ValueError(f"exit_mode must be one of {EXIT_MODES}")
    if min(swing_k, min_h1_distance, disarm_bars, time_stop_bars) < 1:
        raise ValueError("swing_k, distances, disarm_bars and time_stop_bars must be positive")
    if max_h1_distance < min_h1_distance:
        raise ValueError("max_h1_distance must be >= min_h1_distance")
    if min(buffer_atr, stop_atr, target_r, slippage_bps, taker_fee_rate, position_btc) < 0:
        raise ValueError("buffer, stop, target, slippage, fee and size must be non-negative")

    slip = slippage_bps / 10_000.0
    frame = bar_frame.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    n = len(frame)

    close = frame["close"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    atr15 = frame["atr15"].to_numpy(dtype=float)

    # Confirmed swing pivots as (index, price) lists, used only once index >= pivot + k.
    swing_highs = [(i, high[i]) for i in np.flatnonzero(frame["is_swing_high"].to_numpy())]
    swing_lows = [(i, low[i]) for i in np.flatnonzero(frame["is_swing_low"].to_numpy())]

    for column, default in (
        ("setup_state", 0), ("h1_index", pd.NA), ("h2_index", pd.NA),
        ("line_value", np.nan), ("entry_signal", False),
    ):
        frame[column] = default
    frame["h1_index"] = frame["h1_index"].astype("Int64")
    frame["h2_index"] = frame["h2_index"].astype("Int64")

    trades: list[dict[str, object]] = []
    trendlines: dict[tuple[int, int], dict[str, object]] = {}
    position: Position | None = None
    pending_entry: dict[str, object] | None = None

    # Setup state (0 wait, 1 pullback, 2 armed).
    state = 0
    h1_index: int | None = None
    h1_price = np.nan
    pullback_low = np.inf
    last_up_leg_start = 0
    golden_index: int | None = None

    def ts(i: int) -> pd.Timestamp:
        return pd.Timestamp(frame.iloc[i]["timestamp"])

    def line_value_at(h1_i: int, h1_p: float, slope: float, idx: int) -> float:
        return h1_p + slope * (idx - h1_i)

    def record(pos: Position, bar: pd.Series, exit_time: pd.Timestamp, raw_exit: float, reason: str) -> dict[str, object]:
        return _trade_record(pos, bar, exit_time, raw_exit, reason, slippage_bps, taker_fee_rate, position_btc)

    def confirmed_swing_high_h2(h1_i: int, now: int) -> tuple[int, float] | None:
        """Most recent confirmed swing high after H1 that is lower than H1."""
        best: tuple[int, float] | None = None
        for p_idx, p_price in swing_highs:
            if p_idx <= h1_i or p_idx + swing_k > now or p_price >= h1_price:
                continue
            if best is None or p_idx > best[0]:
                best = (p_idx, p_price)
        return best

    def latest_confirmed_swing_low(now: int) -> float | None:
        best: tuple[int, float] | None = None
        for p_idx, p_price in swing_lows:
            if p_idx + swing_k > now:
                continue
            if best is None or p_idx > best[0]:
                best = (p_idx, p_price)
        return best[1] if best is not None else None

    def reset_setup() -> None:
        nonlocal state, h1_index, h1_price, pullback_low, golden_index
        state = 0
        h1_index = None
        h1_price = np.nan
        pullback_low = np.inf
        golden_index = None

    def upsert_trendline(key: tuple[int, int], h2_i: int, h2_p: float, slope: float, end_i: int, status: str) -> None:
        line = trendlines.get(key)
        if line is None:
            trendlines[key] = {
                "h1_index": h1_index, "h1_time": ts(h1_index), "h1_price": h1_price,
                "h2_index": h2_i, "h2_time": ts(h2_i), "h2_price": h2_p, "slope": slope,
                "start_time": ts(h1_index), "end_index": end_i, "end_time": ts(end_i), "status": status,
            }
        else:
            line["end_index"] = end_i
            line["end_time"] = ts(end_i)
            line["slope"] = slope
            if status != "armed":
                line["status"] = status

    for index in range(n):
        bar = frame.iloc[index]
        timestamp = pd.Timestamp(bar["timestamp"])
        bar_start = pd.Timestamp(bar["minute_start"])
        raw_open = float(bar["open"])
        trend_ok = bool(bar["hourly_trend_ok"]) if pd.notna(bar["hourly_trend_ok"]) else False
        trend_invalidated = bool(bar["hourly_trend_invalidated"]) if pd.notna(bar["hourly_trend_invalidated"]) else False
        atr = atr15[index]

        # --- A1) manage open position: gap through stop at the open -----------------------
        if position is not None:
            active_stop = position.initial_stop
            if exit_mode == "trailing_swinglow" and position.trailing_stop is not None:
                active_stop = max(active_stop, position.trailing_stop)
            if raw_open <= active_stop:
                reason = "trailing_stop_gap" if active_stop > position.initial_stop else "initial_stop_gap"
                position.lowest_price = min(position.lowest_price, raw_open)
                trades.append(record(position, bar, bar_start, raw_open, reason))
                position = None
                reset_setup()

        # --- A2) fill a pending entry on this bar's open ---------------------------------
        if position is None and pending_entry is not None:
            raw_entry = raw_open
            entry_fill = raw_entry * (1 + slip)
            risk_atr = float(pending_entry["risk_atr"])
            pb_low = float(pending_entry["pullback_low"])
            stop_atr_level = entry_fill - stop_atr * risk_atr
            initial_stop = max(pb_low, stop_atr_level)  # "nearer" of the two → higher stop
            initial_risk = entry_fill - initial_stop
            if initial_risk > 0 and entry_fill > initial_stop:
                position = Position(
                    signal_time=pd.Timestamp(pending_entry["signal_time"]),
                    entry_time=bar_start,
                    entry_session=str(bar["session_id"]),
                    entry_type="trendline_breakout",
                    entry_index=index,
                    h1_time=pd.Timestamp(pending_entry["h1_time"]),
                    h2_time=pd.Timestamp(pending_entry["h2_time"]),
                    line_slope=float(pending_entry["slope"]),
                    raw_entry_price=raw_entry,
                    entry_price=entry_fill,
                    initial_stop=initial_stop,
                    initial_risk=initial_risk,
                    atr_at_entry=risk_atr,
                    target_price=entry_fill + target_r * initial_risk,
                    pullback_low=pb_low,
                    lowest_price=entry_fill,
                    highest_price=entry_fill,
                )
            pending_entry = None
            reset_setup()

        # --- A3) intrabar management of an open position ---------------------------------
        if position is not None:
            if exit_mode == "trailing_swinglow":
                swing_low = latest_confirmed_swing_low(index)
                if swing_low is not None:
                    position.trailing_stop = (
                        swing_low if position.trailing_stop is None else max(position.trailing_stop, swing_low)
                    )
            active_stop = position.initial_stop
            if exit_mode == "trailing_swinglow" and position.trailing_stop is not None:
                active_stop = max(active_stop, position.trailing_stop)

            exited = False
            if low[index] <= active_stop:  # stop priority over target within the bar
                reason = "trailing_stop" if active_stop > position.initial_stop else "initial_stop"
                position.highest_price = max(position.highest_price, high[index])
                position.lowest_price = min(position.lowest_price, active_stop)
                trades.append(record(position, bar, timestamp, active_stop, reason))
                position = None
                exited = True
            elif exit_mode == "fixed_2r" and high[index] >= position.target_price:
                position.highest_price = max(position.highest_price, position.target_price)
                position.lowest_price = min(position.lowest_price, low[index])
                trades.append(record(position, bar, timestamp, position.target_price, "fixed_target_2r"))
                position = None
                exited = True

            if not exited and position is not None:
                position.lowest_price = min(position.lowest_price, low[index])
                position.highest_price = max(position.highest_price, high[index])
                if not position.reached_one_r and position.highest_price - position.entry_price >= position.initial_risk:
                    position.reached_one_r = True
                    position.one_r_time = timestamp
                if trend_invalidated:
                    trades.append(record(position, bar, timestamp, close[index], "hourly_ma_break"))
                    position = None
                    exited = True
                elif index - position.entry_index >= time_stop_bars and not position.reached_one_r:
                    trades.append(record(position, bar, timestamp, close[index], "time_stop"))
                    position = None
                    exited = True
            if exited:
                reset_setup()

        # --- B) setup state machine (only when flat) -------------------------------------
        if position is None and pending_entry is None:
            if not trend_ok:
                reset_setup()
            else:
                if bool(bar["cross_above_zero"]):
                    last_up_leg_start = index

                if state == 0:
                    if bool(bar["cross_below_zero"]):
                        start = max(last_up_leg_start, index - max_h1_distance)
                        segment = high[start : index + 1]
                        h1_rel = int(np.argmax(segment))
                        h1_index = start + h1_rel
                        h1_price = float(high[h1_index])
                        pullback_low = float(low[index])
                        state = 1
                elif state == 1:
                    pullback_low = min(pullback_low, float(low[index]))
                    if bool(bar["cross_above_zero"]):
                        # Pullback resolved upward before any sub-zero golden cross → no setup.
                        reset_setup()
                    elif bool(bar["golden_cross_below"]):
                        state = 2
                        golden_index = index
                elif state == 2:
                    pullback_low = min(pullback_low, float(low[index]))
                    # Once armed, only the spec's disarm rules apply (a DIF rise back above
                    # zero is normal as the down-line breaks and must NOT disarm the setup).
                    if bool(bar["death_cross_below"]):
                        state = 1  # keep H1, wait for the next golden cross
                        golden_index = None
                    elif golden_index is not None and index - golden_index > disarm_bars:
                        reset_setup()

            # Armed: build/evaluate the downtrend line and test the breakout.
            if state == 2 and h1_index is not None and pd.notna(atr) and atr > 0:
                h2 = confirmed_swing_high_h2(h1_index, index)
                if h2 is not None:
                    h2_index, h2_price = h2
                    distance = index - h1_index
                    slope = (h2_price - h1_price) / (h2_index - h1_index)
                    line_now = line_value_at(h1_index, h1_price, slope, index)
                    slope_ok = (slope / atr) <= slope_atr_max
                    distance_ok = min_h1_distance <= distance <= max_h1_distance
                    prior_breached = any(
                        close[j] > line_value_at(h1_index, h1_price, slope, j)
                        for j in range(h1_index + 1, index)
                    )
                    frame.at[index, "h2_index"] = h2_index
                    frame.at[index, "line_value"] = line_now
                    key = (h1_index, h2_index)
                    if slope_ok and distance_ok:
                        upsert_trendline(key, h2_index, h2_price, slope, index, "armed")
                        breakout = close[index] > line_now + buffer_atr * atr
                        depth_ok = True
                        if pullback_depth_atr > 0 and pd.notna(bar["hourly_ma"]) and pd.notna(bar["hourly_atr"]):
                            depth_ok = pullback_low >= float(bar["hourly_ma"]) - pullback_depth_atr * float(bar["hourly_atr"])
                        if breakout and not prior_breached and depth_ok and index < n - 1:
                            frame.at[index, "entry_signal"] = True
                            trendlines[key]["status"] = "entered"
                            trendlines[key]["end_index"] = index
                            trendlines[key]["end_time"] = ts(index)
                            pending_entry = {
                                "signal_time": timestamp,
                                "h1_time": ts(h1_index),
                                "h2_time": ts(h2_index),
                                "slope": slope,
                                "risk_atr": float(atr),
                                "pullback_low": float(pullback_low),
                            }

        frame.at[index, "setup_state"] = state
        if h1_index is not None:
            frame.at[index, "h1_index"] = h1_index

    # Finalise any unresolved trend lines and close any still-open position.
    for line in trendlines.values():
        if line["status"] == "armed":
            line["status"] = "unresolved"
    if position is not None:
        last = frame.iloc[-1]
        raw_exit = float(last["close"])
        position.lowest_price = min(position.lowest_price, float(last["low"]))
        position.highest_price = max(position.highest_price, float(last["high"]))
        trades.append(record(position, last, pd.Timestamp(last["timestamp"]), raw_exit, "data_end"))

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

    if trendlines:
        line_frame = pd.DataFrame(
            [
                {
                    "h1_time": line["h1_time"], "h1_price": line["h1_price"],
                    "h2_time": line["h2_time"], "h2_price": line["h2_price"], "slope": line["slope"],
                    "start_time": line["start_time"], "end_time": line["end_time"],
                    "end_price": line["h1_price"] + line["slope"] * (line["end_index"] - line["h1_index"]),
                    "status": line["status"],
                }
                for line in trendlines.values()
            ]
        ).reindex(columns=TRENDLINE_COLUMNS)
    else:
        line_frame = pd.DataFrame(columns=TRENDLINE_COLUMNS)

    return trade_frame, frame, line_frame


# --------------------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------------------
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
    lines: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    metric = lambda name, default=0: summary.get(name, default)
    rows = "| - | - | - | - | - | - | No trade |"
    if not trades.empty:
        rows = "\n".join(
            f"| {row.trade_number} | {row.entry_time:%Y-%m-%d %H:%M} @ {row.entry_price:.1f} | "
            f"{row.exit_time:%Y-%m-%d %H:%M} @ {row.exit_price:.1f} | {row.net_usdt:.2f} | "
            f"{row.net_r:.2f} | {row.exit_reason} |"
            for row in trades.itertuples(index=False)
        )
    exit_counts = trades["exit_reason"].value_counts() if not trades.empty else pd.Series(dtype=int)
    exit_lines = "\n".join(f"- `{name}`: {count}" for name, count in exit_counts.items()) or "- no trades"
    status_counts = lines["status"].value_counts() if not lines.empty else pd.Series(dtype=int)
    line_lines = "\n".join(f"- `{name}`: {count}" for name, count in status_counts.items()) or "- no trend lines"
    warmup_text = ", ".join(warmup_months) if warmup_months else "none"
    text = f"""# BTCUSDT 1h-trend + 15m MACD trend-line breakout (LONG) — {month}

## Data & Setup

- Backtest month: `{month}` (UTC); warm-up months: {warmup_text}.
- Hourly bars in span: {hourly_rows:,}; simulated 15m bars (target month): {bar_rows:,}.
- Costs: slippage `{args.slippage_bps:g}` bps/side, taker fee `{args.taker_fee_rate:.4%}`, size `{args.position_btc:g}` BTC.
- Trend filter: last closed 1h close > MA({args.ma_length}) and the last `{args.bars_above_ma}` 15m closes all above that 1h MA.
- Pullback: 15m MACD({args.macd_fast},{args.macd_slow},{args.macd_signal}) DIF below zero; golden cross below zero arms the setup.
- Trend line through H1 and the most recent confirmed swing high (k={args.swing_k}) below H1; valid when slope/ATR({args.atr_length}) ≤ `{args.slope_atr_max:g}`, H1 distance `{args.min_h1_distance}`–`{args.max_h1_distance}` bars, and no prior close has breached it.
- Entry: 15m close > line + `{args.buffer_atr:g} × ATR(15m)`; long filled on the next 15m open.
- Disarm after `{args.disarm_bars}` bars without a breakout; sub-zero death cross returns to pullback; 1h filter failure resets.
- Exit mode: `{args.exit_mode}`. Initial stop = nearer of pullback low / `{args.stop_atr:g} × ATR(15m)` below entry (= 1R); fixed target `{args.target_r:g}R`; 1h close below MA exits; time stop `{args.time_stop_bars}` bars without 1R.
- Pullback-depth filter: {"off" if args.pullback_depth_atr <= 0 else f"low ≥ 1h MA − {args.pullback_depth_atr:g} × ATR(1h)"}.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | {len(lines)} |
| Entry signals | {int(bars['entry_signal'].sum())} |
| DIF sub-zero crosses | {int(bars['cross_below_zero'].sum())} |
| Sub-zero golden crosses | {int(bars['golden_cross_below'].sum())} |

### Trend-line outcomes

{line_lines}

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

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
{rows}

## Notes

- 15m OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, swing pivots are consumed only after their k-bar confirmation, and each 15m bar sees only the previously closed 1h bar.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_html_report(
    path: Path,
    month: str,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    lines: pd.DataFrame,
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
            "15m candles, drawn trend lines, and trades",
            "MACD (DIF / DEA)",
            "Closed-trade net equity (USDT)",
            "Trade ledger",
        ),
    )
    figure.add_trace(
        go.Candlestick(
            x=bars["timestamp"], open=bars["open"], high=bars["high"], low=bars["low"],
            close=bars["close"], name="BTCUSDT 15m",
        ), row=1, col=1,
    )
    # Last-closed 1h MA(20), stepped across the 15m bars it governs.
    if "hourly_ma" in bars.columns:
        figure.add_trace(
            go.Scatter(
                x=bars["timestamp"], y=bars["hourly_ma"], mode="lines", name="1h MA20",
                line={"color": "#fb8c00", "width": 1.6, "shape": "hv"},
                hovertemplate="1h MA20<br>%{x}<br>%{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
    # Every drawn trend line, coloured by outcome.
    status_color = {"entered": "#2e7d32", "unresolved": "#90a4ae", "death_cross": "#8d6e63"}
    legend_seen: set[str] = set()
    for line in lines.itertuples(index=False):
        color = status_color.get(line.status, "#b0bec5")
        show = line.status not in legend_seen
        legend_seen.add(line.status)
        figure.add_trace(
            go.Scatter(
                x=[line.h1_time, line.end_time], y=[line.h1_price, line.end_price], mode="lines",
                line={"color": color, "width": 1.4, "dash": "solid" if line.status == "entered" else "dot"},
                name=f"line ({line.status})", legendgroup=line.status, showlegend=show,
                hovertemplate=f"trend line ({line.status})<br>slope %{{customdata:.3f}}<extra></extra>",
                customdata=[line.slope, line.slope],
            ), row=1, col=1,
        )
    if not lines.empty:
        figure.add_trace(
            go.Scatter(
                x=lines["h1_time"], y=lines["h1_price"], mode="markers", name="H1",
                marker={"symbol": "circle", "size": 7, "color": "#ef6c00"},
                hovertemplate="H1<br>%{x}<br>%{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=lines["h2_time"], y=lines["h2_price"], mode="markers", name="H2",
                marker={"symbol": "circle-open", "size": 7, "color": "#ef6c00"},
                hovertemplate="H2<br>%{x}<br>%{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["entry_time"], y=trades["raw_entry_price"], mode="markers", name="Long entry",
                marker={"symbol": "triangle-up", "size": 13, "color": "#6a1b9a"},
                hovertemplate="entry<br>%{x}<br>%{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit",
                marker={"symbol": "x", "size": 11, "color": "#00897b"}, text=trades["exit_reason"],
                hovertemplate="%{text}<br>%{x}<br>%{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
    figure.add_trace(
        go.Scatter(x=bars["timestamp"], y=bars["dif"], mode="lines", name="DIF", line={"color": "#1565c0"}),
        row=2, col=1,
    )
    figure.add_trace(
        go.Scatter(x=bars["timestamp"], y=bars["dea"], mode="lines", name="DEA", line={"color": "#e53935"}),
        row=2, col=1,
    )
    figure.add_hline(y=0, line={"color": "#9e9e9e", "width": 1, "dash": "dash"}, row=2, col=1)
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["cumulative_net_usdt"], mode="lines+markers",
                name="Net cumulative P&L", line={"color": "#3949ab", "width": 2},
                fill="tozeroy", fillcolor="rgba(57,73,171,0.10)",
            ), row=3, col=1,
        )
        table_values = [
            trades["trade_number"].tolist(),
            trades["entry_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["exit_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["net_usdt"].map(lambda value: f"{value:.2f}").tolist(),
            trades["net_r"].map(lambda value: f"{value:.2f}").tolist(),
            trades["exit_reason"].tolist(),
        ]
    else:
        table_values = [["-"], ["No trade"], ["-"], ["-"], ["-"], ["-"]]
    figure.add_trace(
        go.Table(
            header={
                "values": ["#", "Entry", "Exit", "Net USDT", "Net R", "Exit reason"],
                "fill_color": "#263238", "font": {"color": "white"}, "align": "left",
            },
            cells={"values": table_values, "fill_color": "#f7f9fb", "align": "left", "height": 25},
        ), row=4, col=1,
    )
    title = (
        f"BTCUSDT {month} 15m MACD trend-line LONG | Trades {metric('trades')} · "
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
    figure.update_yaxes(title_text="MACD", row=2, col=1)
    figure.update_yaxes(title_text="Net USDT", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True, full_html=True)


# --------------------------------------------------------------------------------------
# Orchestration
# --------------------------------------------------------------------------------------
def run_month(month: str, args: argparse.Namespace) -> dict[str, object]:
    span_months = month_range(
        f"{(pd.Period(month, freq='M') - args.warmup_months)}", month
    ) if args.warmup_months > 0 else [month]
    warmup_months = span_months[:-1]

    hourly_raw = load_span(args.bars_dir, span_months, "1h")
    hourly = add_hourly_features(hourly_raw, args.ma_length, args.atr_length)

    bars = load_span(args.bars_dir, span_months, "15m")
    bars = add_15m_features(bars, args.macd_fast, args.macd_slow, args.macd_signal, args.atr_length, args.swing_k)
    bars = attach_hourly_features(bars, hourly).sort_values("timestamp", kind="stable").reset_index(drop=True)
    bars = add_trend_filter(bars, args.bars_above_ma)

    month_period = pd.Period(month, freq="M")
    month_start = pd.Timestamp(month_period.start_time, tz="UTC")
    month_end = pd.Timestamp(month_period.end_time, tz="UTC")
    month_mask = (bars["timestamp"] >= month_start) & (bars["timestamp"] <= month_end)
    month_bars = bars[month_mask].reset_index(drop=True)
    if month_bars.empty:
        raise ValueError(f"no 15m bars fall inside {month}")

    trades, bar_state, lines = backtest_strategy(
        month_bars, args.exit_mode, args.swing_k, args.slope_atr_max,
        args.min_h1_distance, args.max_h1_distance, args.buffer_atr, args.disarm_bars,
        args.stop_atr, args.target_r, args.time_stop_bars, args.pullback_depth_atr,
        args.slippage_bps, args.taker_fee_rate, args.position_btc,
    )
    summary = performance_summary(trades)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"BTCUSDT_{month}_macd_trendline_long"
    hourly.to_csv(args.output_dir / f"{stem}_hourly.csv", index=False, encoding="utf-8-sig")
    bar_state.to_csv(args.output_dir / f"{stem}_bar_state.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(args.output_dir / f"{stem}_trades.csv", index=False, encoding="utf-8-sig")
    lines.to_csv(args.output_dir / f"{stem}_trendlines.csv", index=False, encoding="utf-8-sig")
    write_markdown_report(
        args.doc_dir / f"btcusdt_{month.replace('-', '')}_macd_trendline_long_backtest.md",
        args, month, warmup_months, len(hourly), len(month_bars),
        bar_state, trades, lines, summary,
    )
    write_html_report(
        args.output_dir / f"{stem}_backtest.html",
        month, bar_state, trades, lines, summary,
    )
    print(
        f"{month}: warmup={warmup_months or 'none'} hourly={len(hourly)} bars={len(month_bars)} "
        f"lines={len(lines)} trades={summary['trades']} net_usdt={float(summary.get('net_usdt', 0)):,.2f}"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest the BTCUSDT 1h-trend / 15m MACD trend-line breakout long strategy per month."
    )
    parser.add_argument("--bars-dir", type=Path, default=DEFAULT_BARS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-dir", type=Path, default=DEFAULT_DOC_DIR)
    parser.add_argument("--start-month", type=parse_month, default=DEFAULT_START_MONTH)
    parser.add_argument("--end-month", type=parse_month, default=DEFAULT_END_MONTH)
    parser.add_argument("--warmup-months", type=int, default=1)
    parser.add_argument("--ma-length", type=int, default=20)
    parser.add_argument("--bars-above-ma", type=int, default=7,
                        help="consecutive 15m closes required above the 1h MA to allow the setup")
    parser.add_argument("--macd-fast", type=int, default=12)
    parser.add_argument("--macd-slow", type=int, default=26)
    parser.add_argument("--macd-signal", type=int, default=9)
    parser.add_argument("--atr-length", type=int, default=14)
    parser.add_argument("--swing-k", type=int, default=2)
    parser.add_argument("--slope-atr-max", type=float, default=-0.03)
    parser.add_argument("--min-h1-distance", type=int, default=6)
    parser.add_argument("--max-h1-distance", type=int, default=40)
    parser.add_argument("--buffer-atr", type=float, default=0.15)
    parser.add_argument("--disarm-bars", type=int, default=20)
    parser.add_argument("--stop-atr", type=float, default=1.5)
    parser.add_argument("--target-r", type=float, default=2.0)
    parser.add_argument("--time-stop-bars", type=int, default=24)
    parser.add_argument("--pullback-depth-atr", type=float, default=0.0, help="0 disables the optional 1h pullback-depth filter")
    parser.add_argument("--exit-mode", choices=EXIT_MODES, default="fixed_2r")
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0004)
    parser.add_argument("--position-btc", type=float, default=1.0)
    args = parser.parse_args()
    if pd.Period(args.end_month, freq="M") < pd.Period(args.start_month, freq="M"):
        parser.error("--end-month must be on or after --start-month")
    if args.warmup_months < 0:
        parser.error("--warmup-months must be non-negative")
    positive_lengths = (
        args.ma_length, args.bars_above_ma, args.macd_fast, args.macd_slow, args.macd_signal,
        args.atr_length, args.swing_k, args.min_h1_distance, args.disarm_bars, args.time_stop_bars,
    )
    if min(positive_lengths) < 1:
        parser.error("all lengths must be positive")
    if args.max_h1_distance < args.min_h1_distance:
        parser.error("--max-h1-distance must be >= --min-h1-distance")
    if args.macd_slow <= args.macd_fast:
        parser.error("--macd-slow must exceed --macd-fast")
    if args.slope_atr_max >= 0:
        parser.error("--slope-atr-max must be negative (down-sloping line)")
    if min(args.buffer_atr, args.stop_atr, args.target_r, args.pullback_depth_atr, args.slippage_bps, args.taker_fee_rate, args.position_btc) < 0:
        parser.error("buffer, stop, target, depth, slippage, fee and size must be non-negative")
    args.bars_dir = args.bars_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    args.doc_dir = args.doc_dir.resolve()
    return args


def main() -> None:
    args = parse_args()
    for month in month_range(args.start_month, args.end_month):
        run_month(month, args)


if __name__ == "__main__":
    main()
