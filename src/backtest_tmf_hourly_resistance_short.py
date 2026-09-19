#!/usr/bin/env python
"""Backtest short-only dense tick reversals at Pine-style hourly resistance."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_tmf_dense_long import metric_summary
    from .backtest_tmf_hourly_support_long import pine_style_zones, zone_active
except ImportError:
    from backtest_tmf_dense_long import metric_summary
    from backtest_tmf_hourly_support_long import pine_style_zones, zone_active


ROOT = Path(__file__).resolve().parents[1]
TICK_DIR = ROOT / "txf_tick"
DEFAULT_HOURLY = TICK_DIR / "TMF_202609_hourly_bars_2026-09-01_to_2026-09-11.csv"
DEFAULT_VOLUME_BARS = TICK_DIR / "TMF_202609_volume_bars_2026-09-01_to_2026-09-11.csv"
DEFAULT_TRADES = TICK_DIR / "TMF_202609_hourly_resistance_short_trades_2026-09-01_to_2026-09-11.csv"
DEFAULT_CHART = TICK_DIR / "TMF_202609_hourly_resistance_short_backtest_2026-09-01_to_2026-09-11.html"
DEFAULT_REPORT = ROOT / "doc" / "tmf_202609_hourly_resistance_short_backtest_2026-09-01_to_2026-09-11.md"


@dataclass
class ShortPosition:
    entry_index: int
    entry_time: pd.Timestamp
    entry_price: float
    signal_time: pd.Timestamp
    entry_hourly_supertrend: float | None
    entry_hourly_direction: int | None
    last_hourly_direction: int | None
    resistance_id: int


def add_bearish_rejection_signals(bars: pd.DataFrame, close_position_max: float) -> pd.DataFrame:
    """Find bearish volume-bar reversals without requiring an extreme trade rate."""
    result = bars.copy()
    price_range = (result["high"] - result["low"]).replace(0, np.nan)
    result["close_position"] = (result["close"] - result["low"]) / price_range
    result["bearish_rejection"] = (
        result["recent_high"]
        & (result["close"] < result["open"])
        & (result["close_position"] <= close_position_max)
    )
    return result


def add_supertrend(bars: pd.DataFrame, atr_length: int, multiplier: float) -> pd.DataFrame:
    """Calculate a session-local Supertrend from completed 2,000-contract bars."""
    groups: list[pd.DataFrame] = []
    for _, frame in bars.groupby("session_id", sort=True):
        result = frame.copy().reset_index(drop=True)
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

        result["supertrend"] = supertrend
        result["supertrend_direction"] = direction
        groups.append(result)
    return pd.concat(groups, ignore_index=True)


def add_hourly_supertrend(hourly: pd.DataFrame, atr_length: int, multiplier: float) -> pd.DataFrame:
    """Calculate continuous 60-minute Supertrend, including across session breaks."""
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

    result["supertrend"] = supertrend
    result["supertrend_direction"] = direction
    return result


def attach_hourly_supertrend(volume_bars: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    """Attach only the last *previously completed* hourly Supertrend to every volume bar."""
    right = hourly[["timestamp", "supertrend", "supertrend_direction"]].rename(
        columns={
            "timestamp": "hourly_confirmation_time",
            "supertrend": "hourly_supertrend",
            "supertrend_direction": "hourly_supertrend_direction",
        }
    )
    left = volume_bars.sort_values("timestamp", kind="stable")
    return pd.merge_asof(
        left,
        right.sort_values("hourly_confirmation_time", kind="stable"),
        left_on="timestamp",
        right_on="hourly_confirmation_time",
        direction="backward",
        allow_exact_matches=False,
    )


def assign_resistance_entries(bars: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    result = bars.copy()
    result["resistance_id"] = pd.NA
    result["resistance_bottom"] = np.nan
    result["resistance_top"] = np.nan
    resistances = zones[zones["zone_type"] == "resistance"] if not zones.empty else zones
    for index, bar in result[result["bearish_rejection"]].iterrows():
        candidates = resistances[
            resistances.apply(lambda zone: zone_active(zone, bar["timestamp"]), axis=1)
            & (resistances["bottom"] <= bar["high"])
            & (resistances["top"] >= bar["low"])
        ]
        if not candidates.empty:
            selected = candidates.sort_values("bottom").iloc[0]
            result.loc[index, ["resistance_id", "resistance_bottom", "resistance_top"]] = [
                int(selected["zone_id"]), selected["bottom"], selected["top"]
            ]
    result["resistance_reversal"] = result["resistance_id"].notna()
    return result


def nearest_support(zones: pd.DataFrame, timestamp: pd.Timestamp, entry_price: float) -> tuple[int | None, float | None]:
    if zones.empty:
        return None, None
    supports = zones[
        (zones["zone_type"] == "support")
        & (zones["top"] < entry_price)
        & zones.apply(lambda zone: zone_active(zone, timestamp), axis=1)
    ]
    if supports.empty:
        return None, None
    selected = supports.sort_values("top", ascending=False).iloc[0]
    return int(selected["zone_id"]), float(selected["top"])


def make_trade(position: ShortPosition, bars: pd.DataFrame, exit_index: int, reason: str, exit_price: float) -> dict[str, object]:
    held = bars.iloc[position.entry_index : exit_index + 1]
    lowest = float(held["low"].min())
    highest = float(held["high"].max())
    pnl = position.entry_price - exit_price
    return {
        "signal_time": position.signal_time, "entry_time": position.entry_time,
        "exit_time": bars.iloc[exit_index]["timestamp"], "session_id": bars.iloc[position.entry_index]["session_id"],
        "entry_price": position.entry_price, "exit_price": exit_price,
        "entry_hourly_supertrend": position.entry_hourly_supertrend,
        "entry_hourly_direction": position.entry_hourly_direction,
        "resistance_id": position.resistance_id,
        "pnl_points": pnl, "pnl_r": np.nan,
        "mfe_points": position.entry_price - lowest, "mae_points": position.entry_price - highest,
        "exit_reason": reason,
    }


def backtest_short_only(bars: pd.DataFrame, zones: pd.DataFrame) -> pd.DataFrame:
    trades: list[dict[str, object]] = []
    for _, session_bars in bars.groupby("session_id", sort=True):
        frame = session_bars.reset_index(drop=True)
        position: ShortPosition | None = None
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
                    hourly_supertrend = None if pd.isna(signal["hourly_supertrend"]) else float(signal["hourly_supertrend"])
                    hourly_direction = None if pd.isna(signal["hourly_supertrend_direction"]) else int(signal["hourly_supertrend_direction"])
                    position = ShortPosition(
                        index,
                        bar["bar_start_time"],
                        entry,
                        signal["timestamp"],
                        hourly_supertrend,
                        hourly_direction,
                        hourly_direction,
                        int(signal["resistance_id"]),
                    )
                    signal_index = None
                if position is None and bool(bar["resistance_reversal"]) and index < len(frame) - 1:
                    signal_index = index
                    continue
                if position is None:
                    continue
            direction = None if pd.isna(bar["hourly_supertrend_direction"]) else int(bar["hourly_supertrend_direction"])
            if position.last_hourly_direction == -1 and direction == 1:
                scheduled_exit = "hourly_supertrend_bullish_flip"
            if direction is not None:
                position.last_hourly_direction = direction
        if position is not None:
            last = frame.iloc[-1]
            trades.append(make_trade(position, frame, len(frame) - 1, "session_end", float(last["close"])))

    columns = [
        "trade_number", "signal_time", "entry_time", "exit_time", "session_id", "entry_price", "exit_price",
        "entry_hourly_supertrend", "entry_hourly_direction", "resistance_id", "pnl_points", "pnl_r", "mfe_points", "mae_points",
        "exit_reason", "cumulative_points", "drawdown_points",
    ]
    result = pd.DataFrame(trades)
    if result.empty:
        return pd.DataFrame(columns=columns)
    result.insert(0, "trade_number", range(1, len(result) + 1))
    result["cumulative_points"] = result["pnl_points"].cumsum()
    result["drawdown_points"] = result["cumulative_points"] - result["cumulative_points"].cummax()
    return result


def write_report(
    path: Path,
    zones: pd.DataFrame,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, object],
    close_position_max: float,
    supertrend_atr_length: int,
    supertrend_multiplier: float,
) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    resistance_count = int((zones["zone_type"] == "resistance").sum()) if not zones.empty else 0
    signals = int(bars["resistance_reversal"].sum())
    rows = "沒有符合已確認壓力區的空方 tick 反轉。"
    if not trades.empty:
        rows = "\n".join(
            f"| {trade.trade_number} | {trade.resistance_id} | {trade.signal_time:%Y-%m-%d %H:%M:%S} | {trade.entry_price:.0f} | {trade.exit_time:%Y-%m-%d %H:%M:%S} | {trade.exit_price:.0f} | {trade.pnl_points:.1f} | {trade.exit_reason} |"
            for trade in trades.itertuples(index=False)
        )
        rows = "| # | Resistance | Signal | Entry | Exit | Exit Px | P&L | Reason |\n|---:|---:|---|---:|---|---:|---:|---|\n" + rows
    text = f"""# TMF 202609：60 分 K 壓力 + Tick 反轉僅做空回測

## 規則

- 僅在已確認、尚未突破的 60 分 K 壓力箱內，出現 2,000 口 K 的空方反轉時放空。
- 空方反轉必須是最近 5 根 volume bar 的高點、收黑，且 close 位於全幅下方 {close_position_max:.0%}；不要求成交速度超過密集成交門檻。
- 訊號完成後，下一根 volume bar open 進場；同一時間只持有一口空單。
- 不使用固定點數停損或固定獲利目標。以連續 60 分 K 的 Supertrend `ATR({supertrend_atr_length}) × {supertrend_multiplier:g}` 管理部位。
- 空單存續期間，已完成的 60 分 K Supertrend 從空頭翻為多頭後，在下一根 volume bar open 平倉；交易時段結束仍強制平倉。
- 日盤 `08:45–13:45`、夜盤 `15:00–次日 05:00`；不跨時段留倉。

## 結果

| Metric | Value |
| --- | ---: |
| Confirmed resistance zones | {resistance_count} |
| Resistance + bearish tick signals | {signals} |
| Trades | {summary['trades']} |
| Wins / Losses | {summary.get('wins', 0)} / {summary.get('losses', 0)} |
| Win rate | {summary.get('win_rate', 0):.1f}% |
| Net P&L | {summary.get('net_points', 0):.1f} points |
| Profit factor | {summary.get('profit_factor', 'n/a')} |
| Maximum drawdown | {summary.get('max_drawdown', 0):.1f} points |

## Trade Ledger

{rows}

結果未計入手續費、期交稅、價差及滑價。壓力 pivot 要等右側 20 根 60 分 K 完成才使用，tick 訊號也在完成後才以下一根 bar open 執行，因此沒有使用未來資料。
"""
    path.write_text(text, encoding="utf-8")


def write_chart(path: Path, hourly: pd.DataFrame, zones: pd.DataFrame, bars: pd.DataFrame, trades: pd.DataFrame) -> None:
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.78, 0.22], vertical_spacing=0.04)
    figure.add_trace(go.Candlestick(x=hourly["timestamp"], open=hourly["open"], high=hourly["high"], low=hourly["low"], close=hourly["close"], name="60-minute bars"), row=1, col=1)
    figure.add_trace(go.Scatter(x=hourly["timestamp"], y=hourly["supertrend"], mode="lines", name="60-minute Supertrend", line={"color": "#7b1fa2", "width": 2}), row=1, col=1)
    end = hourly["timestamp"].iloc[-1]
    for zone in zones.itertuples(index=False):
        color = "rgba(211,47,47,0.16)" if zone.zone_type == "resistance" else "rgba(0,137,123,0.16)"
        zone_end = zone.broken_time if pd.notna(zone.broken_time) else end
        figure.add_shape(type="rect", x0=zone.created_time, x1=zone_end, y0=zone.bottom, y1=zone.top, fillcolor=color, line={"color": color.replace("0.16", "0.8"), "width": 1}, row=1, col=1)
    signals = bars[bars["resistance_reversal"]]
    figure.add_trace(go.Scatter(x=signals["timestamp"], y=signals["high"], mode="markers", name="Resistance bearish reversal", marker={"symbol": "triangle-down", "size": 10, "color": "#d32f2f"}), row=1, col=1)
    if not trades.empty:
        figure.add_trace(go.Scatter(x=trades["entry_time"], y=trades["entry_price"], mode="markers", name="Short entry", marker={"symbol": "triangle-down", "size": 13, "color": "#6a1b9a"}), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit", marker={"symbol": "x", "size": 10, "color": "#00897b"}), row=1, col=1)
        figure.add_trace(go.Scatter(x=trades["exit_time"], y=trades["cumulative_points"], mode="lines+markers", name="Cumulative P&L", line={"color": "#3949ab"}), row=2, col=1)
    figure.update_layout(title="TMF 202609: Hourly Resistance + Tick Reversal Short-only", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Points", row=2, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest short-only hourly resistance and tick reversals.")
    parser.add_argument("--hourly-source", type=Path, default=DEFAULT_HOURLY)
    parser.add_argument("--volume-bars-source", type=Path, default=DEFAULT_VOLUME_BARS)
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--atr-length", type=int, default=20)
    parser.add_argument("--box-width", type=float, default=1.0)
    parser.add_argument("--close-position-max", type=float, default=0.35)
    parser.add_argument("--hourly-supertrend-atr-length", type=int, default=10)
    parser.add_argument("--hourly-supertrend-multiplier", type=float, default=3.0)
    parser.add_argument("--trades-output", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    hourly = pd.read_csv(args.hourly_source, encoding="utf-8-sig")
    bars = pd.read_csv(args.volume_bars_source, encoding="utf-8-sig")
    for column in ("timestamp", "hour_start"):
        hourly[column] = pd.to_datetime(hourly[column])
    for column in ("timestamp", "bar_start_time"):
        bars[column] = pd.to_datetime(bars[column])
    zones = pine_style_zones(hourly, args.pivot_lookback, args.volume_filter_length, args.atr_length, args.box_width)
    hourly = add_hourly_supertrend(
        hourly,
        args.hourly_supertrend_atr_length,
        args.hourly_supertrend_multiplier,
    )
    bars = add_bearish_rejection_signals(bars, args.close_position_max)
    bars = assign_resistance_entries(bars, zones)
    bars = attach_hourly_supertrend(bars, hourly)
    trades = backtest_short_only(bars, zones)
    summary = metric_summary(trades)
    args.trades_output.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(args.trades_output, index=False, encoding="utf-8-sig")
    write_report(
        args.report_output,
        zones,
        bars,
        trades,
        summary,
        args.close_position_max,
        args.hourly_supertrend_atr_length,
        args.hourly_supertrend_multiplier,
    )
    write_chart(args.chart_output, hourly, zones, bars, trades)
    print(f"resistance_signals={int(bars['resistance_reversal'].sum())} trades={summary['trades']} net_points={summary.get('net_points', 0):.1f}")
    print(f"report={args.report_output}")


if __name__ == "__main__":
    main()
