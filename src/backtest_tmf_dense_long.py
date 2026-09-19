#!/usr/bin/env python
"""Backtest long-only TMF dense-reversal trades from TAIFEX daily tick files."""

from __future__ import annotations

import argparse
import csv
import io
import re
import zipfile
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .dense_reversal_bars import detect_dense_reversals
    from .tick_snr_indicator import build_volume_bars
except ImportError:
    from dense_reversal_bars import detect_dense_reversals
    from tick_snr_indicator import build_volume_bars


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_OUTPUT_DIR = ROOT / "txf_tick"
DEFAULT_REPORT = ROOT / "doc" / "tmf_202609_dense_reversal_long_backtest_2026-09-01_to_2026-09-11.md"
EXPECTED_HEADERS = (
    "成交日期",
    "商品代號",
    "到期月份(週別)",
    "成交時間",
    "成交價格",
    "成交數量(B+S)",
    "近月價格",
    "遠月價格",
    "開盤集合競價",
)
FILE_DATE_PATTERN = re.compile(r"Daily_(\d{4})_(\d{2})_(\d{2})\.(?:csv|zip)$")


@dataclass
class Position:
    entry_index: int
    entry_time: pd.Timestamp
    entry_price: float
    signal_time: pd.Timestamp
    signal_low: float
    entry_bar_low: float
    initial_stop: float
    risk_r: float
    entry_supertrend: float | None
    entry_direction: int | None
    entry_atr_multiplier: float | None
    last_direction: int | None


def parse_date(value: str) -> date:
    return datetime.strptime(value, "%Y-%m-%d").date()


def source_file_date(path: Path) -> date | None:
    match = FILE_DATE_PATTERN.fullmatch(path.name)
    if match is None:
        return None
    return date(int(match.group(1)), int(match.group(2)), int(match.group(3)))


def discover_daily_sources(input_dir: Path, start_date: date, end_date: date) -> list[Path]:
    """Find one CSV/ZIP source per date, preferring ZIP when both exist."""
    selected: dict[date, Path] = {}
    for path in input_dir.glob("Daily_*"):
        file_date = source_file_date(path)
        if file_date is None or not start_date <= file_date <= end_date:
            continue
        current = selected.get(file_date)
        if current is None or (path.suffix.lower() == ".zip" and current.suffix.lower() != ".zip"):
            selected[file_date] = path
    return [selected[file_date] for file_date in sorted(selected)]


def read_source_text(path: Path) -> str:
    if path.suffix.lower() == ".zip":
        with zipfile.ZipFile(path) as archive:
            csv_names = [name for name in archive.namelist() if name.lower().endswith(".csv")]
            if len(csv_names) != 1:
                raise ValueError(f"{path} must contain exactly one CSV file.")
            return archive.read(csv_names[0]).decode("cp950")
    return path.read_text(encoding="cp950")


def load_daily_ticks(paths: list[Path], product: str, contract_month: str) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for path in paths:
        reader = csv.reader(io.StringIO(read_source_text(path), newline=""))
        header = tuple(cell.strip() for cell in next(reader))
        if header != EXPECTED_HEADERS:
            raise ValueError(f"Unexpected TAIFEX headers in {path}: {header}")
        for sequence, row in enumerate(reader):
            cleaned = [cell.strip() for cell in row]
            if len(cleaned) < 6 or cleaned[1] != product or cleaned[2] != contract_month:
                continue
            records.append(
                {
                    "trade_date": cleaned[0],
                    "trade_time": cleaned[3].zfill(6),
                    "price": cleaned[4],
                    "quantity": cleaned[5],
                    "source_file": path.name,
                    "source_sequence": sequence,
                }
            )

    ticks = pd.DataFrame(records)
    if ticks.empty:
        raise ValueError(f"No {product} / {contract_month} tick rows were found.")
    ticks["timestamp"] = pd.to_datetime(
        ticks["trade_date"] + ticks["trade_time"], format="%Y%m%d%H%M%S", errors="coerce"
    )
    ticks["price"] = pd.to_numeric(ticks["price"], errors="coerce")
    ticks["quantity"] = pd.to_numeric(ticks["quantity"], errors="coerce")
    ticks = ticks.dropna(subset=["timestamp", "price", "quantity"])
    # Official files can contain multiple genuine transactions with the same second, price, and quantity.
    # Keep their source-file order rather than treating them as duplicate ticks.
    ticks = ticks.sort_values(["timestamp", "source_file", "source_sequence"], kind="stable").reset_index(drop=True)
    return ticks


def session_fields(timestamp: pd.Timestamp) -> tuple[str, pd.Timestamp] | None:
    clock = timestamp.time()
    day_start, day_end = time(8, 45), time(13, 45)
    night_start, night_end = time(15, 0), time(5, 0)
    if day_start <= clock < day_end:
        return "day", timestamp.normalize()
    if clock >= night_start:
        return "night", timestamp.normalize() + pd.Timedelta(days=1)
    if clock < night_end:
        return "night", timestamp.normalize()
    return None


def add_sessions(ticks: pd.DataFrame) -> pd.DataFrame:
    fields = ticks["timestamp"].map(session_fields)
    session_ticks = ticks.loc[fields.notna()].copy()
    session_ticks["session_type"] = fields[fields.notna()].map(lambda value: value[0])
    session_ticks["session_date"] = fields[fields.notna()].map(lambda value: value[1])
    session_ticks["session_id"] = (
        session_ticks["session_date"].dt.strftime("%Y-%m-%d") + " " + session_ticks["session_type"]
    )
    return session_ticks


def build_session_bars(ticks: pd.DataFrame, volume_bar_size: float, min_completed_bars: int) -> pd.DataFrame:
    all_bars: list[pd.DataFrame] = []
    for session_id, session_ticks in ticks.groupby("session_id", sort=True):
        session_ticks = session_ticks.copy()
        direction = np.sign(session_ticks["price"].diff()).replace(0, np.nan).ffill().fillna(1)
        session_ticks["signed_quantity"] = session_ticks["quantity"] * direction
        try:
            bars = build_volume_bars(session_ticks, volume_bar_size, min_completed_bars=min_completed_bars)
        except ValueError as error:
            if "Not enough completed volume bars" in str(error):
                continue
            raise
        bars["session_id"] = session_id
        bars["session_type"] = session_ticks["session_type"].iloc[0]
        bars["session_date"] = session_ticks["session_date"].iloc[0]
        all_bars.append(bars)
    if not all_bars:
        raise ValueError("No session has enough completed volume bars.")
    return pd.concat(all_bars, ignore_index=True)


def add_signals(bars: pd.DataFrame, lookback: int, density_window: int, density_quantile: float) -> pd.DataFrame:
    groups: list[pd.DataFrame] = []
    for _, session_bars in bars.groupby("session_id", sort=True):
        groups.append(detect_dense_reversals(session_bars, lookback, density_window, density_quantile))
    return pd.concat(groups, ignore_index=True)


def add_adaptive_supertrend(
    bars: pd.DataFrame,
    atr_length: int,
    base_multiplier: float,
    min_multiplier: float,
    speed_lookback: int,
    low_speed: float,
    high_speed: float,
    smoothing_span: int,
) -> pd.DataFrame:
    """Add an adaptive Supertrend that resets for every day/night volume-bar session."""
    groups: list[pd.DataFrame] = []
    for _, session_bars in bars.groupby("session_id", sort=True):
        result = session_bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
        previous_close = result["close"].shift(1)
        true_range = pd.concat(
            [
                result["high"] - result["low"],
                (result["high"] - previous_close).abs(),
                (result["low"] - previous_close).abs(),
            ],
            axis=1,
        ).max(axis=1)
        atr = true_range.ewm(alpha=1 / atr_length, adjust=False, min_periods=atr_length).mean()
        speed = (result["close"] - result["close"].shift(speed_lookback)).abs() / (atr * speed_lookback)
        smooth_speed = speed.ewm(span=smoothing_span, adjust=False, min_periods=smoothing_span).mean()
        normalized_speed = ((smooth_speed - low_speed) / (high_speed - low_speed)).clip(0, 1)
        multiplier = base_multiplier - (base_multiplier - min_multiplier) * normalized_speed.fillna(0)

        midpoint = (result["high"] + result["low"]) / 2
        basic_upper = midpoint + multiplier * atr
        basic_lower = midpoint - multiplier * atr
        final_upper = np.full(len(result), np.nan)
        final_lower = np.full(len(result), np.nan)
        supertrend = np.full(len(result), np.nan)
        direction = np.full(len(result), np.nan)
        for index in range(len(result)):
            if pd.isna(atr.iloc[index]):
                continue
            if index == 0 or pd.isna(final_upper[index - 1]):
                final_upper[index] = basic_upper.iloc[index]
                final_lower[index] = basic_lower.iloc[index]
                supertrend[index] = final_upper[index]
                direction[index] = -1
                continue
            previous = result.iloc[index - 1]
            final_upper[index] = (
                basic_upper.iloc[index]
                if basic_upper.iloc[index] < final_upper[index - 1] or previous["close"] > final_upper[index - 1]
                else final_upper[index - 1]
            )
            final_lower[index] = (
                basic_lower.iloc[index]
                if basic_lower.iloc[index] > final_lower[index - 1] or previous["close"] < final_lower[index - 1]
                else final_lower[index - 1]
            )
            if supertrend[index - 1] == final_upper[index - 1]:
                supertrend[index] = final_upper[index] if result.iloc[index]["close"] <= final_upper[index] else final_lower[index]
            else:
                supertrend[index] = final_lower[index] if result.iloc[index]["close"] >= final_lower[index] else final_upper[index]
            direction[index] = -1 if supertrend[index] == final_upper[index] else 1

        result["atr"] = atr
        result["price_speed"] = smooth_speed
        result["adaptive_multiplier"] = multiplier
        result["supertrend"] = supertrend
        result["supertrend_direction"] = direction
        groups.append(result)
    return pd.concat(groups, ignore_index=True)


def optional_float(value: object) -> float | None:
    return None if pd.isna(value) else float(value)


def optional_int(value: object) -> int | None:
    return None if pd.isna(value) else int(value)


def trade_record(position: Position, bars: pd.DataFrame, exit_index: int, reason: str, exit_price: float) -> dict[str, object]:
    held = bars.iloc[position.entry_index : exit_index + 1]
    max_price = float(held["high"].max())
    min_price = float(held["low"].min())
    pnl = exit_price - position.entry_price
    return {
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": bars.iloc[exit_index]["timestamp"],
        "session_id": bars.iloc[position.entry_index]["session_id"],
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "signal_low": position.signal_low,
        "entry_bar_low": position.entry_bar_low,
        "initial_stop": position.initial_stop,
        "risk_r": position.risk_r,
        "pnl_points": pnl,
        "pnl_r": pnl / position.risk_r if position.risk_r > 0 else np.nan,
        "mfe_points": max_price - position.entry_price,
        "mfe_r": (max_price - position.entry_price) / position.risk_r if position.risk_r > 0 else np.nan,
        "mae_points": min_price - position.entry_price,
        "mae_r": (min_price - position.entry_price) / position.risk_r if position.risk_r > 0 else np.nan,
        "exit_reason": reason,
        "entry_supertrend": position.entry_supertrend,
        "entry_supertrend_direction": position.entry_direction,
        "entry_atr_multiplier": position.entry_atr_multiplier,
        "exit_supertrend": optional_float(bars.iloc[exit_index]["supertrend"]),
        "exit_supertrend_direction": optional_int(bars.iloc[exit_index]["supertrend_direction"]),
        "exit_atr_multiplier": optional_float(bars.iloc[exit_index]["adaptive_multiplier"]),
    }


def backtest_long_only(bars: pd.DataFrame) -> pd.DataFrame:
    trades: list[dict[str, object]] = []
    for _, session_bars in bars.groupby("session_id", sort=True):
        session_bars = session_bars.reset_index(drop=True)
        position: Position | None = None
        entry_signal_index: int | None = None

        for index, bar in session_bars.iterrows():
            if position is None:
                if entry_signal_index is not None:
                    signal = session_bars.iloc[entry_signal_index]
                    entry = float(bar["open"])
                    stop = float(bar["low"])
                    risk = entry - stop
                    previous_direction = optional_int(session_bars.iloc[index - 1]["supertrend_direction"])
                    position = Position(
                        entry_index=index,
                        entry_time=bar["bar_start_time"],
                        entry_price=entry,
                        signal_time=signal["timestamp"],
                        signal_low=float(signal["low"]),
                        entry_bar_low=stop,
                        initial_stop=stop,
                        risk_r=risk,
                        entry_supertrend=optional_float(bar["supertrend"]),
                        entry_direction=optional_int(bar["supertrend_direction"]),
                        entry_atr_multiplier=optional_float(bar["adaptive_multiplier"]),
                        last_direction=previous_direction,
                    )
                    entry_signal_index = None
                if position is None and bool(bar["bullish_reversal"]) and index < len(session_bars) - 1:
                    entry_signal_index = index
                    continue
                if position is None:
                    continue

            current_direction = optional_int(bar["supertrend_direction"])
            if index > position.entry_index and float(bar["low"]) <= position.initial_stop:
                trades.append(trade_record(position, session_bars, index, "entry_bar_low_stop", position.initial_stop))
                position = None
                entry_signal_index = None
                continue
            if position.last_direction == 1 and current_direction == -1:
                trades.append(
                    trade_record(
                        position,
                        session_bars,
                        index,
                        "adaptive_volume_supertrend_bearish_flip",
                        float(bar["close"]),
                    )
                )
                position = None
                entry_signal_index = None
                continue
            if current_direction is not None:
                position.last_direction = current_direction

        if position is not None:
            last = session_bars.iloc[-1]
            trades.append(trade_record(position, session_bars, len(session_bars) - 1, "session_end", float(last["close"])))

    result = pd.DataFrame(trades)
    if not result.empty:
        result.insert(0, "trade_number", range(1, len(result) + 1))
        result["cumulative_points"] = result["pnl_points"].cumsum()
        result["equity_peak"] = result["cumulative_points"].cummax()
        result["drawdown_points"] = result["cumulative_points"] - result["equity_peak"]
    return result


def metric_summary(trades: pd.DataFrame) -> dict[str, float | int | str]:
    if trades.empty:
        return {"trades": 0}
    winners = trades[trades["pnl_points"] > 0]
    losers = trades[trades["pnl_points"] < 0]
    breakeven = trades[trades["pnl_points"] == 0]
    gross_profit = float(winners["pnl_points"].sum())
    gross_loss = float(losers["pnl_points"].sum())
    profit_factor = "n/a" if gross_loss == 0 else f"{gross_profit / abs(gross_loss):.2f}"
    return {
        "trades": len(trades),
        "wins": len(winners),
        "losses": len(losers),
        "breakeven": len(breakeven),
        "win_rate": float(len(winners) / len(trades) * 100),
        "net_points": float(trades["pnl_points"].sum()),
        "gross_profit": gross_profit,
        "gross_loss": gross_loss,
        "profit_factor": profit_factor,
        "average_points": float(trades["pnl_points"].mean()),
        "average_r": float(trades["pnl_r"].mean()),
        "median_points": float(trades["pnl_points"].median()),
        "max_win": float(trades["pnl_points"].max()),
        "max_loss": float(trades["pnl_points"].min()),
        "max_drawdown": float(trades["drawdown_points"].min()),
        "average_mfe": float(trades["mfe_points"].mean()),
        "average_mae": float(trades["mae_points"].mean()),
    }


def format_trades(trades: pd.DataFrame) -> str:
    if trades.empty:
        return "No eligible long trades were generated."
    display = trades.copy()
    for column in ("signal_time", "entry_time", "exit_time"):
        display[column] = pd.to_datetime(display[column]).dt.strftime("%Y-%m-%d %H:%M:%S")
    columns = [
        "trade_number", "session_id", "signal_time", "entry_time", "entry_price", "exit_time", "exit_price",
        "pnl_points", "pnl_r", "mfe_points", "mae_points", "exit_reason",
    ]
    for column in ("entry_price", "exit_price", "pnl_points", "pnl_r", "mfe_points", "mae_points"):
        display[column] = display[column].map(lambda value: f"{value:.1f}")
    headers = ["#", "Session", "Signal", "Entry", "Entry Px", "Exit", "Exit Px", "P&L", "R", "MFE", "MAE", "Reason"]
    lines = ["| " + " | ".join(headers) + " |", "|" + "---|" * len(headers)]
    for row in display[columns].itertuples(index=False, name=None):
        lines.append("| " + " | ".join(map(str, row)) + " |")
    return "\n".join(lines)


def write_report(
    report: Path,
    trades: pd.DataFrame,
    summary: dict[str, float | int | str],
    bars: pd.DataFrame,
    source_paths: list[Path],
    args: argparse.Namespace,
) -> None:
    report.parent.mkdir(parents=True, exist_ok=True)
    source_names = ", ".join(path.name for path in source_paths)
    text = f"""# TMF 202609 密集成交反轉進場＋自適應 Volume-Bar Supertrend：僅做多回測

## 範圍

- 原始檔：{source_names}
- 商品 / 到期月份：`TMF / 202609`
- 交易時段：日盤 `08:45:00–13:45:00`；夜盤 `15:00:00–次日 05:00:00`。
- 每個時段獨立建立 2,000 口 volume bar；不跨休市時段累積未完成 K 棒，也不留倉或保留待進場訊號。
- 完成 volume bars：{len(bars):,}

## 規則

- 多方密集反轉：前 50 根已完成 K 棒成交速度第 75 百分位為門檻；本根為最近 5 根低點、收紅、且收在全幅上半部。
- 只做多，訊號完成後，以下一根 volume bar 的開盤價進場；同一時間只允許一筆部位。
- 初始停損：進場 K 棒完成後，以該 K 棒 low 為停損價；不回頭套用在進場 K 棒本身。後續 K 棒 low 觸及時，以停損價成交。
- 自適應 Supertrend 直接使用同一組 {args.volume_bar_size:,.0f} 口 volume bar，且每個日／夜盤重新計算。參數為 `ATR({args.atr_length})`、基礎倍數 `{args.base_multiplier:g}`、最小倍數 `{args.min_multiplier:g}`、速度回看 `{args.speed_lookback}`、速度門檻 `{args.low_speed:g}–{args.high_speed:g}`、平滑 `{args.smoothing_span}`。
- Supertrend 由多翻空時，以翻轉 K 棒 close 平多；若同一根 K 棒也觸及初始停損，停損優先。
- 不再使用 `2R` 追蹤停損或空方密集反轉出場；時段結束仍持倉者，以最後一根完成 K 棒的 close 強制平倉。

## 結果

| Metric | Value |
| --- | ---: |
| Trades | {summary['trades']} |
| Wins / Losses / Breakeven | {summary.get('wins', 0)} / {summary.get('losses', 0)} / {summary.get('breakeven', 0)} |
| Win rate | {summary.get('win_rate', 0):.1f}% |
| Net P&L | {summary.get('net_points', 0):.1f} points |
| Gross profit / loss | {summary.get('gross_profit', 0):.1f} / {summary.get('gross_loss', 0):.1f} points |
| Profit factor | {summary.get('profit_factor', 'n/a')} |
| Average P&L | {summary.get('average_points', 0):.1f} points ({summary.get('average_r', 0):.2f}R) |
| Median P&L | {summary.get('median_points', 0):.1f} points |
| Largest win / loss | {summary.get('max_win', 0):.1f} / {summary.get('max_loss', 0):.1f} points |
| Maximum drawdown | {summary.get('max_drawdown', 0):.1f} points |
| Average MFE / MAE | {summary.get('average_mfe', 0):.1f} / {summary.get('average_mae', 0):.1f} points |

## Trade Ledger

{format_trades(trades)}

## Interpretation

This is a deterministic historical simulation, not an execution guarantee. Results are stated in index points and exclude brokerage fees, futures transaction tax, bid/ask spread, queue position, and slippage. The entry-bar low only becomes available after that bar completes. Later stop touches are modeled at the exact stop price, while adaptive-Supertrend flips are filled at the completed flip bar close; actual fills may be worse.
"""
    report.write_text(text, encoding="utf-8")


def write_chart(bars: pd.DataFrame, trades: pd.DataFrame, chart: Path) -> None:
    figure = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.025,
        row_heights=[0.52, 0.18, 0.14, 0.16],
        subplot_titles=("TMF volume bars, adaptive Supertrend, and long trades", "Trade rate", "Adaptive ATR multiplier", "Closed-trade equity"),
    )
    figure.add_trace(go.Candlestick(x=bars["timestamp"], open=bars["open"], high=bars["high"], low=bars["low"], close=bars["close"], name="TMF bars"), row=1, col=1)
    figure.add_trace(go.Scatter(x=bars["timestamp"], y=bars["supertrend"], mode="lines", name="Adaptive volume-bar Supertrend", line={"color": "#7b1fa2", "width": 2}), row=1, col=1)
    signals = bars[bars["bullish_reversal"]]
    figure.add_trace(go.Scatter(x=signals["timestamp"], y=signals["low"], mode="markers", name="Bullish dense reversal", marker={"symbol": "triangle-up", "size": 9, "color": "#43a047"}), row=1, col=1)
    figure.add_trace(go.Bar(x=bars["timestamp"], y=bars["contracts_per_second"], name="Contracts/s", marker_color="#607d8b"), row=2, col=1)
    figure.add_trace(go.Scatter(x=bars["timestamp"], y=bars["density_threshold"], mode="lines", name="Prior density threshold", line={"color": "#f9a825"}), row=2, col=1)
    figure.add_trace(go.Scatter(x=bars["timestamp"], y=bars["adaptive_multiplier"], mode="lines", name="Adaptive ATR multiplier", line={"color": "#ef6c00"}), row=3, col=1)
    if not trades.empty:
        figure.add_trace(go.Scatter(x=trades["entry_time"], y=trades["entry_price"], mode="markers", name="Long entry", marker={"symbol": "triangle-up", "size": 11, "color": "#00897b"}), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit", marker={"symbol": "x", "size": 10, "color": "#d32f2f"}, text=trades["exit_reason"], hovertemplate="Exit: %{x}<br>Price: %{y}<br>Reason: %{text}<extra></extra>"), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["cumulative_points"], mode="lines+markers", name="Cumulative P&L", line={"color": "#3949ab"}), row=4, col=1)
    figure.update_layout(title="TMF 202609 Long-only Dense Reversal with Adaptive Volume-Bar Supertrend", xaxis_rangeslider_visible=False, barmode="overlay")
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Contracts/s", row=2, col=1)
    figure.update_yaxes(title_text="ATR multiplier", row=3, col=1)
    figure.update_yaxes(title_text="Points", row=4, col=1)
    chart.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(chart, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest long-only TMF dense reversals by trading session.")
    parser.add_argument("--input-dir", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--start-date", type=parse_date, required=True)
    parser.add_argument("--end-date", type=parse_date, required=True)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--volume-bar-size", type=float, default=2000)
    parser.add_argument("--lookback-bars", type=int, default=5)
    parser.add_argument("--density-window", type=int, default=50)
    parser.add_argument("--density-quantile", type=float, default=0.75)
    parser.add_argument("--atr-length", type=int, default=10)
    parser.add_argument("--base-multiplier", type=float, default=3.0)
    parser.add_argument("--min-multiplier", type=float, default=0.8)
    parser.add_argument("--speed-lookback", type=int, default=2)
    parser.add_argument("--low-speed", type=float, default=0.25)
    parser.add_argument("--high-speed", type=float, default=0.8)
    parser.add_argument("--smoothing-span", type=int, default=2)
    parser.add_argument("--trades-output", type=Path, default=DEFAULT_OUTPUT_DIR / "TMF_202609_dense_long_trades_2026-09-01_to_2026-09-11.csv")
    parser.add_argument("--bars-output", type=Path, default=DEFAULT_OUTPUT_DIR / "TMF_202609_volume_bars_2026-09-01_to_2026-09-11.csv")
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_OUTPUT_DIR / "TMF_202609_dense_long_backtest_2026-09-01_to_2026-09-11.html")
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    if args.atr_length <= 0 or args.speed_lookback <= 0 or args.smoothing_span <= 0:
        parser.error("adaptive Supertrend lookbacks must be positive")
    if not 0 < args.min_multiplier <= args.base_multiplier:
        parser.error("--min-multiplier must be positive and no greater than --base-multiplier")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must be greater than --low-speed")
    return args


def main() -> None:
    args = parse_args()
    source_paths = sorted(
        path for path in args.input_dir.glob("Daily_*.zip")
        if (file_date := source_file_date(path)) is not None and args.start_date <= file_date <= args.end_date
    )
    if not source_paths:
        raise ValueError("No matching Daily_YYYY_MM_DD.zip files were found in --input-dir.")
    ticks = add_sessions(load_daily_ticks(source_paths, args.product.strip(), args.contract_month.strip()))
    bars = add_signals(
        build_session_bars(ticks, args.volume_bar_size, args.density_window + 1),
        args.lookback_bars,
        args.density_window,
        args.density_quantile,
    )
    bars = add_adaptive_supertrend(
        bars,
        args.atr_length,
        args.base_multiplier,
        args.min_multiplier,
        args.speed_lookback,
        args.low_speed,
        args.high_speed,
        args.smoothing_span,
    )
    trades = backtest_long_only(bars)
    summary = metric_summary(trades)
    args.trades_output.parent.mkdir(parents=True, exist_ok=True)
    args.bars_output.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.trades_output, index=False, encoding="utf-8-sig")
    bars.to_csv(args.bars_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, trades, summary, bars, source_paths, args)
    write_chart(bars, trades, args.chart_output)
    print(f"source_files={len(source_paths)} ticks={len(ticks)} volume_bars={len(bars)}")
    print(f"trades={summary['trades']} net_points={summary.get('net_points', 0):.1f} max_drawdown={summary.get('max_drawdown', 0):.1f}")
    print(f"report={args.report_output}")
    print(f"chart={args.chart_output}")


if __name__ == "__main__":
    main()
