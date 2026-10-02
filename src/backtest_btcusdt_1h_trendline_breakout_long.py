#!/usr/bin/env python
"""Backtest the BTCUSDT 1-hour-only descending-trendline breakout LONG strategy.

A deliberately simple, single-timeframe strategy — it reads only the committed 1h bars:

1. Trend line: over the last ``--lookback`` (default 48) closed 1h bars, connect the **two most
   recent confirmed swing-high pivots** and extend the line to the right.  The line must be
   descending (slope ≤ ``--max-line-slope``) so a break above it is a genuine resistance break.
2. Entry: when a 1h **close** rises above ``line + buffer`` for the first time (a crossing), go
   long on the **next** 1h open.
3. Risk: ``R = entry − the most recent confirmed swing-low *close*``.  The initial stop sits at
   that swing-low close (−1R); the target is ``entry + 2R`` (``--target-r``).

No look-ahead: every signal reads only closed-bar data, fills are next-bar open, and swing
pivots are consumed only once confirmed (pivot index + k bars).  Every drawn trend line is
rendered on the HTML.

Reads ``data/btcusdt_bars/BTCUSDT_YYYY-MM_1h.csv`` (from ``preprocess_btcusdt_bars.py``).  Each
calendar month is backtested on its own, warmed with the preceding month(s).  Costs follow the
Binance-perp model of the sibling scripts: per-side slippage in bps plus a taker fee, P&L in
USDT for a fixed BTC size.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .backtest_tmf_hourly_diamond_short import pine_atr
    from .backtest_btcusdt_1h_trend_15m_macd_trendline_long import swing_high_flags, swing_low_flags
except ImportError:
    from backtest_tmf_hourly_diamond_short import pine_atr
    from backtest_btcusdt_1h_trend_15m_macd_trendline_long import swing_high_flags, swing_low_flags


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BARS_DIR = ROOT / "data" / "btcusdt_bars"
DEFAULT_OUTPUT_DIR = ROOT / "btcusdt_tick"
DEFAULT_DOC_DIR = ROOT / "doc"
DEFAULT_START_MONTH = "2025-02"
DEFAULT_END_MONTH = "2025-08"


@dataclass
class Position:
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    entry_index: int
    h1_time: pd.Timestamp
    h2_time: pd.Timestamp
    line_slope: float
    raw_entry_price: float
    entry_price: float
    initial_stop: float
    initial_risk: float
    target_price: float
    atr_at_entry: float
    swing_low_close: float
    lowest_price: float
    highest_price: float


TRADE_COLUMNS = [
    "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
    "h1_time", "h2_time", "line_slope", "swing_low_close",
    "raw_entry_price", "entry_price", "exit_price", "initial_stop", "initial_risk", "target_price",
    "atr_at_entry", "gross_points", "net_points",
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


def load_bars(bars_dir: Path, month: str) -> pd.DataFrame:
    path = bars_dir / f"BTCUSDT_{month}_1h.csv"
    if not path.is_file():
        raise FileNotFoundError(f"missing bar file: {path}")
    frame = pd.read_csv(path)
    for column in ("timestamp", "hour_start"):
        frame[column] = pd.to_datetime(frame[column], utc=True, format="ISO8601")
    return frame


def load_span(bars_dir: Path, months: list[str]) -> pd.DataFrame:
    frames = [load_bars(bars_dir, month) for month in months]
    return pd.concat(frames, ignore_index=True).sort_values("timestamp", kind="stable").reset_index(drop=True)


def add_features(bars: pd.DataFrame, atr_length: int, swing_k: int) -> pd.DataFrame:
    frame = bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    frame["atr"] = pine_atr(frame, atr_length)
    frame["is_swing_high"] = swing_high_flags(frame["high"].to_numpy(dtype=float), swing_k)
    frame["is_close_swing_low"] = swing_low_flags(frame["close"].to_numpy(dtype=float), swing_k)
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
        "h1_time": position.h1_time,
        "h2_time": position.h2_time,
        "line_slope": position.line_slope,
        "swing_low_close": position.swing_low_close,
        "raw_entry_price": position.raw_entry_price,
        "entry_price": position.entry_price,
        "exit_price": exit_fill,
        "initial_stop": position.initial_stop,
        "initial_risk": position.initial_risk,
        "target_price": position.target_price,
        "atr_at_entry": position.atr_at_entry,
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
# Backtest
# --------------------------------------------------------------------------------------
def backtest_strategy(
    bar_frame: pd.DataFrame,
    lookback: int = 48,
    swing_k: int = 2,
    buffer_atr: float = 0.0,
    max_line_slope: float = 0.0,
    target_r: float = 2.0,
    slippage_bps: float = 1.0,
    taker_fee_rate: float = 0.0004,
    position_btc: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    if min(lookback, swing_k) < 1:
        raise ValueError("lookback and swing_k must be positive")
    if min(buffer_atr, target_r, slippage_bps, taker_fee_rate, position_btc) < 0:
        raise ValueError("buffer, target, slippage, fee and size must be non-negative")

    slip = slippage_bps / 10_000.0
    frame = bar_frame.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    n = len(frame)

    close = frame["close"].to_numpy(dtype=float)
    high = frame["high"].to_numpy(dtype=float)
    low = frame["low"].to_numpy(dtype=float)
    atr = frame["atr"].to_numpy(dtype=float)

    swing_highs = [(i, high[i]) for i in np.flatnonzero(frame["is_swing_high"].to_numpy())]
    swing_low_closes = [(i, close[i]) for i in np.flatnonzero(frame["is_close_swing_low"].to_numpy())]

    for column, default in (("line_value", np.nan), ("entry_signal", False)):
        frame[column] = default

    trades: list[dict[str, object]] = []
    trendlines: dict[tuple[int, int], dict[str, object]] = {}
    position: Position | None = None
    pending_entry: dict[str, object] | None = None

    def ts(i: int) -> pd.Timestamp:
        return pd.Timestamp(frame.iloc[i]["timestamp"])

    def record(pos: Position, bar: pd.Series, exit_time: pd.Timestamp, raw_exit: float, reason: str) -> dict[str, object]:
        return _trade_record(pos, bar, exit_time, raw_exit, reason, slippage_bps, taker_fee_rate, position_btc)

    def two_recent_swing_highs(now: int) -> tuple[tuple[int, float], tuple[int, float]] | None:
        """The two most recent confirmed swing highs inside the lookback window."""
        window_start = now - lookback + 1
        found: list[tuple[int, float]] = [
            (p_idx, p_price)
            for p_idx, p_price in swing_highs
            if p_idx + swing_k <= now and p_idx >= window_start
        ]
        if len(found) < 2:
            return None
        last, prev = found[-1], found[-2]  # most recent, second most recent
        return prev, last

    def latest_swing_low_close(now: int) -> tuple[int, float] | None:
        best: tuple[int, float] | None = None
        for p_idx, p_price in swing_low_closes:
            if p_idx + swing_k > now:
                continue
            if best is None or p_idx > best[0]:
                best = (p_idx, p_price)
        return best

    for index in range(n):
        bar = frame.iloc[index]
        timestamp = pd.Timestamp(bar["timestamp"])
        bar_start = pd.Timestamp(bar["hour_start"])
        raw_open = float(bar["open"])

        # A1) gap through the stop at the open ------------------------------------------------
        if position is not None and raw_open <= position.initial_stop:
            position.lowest_price = min(position.lowest_price, raw_open)
            trades.append(record(position, bar, bar_start, raw_open, "initial_stop_gap"))
            position = None

        # A2) fill a pending entry on this bar's open ---------------------------------------
        if position is None and pending_entry is not None:
            raw_entry = raw_open
            entry_fill = raw_entry * (1 + slip)
            swing_low_close = float(pending_entry["swing_low_close"])
            initial_stop = swing_low_close
            initial_risk = entry_fill - initial_stop
            if initial_risk > 0 and entry_fill > initial_stop:
                position = Position(
                    signal_time=pd.Timestamp(pending_entry["signal_time"]),
                    entry_time=bar_start,
                    entry_session=str(bar["session_id"]),
                    entry_index=index,
                    h1_time=pd.Timestamp(pending_entry["h1_time"]),
                    h2_time=pd.Timestamp(pending_entry["h2_time"]),
                    line_slope=float(pending_entry["slope"]),
                    raw_entry_price=raw_entry,
                    entry_price=entry_fill,
                    initial_stop=initial_stop,
                    initial_risk=initial_risk,
                    target_price=entry_fill + target_r * initial_risk,
                    atr_at_entry=float(pending_entry["atr"]),
                    swing_low_close=swing_low_close,
                    lowest_price=entry_fill,
                    highest_price=entry_fill,
                )
            pending_entry = None

        # A3) intrabar management of an open position ---------------------------------------
        if position is not None:
            if low[index] <= position.initial_stop:  # stop priority over the target
                position.highest_price = max(position.highest_price, high[index])
                position.lowest_price = min(position.lowest_price, position.initial_stop)
                trades.append(record(position, bar, timestamp, position.initial_stop, "initial_stop"))
                position = None
            elif high[index] >= position.target_price:
                position.highest_price = max(position.highest_price, position.target_price)
                position.lowest_price = min(position.lowest_price, low[index])
                trades.append(record(position, bar, timestamp, position.target_price, "target_2r"))
                position = None
            else:
                position.lowest_price = min(position.lowest_price, low[index])
                position.highest_price = max(position.highest_price, high[index])

        # B) look for a breakout entry (only when flat) -------------------------------------
        if position is None and pending_entry is None and pd.notna(atr[index]) and index < n - 1:
            anchors = two_recent_swing_highs(index)
            if anchors is not None:
                (h1_i, h1_p), (h2_i, h2_p) = anchors
                slope = (h2_p - h1_p) / (h2_i - h1_i)
                if slope <= max_line_slope:
                    line_now = h2_p + slope * (index - h2_i)
                    line_prev = h2_p + slope * ((index - 1) - h2_i)
                    frame.at[index, "line_value"] = line_now
                    key = (h1_i, h2_i)
                    line = trendlines.get(key)
                    if line is None:
                        trendlines[key] = {
                            "h1_index": h1_i, "h1_time": ts(h1_i), "h1_price": h1_p,
                            "h2_index": h2_i, "h2_time": ts(h2_i), "h2_price": h2_p, "slope": slope,
                            "start_time": ts(h1_i), "end_index": index, "end_time": ts(index), "status": "armed",
                        }
                    else:
                        line["end_index"] = index
                        line["end_time"] = ts(index)
                    buffer = buffer_atr * float(atr[index])
                    crossing = close[index] > line_now + buffer and close[index - 1] <= line_prev + buffer
                    swing_low = latest_swing_low_close(index)
                    if crossing and swing_low is not None and swing_low[1] < raw_open:
                        frame.at[index, "entry_signal"] = True
                        trendlines[key]["status"] = "entered"
                        trendlines[key]["end_index"] = index
                        trendlines[key]["end_time"] = ts(index)
                        pending_entry = {
                            "signal_time": timestamp,
                            "h1_time": ts(h1_i),
                            "h2_time": ts(h2_i),
                            "slope": slope,
                            "atr": float(atr[index]),
                            "swing_low_close": float(swing_low[1]),
                        }

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
    text = f"""# BTCUSDT 1h trend-line breakout (LONG) — {month}

## Data & Setup

- Backtest month: `{month}` (UTC); warm-up months: {warmup_text}.
- Simulated 1h bars (target month): {bar_rows:,}.
- Costs: slippage `{args.slippage_bps:g}` bps/side, taker fee `{args.taker_fee_rate:.4%}`, size `{args.position_btc:g}` BTC.
- Trend line: two most recent confirmed swing highs (k={args.swing_k}) within the last `{args.lookback}` 1h bars; slope ≤ `{args.max_line_slope:g}` (descending).
- Entry: 1h close crosses above line + `{args.buffer_atr:g} × ATR({args.atr_length})`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `{args.target_r:g}R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | {len(lines)} |
| Entry signals | {int(bars['entry_signal'].sum())} |

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

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
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
        rows=3, cols=1, shared_xaxes=False, vertical_spacing=0.06,
        row_heights=[0.62, 0.17, 0.21],
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=("1h candles, drawn trend lines, and trades", "Closed-trade net equity (USDT)", "Trade ledger"),
    )
    figure.add_trace(
        go.Candlestick(
            x=bars["timestamp"], open=bars["open"], high=bars["high"], low=bars["low"],
            close=bars["close"], name="BTCUSDT 1h",
        ), row=1, col=1,
    )
    status_color = {"entered": "#2e7d32", "unresolved": "#90a4ae"}
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
                x=lines["h1_time"], y=lines["h1_price"], mode="markers", name="swing high",
                marker={"symbol": "circle", "size": 7, "color": "#ef6c00"},
                hovertemplate="swing high<br>%{x}<br>%{y:.1f}<extra></extra>",
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=lines["h2_time"], y=lines["h2_price"], mode="markers", name="swing high",
                marker={"symbol": "circle", "size": 7, "color": "#ef6c00"}, showlegend=False,
                hovertemplate="swing high<br>%{x}<br>%{y:.1f}<extra></extra>",
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
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["cumulative_net_usdt"], mode="lines+markers",
                name="Net cumulative P&L", line={"color": "#3949ab", "width": 2},
                fill="tozeroy", fillcolor="rgba(57,73,171,0.10)",
            ), row=2, col=1,
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
        ), row=3, col=1,
    )
    title = (
        f"BTCUSDT {month} 1h trend-line breakout LONG | Trades {metric('trades')} · "
        f"Win rate {float(metric('win_rate')):.1f}% · Net {float(metric('net_usdt')):,.0f} USDT · "
        f"PF {metric('profit_factor', 'n/a')}"
    )
    figure.update_layout(
        title={"text": title, "x": 0.5}, template="plotly_white", height=1050,
        hovermode="x unified", legend={"orientation": "h", "y": 1.02, "x": 0},
        margin={"l": 65, "r": 35, "t": 105, "b": 35},
    )
    figure.update_xaxes(rangeslider_visible=False, row=1, col=1)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Net USDT", row=2, col=1)
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

    bars = load_span(args.bars_dir, span_months)
    bars = add_features(bars, args.atr_length, args.swing_k).sort_values("timestamp", kind="stable").reset_index(drop=True)

    month_period = pd.Period(month, freq="M")
    month_start = pd.Timestamp(month_period.start_time, tz="UTC")
    month_end = pd.Timestamp(month_period.end_time, tz="UTC")
    month_mask = (bars["timestamp"] >= month_start) & (bars["timestamp"] <= month_end)
    month_bars = bars[month_mask].reset_index(drop=True)
    if month_bars.empty:
        raise ValueError(f"no 1h bars fall inside {month}")

    trades, bar_state, lines = backtest_strategy(
        month_bars, args.lookback, args.swing_k, args.buffer_atr, args.max_line_slope,
        args.target_r, args.slippage_bps, args.taker_fee_rate, args.position_btc,
    )
    summary = performance_summary(trades)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"BTCUSDT_{month}_trendline_breakout_long"
    bar_state.to_csv(args.output_dir / f"{stem}_bar_state.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(args.output_dir / f"{stem}_trades.csv", index=False, encoding="utf-8-sig")
    lines.to_csv(args.output_dir / f"{stem}_trendlines.csv", index=False, encoding="utf-8-sig")
    write_markdown_report(
        args.doc_dir / f"btcusdt_{month.replace('-', '')}_trendline_breakout_long_backtest.md",
        args, month, warmup_months, len(month_bars), bar_state, trades, lines, summary,
    )
    write_html_report(
        args.output_dir / f"{stem}_backtest.html", month, bar_state, trades, lines, summary,
    )
    print(
        f"{month}: warmup={warmup_months or 'none'} bars={len(month_bars)} "
        f"lines={len(lines)} trades={summary['trades']} net_usdt={float(summary.get('net_usdt', 0)):,.2f}"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest the BTCUSDT 1h-only descending-trend-line breakout long strategy per month."
    )
    parser.add_argument("--bars-dir", type=Path, default=DEFAULT_BARS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-dir", type=Path, default=DEFAULT_DOC_DIR)
    parser.add_argument("--start-month", type=parse_month, default=DEFAULT_START_MONTH)
    parser.add_argument("--end-month", type=parse_month, default=DEFAULT_END_MONTH)
    parser.add_argument("--warmup-months", type=int, default=1)
    parser.add_argument("--lookback", type=int, default=48, help="1h bars to search for the two swing highs")
    parser.add_argument("--swing-k", type=int, default=2)
    parser.add_argument("--atr-length", type=int, default=14)
    parser.add_argument("--buffer-atr", type=float, default=0.0, help="breakout buffer in ATR units above the line")
    parser.add_argument("--max-line-slope", type=float, default=0.0, help="line slope must be ≤ this (≤0 = descending)")
    parser.add_argument("--target-r", type=float, default=2.0)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0004)
    parser.add_argument("--position-btc", type=float, default=1.0)
    args = parser.parse_args()
    if pd.Period(args.end_month, freq="M") < pd.Period(args.start_month, freq="M"):
        parser.error("--end-month must be on or after --start-month")
    if args.warmup_months < 0:
        parser.error("--warmup-months must be non-negative")
    if min(args.lookback, args.swing_k, args.atr_length) < 1:
        parser.error("--lookback, --swing-k and --atr-length must be positive")
    if min(args.buffer_atr, args.target_r, args.slippage_bps, args.taker_fee_rate, args.position_btc) < 0:
        parser.error("buffer, target, slippage, fee and size must be non-negative")
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
