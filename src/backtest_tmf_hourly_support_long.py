#!/usr/bin/env python
"""Backtest long-only dense tick reversals at Pine-style hourly support zones."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_tmf_dense_long import (
        DEFAULT_OUTPUT_DIR,
        add_sessions,
        add_signals,
        build_session_bars,
        load_daily_ticks,
        metric_summary,
        parse_date,
        source_file_date,
    )
except ImportError:
    from backtest_tmf_dense_long import (
        DEFAULT_OUTPUT_DIR,
        add_sessions,
        add_signals,
        build_session_bars,
        load_daily_ticks,
        metric_summary,
        parse_date,
        source_file_date,
    )


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_REPORT = ROOT / "doc" / "tmf_202609_hourly_support_long_backtest_2026-09-01_to_2026-09-11.md"


@dataclass
class Position:
    entry_index: int
    entry_time: pd.Timestamp
    entry_price: float
    signal_time: pd.Timestamp
    initial_stop: float
    risk_r: float
    support_id: int
    resistance_id: int | None
    resistance_bottom: float | None
    highest_price: float
    trail_active: bool = False
    trailing_stop: float | None = None


def session_anchor(session_id: str) -> pd.Timestamp:
    date_text, session_type = session_id.split()
    session_date = pd.Timestamp(date_text)
    if session_type == "day":
        return session_date + pd.Timedelta(hours=8, minutes=45)
    return session_date - pd.Timedelta(days=1) + pd.Timedelta(hours=15)


def build_hourly_bars(ticks: pd.DataFrame) -> pd.DataFrame:
    records: list[dict[str, object]] = []
    for session_id, session_ticks in ticks.groupby("session_id", sort=True):
        frame = session_ticks.copy()
        anchor = session_anchor(session_id)
        frame["hour_start"] = anchor + pd.to_timedelta(
            ((frame["timestamp"] - anchor).dt.total_seconds() // 3600).astype(int), unit="h"
        )
        for start, hour_ticks in frame.groupby("hour_start", sort=True):
            records.append(
                {
                    "timestamp": hour_ticks["timestamp"].iloc[-1],
                    "hour_start": start,
                    "open": float(hour_ticks["price"].iloc[0]),
                    "high": float(hour_ticks["price"].max()),
                    "low": float(hour_ticks["price"].min()),
                    "close": float(hour_ticks["price"].iloc[-1]),
                    "volume": float(hour_ticks["quantity"].sum()),
                    "session_id": session_id,
                }
            )
    return pd.DataFrame(records).sort_values("timestamp", kind="stable").reset_index(drop=True)


def wilder_atr(bars: pd.DataFrame, length: int) -> pd.Series:
    previous_close = bars["close"].shift(1)
    true_range = pd.concat(
        [bars["high"] - bars["low"], (bars["high"] - previous_close).abs(), (bars["low"] - previous_close).abs()], axis=1
    ).max(axis=1)
    return true_range.ewm(alpha=1 / length, adjust=False, min_periods=length).mean()


def pine_style_zones(bars: pd.DataFrame, lookback: int, volume_length: int, atr_length: int, box_width: float) -> pd.DataFrame:
    """Replicate Pine's delayed close pivots, signed volume filter, and ATR boxes."""
    result = bars.copy()
    direction = np.sign(result["close"] - result["open"])
    is_buy = direction.replace(0, np.nan).ffill().fillna(1) > 0
    result["delta_volume"] = np.where(is_buy, result["volume"], -result["volume"])
    result["atr"] = wilder_atr(result, atr_length)
    zones: list[dict[str, object]] = []
    active_supports: list[dict[str, object]] = []
    active_resistances: list[dict[str, object]] = []
    zone_id = 0

    for confirmation_index in range(lookback * 2, len(result)):
        current = result.iloc[confirmation_index]
        candidate_index = confirmation_index - lookback
        candidate = result.iloc[candidate_index]
        window = result["close"].iloc[candidate_index - lookback : candidate_index + lookback + 1]
        recent_delta = result["delta_volume"].iloc[confirmation_index - volume_length + 1 : confirmation_index + 1]
        if len(recent_delta) < volume_length or pd.isna(current["atr"]):
            continue
        for zone in active_supports:
            if zone["broken_time"] is None and float(current["high"]) < zone["bottom"]:
                zone["broken_time"] = current["timestamp"]
        for zone in active_resistances:
            if zone["broken_time"] is None and float(current["low"]) > zone["top"]:
                zone["broken_time"] = current["timestamp"]

        width = float(current["atr"]) * box_width
        delta_volume = float(current["delta_volume"])
        if float(candidate["close"]) == float(window.min()) and delta_volume > float((recent_delta / 2.5).max()):
            zone_id += 1
            zone = {
                "zone_id": zone_id,
                "zone_type": "support",
                "pivot_time": candidate["timestamp"],
                "created_time": current["timestamp"],
                "top": float(candidate["close"]),
                "bottom": float(candidate["close"]) - width,
                "delta_volume": delta_volume,
                "broken_time": None,
            }
            zones.append(zone)
            active_supports.append(zone)
        if float(candidate["close"]) == float(window.max()) and delta_volume < float((recent_delta / 2.5).min()):
            zone_id += 1
            zone = {
                "zone_id": zone_id,
                "zone_type": "resistance",
                "pivot_time": candidate["timestamp"],
                "created_time": current["timestamp"],
                "bottom": float(candidate["close"]),
                "top": float(candidate["close"]) + width,
                "delta_volume": delta_volume,
                "broken_time": None,
            }
            zones.append(zone)
            active_resistances.append(zone)
    return pd.DataFrame(zones)


def zone_active(zone: pd.Series, timestamp: pd.Timestamp) -> bool:
    return bool(zone["created_time"] < timestamp and (pd.isna(zone["broken_time"]) or timestamp < zone["broken_time"]))


def assign_support_entries(volume_bars: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    result = volume_bars.copy()
    result["support_id"] = pd.NA
    result["support_top"] = np.nan
    result["support_bottom"] = np.nan
    supports = zones[zones["zone_type"] == "support"] if not zones.empty else zones
    for index, bar in result[result["bullish_reversal"]].iterrows():
        candidates = supports[
            supports.apply(lambda zone: zone_active(zone, bar["timestamp"]), axis=1)
            & (supports["top"] >= bar["low"])
            & (supports["bottom"] <= bar["high"])
        ]
        if not candidates.empty:
            selected = candidates.sort_values("top", ascending=False).iloc[0]
            result.loc[index, ["support_id", "support_top", "support_bottom"]] = [
                int(selected["zone_id"]), selected["top"], selected["bottom"]
            ]
    result["support_reversal"] = result["support_id"].notna()
    return result


def nearest_resistance(zones: pd.DataFrame, timestamp: pd.Timestamp, entry_price: float) -> tuple[int | None, float | None]:
    if zones.empty:
        return None, None
    candidates = zones[
        (zones["zone_type"] == "resistance")
        & (zones["bottom"] > entry_price)
        & zones.apply(lambda zone: zone_active(zone, timestamp), axis=1)
    ]
    if candidates.empty:
        return None, None
    zone = candidates.sort_values("bottom").iloc[0]
    return int(zone["zone_id"]), float(zone["bottom"])


def make_trade(position: Position, bars: pd.DataFrame, exit_index: int, reason: str, exit_price: float) -> dict[str, object]:
    held = bars.iloc[position.entry_index : exit_index + 1]
    high = max(position.highest_price, float(held["high"].max()))
    low = float(held["low"].min())
    pnl = exit_price - position.entry_price
    return {
        "signal_time": position.signal_time, "entry_time": position.entry_time,
        "exit_time": bars.iloc[exit_index]["timestamp"], "session_id": bars.iloc[position.entry_index]["session_id"],
        "entry_price": position.entry_price, "exit_price": exit_price, "initial_stop": position.initial_stop,
        "risk_r": position.risk_r, "support_id": position.support_id, "resistance_id": position.resistance_id,
        "resistance_target": position.resistance_bottom, "pnl_points": pnl, "pnl_r": pnl / position.risk_r,
        "mfe_points": high - position.entry_price, "mae_points": low - position.entry_price,
        "exit_reason": reason, "trail_active": position.trail_active, "trailing_stop": position.trailing_stop,
    }


def backtest(bars: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    trades: list[dict[str, object]] = []
    for _, session_bars in bars.groupby("session_id", sort=True):
        frame = session_bars.reset_index(drop=True)
        position: Position | None = None
        signal_index: int | None = None
        scheduled_exit: str | None = None
        for index, bar in frame.iterrows():
            if position is not None and scheduled_exit is not None:
                trades.append(make_trade(position, frame, index, scheduled_exit, float(bar["open"])))
                position, scheduled_exit, signal_index = None, None, None
                continue
            if position is None:
                if signal_index is not None:
                    signal = frame.iloc[signal_index]
                    entry = float(bar["open"])
                    stop = float(signal["low"]) - 2.0
                    risk = entry - stop
                    if risk > 0:
                        resistance_id, resistance_bottom = nearest_resistance(zones, bar["bar_start_time"], entry)
                        position = Position(index, bar["bar_start_time"], entry, signal["timestamp"], stop, risk, int(signal["support_id"]), resistance_id, resistance_bottom, float(bar["high"]))
                    signal_index = None
                if position is None and bool(bar["support_reversal"]) and index < len(frame) - 1:
                    signal_index = index
                    continue
                if position is None:
                    continue
            position.highest_price = max(position.highest_price, float(bar["high"]))
            if float(bar["low"]) <= position.initial_stop:
                scheduled_exit = "initial_stop_breach"
            elif position.resistance_bottom is not None and float(bar["high"]) >= position.resistance_bottom:
                scheduled_exit = "resistance_touch"
            else:
                if position.highest_price >= position.entry_price + 2 * position.risk_r:
                    position.trail_active = True
                    position.trailing_stop = position.highest_price - position.risk_r
                if position.trail_active and float(bar["close"]) <= float(position.trailing_stop):
                    scheduled_exit = "trailing_stop_close_breach"
                elif bool(bar["bearish_reversal"]):
                    scheduled_exit = "bearish_dense_reversal"
        if position is not None:
            last = frame.iloc[-1]
            trades.append(make_trade(position, frame, len(frame) - 1, "session_end", float(last["close"])))
    trade_columns = [
        "trade_number", "signal_time", "entry_time", "exit_time", "session_id", "entry_price", "exit_price",
        "initial_stop", "risk_r", "support_id", "resistance_id", "resistance_target", "pnl_points", "pnl_r",
        "mfe_points", "mae_points", "exit_reason", "trail_active", "trailing_stop", "cumulative_points", "drawdown_points",
    ]
    trades_frame = pd.DataFrame(trades)
    if not trades_frame.empty:
        trades_frame.insert(0, "trade_number", range(1, len(trades_frame) + 1))
        trades_frame["cumulative_points"] = trades_frame["pnl_points"].cumsum()
        trades_frame["drawdown_points"] = trades_frame["cumulative_points"] - trades_frame["cumulative_points"].cummax()
    else:
        trades_frame = pd.DataFrame(columns=trade_columns)
    return trades_frame


def trade_table(trades: pd.DataFrame) -> str:
    if trades.empty:
        return "沒有符合「已確認支撐 + tick 多方反轉」的多單。"
    rows = ["| # | Support | Signal | Entry | Exit | P&L | Reason |", "|---:|---:|---|---|---|---:|---|"]
    for trade in trades.itertuples(index=False):
        rows.append(
            f"| {trade.trade_number} | {trade.support_id} | {trade.signal_time:%Y-%m-%d %H:%M:%S} | "
            f"{trade.entry_time:%Y-%m-%d %H:%M:%S} @ {trade.entry_price:.0f} | "
            f"{trade.exit_time:%Y-%m-%d %H:%M:%S} @ {trade.exit_price:.0f} | {trade.pnl_points:.1f} | {trade.exit_reason} |"
        )
    return "\n".join(rows)


def write_report(path: Path, bars: pd.DataFrame, hourly: pd.DataFrame, zones: pd.DataFrame, trades: pd.DataFrame, summary: dict[str, object], sources: list[Path], args: argparse.Namespace) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    text = f"""# TMF 202609：60 分 K 支撐 + Tick 反轉僅做多回測

## 資料與時段

- 日檔：{', '.join(source.name for source in sources)}
- 商品：`{args.product} / {args.contract_month}`；逐筆成交：{args.tick_count:,} 筆。
- 交易時段：日盤 `08:45–13:45`，夜盤 `15:00–次日 05:00`。不跨時段累積 2,000 口 K 棒，也不隔夜留倉。
- 60 分 K：{len(hourly)} 根；2,000 口 volume bar：{len(bars):,} 根。

## 支撐壓力計算

依照 `pine_script.txt` 的邏輯，以 60 分 K 的 **close** 尋找左右各 {args.pivot_lookback} 根 K 的 pivot low/high。pivot 必須等右側 K 線完成後才確認，因此不會在轉折當下提前知道支撐。

- 支撐：pivot low，且確認 K 為正 delta volume；箱體為 `pivot close` 到 `pivot close - ATR({args.atr_length}) × {args.box_width:g}`。
- 壓力：pivot high，且確認 K 為負 delta volume；箱體向上使用同一 ATR 寬度。
- Pine 原稿使用 `ATR(200)`；本資料只有 {len(hourly)} 根 60 分 K，無法完成 200 根初始化，故本回測使用 `ATR({args.atr_length})`。
- 已確認 zones：支撐 {int((zones.zone_type == 'support').sum()) if not zones.empty else 0} 個、壓力 {int((zones.zone_type == 'resistance').sum()) if not zones.empty else 0} 個。

## 交易規則

- 僅當一根 2,000 口 volume bar 出現原策略的多方密集反轉，且該 bar 價格範圍接觸一個已確認、未跌破的 60 分 K 支撐箱體，才建立做多訊號。
- 訊號完成後，以**下一根** volume bar open 進場；同一時間最多一口多單。
- 初始停損為訊號 bar low - 2 點。停損、壓力觸及、追蹤停損與空方密集反轉都在 bar 完成後確認，再以下一根 open 出場。
- 最高價達 `+2R` 時，啟用最高價 - `1R` 的追蹤停損。若進場時已有上方已確認壓力，觸及壓力箱體下緣也會出場。

## 結果

| Metric | Value |
| --- | ---: |
| Trades | {summary['trades']} |
| Wins / Losses | {summary.get('wins', 0)} / {summary.get('losses', 0)} |
| Win rate | {summary.get('win_rate', 0):.1f}% |
| Net P&L | {summary.get('net_points', 0):.1f} points |
| Profit factor | {summary.get('profit_factor', 'n/a')} |
| Average P&L | {summary.get('average_points', 0):.1f} points |
| Maximum drawdown | {summary.get('max_drawdown', 0):.1f} points |

## Trade Ledger

{trade_table(trades)}

## 限制

結果未扣手續費、期交稅、買賣價差與滑價。Pine 的 pivot 需要右側 {args.pivot_lookback} 根 60 分 K 才確認，回測也只在確認後的 tick 訊號交易，避免 look-ahead bias。
"""
    path.write_text(text, encoding="utf-8")


def write_chart(path: Path, hourly: pd.DataFrame, zones: pd.DataFrame, volume_bars: pd.DataFrame, trades: pd.DataFrame) -> None:
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.78, 0.22], subplot_titles=("TMF 60-minute support/resistance and trades", "Closed-trade equity"))
    figure.add_trace(go.Candlestick(x=hourly["timestamp"], open=hourly["open"], high=hourly["high"], low=hourly["low"], close=hourly["close"], name="60-minute bars"), row=1, col=1)
    chart_end = hourly["timestamp"].iloc[-1]
    if not zones.empty:
        for zone in zones.itertuples(index=False):
            color = "rgba(0,137,123,0.18)" if zone.zone_type == "support" else "rgba(211,47,47,0.16)"
            end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
            figure.add_shape(type="rect", x0=zone.created_time, x1=end, y0=zone.bottom, y1=zone.top, fillcolor=color, line={"color": color.replace("0.18", "0.8").replace("0.16", "0.8"), "width": 1}, row=1, col=1)
    marked = volume_bars[volume_bars["support_reversal"]]
    figure.add_trace(go.Scatter(x=marked["timestamp"], y=marked["low"], mode="markers", name="Support tick reversal", marker={"symbol": "triangle-up", "size": 9, "color": "#00897b"}), row=1, col=1)
    if not trades.empty:
        figure.add_trace(go.Scatter(x=trades["entry_time"], y=trades["entry_price"], mode="markers", name="Long entry", marker={"symbol": "triangle-up", "size": 13, "color": "#1565c0"}), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit", marker={"symbol": "x", "size": 10, "color": "#d32f2f"}, text=trades["exit_reason"], hovertemplate="%{x}<br>%{y}<br>%{text}<extra></extra>"), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["cumulative_points"], mode="lines+markers", name="Cumulative P&L", line={"color": "#3949ab"}), row=2, col=1)
    figure.update_layout(title="TMF 202609: Hourly Support + Tick Reversal Long-only", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Points", row=2, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest hourly Pine-style support with tick reversal confirmation.")
    parser.add_argument("--input-dir", type=Path, default=Path.home() / "Downloads")
    parser.add_argument("--start-date", type=parse_date, required=True)
    parser.add_argument("--end-date", type=parse_date, required=True)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--volume-bar-size", type=float, default=2000)
    parser.add_argument("--density-window", type=int, default=50)
    parser.add_argument("--density-quantile", type=float, default=0.75)
    parser.add_argument("--tick-lookback-bars", type=int, default=5)
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--atr-length", type=int, default=20)
    parser.add_argument("--box-width", type=float, default=1.0)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_OUTPUT_DIR / "TMF_202609_hourly_support_long_backtest_2026-09-01_to_2026-09-11.html")
    parser.add_argument("--trades-output", type=Path, default=DEFAULT_OUTPUT_DIR / "TMF_202609_hourly_support_long_trades_2026-09-01_to_2026-09-11.csv")
    parser.add_argument("--hourly-output", type=Path, default=DEFAULT_OUTPUT_DIR / "TMF_202609_hourly_bars_2026-09-01_to_2026-09-11.csv")
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    return args


def main() -> None:
    args = parse_args()
    sources = sorted(path for path in args.input_dir.glob("Daily_*.zip") if (file_date := source_file_date(path)) is not None and args.start_date <= file_date <= args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.zip files were found.")
    ticks = add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip()))
    args.tick_count = len(ticks)
    hourly = build_hourly_bars(ticks)
    zones = pine_style_zones(hourly, args.pivot_lookback, args.volume_filter_length, args.atr_length, args.box_width)
    volume_bars = add_signals(build_session_bars(ticks, args.volume_bar_size, args.density_window + 1), args.tick_lookback_bars, args.density_window, args.density_quantile)
    volume_bars = assign_support_entries(volume_bars, zones)
    trades = backtest(volume_bars, zones)
    summary = metric_summary(trades)
    for output in (args.trades_output, args.hourly_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.trades_output, index=False, encoding="utf-8-sig")
    hourly.to_csv(args.hourly_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, volume_bars, hourly, zones, trades, summary, sources, args)
    write_chart(args.chart_output, hourly, zones, volume_bars, trades)
    print(f"ticks={len(ticks)} hourly_bars={len(hourly)} support_zones={int((zones.zone_type == 'support').sum()) if not zones.empty else 0}")
    print(f"trades={summary['trades']} net_points={summary.get('net_points', 0):.1f}")
    print(f"report={args.report_output}")


if __name__ == "__main__":
    main()
