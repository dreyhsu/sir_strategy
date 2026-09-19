#!/usr/bin/env python
"""Continuous short-only TMF backtest with adaptive hourly Supertrend exits."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, metric_summary, parse_date
    from .backtest_tmf_hourly_resistance_short import add_bearish_rejection_signals, assign_resistance_entries
    from .backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones
    from .dense_reversal_bars import detect_dense_reversals
    from .tick_snr_indicator import build_volume_bars
except ImportError:
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, metric_summary, parse_date
    from backtest_tmf_hourly_resistance_short import add_bearish_rejection_signals, assign_resistance_entries
    from backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones
    from dense_reversal_bars import detect_dense_reversals
    from tick_snr_indicator import build_volume_bars


ROOT = Path(__file__).resolve().parents[1]
TICK_DIR = ROOT / "txf_tick"
DATA_DIR = ROOT / "data"
OUTPUT_PERIOD = "2026-08-05_to_2026-09-15"
DEFAULT_TRADES = TICK_DIR / f"TMF_202609_adaptive_hourly_short_trades_{OUTPUT_PERIOD}.csv"
DEFAULT_CHART = TICK_DIR / f"TMF_202609_adaptive_hourly_short_backtest_{OUTPUT_PERIOD}.html"
DEFAULT_REPORT = ROOT / "doc" / f"tmf_202609_adaptive_hourly_short_backtest_{OUTPUT_PERIOD}.md"


@dataclass
class Position:
    entry_index: int
    entry_time: pd.Timestamp
    entry_price: float
    signal_time: pd.Timestamp
    resistance_id: int
    entry_supertrend: float | None
    entry_direction: int | None
    last_direction: int | None


def build_continuous_volume_bars(ticks: pd.DataFrame, size: float) -> pd.DataFrame:
    frame = ticks.copy()
    direction = np.sign(frame["price"].diff()).replace(0, np.nan).ffill().fillna(1)
    frame["signed_quantity"] = frame["quantity"] * direction
    bars = build_volume_bars(frame, size, min_completed_bars=51)
    session_lookup = frame[["timestamp", "session_id"]].sort_values("timestamp", kind="stable")
    bars = pd.merge_asof(
        bars.sort_values("bar_start_time", kind="stable"),
        session_lookup,
        left_on="bar_start_time",
        right_on="timestamp",
        direction="backward",
    ).drop(columns="timestamp_y").rename(columns={"timestamp_x": "timestamp"})
    return bars.reset_index(drop=True)


def add_adaptive_supertrend(
    hourly: pd.DataFrame,
    atr_length: int,
    base_multiplier: float,
    min_multiplier: float,
    speed_lookback: int,
    low_speed: float,
    high_speed: float,
    smoothing_span: int,
) -> pd.DataFrame:
    """Calculate continuous Supertrend whose ATR multiplier tightens during fast moves."""
    result = hourly.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
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
        final_upper[index] = basic_upper.iloc[index] if basic_upper.iloc[index] < final_upper[index - 1] or previous["close"] > final_upper[index - 1] else final_upper[index - 1]
        final_lower[index] = basic_lower.iloc[index] if basic_lower.iloc[index] > final_lower[index - 1] or previous["close"] < final_lower[index - 1] else final_lower[index - 1]
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
    return result


def attach_hourly_state(bars: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    state = hourly[["timestamp", "supertrend", "supertrend_direction", "adaptive_multiplier"]].rename(
        columns={
            "timestamp": "hourly_confirmation_time",
            "supertrend": "hourly_supertrend",
            "supertrend_direction": "hourly_supertrend_direction",
            "adaptive_multiplier": "hourly_atr_multiplier",
        }
    )
    return pd.merge_asof(
        bars.sort_values("timestamp", kind="stable"),
        state.sort_values("hourly_confirmation_time", kind="stable"),
        left_on="timestamp",
        right_on="hourly_confirmation_time",
        direction="backward",
        allow_exact_matches=False,
    )


def backtest(bars: pd.DataFrame) -> pd.DataFrame:
    trades: list[dict[str, object]] = []
    position: Position | None = None
    signal_index: int | None = None
    scheduled_exit: str | None = None

    for index, bar in bars.iterrows():
        if position is not None and scheduled_exit is not None:
            held = bars.iloc[position.entry_index : index + 1]
            exit_price = float(bar["open"])
            pnl = position.entry_price - exit_price
            trades.append(
                {
                    "signal_time": position.signal_time,
                    "entry_time": position.entry_time,
                    "exit_time": bar["bar_start_time"],
                    "entry_session": bars.iloc[position.entry_index]["session_id"],
                    "exit_session": bar["session_id"],
                    "entry_price": position.entry_price,
                    "exit_price": exit_price,
                    "entry_supertrend": position.entry_supertrend,
                    "entry_supertrend_direction": position.entry_direction,
                    "resistance_id": position.resistance_id,
                    "pnl_points": pnl,
                    "pnl_r": np.nan,
                    "mfe_points": position.entry_price - float(held["low"].min()),
                    "mae_points": position.entry_price - float(held["high"].max()),
                    "exit_reason": scheduled_exit,
                    "cross_session": bars.iloc[position.entry_index]["session_id"] != bar["session_id"],
                }
            )
            position, scheduled_exit, signal_index = None, None, None
            continue

        if position is None:
            if signal_index is not None:
                signal = bars.iloc[signal_index]
                entry_direction = None if pd.isna(signal["hourly_supertrend_direction"]) else int(signal["hourly_supertrend_direction"])
                entry_supertrend = None if pd.isna(signal["hourly_supertrend"]) else float(signal["hourly_supertrend"])
                position = Position(
                    index,
                    bar["bar_start_time"],
                    float(bar["open"]),
                    signal["timestamp"],
                    int(signal["resistance_id"]),
                    entry_supertrend,
                    entry_direction,
                    entry_direction,
                )
                signal_index = None
            if position is None and bool(bar["resistance_reversal"]) and index < len(bars) - 1:
                signal_index = index
                continue
            if position is None:
                continue

        current_direction = None if pd.isna(bar["hourly_supertrend_direction"]) else int(bar["hourly_supertrend_direction"])
        if position.last_direction == -1 and current_direction == 1:
            scheduled_exit = "adaptive_hourly_supertrend_bullish_flip"
        if current_direction is not None:
            position.last_direction = current_direction

    if position is not None:
        held = bars.iloc[position.entry_index :]
        last = bars.iloc[-1]
        pnl = position.entry_price - float(last["close"])
        trades.append(
            {
                "signal_time": position.signal_time,
                "entry_time": position.entry_time,
                "exit_time": last["timestamp"],
                "entry_session": bars.iloc[position.entry_index]["session_id"],
                "exit_session": last["session_id"],
                "entry_price": position.entry_price,
                "exit_price": float(last["close"]),
                "entry_supertrend": position.entry_supertrend,
                "entry_supertrend_direction": position.entry_direction,
                "resistance_id": position.resistance_id,
                "pnl_points": pnl,
                "pnl_r": np.nan,
                "mfe_points": position.entry_price - float(held["low"].min()),
                "mae_points": position.entry_price - float(held["high"].max()),
                "exit_reason": "data_end",
                "cross_session": bars.iloc[position.entry_index]["session_id"] != last["session_id"],
            }
        )

    columns = [
        "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session", "entry_price",
        "exit_price", "entry_supertrend", "entry_supertrend_direction", "resistance_id", "pnl_points", "pnl_r",
        "mfe_points", "mae_points", "exit_reason", "cross_session", "cumulative_points", "drawdown_points",
    ]
    result = pd.DataFrame(trades)
    if result.empty:
        return pd.DataFrame(columns=columns)
    result.insert(0, "trade_number", range(1, len(result) + 1))
    result["cumulative_points"] = result["pnl_points"].cumsum()
    result["drawdown_points"] = result["cumulative_points"] - result["cumulative_points"].cummax()
    return result


def write_report(path: Path, args: argparse.Namespace, ticks: pd.DataFrame, hourly: pd.DataFrame, zones: pd.DataFrame, bars: pd.DataFrame, trades: pd.DataFrame, summary: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resistance_count = int((zones["zone_type"] == "resistance").sum()) if not zones.empty else 0
    text = f"""# TMF 202609：自適應 60 分 K Supertrend 壓力反轉空單回測

## 資料與持倉

- 商品 / 到期月份：`{args.product} / {args.contract_month}`
- 日檔範圍：`{args.start_date}` 至 `{args.end_date}`；有效 tick：{len(ticks):,} 筆。
- 實際成交資料截止：`{ticks['timestamp'].max():%Y-%m-%d %H:%M:%S}`。
- 2,000 口 volume bar：{len(bars):,} 根，跨日盤、夜盤與休市時段連續累積。
- 不強制在 `13:45` 或 `05:00` 平倉；未結束部位只在資料結尾以最後一根完成 volume bar close 結算。

## 進場

- 60 分 K 依 Pine pivot 與 delta volume 建立壓力箱；已確認壓力：{resistance_count} 個。
- 2,000 口 volume bar 必須接觸已確認、未失效壓力，為最近 {args.tick_lookback} 根高點、收黑，且 close 位於全幅下方 {args.close_position_max:.0%}。
- 訊號完成後，下一根 volume bar open 放空；同一時間最多一口。

## 自適應 60 分 K Supertrend 出場

- 基礎寬度：`ATR({args.atr_length}) × {args.base_multiplier:g}`；最小寬度：`ATR × {args.min_multiplier:g}`。
- 價格速度使用最近 {args.speed_lookback} 根 60 分 K 的 ATR 正規化移動，並以 {args.smoothing_span} 根平滑。
- 速度低於 {args.low_speed:g} 時使用較寬的基礎倍數；速度高於 {args.high_speed:g} 時收緊至最小倍數，中間線性調整。
- 已完成的 60 分 K Supertrend 從空頭翻多後，下一根 volume bar open 平空。volume bar 只讀取較早完成的小時 K 狀態，沒有 look-ahead。

## 結果

| Metric | Value |
| --- | ---: |
| Resistance + bearish volume-bar signals | {int(bars['resistance_reversal'].sum())} |
| Trades | {summary['trades']} |
| Wins / Losses | {summary.get('wins', 0)} / {summary.get('losses', 0)} |
| Win rate | {summary.get('win_rate', 0):.1f}% |
| Net P&L | {summary.get('net_points', 0):.1f} points |
| Profit factor | {summary.get('profit_factor', 'n/a')} |
| Maximum drawdown | {summary.get('max_drawdown', 0):.1f} points |
| Cross-session trades | {int(trades['cross_session'].sum()) if not trades.empty else 0} |

## Look-Ahead Bias 稽核

- 壓力 pivot 必須等右側 {args.pivot_lookback} 根 60 分 K 完成才建立，訊號時間早於壓力確認時間時不會交易。
- volume-bar 反轉只使用目前與更早的 {args.tick_lookback} 根 volume bar；同一秒多筆官方成交保留原始列順序。
- 自適應 ATR 倍數與 Supertrend 只在 60 分 K 收盤後計算。volume bar 以嚴格早於自身時間的小時 K 狀態判斷，不能使用同時或未完成的小時 K。
- Supertrend 翻轉被觀察到後，仍在下一根 volume bar open 才執行平倉。
- 官方 tick 時間只有秒級；前一根 volume bar 結束與下一根開始可以顯示同一秒，但程式保留官方 CSV 的列順序，實際仍是下一筆成交開始的新 bar，不是用同一根 bar 的未來價格成交。

## Trade Ledger

| # | Signal | Entry | Exit | Entry Px | Exit Px | P&L | Exit Reason | Cross Session |
|---:|---|---|---|---:|---:|---:|---|---|
"""
    if trades.empty:
        text += "| - | - | - | - | - | - | - | No eligible trade | - |\n"
    else:
        for trade in trades.itertuples(index=False):
            text += f"| {trade.trade_number} | {trade.signal_time:%Y-%m-%d %H:%M:%S} | {trade.entry_time:%Y-%m-%d %H:%M:%S} | {trade.exit_time:%Y-%m-%d %H:%M:%S} | {trade.entry_price:.0f} | {trade.exit_price:.0f} | {trade.pnl_points:.1f} | {trade.exit_reason} | {trade.cross_session} |\n"
    text += "\n結果未包含手續費、期交稅、價差與滑價。\n"
    path.write_text(text, encoding="utf-8")


def write_chart(path: Path, hourly: pd.DataFrame, zones: pd.DataFrame, bars: pd.DataFrame, trades: pd.DataFrame) -> None:
    figure = make_subplots(rows=3, cols=1, shared_xaxes=True, vertical_spacing=0.035, row_heights=[0.65, 0.18, 0.17], subplot_titles=("60-minute resistance and adaptive Supertrend", "Adaptive ATR multiplier", "Closed-trade equity"))
    figure.add_trace(go.Candlestick(x=hourly["timestamp"], open=hourly["open"], high=hourly["high"], low=hourly["low"], close=hourly["close"], name="60-minute bars"), row=1, col=1)
    figure.add_trace(go.Scatter(x=hourly["timestamp"], y=hourly["supertrend"], mode="lines", name="Adaptive Supertrend", line={"color": "#7b1fa2", "width": 2}), row=1, col=1)
    chart_end = hourly["timestamp"].iloc[-1]
    for zone in zones.itertuples(index=False):
        color = "rgba(211,47,47,0.16)" if zone.zone_type == "resistance" else "rgba(0,137,123,0.16)"
        end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
        figure.add_shape(type="rect", x0=zone.created_time, x1=end, y0=zone.bottom, y1=zone.top, fillcolor=color, line={"color": color.replace("0.16", "0.8"), "width": 1}, row=1, col=1)
    signals = bars[bars["resistance_reversal"]]
    figure.add_trace(go.Scatter(x=signals["timestamp"], y=signals["high"], mode="markers", name="Tick short signal", marker={"symbol": "triangle-down", "size": 10, "color": "#d32f2f"}), row=1, col=1)
    if not trades.empty:
        figure.add_trace(go.Scatter(x=trades["entry_time"], y=trades["entry_price"], mode="markers", name="Short entry", marker={"symbol": "triangle-down", "size": 13, "color": "#6a1b9a"}), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit", marker={"symbol": "x", "size": 10, "color": "#00897b"}), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["cumulative_points"], mode="lines+markers", name="Cumulative P&L", line={"color": "#3949ab"}), row=3, col=1)
    figure.add_trace(go.Scatter(x=hourly["timestamp"], y=hourly["adaptive_multiplier"], mode="lines", name="ATR multiplier", line={"color": "#ef6c00"}), row=2, col=1)
    figure.update_layout(title="TMF 202609: Continuous Adaptive Hourly Supertrend Short-only", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="ATR multiplier", row=2, col=1)
    figure.update_yaxes(title_text="Points", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Continuous adaptive-hourly-Supertrend short-only TMF backtest.")
    parser.add_argument("--input-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--start-date", type=parse_date, required=True)
    parser.add_argument("--end-date", type=parse_date, required=True)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--volume-bar-size", type=float, default=2000)
    parser.add_argument("--tick-lookback", type=int, default=5)
    parser.add_argument("--close-position-max", type=float, default=0.35)
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
    parser.add_argument("--trades-output", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    if not 0 < args.min_multiplier <= args.base_multiplier:
        parser.error("--min-multiplier must be positive and no greater than --base-multiplier")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must be greater than --low-speed")
    return args


def main() -> None:
    args = parse_args()
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    ticks = add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip()))
    hourly = build_hourly_bars(ticks)
    hourly = add_adaptive_supertrend(hourly, args.atr_length, args.base_multiplier, args.min_multiplier, args.speed_lookback, args.low_speed, args.high_speed, args.smoothing_span)
    zones = pine_style_zones(hourly, args.pivot_lookback, args.volume_filter_length, args.zone_atr_length, args.zone_box_width)
    bars = build_continuous_volume_bars(ticks, args.volume_bar_size)
    bars = detect_dense_reversals(bars, args.tick_lookback, 50, 0.75)
    bars = add_bearish_rejection_signals(bars, args.close_position_max)
    bars = assign_resistance_entries(bars, zones)
    bars = attach_hourly_state(bars, hourly)
    trades = backtest(bars)
    summary = metric_summary(trades)
    args.trades_output.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.trades_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, args, ticks, hourly, zones, bars, trades, summary)
    write_chart(args.chart_output, hourly, zones, bars, trades)
    print(f"ticks={len(ticks)} volume_bars={len(bars)} resistance_signals={int(bars['resistance_reversal'].sum())}")
    print(f"trades={summary['trades']} net_points={summary.get('net_points', 0):.1f}")
    print(f"report={args.report_output}")


if __name__ == "__main__":
    main()
