#!/usr/bin/env python
"""Backtest the BTCUSDT 1-hour KAMA(60) price-cross LONG strategy.

A deliberately simple, single-timeframe trend follower — it reads only the committed 1h bars
and a single adaptive moving average:

1. KAMA(60): Kaufman's Adaptive Moving Average of the close, length 60.  This is the Pine v4
   "Kaufman Moving Average Adaptive" study (``nfastend=0.666``, ``nslowend=0.0645``), which is
   algebraically identical to :func:`pine_kama` with ``fast_length=2, slow_length=30``.
2. Entry: when a 1h **close crosses above KAMA(60)** (close ≤ KAMA on the prior bar, close >
   KAMA now), go long on the **next** 1h open.
3. Exit: when a 1h **close crosses below KAMA(60)**, exit on the **next** 1h open.

There is no stop and no target — the KAMA cross is the only entry/exit, plus a forced close of
any open position at the end of the month's data (``data_end``).  Because no stop defines a risk
distance, R-multiples use the hourly ATR at the signal bar as the risk reference, exactly as the
sibling ``backtest_btcusdt_kama_cross_1h_long.py`` does.

No look-ahead: every signal reads only closed-bar data and fills are next-bar open.

Reads ``data/btcusdt_bars/BTCUSDT_YYYY-MM_1h.csv`` (from ``preprocess_btcusdt_bars.py``).  Each
calendar month is backtested on its own, warmed with the preceding month(s) so KAMA is settled
at the month's first bar.  Costs follow the Binance-perp model of the sibling scripts: per-side
slippage in bps plus a taker fee, P&L in USDT for a fixed BTC size.
"""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .backtest_tmf_hourly_diamond_short import pine_atr
    from .backtest_btcusdt_kama_cross_1h_long import pine_kama
except ImportError:
    from backtest_tmf_hourly_diamond_short import pine_atr
    from backtest_btcusdt_kama_cross_1h_long import pine_kama


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_BARS_DIR = ROOT / "data" / "btcusdt_bars"
DEFAULT_OUTPUT_DIR = ROOT / "btcusdt_tick"
DEFAULT_DOC_DIR = ROOT / "doc"
DEFAULT_START_MONTH = "2025-02"
DEFAULT_END_MONTH = "2026-08"


@dataclass
class Position:
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    entry_index: int
    kama_at_entry: float
    atr_at_entry: float
    raw_entry_price: float
    entry_price: float
    risk_reference: float
    lowest_price: float
    highest_price: float


TRADE_COLUMNS = [
    "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
    "kama_at_entry", "atr_at_entry", "risk_reference",
    "raw_entry_price", "entry_price", "exit_price",
    "bars_held", "hours_held", "gross_points", "net_points",
    "entry_fee_usdt", "exit_fee_usdt", "gross_usdt", "net_usdt",
    "gross_r", "net_r", "mfe_points", "mae_points", "exit_reason",
    "cumulative_gross_usdt", "cumulative_net_usdt", "gross_drawdown_usdt", "net_drawdown_usdt",
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


def add_features(
    bars: pd.DataFrame,
    kama_length: int,
    kama_fast_const: int,
    kama_slow_const: int,
    atr_length: int,
) -> pd.DataFrame:
    """Attach KAMA(length) on the close, the ATR risk reference, and the price-cross flags.

    Computed on the full (warmup + target) span so that the cross flag on the month's first bar
    references the genuine preceding bar rather than wrapping within the sliced month.
    """
    frame = bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    frame["kama"], _ = pine_kama(frame["close"], kama_length, kama_fast_const, kama_slow_const)
    frame["atr"] = pine_atr(frame, atr_length)

    close = frame["close"]
    kama = frame["kama"]
    prev_close = close.shift(1)
    prev_kama = kama.shift(1)
    ready = close.notna() & kama.notna() & prev_close.notna() & prev_kama.notna()
    frame["cross_up"] = ready & (close > kama) & (prev_close <= prev_kama)
    frame["cross_down"] = ready & (close < kama) & (prev_close >= prev_kama)
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
    exit_index: int,
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
    risk = position.risk_reference
    scalable = pd.notna(risk) and risk > 0
    return {
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": exit_time,
        "entry_session": position.entry_session,
        "exit_session": str(bar["session_id"]),
        "kama_at_entry": position.kama_at_entry,
        "atr_at_entry": position.atr_at_entry,
        "risk_reference": risk,
        "raw_entry_price": position.raw_entry_price,
        "entry_price": position.entry_price,
        "exit_price": exit_fill,
        "bars_held": exit_index - position.entry_index,
        "hours_held": (exit_time - position.entry_time).total_seconds() / 3600.0,
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


# --------------------------------------------------------------------------------------
# Backtest
# --------------------------------------------------------------------------------------
def backtest_strategy(
    bar_frame: pd.DataFrame,
    slippage_bps: float = 1.0,
    taker_fee_rate: float = 0.0004,
    position_btc: float = 1.0,
) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Long-only KAMA price-cross state machine on 1-hour bars.

    Signals are read at the bar close (via the precomputed ``cross_up``/``cross_down`` flags)
    and filled at the *next* bar's open, which keeps the simulation free of look-ahead.  One
    position at a time; a cross-up while already long is ignored.  An exit is evaluated before
    an entry within the same bar, so a cross-down then cross-up flips cleanly.
    """
    if min(slippage_bps, taker_fee_rate, position_btc) < 0:
        raise ValueError("slippage, fee and size must be non-negative")

    slip = slippage_bps / 10_000.0
    frame = bar_frame.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    n = len(frame)

    for column in ("entry_signal", "exit_signal", "in_position"):
        frame[column] = False

    trades: list[dict[str, object]] = []
    position: Position | None = None
    pending_entry: dict[str, object] | None = None
    pending_exit: dict[str, object] | None = None
    last_index = n - 1

    def record(pos: Position, bar: pd.Series, exit_time, raw_exit, reason, exit_index) -> dict[str, object]:
        return _trade_record(
            pos, bar, exit_time, raw_exit, reason, exit_index,
            slippage_bps, taker_fee_rate, position_btc,
        )

    for index, bar in frame.iterrows():
        bar_start = pd.Timestamp(bar["hour_start"])
        raw_open = float(bar["open"])

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
                entry_fill = raw_open * (1 + slip)  # long entry is a buy → filled higher
                position = Position(
                    signal_time=pd.Timestamp(pending_entry["signal_time"]),
                    entry_time=bar_start,
                    entry_session=str(bar["session_id"]),
                    entry_index=index,
                    kama_at_entry=float(pending_entry["kama"]),
                    atr_at_entry=float(pending_entry["atr"]),
                    raw_entry_price=raw_open,
                    entry_price=entry_fill,
                    risk_reference=float(pending_entry["atr"]),
                    lowest_price=entry_fill,
                    highest_price=entry_fill,
                )
            pending_entry = None

        if position is not None:
            position.highest_price = max(position.highest_price, float(bar["high"]))
            position.lowest_price = min(position.lowest_price, float(bar["low"]))
            frame.at[index, "in_position"] = True

        # Signals are evaluated on this bar's close; the final bar has no next open to fill.
        if index < last_index:
            if position is not None and bool(bar["cross_down"]):
                frame.at[index, "exit_signal"] = True
                pending_exit = {"reason": "kama_cross_down"}
            if position is None and pending_entry is None and bool(bar["cross_up"]):
                frame.at[index, "entry_signal"] = True
                pending_entry = {
                    "signal_time": pd.Timestamp(bar["timestamp"]),
                    "kama": float(bar["kama"]),
                    "atr": float(bar["atr"]) if pd.notna(bar["atr"]) else np.nan,
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
        "average_hours_held": float(trades["hours_held"].mean()),
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
    summary: dict[str, object],
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
    exit_counts = trades["exit_reason"].value_counts() if not trades.empty else pd.Series(dtype=int)
    exit_lines = "\n".join(f"- `{name}`: {count}" for name, count in exit_counts.items()) or "- no trades"
    warmup_text = ", ".join(warmup_months) if warmup_months else "none"
    text = f"""# BTCUSDT 1h KAMA({args.kama_length}) price-cross (LONG) — {month}

## Data & Setup

- Backtest month: `{month}` (UTC); warm-up months: {warmup_text}.
- Simulated 1h bars (target month): {bar_rows:,}.
- Costs: slippage `{args.slippage_bps:g}` bps/side, taker fee `{args.taker_fee_rate:.4%}`, size `{args.position_btc:g}` BTC.
- KAMA: Pine v4 "Kaufman Moving Average Adaptive" on the close, `length={args.kama_length}`, `fastLength={args.kama_fast_const}`, `slowLength={args.kama_slow_const}`; `alpha = (er × (2/(fast+1) − 2/(slow+1)) + 2/(slow+1))²`, seeded `nz(kama[1], src)`, so it is warmed by the preceding month(s).
- Entry: 1h close crosses **above** KAMA({args.kama_length}); long filled on the next 1h open.
- Exit: 1h close crosses **below** KAMA({args.kama_length}); filled on the next 1h open.
- No stop and no target — the cross is the only exit. R-multiples use hourly ATR({args.atr_length}) at the signal bar as the risk reference (`risk_reference`).

## Signals & Structure

| Item | Count |
| --- | ---: |
| Close cross-ups above KAMA | {int(bars['cross_up'].sum())} |
| Close cross-downs below KAMA | {int(bars['cross_down'].sum())} |
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
| Net P&L after costs | {float(metric('net_usdt')):,.2f} USDT |
| Total fees | {float(metric('total_fees_usdt')):,.2f} USDT |
| Net profit factor | {metric('profit_factor', 'n/a')} |
| Average net P&L | {float(metric('average_net_usdt')):,.2f} USDT |
| Average holding time | {float(metric('average_hours_held')):,.1f} h |
| Maximum net drawdown | {float(metric('max_net_drawdown_usdt')):,.2f} USDT |

## Exit Reasons

{exit_lines}

## Trade Detail

| # | Entry | Exit | Hours | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---:|---|
{rows}

## Notes

- Signals are read at the hourly close and filled at the next hourly open; no intrabar fills are assumed.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- KAMA is warmed with the preceding month(s); trades are counted only inside the target month.
- An open position at the end of the month's data exits at the final close (`data_end`).
- A cross on the final bar is discarded rather than filled, since no next open exists.
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_html_report(
    path: Path,
    args: argparse.Namespace,
    month: str,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    metric = lambda name, default=0: summary.get(name, default)
    figure = make_subplots(
        rows=3, cols=1, shared_xaxes=False, vertical_spacing=0.06,
        row_heights=[0.62, 0.17, 0.21],
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=(
            f"1h candles, KAMA({args.kama_length}), and trades",
            "Closed-trade net equity (USDT)",
            "Trade ledger",
        ),
    )
    figure.add_trace(
        go.Candlestick(
            x=bars["timestamp"], open=bars["open"], high=bars["high"], low=bars["low"],
            close=bars["close"], name="BTCUSDT 1h",
        ), row=1, col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=bars["timestamp"], y=bars["kama"], mode="lines", name=f"KAMA({args.kama_length})",
            line={"color": "#1565c0", "width": 1.8},
        ), row=1, col=1,
    )
    if not trades.empty:
        figure.add_trace(
            go.Scatter(
                x=trades["entry_time"], y=trades["raw_entry_price"], mode="markers", name="Long entry",
                marker={"symbol": "triangle-up", "size": 13, "color": "#2e7d32"},
                hovertemplate="entry<br>%{x}<br>%{y:,.1f}<extra></extra>",
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit",
                marker={"symbol": "x", "size": 11, "color": "#c62828"}, text=trades["exit_reason"],
                hovertemplate="%{text}<br>%{x}<br>%{y:,.1f}<extra></extra>",
            ), row=1, col=1,
        )
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
        ), row=3, col=1,
    )
    title = (
        f"BTCUSDT {month} 1h KAMA({args.kama_length}) price-cross LONG | Trades {metric('trades')} · "
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
    bars = add_features(
        bars, args.kama_length, args.kama_fast_const, args.kama_slow_const, args.atr_length
    ).sort_values("timestamp", kind="stable").reset_index(drop=True)

    month_period = pd.Period(month, freq="M")
    month_start = pd.Timestamp(month_period.start_time, tz="UTC")
    month_end = pd.Timestamp(month_period.end_time, tz="UTC")
    month_mask = (bars["timestamp"] >= month_start) & (bars["timestamp"] <= month_end)
    month_bars = bars[month_mask].reset_index(drop=True)
    if month_bars.empty:
        raise ValueError(f"no 1h bars fall inside {month}")

    trades, bar_state = backtest_strategy(
        month_bars, args.slippage_bps, args.taker_fee_rate, args.position_btc,
    )
    summary = performance_summary(trades)

    args.output_dir.mkdir(parents=True, exist_ok=True)
    stem = f"BTCUSDT_{month}_kama{args.kama_length}_price_cross_long"
    bar_state.to_csv(args.output_dir / f"{stem}_bar_state.csv", index=False, encoding="utf-8-sig")
    trades.to_csv(args.output_dir / f"{stem}_trades.csv", index=False, encoding="utf-8-sig")
    write_markdown_report(
        args.doc_dir / f"btcusdt_{month.replace('-', '')}_kama{args.kama_length}_price_cross_long_backtest.md",
        args, month, warmup_months, len(month_bars), bar_state, trades, summary,
    )
    write_html_report(
        args.output_dir / f"{stem}_backtest.html", args, month, bar_state, trades, summary,
    )
    print(
        f"{month}: warmup={warmup_months or 'none'} bars={len(month_bars)} "
        f"trades={summary['trades']} net_usdt={float(summary.get('net_usdt', 0)):,.2f}"
    )
    return summary


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Backtest the BTCUSDT 1h KAMA(60) price-cross long strategy per month."
    )
    parser.add_argument("--bars-dir", type=Path, default=DEFAULT_BARS_DIR)
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--doc-dir", type=Path, default=DEFAULT_DOC_DIR)
    parser.add_argument("--start-month", type=parse_month, default=DEFAULT_START_MONTH)
    parser.add_argument("--end-month", type=parse_month, default=DEFAULT_END_MONTH)
    parser.add_argument("--warmup-months", type=int, default=1)
    parser.add_argument("--kama-length", type=int, default=60, help="KAMA length on the close")
    parser.add_argument("--kama-fast-const", type=int, default=2)
    parser.add_argument("--kama-slow-const", type=int, default=30)
    parser.add_argument("--atr-length", type=int, default=14)
    parser.add_argument("--slippage-bps", type=float, default=1.0)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0004)
    parser.add_argument("--position-btc", type=float, default=1.0)
    args = parser.parse_args()
    if pd.Period(args.end_month, freq="M") < pd.Period(args.start_month, freq="M"):
        parser.error("--end-month must be on or after --start-month")
    if args.warmup_months < 0:
        parser.error("--warmup-months must be non-negative")
    if min(args.kama_length, args.kama_fast_const, args.kama_slow_const, args.atr_length) < 1:
        parser.error("--kama-length, --kama-fast-const, --kama-slow-const and --atr-length must be positive")
    if args.kama_slow_const <= args.kama_fast_const:
        parser.error("--kama-slow-const must exceed --kama-fast-const")
    if min(args.slippage_bps, args.taker_fee_rate, args.position_btc) < 0:
        parser.error("slippage, fee and size must be non-negative")
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
