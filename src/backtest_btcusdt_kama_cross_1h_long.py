#!/usr/bin/env python
"""Backtest the BTCUSDT KAMA(20)/KAMA(140) crossover long strategy on 1-hour bars.

A pure adaptive-moving-average trend follower, in contrast to the structure/
mean-reversion scripts beside it (``backtest_btcusdt_hourly_resistance_utbot_3m_short``
and its long twin). There are no support/resistance zones, no UT Bot, no Supertrend
and no 3-minute execution leg:

- **Entry**  KAMA(20) crosses above KAMA(140) *and* the signal bar's close is above
  SMA(200) of the open. Filled at the next 1-hour open.
- **Exit**   KAMA(20) crosses below KAMA(140). Filled at the next 1-hour open.

Two regime gates and two protective stops are available, selected by flag.

The trend gate defaults to ``--trend-filter slope`` (the MA must be *rising*) rather than
the original ``price`` (close above the MA). On this data the price gate is nearly inert:
it rejected only 4 of 32 bullish crosses, because a KAMA bullish cross happens on a bounce,
which is exactly when price regains the MA — gate and signal move together. Requiring the
MA itself to rise decorrelates them, and improved net P&L on 8 of 9 (fast, slow) pairs tested.

``--trailing-atr`` and ``--breakeven-after-r`` are **off by default**, because measurement
says they do not help here: median MFE is ~1.5% while hourly ATR(20) is ~0.6%, so the whole
move a signal captures is only ~2.5 ATR. Any stop tight enough to protect it is inside the
hourly noise, and any stop loose enough to survive the noise never binds. Switching them on
does cut drawdown, but only by cutting time in market from ~18% to ~2% — it stops the
strategy trading rather than making it trade better.

KAMA is a faithful port of the Pine v4 "Kaufman Adaptive Moving Average" study by
Alex Orekhov (everget), GPL-3.0 — see :func:`pine_kama`. Note its ``nz(kama[1], src)``
seed: the series is never NaN and starts *at the price*, so both KAMAs begin life on
top of each other and cross on noise for the first stretch of data. ``--warmup-bars``
exists to discard those seeding artifacts and is not optional in spirit.

Reads the committed 1h bar CSVs produced by ``preprocess_btcusdt_bars.py``
(``data/btcusdt_bars/BTCUSDT_YYYY-MM_1h.csv``). Unlike the per-month scripts, the whole
requested span is simulated as **one continuous series** so that multi-week trend trades
survive month boundaries; a per-month P&L breakdown is reported separately.

BTCUSDT trades continuously (24/7); every bar is ``session_id = "continuous"``. Costs
follow the Binance-perp model of the other BTC scripts: per-side slippage in basis
points plus a taker fee, with P&L reported in USDT for a fixed BTC size.
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
DEFAULT_START_MONTH = "2026-01"
DEFAULT_END_MONTH = "2026-08"
PRICE_SOURCES = ("open", "high", "low", "close")
TREND_FILTERS = ("slope", "price", "both", "none")


TRADE_COLUMNS = [
    "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
    "entry_type", "raw_entry_price", "entry_price", "raw_exit_price", "exit_price",
    "bars_held", "hours_held", "kama_fast_at_entry", "kama_slow_at_entry", "ma200_at_entry",
    "atr_at_entry", "risk_reference", "one_r_time", "trailing_stop_at_exit",
    "gross_points", "net_points",
    "entry_fee_usdt", "exit_fee_usdt", "gross_usdt", "net_usdt", "gross_r", "net_r",
    "mfe_points", "mae_points", "exit_reason",
    "cumulative_gross_usdt", "cumulative_net_usdt", "gross_drawdown_usdt", "net_drawdown_usdt",
]


@dataclass
class Position:
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    entry_type: str
    entry_index: int
    raw_entry_price: float
    entry_price: float
    atr_at_entry: float
    risk_reference: float
    kama_fast_at_entry: float
    kama_slow_at_entry: float
    ma200_at_entry: float
    lowest_price: float
    highest_price: float
    reached_one_r: bool = False
    one_r_time: pd.Timestamp | None = None
    profit_locked: bool = False
    breakeven_stop: float | None = None
    trailing_stop: float | None = None

    def active_stop(self) -> float | None:
        """Tightest armed protective stop (the highest one, for a long). None if unarmed."""
        armed = [stop for stop in (self.breakeven_stop, self.trailing_stop) if stop is not None]
        return max(armed) if armed else None


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


def load_bars(bars_dir: Path, month: str, timeframe: str = "1h") -> pd.DataFrame:
    path = bars_dir / f"BTCUSDT_{month}_{timeframe}.csv"
    if not path.is_file():
        raise FileNotFoundError(f"missing bar file: {path}")
    time_columns = ["timestamp", "hour_start" if timeframe == "1h" else "minute_start"]
    frame = pd.read_csv(path)
    for column in time_columns:
        frame[column] = pd.to_datetime(frame[column], utc=True, format="ISO8601")
    return frame


def load_span(bars_dir: Path, months: list[str], timeframe: str = "1h") -> pd.DataFrame:
    frames = [load_bars(bars_dir, month, timeframe) for month in months]
    return pd.concat(frames, ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)


def pine_kama(
    values: pd.Series,
    length: int,
    fast_length: int = 2,
    slow_length: int = 30,
) -> tuple[pd.Series, pd.Series]:
    """Port of the Pine v4 "Kaufman Adaptive Moving Average" (everget, GPL-3.0).

    ::

        mom        = abs(change(src, length))
        volatility = sum(abs(change(src)), length)
        er         = volatility != 0 ? mom / volatility : 0
        alpha      = pow(er * (fastAlpha - slowAlpha) + slowAlpha, 2)
        kama      := alpha * src + (1 - alpha) * nz(kama[1], src)

    Returns ``(kama, er)``. Two Pine behaviours are deliberately preserved:

    * ``nz(kama[1], src)`` seeds the recursion from the price itself, so bar 0 collapses
      to ``src[0]`` and the output has **no NaN prefix** (unlike :func:`pine_rma`).
    * ``mom`` and ``volatility`` are ``na`` until index ``length``, and Pine's ternary
      takes the false branch on an ``na`` comparison, so ``er = 0`` and
      ``alpha = slowAlpha ** 2`` across indices ``0 … length - 1``.
    """
    if length < 1:
        raise ValueError("length must be at least 1")
    if fast_length < 1:
        raise ValueError("fast_length must be at least 1")
    if slow_length <= fast_length:
        raise ValueError("slow_length must exceed fast_length")

    source = pd.to_numeric(values, errors="coerce").astype(float)
    momentum = (source - source.shift(length)).abs()
    volatility = source.diff().abs().rolling(length).sum()
    efficiency = (momentum / volatility).where(volatility.notna() & (volatility != 0), 0.0)
    efficiency = efficiency.fillna(0.0)

    fast_alpha = 2.0 / (fast_length + 1)
    slow_alpha = 2.0 / (slow_length + 1)
    alpha = (efficiency * (fast_alpha - slow_alpha) + slow_alpha) ** 2

    output = pd.Series(np.nan, index=source.index, dtype=float)
    previous = np.nan
    for position in range(len(source)):
        price = source.iloc[position]
        if pd.isna(price):
            output.iloc[position] = previous
            continue
        weight = float(alpha.iloc[position])
        base = price if pd.isna(previous) else previous
        previous = weight * price + (1.0 - weight) * base
        output.iloc[position] = previous
    return output, efficiency


def add_kama_features(
    hourly: pd.DataFrame,
    kama_fast_length: int = 20,
    kama_slow_length: int = 140,
    kama_fast_const: int = 2,
    kama_slow_const: int = 30,
    kama_source: str = "close",
    ma200_length: int = 200,
    ma200_source: str = "open",
    ma200_slope_hours: int = 24,
    risk_atr_length: int = 20,
) -> pd.DataFrame:
    """Attach the KAMA pair, the SMA(200) trend gate, the cross flags, and the risk ATR."""
    if kama_slow_length <= kama_fast_length:
        raise ValueError("kama_slow_length must exceed kama_fast_length")
    if min(ma200_length, risk_atr_length, ma200_slope_hours) < 1:
        raise ValueError("ma200_length, ma200_slope_hours and risk_atr_length must be positive")
    for name, column in (("kama_source", kama_source), ("ma200_source", ma200_source)):
        if column not in hourly.columns:
            raise ValueError(f"{name} {column!r} is not a column of the bar frame")

    result = hourly.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    result["kama_fast"], result["er_fast"] = pine_kama(
        result[kama_source], kama_fast_length, kama_fast_const, kama_slow_const
    )
    result["kama_slow"], result["er_slow"] = pine_kama(
        result[kama_source], kama_slow_length, kama_fast_const, kama_slow_const
    )
    result["kama_spread"] = result["kama_fast"] - result["kama_slow"]
    result["ma200"] = (
        result[ma200_source].rolling(ma200_length, min_periods=ma200_length).mean()
    )
    # A NaN ma200 compares False, so the gate closes on its own during warm-up.
    result["above_ma200"] = result["close"] > result["ma200"]
    # Slope of the MA itself, in percent over ``ma200_slope_hours`` — a trend-direction
    # read that does not move in lockstep with the KAMA cross the way price-vs-MA does.
    result["ma200_slope"] = (
        result["ma200"] / result["ma200"].shift(ma200_slope_hours) - 1.0
    ) * 100.0

    previous_fast = result["kama_fast"].shift(1)
    previous_slow = result["kama_slow"].shift(1)
    ready = (
        result["kama_fast"].notna() & result["kama_slow"].notna()
        & previous_fast.notna() & previous_slow.notna()
    )
    result["kama_cross_up"] = (
        ready & (result["kama_fast"] > result["kama_slow"]) & (previous_fast <= previous_slow)
    )
    result["kama_cross_down"] = (
        ready & (result["kama_fast"] < result["kama_slow"]) & (previous_fast >= previous_slow)
    )
    result["risk_atr"] = pine_atr(result, risk_atr_length)
    return result


def _trade_record(
    position: Position,
    bar: pd.Series,
    exit_time: pd.Timestamp,
    raw_exit_price: float,
    exit_reason: str,
    exit_index: int,
    slippage_bps: float,
    taker_fee_rate: float,
    position_btc: float,
) -> dict[str, object]:
    slip = slippage_bps / 10_000.0
    exit_fill = raw_exit_price * (1 - slip)  # long exit is a sell -> filled lower
    entry_fee = position.entry_price * position_btc * taker_fee_rate
    exit_fee = exit_fill * position_btc * taker_fee_rate
    gross_points = raw_exit_price - position.raw_entry_price
    net_points = exit_fill - position.entry_price
    gross_usdt = gross_points * position_btc
    net_usdt = net_points * position_btc - entry_fee - exit_fee
    risk = position.risk_reference
    scalable = pd.notna(risk) and risk > 0
    return {
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": exit_time,
        "entry_session": position.entry_session,
        "exit_session": str(bar["session_id"]),
        "entry_type": position.entry_type,
        "raw_entry_price": position.raw_entry_price,
        "entry_price": position.entry_price,
        "raw_exit_price": raw_exit_price,
        "exit_price": exit_fill,
        "bars_held": exit_index - position.entry_index,
        "hours_held": (exit_time - position.entry_time).total_seconds() / 3600.0,
        "kama_fast_at_entry": position.kama_fast_at_entry,
        "kama_slow_at_entry": position.kama_slow_at_entry,
        "ma200_at_entry": position.ma200_at_entry,
        "atr_at_entry": position.atr_at_entry,
        "risk_reference": risk,
        "one_r_time": position.one_r_time,
        "trailing_stop_at_exit": position.trailing_stop,
        "gross_points": gross_points,
        "net_points": net_points,
        "entry_fee_usdt": entry_fee,
        "exit_fee_usdt": exit_fee,
        "gross_usdt": gross_usdt,
        "net_usdt": net_usdt,
        # No stop exists, so 1R is the hourly ATR at the signal bar, not a stop distance.
        "gross_r": gross_points / risk if scalable else np.nan,
        "net_r": net_points / risk if scalable else np.nan,
        "mfe_points": position.highest_price - position.entry_price,
        "mae_points": position.lowest_price - position.entry_price,
        "exit_reason": exit_reason,
    }


def backtest_strategy(
    bar_frame: pd.DataFrame,
    warmup_bars: int = 340,
    trend_filter: str = "slope",
    min_ma200_slope: float = 0.0,
    min_entry_er: float = 0.30,
    trailing_atr: float = 0.0,
    breakeven_after_r: float = 0.0,
    slippage_bps: float = 1.0,
    taker_fee_rate: float = 0.0004,
    position_btc: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long-only KAMA crossover state machine on 1-hour bars.

    Signals are read at the bar close and filled at the *next* bar's open, which is what
    keeps the simulation free of look-ahead. One position at a time; a bullish cross while
    already long is ignored. ``warmup_bars`` gates **entries only**, so an exit can never
    be stranded by it.

    Two optional protections sit on top of the bare crossover, both disabled by passing 0:

    ``breakeven_after_r``
        Once unrealised profit reaches N x the ATR risk reference, ratchet a stop to the
        price at which the round trip nets zero after fees and slippage, so a trade that
        ran in profit cannot come back as a loss.
    ``trailing_atr``
        Once the trade has reached 1R, trail a stop at ``highest_price - N x ATR``,
        ratcheting up only. This is what caps the give-back between MFE and the exit.

    ``trend_filter`` selects the entry regime gate: ``"price"`` (close above the MA),
    ``"slope"`` (the MA itself rising by at least ``min_ma200_slope`` percent),
    ``"both"``, or ``"none"``.

    ``min_entry_er`` is the chop filter. At the bar of a crossover the two KAMAs are by
    definition nearly coincident, so the spread carries no information there and cannot be
    thresholded; what separates a decisive cross from a whipsaw is whether the market is
    *trending at all*. KAMA already measures exactly that — its efficiency ratio — so the
    gate reuses ``er_fast`` rather than adding an indicator. Set 0 to disable.
    """
    if warmup_bars < 0:
        raise ValueError("warmup_bars must be non-negative")
    if trend_filter not in TREND_FILTERS:
        raise ValueError(f"trend_filter must be one of {TREND_FILTERS}")
    if not 0.0 <= min_entry_er <= 1.0:
        raise ValueError("min_entry_er must be between 0 and 1")
    if min(trailing_atr, breakeven_after_r) < 0:
        raise ValueError("trailing_atr and breakeven_after_r must be non-negative")
    if min(slippage_bps, taker_fee_rate, position_btc) < 0:
        raise ValueError("slippage, fee, and size must be non-negative")

    slip = slippage_bps / 10_000.0
    frame = bar_frame.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    for column in ("entry_signal", "exit_signal", "in_position", "warming_up", "trend_ok", "er_ok"):
        frame[column] = False
    frame["stop_level"] = np.nan

    def er_ok(bar: pd.Series) -> bool:
        if min_entry_er <= 0:
            return True
        value = bar["er_fast"] if "er_fast" in bar.index else np.nan
        return bool(pd.notna(value) and float(value) >= min_entry_er)

    def trend_ok(bar: pd.Series) -> bool:
        if trend_filter == "none":
            return True
        price_ok = bool(bar["above_ma200"])
        slope = bar["ma200_slope"] if "ma200_slope" in bar.index else np.nan
        slope_ok = bool(pd.notna(slope) and float(slope) >= min_ma200_slope)
        if trend_filter == "price":
            return price_ok
        if trend_filter == "slope":
            return slope_ok
        return price_ok and slope_ok

    trades: list[dict[str, object]] = []
    position: Position | None = None
    pending_entry: dict[str, object] | None = None
    pending_exit: dict[str, object] | None = None
    last_index = len(frame) - 1

    def record(pos: Position, bar: pd.Series, exit_time, raw_exit, reason, exit_index) -> dict[str, object]:
        return _trade_record(
            pos, bar, exit_time, raw_exit, reason, exit_index,
            slippage_bps, taker_fee_rate, position_btc,
        )

    for index, bar in frame.iterrows():
        bar_start = pd.Timestamp(bar["hour_start"])
        timestamp = pd.Timestamp(bar["timestamp"])
        raw_open = float(bar["open"])
        frame.at[index, "warming_up"] = index < warmup_bars
        frame.at[index, "trend_ok"] = trend_ok(bar)
        frame.at[index, "er_ok"] = er_ok(bar)

        # Exit before entry, so a bearish cross then a bullish cross flips cleanly.
        if pending_exit is not None:
            if position is not None:
                trades.append(
                    record(position, bar, bar_start, raw_open, str(pending_exit["reason"]), index)
                )
                position = None
            pending_exit = None

        if pending_entry is not None:
            if position is None:
                entry_fill = raw_open * (1 + slip)  # long entry is a buy -> filled higher
                position = Position(
                    signal_time=pd.Timestamp(pending_entry["signal_time"]),
                    entry_time=bar_start,
                    entry_session=str(bar["session_id"]),
                    entry_type=str(pending_entry["entry_type"]),
                    entry_index=index,
                    raw_entry_price=raw_open,
                    entry_price=entry_fill,
                    atr_at_entry=float(pending_entry["risk_atr"]),
                    risk_reference=float(pending_entry["risk_atr"]),
                    kama_fast_at_entry=float(pending_entry["kama_fast"]),
                    kama_slow_at_entry=float(pending_entry["kama_slow"]),
                    ma200_at_entry=float(pending_entry["ma200"]),
                    lowest_price=entry_fill,
                    highest_price=entry_fill,
                )
            pending_entry = None

        # Protective stops are checked before this bar can move them, so a stop derived
        # from this bar's high can never also be triggered by this bar's low.
        if position is not None:
            active = position.active_stop()
            if active is not None:
                trailing = position.trailing_stop if position.trailing_stop is not None else -np.inf
                reason = "breakeven_lock" if (
                    position.breakeven_stop is not None and position.breakeven_stop >= trailing
                ) else "atr_trailing_stop"
                if raw_open <= active:  # gapped straight through the stop
                    position.lowest_price = min(position.lowest_price, raw_open)
                    trades.append(record(position, bar, bar_start, raw_open, f"{reason}_gap", index))
                    position = None
                    pending_exit = None
                elif float(bar["low"]) <= active:
                    position.lowest_price = min(position.lowest_price, active)
                    trades.append(record(position, bar, timestamp, active, reason, index))
                    position = None
                    pending_exit = None

        if position is not None:
            position.highest_price = max(position.highest_price, float(bar["high"]))
            position.lowest_price = min(position.lowest_price, float(bar["low"]))
            frame.at[index, "in_position"] = True

            risk = position.risk_reference
            scalable = pd.notna(risk) and risk > 0
            gain = position.highest_price - position.entry_price
            if (
                breakeven_after_r > 0 and not position.profit_locked
                and scalable and gain >= breakeven_after_r * risk
            ):
                position.profit_locked = True
                position.breakeven_stop = (
                    position.entry_price * (1 + taker_fee_rate) / ((1 - taker_fee_rate) * (1 - slip))
                )
            if not position.reached_one_r and scalable and gain >= risk:
                position.reached_one_r = True
                position.one_r_time = timestamp
            if trailing_atr > 0 and position.reached_one_r and pd.notna(bar["risk_atr"]):
                candidate = position.highest_price - trailing_atr * float(bar["risk_atr"])
                position.trailing_stop = (
                    candidate if position.trailing_stop is None
                    else max(position.trailing_stop, candidate)
                )
            armed = position.active_stop()
            if armed is not None:
                frame.at[index, "stop_level"] = armed

        # Signals are evaluated on this bar's close; the final bar has no next open to fill.
        if index < last_index:
            if position is not None and bool(bar["kama_cross_down"]):
                frame.at[index, "exit_signal"] = True
                pending_exit = {"reason": "kama_bearish_cross"}
            if (
                position is None
                and pending_entry is None
                and index >= warmup_bars
                and bool(bar["kama_cross_up"])
                and trend_ok(bar)
                and er_ok(bar)
            ):
                frame.at[index, "entry_signal"] = True
                pending_entry = {
                    "signal_time": pd.Timestamp(bar["timestamp"]),
                    "entry_type": "kama_bullish_cross",
                    "risk_atr": float(bar["risk_atr"]) if pd.notna(bar["risk_atr"]) else np.nan,
                    "kama_fast": float(bar["kama_fast"]),
                    "kama_slow": float(bar["kama_slow"]),
                    "ma200": float(bar["ma200"]),
                }

    if position is not None and last_index >= 0:
        last = frame.iloc[-1]
        position.highest_price = max(position.highest_price, float(last["high"]))
        position.lowest_price = min(position.lowest_price, float(last["low"]))
        trades.append(
            record(position, last, pd.Timestamp(last["timestamp"]), float(last["close"]), "data_end", last_index)
        )

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
    return trade_frame, frame


def buy_hold_net_usdt(
    bars: pd.DataFrame,
    start_index: int,
    slippage_bps: float = 1.0,
    taker_fee_rate: float = 0.0004,
    position_btc: float = 1.0,
) -> float:
    """Buy the first tradable open, sell the final close, same cost model."""
    if bars.empty or start_index >= len(bars):
        return 0.0
    slip = slippage_bps / 10_000.0
    entry_fill = float(bars.iloc[start_index]["open"]) * (1 + slip)
    exit_fill = float(bars.iloc[-1]["close"]) * (1 - slip)
    fees = (entry_fill + exit_fill) * position_btc * taker_fee_rate
    return (exit_fill - entry_fill) * position_btc - fees


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
        "average_hours_held": float(trades["hours_held"].mean()),
        "largest_win_usdt": float(trades["net_usdt"].max()),
        "largest_loss_usdt": float(trades["net_usdt"].min()),
    }


def monthly_breakdown(trades: pd.DataFrame) -> pd.DataFrame:
    """Per-month P&L, attributing each trade to the month it exited in."""
    columns = ["month", "trades", "wins", "win_rate", "net_usdt", "cumulative_net_usdt"]
    if trades.empty:
        return pd.DataFrame(columns=columns)
    frame = trades.copy()
    # Months are UTC buckets; format explicitly rather than letting to_period drop the tz.
    frame["month"] = frame["exit_time"].dt.tz_convert("UTC").dt.strftime("%Y-%m")
    grouped = frame.groupby("month", sort=True).agg(
        trades=("net_usdt", "size"),
        wins=("net_usdt", lambda values: int((values > 0).sum())),
        net_usdt=("net_usdt", "sum"),
    ).reset_index()
    grouped["win_rate"] = grouped["wins"] / grouped["trades"] * 100.0
    grouped["cumulative_net_usdt"] = grouped["net_usdt"].cumsum()
    return grouped.reindex(columns=columns)


def write_markdown_report(
    path: Path,
    args: argparse.Namespace,
    span_label: str,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    monthly: pd.DataFrame,
    summary: dict[str, object],
    first_tradable: pd.Timestamp | None,
    hold_net: float,
) -> None:
    metric = lambda name, default=0: summary.get(name, default)
    rows = "| - | - | - | - | - | - | No trade |"
    if not trades.empty:
        rows = "\n".join(
            f"| {row.trade_number} | {row.entry_time:%Y-%m-%d %H:%M} @ {row.entry_price:,.1f} | "
            f"{row.exit_time:%Y-%m-%d %H:%M} @ {row.exit_price:,.1f} | {row.hours_held:,.0f} | "
            f"{row.net_usdt:,.2f} | {row.net_r:.2f} | {row.exit_reason} |"
            for row in trades.itertuples(index=False)
        )
    month_rows = "| - | - | - | - | - |"
    if not monthly.empty:
        month_rows = "\n".join(
            f"| {row.month} | {row.trades} | {row.wins} | {row.win_rate:.1f}% | {row.net_usdt:,.2f} |"
            for row in monthly.itertuples(index=False)
        )
    exit_counts = trades["exit_reason"].value_counts() if not trades.empty else pd.Series(dtype=int)
    exit_lines = "\n".join(f"- `{name}`: {count}" for name, count in exit_counts.items()) or "- no trades"
    tradable_text = "none" if first_tradable is None else f"{first_tradable:%Y-%m-%d %H:%M} UTC"
    trend_text = {
        "slope": f"SMA({args.ma200_length}) of `{args.ma200_source}` must be rising at least "
                 f"`{args.min_ma200_slope:g}%` over `{args.ma200_slope_hours}h`",
        "price": f"close must be above SMA({args.ma200_length}) of `{args.ma200_source}`",
        "both": f"close above SMA({args.ma200_length}) of `{args.ma200_source}` **and** that MA rising "
                f"at least `{args.min_ma200_slope:g}%` over `{args.ma200_slope_hours}h`",
        "none": "no regime filter",
    }[args.trend_filter]
    er_text = (
        "disabled — every crossover is taken." if args.min_entry_er <= 0 else
        f"the KAMA efficiency ratio `er_fast` must be at least `{args.min_entry_er:g}` at the signal "
        f"bar. At a crossover the two KAMAs are coincident by construction, so their spread cannot "
        f"be thresholded; this gates on whether the market is trending at all instead."
    )
    breakeven_text = (
        "disabled." if args.breakeven_after_r <= 0 else
        f"once unrealised profit reaches `{args.breakeven_after_r:g}R`, the stop ratchets to the "
        f"price that nets zero after round-trip fees and slippage (`breakeven_lock`)."
    )
    trailing_text = (
        "disabled — the bearish cross is the only exit." if args.trailing_atr <= 0 else
        f"once the trade reaches 1R, trail at `highest - {args.trailing_atr:g} x hourly "
        f"ATR({args.risk_atr_length})`, ratcheting up only (`atr_trailing_stop`)."
    )
    net_usdt = float(metric("net_usdt"))
    text = f"""# BTCUSDT KAMA({args.kama_fast_length})/KAMA({args.kama_slow_length}) Crossover Long — {span_label}

## Data & Setup

- Span: `{span_label}` (UTC), simulated as **one continuous series**, so no trade is force-closed at a month boundary.
- Hourly bars: {len(bars):,}; warm-up bars (no entries): {args.warmup_bars:,}; first tradable bar: {tradable_text}.
- Costs: slippage `{args.slippage_bps:g}` bps/side, taker fee `{args.taker_fee_rate:.4%}`, size `{args.position_btc:g}` BTC.
- Entry: KAMA({args.kama_fast_length}) crosses **above** KAMA({args.kama_slow_length}) on the hourly close and the trend gate below is open; filled at the next hourly open.
- Exit: KAMA({args.kama_fast_length}) crosses **below** KAMA({args.kama_slow_length}); filled at the next hourly open.
- Trend gate: `{args.trend_filter}` — {trend_text}.
- Chop gate: {er_text}
- Break-even lock: {breakeven_text}
- Trailing stop: {trailing_text}
- KAMA: Pine v4 port (everget, GPL-3.0) on `{args.kama_source}`, `fastLength={args.kama_fast_const}`, `slowLength={args.kama_slow_const}`; `alpha = (er × (2/(fast+1) − 2/(slow+1)) + 2/(slow+1))²`, seeded `nz(kama[1], src)`.
- Because of that seed both KAMAs start at the first bar's price and creep at `slowAlpha²` until index `length`, so the first `{args.warmup_bars:,}` bars are excluded from entry consideration as seeding artifacts.
- R-multiples use hourly ATR({args.risk_atr_length}) at the signal bar as the risk reference (`risk_reference`) — there is no stop distance to define 1R.
- One position at a time; a bullish cross while already long is ignored. An open position at the end of data exits at the final close (`data_end`).

## Signals & Structure

| Item | Count |
| --- | ---: |
| KAMA bullish crosses (all) | {int(bars['kama_cross_up'].sum())} |
| KAMA bearish crosses (all) | {int(bars['kama_cross_down'].sum())} |
| Bullish crosses inside warm-up (discarded) | {int(bars.loc[bars['warming_up'], 'kama_cross_up'].sum())} |
| Bullish crosses rejected by the `{args.trend_filter}` trend gate | {int((bars['kama_cross_up'] & ~bars['trend_ok'] & ~bars['warming_up']).sum())} |
| Bullish crosses rejected by the chop gate (`er_fast`) | {int((bars['kama_cross_up'] & bars['trend_ok'] & ~bars['er_ok'] & ~bars['warming_up']).sum())} |
| Entry signals taken | {int(bars['entry_signal'].sum())} |
| Exit signals fired | {int(bars['exit_signal'].sum())} |
| Hours in position | {int(bars['in_position'].sum())} ({bars['in_position'].mean() * 100:.1f}% of bars) |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | {metric('trades')} |
| Wins / Losses / Breakeven | {metric('wins')} / {metric('losses')} / {metric('breakeven')} |
| Win rate | {float(metric('win_rate')):.1f}% |
| Gross P&L | {float(metric('gross_usdt')):,.2f} USDT |
| Net P&L after costs | {net_usdt:,.2f} USDT |
| Total fees | {float(metric('total_fees_usdt')):,.2f} USDT |
| Net profit factor | {metric('profit_factor', 'n/a')} |
| Average net P&L | {float(metric('average_net_usdt')):,.2f} USDT |
| Largest win / loss | {float(metric('largest_win_usdt')):,.2f} / {float(metric('largest_loss_usdt')):,.2f} USDT |
| Average holding time | {float(metric('average_hours_held')):,.1f} h |
| Maximum net drawdown | {float(metric('max_net_drawdown_usdt')):,.2f} USDT |
| Buy & hold over the same window | {hold_net:,.2f} USDT |
| Strategy vs buy & hold | {net_usdt - hold_net:,.2f} USDT |

## Monthly Breakdown

Each trade is attributed to the month it **exited** in, so a trade opened late in one month
lands in the next. Month figures therefore sum to the headline net P&L.

| Month | Trades | Wins | Win rate | Net USDT |
| --- | ---: | ---: | ---: | ---: |
{month_rows}

## Exit Reasons

{exit_lines}

## Trade Detail

| # | Entry | Exit | Hours | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---:|---|
{rows}

## Notes

- Signals are read at the hourly close and filled at the next hourly open; no intrabar fills are assumed.
- When a stop is armed, 1h OHLC cannot resolve whether the bar's high or low came first. A stop is checked against the open (gap) and then the low, and is only *updated* from this bar's high afterwards, so a stop derived from a bar can never also be triggered by that same bar.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- A cross on the final bar is discarded rather than filled, since no next open exists.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_html_report(
    path: Path,
    span_label: str,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, object],
    warmup_bars: int,
    position_btc: float,
) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    metric = lambda name, default=0: summary.get(name, default)
    figure = make_subplots(
        rows=4, cols=1, shared_xaxes=False, vertical_spacing=0.045,
        row_heights=[0.55, 0.14, 0.13, 0.18],
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=(
            "Hourly price with KAMA pair, SMA trend gate, and trades",
            "KAMA spread (fast − slow); zero crossings are the signals",
            "Closed-trade net equity vs buy & hold (USDT)",
            "Trade ledger",
        ),
    )
    figure.add_trace(
        go.Candlestick(
            x=bars["timestamp"], open=bars["open"], high=bars["high"], low=bars["low"],
            close=bars["close"], name="BTCUSDT hourly",
        ), row=1, col=1,
    )
    for column, label, color, width in (
        ("kama_fast", "KAMA fast", "#1565c0", 1.8),
        ("kama_slow", "KAMA slow", "#ef6c00", 1.8),
        ("ma200", "SMA trend gate", "#6d4c41", 1.2),
    ):
        figure.add_trace(
            go.Scatter(
                x=bars["timestamp"], y=bars[column], mode="lines", name=label,
                line={"color": color, "width": width},
            ), row=1, col=1,
        )
    if warmup_bars > 0 and len(bars) > 0:
        edge = bars["timestamp"].iloc[min(warmup_bars, len(bars) - 1)]
        figure.add_vrect(
            x0=bars["timestamp"].iloc[0], x1=edge, fillcolor="rgba(120,144,156,0.16)",
            line_width=0, layer="below", annotation_text="warm-up (no entries)",
            annotation_position="top left", row=1, col=1,
        )
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["entry_time"], y=trades["raw_entry_price"], mode="markers", name="Long entry",
                marker={"symbol": "triangle-up", "size": 13, "color": "#2e7d32"},
                text=trades["entry_type"],
                hovertemplate="%{text}<br>%{x}<br>Raw %{y:,.1f}<extra></extra>",
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit",
                marker={"symbol": "x", "size": 11, "color": "#c62828"}, text=trades["exit_reason"],
                hovertemplate="%{text}<br>%{x}<br>Fill %{y:,.1f}<extra></extra>",
            ), row=1, col=1,
        )
    figure.add_trace(
        go.Scatter(
            x=bars["timestamp"], y=bars["kama_spread"], mode="lines", name="KAMA spread",
            line={"color": "#5e35b1"}, fill="tozeroy", fillcolor="rgba(94,53,177,0.12)",
        ), row=2, col=1,
    )
    figure.add_hline(y=0.0, line={"color": "#546e7a", "width": 1, "dash": "dot"}, row=2, col=1)
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["cumulative_net_usdt"], mode="lines+markers",
                name="Net cumulative P&L", line={"color": "#3949ab", "width": 2},
                fill="tozeroy", fillcolor="rgba(57,73,171,0.10)",
            ), row=3, col=1,
        )
        start = bars.iloc[min(warmup_bars, len(bars) - 1)]
        hold_curve = (bars["close"] - float(start["open"])) * position_btc
        inside = bars["timestamp"] >= start["timestamp"]
        figure.add_trace(
            go.Scatter(
                x=bars.loc[inside, "timestamp"], y=hold_curve[inside], mode="lines",
                name="Buy & hold (gross)", line={"color": "#90a4ae", "width": 1.4, "dash": "dash"},
            ), row=3, col=1,
        )
        table_values = [
            trades["trade_number"].tolist(),
            trades["entry_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["exit_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["hours_held"].map(lambda value: f"{value:,.0f}").tolist(),
            trades["net_usdt"].map(lambda value: f"{value:,.2f}").tolist(),
            trades["net_r"].map(lambda value: f"{value:.2f}").tolist(),
            trades["exit_reason"].tolist(),
        ]
    else:
        table_values = [["-"], ["No trade"], ["-"], ["-"], ["-"], ["-"], ["-"]]
    figure.add_trace(
        go.Table(
            header={
                "values": ["#", "Entry", "Exit", "Hours", "Net USDT", "Net R", "Exit reason"],
                "fill_color": "#263238", "font": {"color": "white"}, "align": "left",
            },
            cells={"values": table_values, "fill_color": "#f7f9fb", "align": "left", "height": 25},
        ), row=4, col=1,
    )
    title = (
        f"BTCUSDT {span_label} KAMA Crossover Long (1h) | Trades {metric('trades')} · "
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
    figure.update_yaxes(title_text="Fast − slow", row=2, col=1)
    figure.update_yaxes(title_text="Net USDT", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True, full_html=True)


def run_span(args: argparse.Namespace) -> dict[str, object]:
    months = month_range(args.start_month, args.end_month)
    span_label = f"{args.start_month}_to_{args.end_month}"

    hourly = load_span(args.bars_dir, months, "1h")
    hourly = add_kama_features(
        hourly, args.kama_fast_length, args.kama_slow_length, args.kama_fast_const,
        args.kama_slow_const, args.kama_source, args.ma200_length, args.ma200_source,
        args.ma200_slope_hours, args.risk_atr_length,
    )
    trades, bar_state = backtest_strategy(
        hourly, args.warmup_bars, args.trend_filter, args.min_ma200_slope, args.min_entry_er,
        args.trailing_atr, args.breakeven_after_r,
        args.slippage_bps, args.taker_fee_rate, args.position_btc,
    )
    summary = performance_summary(trades)
    first_index = min(args.warmup_bars, len(bar_state) - 1) if len(bar_state) else 0
    first_tradable = (
        pd.Timestamp(bar_state.iloc[first_index]["hour_start"]) if len(bar_state) else None
    )
    hold_net = buy_hold_net_usdt(
        bar_state, first_index, args.slippage_bps, args.taker_fee_rate, args.position_btc,
    )
    summary["buy_hold_net_usdt"] = hold_net
    monthly = monthly_breakdown(trades)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    config = f"kama{args.kama_fast_length}_{args.kama_slow_length}_{args.trend_filter}"
    if args.min_entry_er > 0:
        config += f"_er{args.min_entry_er:g}".replace(".", "")
    stem = f"BTCUSDT_{config}_1h_long_{span_label}"
    bar_state.to_csv(args.output_dir / f"{stem}_hourly.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(args.output_dir / f"{stem}_trades.csv", index=False, encoding="utf-8-sig")
    monthly.to_csv(args.output_dir / f"{stem}_monthly.csv", index=False, encoding="utf-8-sig")
    write_markdown_report(
        args.doc_dir / f"btcusdt_{config}_1h_long_backtest_{span_label.replace('_', '-')}.md",
        args, f"{args.start_month} → {args.end_month}", bar_state, trades, monthly,
        summary, first_tradable, hold_net,
    )
    write_html_report(
        args.output_dir / f"{stem}_backtest.html",
        f"{args.start_month} → {args.end_month}", bar_state, trades, summary,
        args.warmup_bars, args.position_btc,
    )
    print(
        f"{args.start_month}..{args.end_month} [{config}]: hourly={len(bar_state):,} warmup={args.warmup_bars} "
        f"trades={summary['trades']} net_usdt={float(summary.get('net_usdt', 0)):,.2f} "
        f"buy_hold={hold_net:,.2f}"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest the BTCUSDT KAMA(20)/KAMA(140) crossover long strategy on 1-hour bars."
    )
    parser.add_argument("--bars-dir", type=Path, default=DEFAULT_BARS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-dir", type=Path, default=DEFAULT_DOC_DIR)
    parser.add_argument("--start-month", type=parse_month, default=DEFAULT_START_MONTH)
    parser.add_argument("--end-month", type=parse_month, default=DEFAULT_END_MONTH)
    parser.add_argument("--warmup-bars", type=int, default=340,
                        help="hourly bars at the start of the span where no entry may fire")
    parser.add_argument("--kama-fast-length", type=int, default=20)
    parser.add_argument("--kama-slow-length", type=int, default=140)
    parser.add_argument("--kama-fast-const", type=int, default=2)
    parser.add_argument("--kama-slow-const", type=int, default=30)
    parser.add_argument("--kama-source", choices=PRICE_SOURCES, default="close")
    parser.add_argument("--ma200-length", type=int, default=200)
    parser.add_argument("--ma200-source", choices=PRICE_SOURCES, default="open")
    parser.add_argument("--ma200-slope-hours", type=int, default=24,
                        help="lookback for the MA slope used by --trend-filter slope/both")
    parser.add_argument("--trend-filter", choices=TREND_FILTERS, default="slope",
                        help="entry regime gate: MA slope (default), price above MA, both, or none")
    parser.add_argument("--min-ma200-slope", type=float, default=0.0,
                        help="minimum MA slope in %% over --ma200-slope-hours; 0 means simply rising")
    parser.add_argument("--min-entry-er", type=float, default=0.30,
                        help="minimum KAMA efficiency ratio (er_fast) at the signal bar; "
                             "filters crossovers that fire in chop. 0 disables it")
    parser.add_argument("--trailing-atr", type=float, default=0.0,
                        help="ATR multiple for the trailing stop once 1R is reached; 0 (default) disables it. "
                             "On BTCUSDT 1h this hurts: see the module docstring")
    parser.add_argument("--breakeven-after-r", type=float, default=0.0,
                        help="ratchet to a fee-adjusted break-even stop after this many R; 0 (default) disables it")
    parser.add_argument("--risk-atr-length", type=int, default=20)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0004)
    parser.add_argument("--position-btc", type=float, default=1.0)
    args = parser.parse_args()
    if pd.Period(args.end_month, freq="M") < pd.Period(args.start_month, freq="M"):
        parser.error("--end-month must be on or after --start-month")
    positive_lengths = (
        args.kama_fast_length, args.kama_slow_length, args.kama_fast_const,
        args.kama_slow_const, args.ma200_length, args.risk_atr_length, args.ma200_slope_hours,
    )
    if min(positive_lengths) < 1:
        parser.error("all lengths must be positive")
    if args.kama_slow_length <= args.kama_fast_length:
        parser.error("--kama-slow-length must exceed --kama-fast-length")
    if args.kama_slow_const <= args.kama_fast_const:
        parser.error("--kama-slow-const must exceed --kama-fast-const")
    if args.warmup_bars < 0:
        parser.error("--warmup-bars must be non-negative")
    if min(args.slippage_bps, args.taker_fee_rate, args.position_btc) < 0:
        parser.error("slippage, fee, and size must be non-negative")
    if min(args.trailing_atr, args.breakeven_after_r) < 0:
        parser.error("--trailing-atr and --breakeven-after-r must be non-negative")
    if not 0.0 <= args.min_entry_er <= 1.0:
        parser.error("--min-entry-er must be between 0 and 1")
    args.bars_dir = args.bars_dir.resolve()
    args.output_dir = args.output_dir.resolve()
    args.doc_dir = args.doc_dir.resolve()
    return args


def main() -> None:
    run_span(parse_args())


if __name__ == "__main__":
    main()
