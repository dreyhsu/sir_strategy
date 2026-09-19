#!/usr/bin/env python
"""Standalone Strategy B backtest for TMF adaptive-hourly resistance shorts."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_tmf_adaptive_hourly_resistance_short import DATA_DIR, TICK_DIR, add_adaptive_supertrend
    from .backtest_tmf_adaptive_hourly_resistance_short_ab import (
        add_strategy_b_signals,
        attach_strategy_b_hourly_state,
        backtest_strategy_b,
        build_session_volume_bars,
        performance_summary,
    )
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_resistance_short import assign_resistance_entries
    from .backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones
except ImportError:
    from backtest_tmf_adaptive_hourly_resistance_short import DATA_DIR, TICK_DIR, add_adaptive_supertrend
    from backtest_tmf_adaptive_hourly_resistance_short_ab import (
        add_strategy_b_signals,
        attach_strategy_b_hourly_state,
        backtest_strategy_b,
        build_session_volume_bars,
        performance_summary,
    )
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_resistance_short import assign_resistance_entries
    from backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones


ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "doc"


def write_strategy_b_report(
    path: Path,
    args: argparse.Namespace,
    ticks: pd.DataFrame,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    summary = performance_summary(trades, "pnl_points")
    gross = performance_summary(trades, "gross_pnl_points")
    text = f"""# TMF {args.contract_month} Strategy B 回測

## 資料與策略

- 日檔範圍：`{args.start_date}` 至 `{args.end_date}`；實際資料截止 `{ticks['timestamp'].max():%Y-%m-%d %H:%M:%S}`。
- 有效 tick：{len(ticks):,} 筆；session-reset {args.volume_bar_size:,.0f} 口 volume bar：{len(bars):,} 根。
- 進出場各使用 `{args.slippage_points:g}` 點不利滑價。
- 初始停損：`max(signal high, resistance top) + hourly ATR × {args.initial_stop_atr_multiplier:g}`。
- Supertrend 確認逾時：`{args.confirmation_timeout_hours:g}` 小時；最大持倉：`{args.maximum_holding_hours:g}` 小時。
- Supertrend 確認翻空後使用 `lowest price + hourly ATR × {args.trailing_atr_multiplier:g}` 追蹤停損。

## 結果

| Metric | Gross | Net after slippage |
| --- | ---: | ---: |
| Trades | {gross['trades']} | {summary['trades']} |
| Wins / Losses | {gross['wins']} / {gross['losses']} | {summary['wins']} / {summary['losses']} |
| Win rate | {gross['win_rate']:.1f}% | {summary['win_rate']:.1f}% |
| P&L | {gross['net']:.1f} points | {summary['net']:.1f} points |
| Profit factor | {gross['profit_factor']} | {summary['profit_factor']} |
| Maximum drawdown | {gross['max_drawdown']:.1f} points | {summary['max_drawdown']:.1f} points |
| Average holding | {summary.get('average_holding_hours', 0):.1f} hours | {summary.get('average_holding_hours', 0):.1f} hours |
| Maximum holding | {summary.get('maximum_holding_hours', 0):.1f} hours | {summary.get('maximum_holding_hours', 0):.1f} hours |

## Exit Reasons

| Exit reason | Trades | Net P&L |
| --- | ---: | ---: |
"""
    if trades.empty:
        text += "| No eligible trade | 0 | 0.0 |\n"
    else:
        reasons = trades.groupby("exit_reason")["pnl_points"].agg(["count", "sum"])
        for reason, row in reasons.iterrows():
            text += f"| {reason} | {int(row['count'])} | {row['sum']:.1f} |\n"
    text += "\n結果未包含手續費、期交稅與買賣價差。\n"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_strategy_b_chart(
    path: Path,
    hourly: pd.DataFrame,
    zones: pd.DataFrame,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
) -> None:
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.65, 0.18, 0.17],
        subplot_titles=(
            "60-minute resistance and adaptive Supertrend",
            "Adaptive ATR multiplier",
            "Strategy B net equity",
        ),
    )
    figure.add_trace(
        go.Candlestick(
            x=hourly["timestamp"],
            open=hourly["open"],
            high=hourly["high"],
            low=hourly["low"],
            close=hourly["close"],
            name="60-minute bars",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=hourly["timestamp"],
            y=hourly["supertrend"],
            mode="lines",
            name="Adaptive Supertrend",
            line={"color": "#7b1fa2", "width": 2},
        ),
        row=1,
        col=1,
    )
    chart_end = hourly["timestamp"].iloc[-1]
    for zone in zones.itertuples(index=False):
        color = "rgba(211,47,47,0.16)" if zone.zone_type == "resistance" else "rgba(0,137,123,0.16)"
        end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
        figure.add_shape(
            type="rect",
            x0=zone.created_time,
            x1=end,
            y0=zone.bottom,
            y1=zone.top,
            fillcolor=color,
            line={"color": color.replace("0.16", "0.8"), "width": 1},
            row=1,
            col=1,
        )
    signals = bars[bars["resistance_reversal"]]
    figure.add_trace(
        go.Scatter(
            x=signals["timestamp"],
            y=signals["high"],
            mode="markers",
            name="Session-reset short signal",
            marker={"symbol": "triangle-down", "size": 9, "color": "#d32f2f"},
        ),
        row=1,
        col=1,
    )
    if not trades.empty:
        entry_custom = np.column_stack([trades["raw_entry_price"], trades["initial_stop"], trades["entry_hourly_atr"]])
        figure.add_trace(
            go.Scatter(
                x=trades["entry_time"],
                y=trades["entry_fill_price"],
                mode="markers",
                name="Strategy B short entry",
                marker={"symbol": "triangle-down", "size": 13, "color": "#6a1b9a"},
                customdata=entry_custom,
                hovertemplate=(
                    "Entry: %{x}<br>Fill: %{y:.0f}<br>Raw tick: %{customdata[0]:.0f}"
                    "<br>Initial stop: %{customdata[1]:.1f}<br>Hourly ATR: %{customdata[2]:.1f}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
        exit_custom = np.column_stack([trades["raw_exit_price"], trades["pnl_points"], trades["holding_hours"]])
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"],
                y=trades["exit_fill_price"],
                mode="markers",
                name="Strategy B exit",
                marker={"symbol": "x", "size": 10, "color": "#00897b"},
                text=trades["exit_reason"],
                customdata=exit_custom,
                hovertemplate=(
                    "Exit: %{x}<br>Fill: %{y:.0f}<br>Raw tick: %{customdata[0]:.0f}"
                    "<br>Net P&L: %{customdata[1]:.1f}<br>Holding: %{customdata[2]:.1f} h"
                    "<br>Reason: %{text}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"],
                y=trades["cumulative_points"],
                mode="lines+markers",
                name="Cumulative net P&L",
                line={"color": "#3949ab"},
            ),
            row=3,
            col=1,
        )
    figure.add_trace(
        go.Scatter(
            x=hourly["timestamp"],
            y=hourly["adaptive_multiplier"],
            mode="lines",
            name="ATR multiplier",
            line={"color": "#ef6c00"},
        ),
        row=2,
        col=1,
    )
    summary = performance_summary(trades, "pnl_points")
    figure.update_layout(
        title=(
            "TMF Strategy B: Session-reset Adaptive Hourly Supertrend Short-only"
            f" — {summary['trades']} trades, net {summary['net']:.1f}, max DD {summary['max_drawdown']:.1f}"
        ),
        xaxis_rangeslider_visible=False,
    )
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="ATR multiplier", row=2, col=1)
    figure.update_yaxes(title_text="Points", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Run standalone TMF Strategy B backtest.")
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
    parser.add_argument("--slippage-points", type=float, default=2.0)
    parser.add_argument("--initial-stop-atr-multiplier", type=float, default=0.5)
    parser.add_argument("--confirmation-timeout-hours", type=float, default=12.0)
    parser.add_argument("--maximum-holding-hours", type=float, default=120.0)
    parser.add_argument("--trailing-atr-multiplier", type=float, default=1.5)
    parser.add_argument("--trades-output", type=Path)
    parser.add_argument("--chart-output", type=Path)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    positive = (
        args.volume_bar_size,
        args.tick_lookback,
        args.atr_length,
        args.initial_stop_atr_multiplier,
        args.confirmation_timeout_hours,
        args.maximum_holding_hours,
        args.trailing_atr_multiplier,
    )
    if any(value <= 0 for value in positive) or args.slippage_points < 0:
        parser.error("bar, lookback, ATR, timeout, holding, trailing, and stop values must be positive")
    return args


def main() -> None:
    args = parse_args()
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    ticks = add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip())).reset_index(drop=True)
    ticks.insert(0, "tick_id", np.arange(len(ticks), dtype=np.int64))
    hourly = add_adaptive_supertrend(
        build_hourly_bars(ticks),
        args.atr_length,
        args.base_multiplier,
        args.min_multiplier,
        args.speed_lookback,
        args.low_speed,
        args.high_speed,
        args.smoothing_span,
    )
    zones = pine_style_zones(
        hourly,
        args.pivot_lookback,
        args.volume_filter_length,
        args.zone_atr_length,
        args.zone_box_width,
    )
    bars = build_session_volume_bars(ticks, args.volume_bar_size)
    bars = add_strategy_b_signals(bars, args.tick_lookback, args.close_position_max)
    bars = assign_resistance_entries(bars, zones)
    bars = attach_strategy_b_hourly_state(bars, hourly)
    trades = backtest_strategy_b(
        ticks,
        bars,
        hourly,
        args.slippage_points,
        args.initial_stop_atr_multiplier,
        args.confirmation_timeout_hours,
        args.maximum_holding_hours,
        args.trailing_atr_multiplier,
    )

    period = f"{args.start_date:%Y-%m-%d}_to_{args.end_date:%Y-%m-%d}"
    trades_path = args.trades_output or TICK_DIR / f"TMF_{args.contract_month}_adaptive_hourly_short_strategy_b_trades_{period}.csv"
    chart_path = args.chart_output or TICK_DIR / f"TMF_{args.contract_month}_adaptive_hourly_short_strategy_b_backtest_{period}.html"
    report_path = args.report_output or DOC_DIR / f"tmf_{args.contract_month}_adaptive_hourly_short_strategy_b_backtest_{period}.md"
    trades_path.parent.mkdir(parents=True, exist_ok=True)
    trades.to_csv(trades_path, index=False, encoding="utf-8-sig")
    write_strategy_b_chart(chart_path, hourly, zones, bars, trades)
    write_strategy_b_report(report_path, args, ticks, bars, trades)
    summary = performance_summary(trades, "pnl_points")
    print(f"ticks={len(ticks)} volume_bars={len(bars)} signals={int(bars['resistance_reversal'].sum())}")
    print(f"trades={summary['trades']} net_points={summary['net']:.1f} max_drawdown={summary['max_drawdown']:.1f}")
    print(f"trades_output={trades_path}\nchart={chart_path}\nreport={report_path}")


if __name__ == "__main__":
    main()
