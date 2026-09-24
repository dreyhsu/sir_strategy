#!/usr/bin/env python3
"""Backtest 5-minute KD bearish crosses at hourly Pine resistance boxes."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_btcusdt_aggtrade_two_position_legacy_exit import (
        DEFAULT_OUTPUT_DIR,
        iter_agg_trades,
        load_or_build_preprocessing,
        output_stem,
        resolve_input_paths,
    )
    from .backtest_btcusdt_5m_diamond_hourly_supertrend_short import (
        DEFAULT_REPORT_DIR,
        backtest,
        format_profit_factor,
        load_or_build_time_bars,
        sample_bars,
    )
    from .backtest_btcusdt_volume_supertrend_short import add_hourly_structure_atr
    from .backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from .backtest_tmf_hourly_support_long import pine_style_zones
except ImportError:
    from backtest_btcusdt_aggtrade_two_position_legacy_exit import (
        DEFAULT_OUTPUT_DIR,
        iter_agg_trades,
        load_or_build_preprocessing,
        output_stem,
        resolve_input_paths,
    )
    from backtest_btcusdt_5m_diamond_hourly_supertrend_short import (
        DEFAULT_REPORT_DIR,
        backtest,
        format_profit_factor,
        load_or_build_time_bars,
        sample_bars,
    )
    from backtest_btcusdt_volume_supertrend_short import add_hourly_structure_atr
    from backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from backtest_tmf_hourly_support_long import pine_style_zones


def add_stochastic_kd(
    bars: pd.DataFrame,
    length: int = 9,
    k_smoothing: int = 3,
    d_smoothing: int = 3,
) -> pd.DataFrame:
    """Calculate TradingView-style Stochastic KD and confirmed bearish crosses."""
    if min(length, k_smoothing, d_smoothing) < 1:
        raise ValueError("KD periods must be positive")
    result = bars.copy().sort_values("tick_end_id", kind="stable").reset_index(drop=True)
    lowest = result["low"].rolling(length, min_periods=length).min()
    highest = result["high"].rolling(length, min_periods=length).max()
    spread = highest - lowest
    result["kd_rsv"] = 100 * (result["close"] - lowest) / spread.replace(0, np.nan)
    result["kd_k"] = result["kd_rsv"].rolling(k_smoothing, min_periods=k_smoothing).mean()
    result["kd_d"] = result["kd_k"].rolling(d_smoothing, min_periods=d_smoothing).mean()
    result["kd_bearish_cross"] = (
        (result["kd_k"] < result["kd_d"])
        & (result["kd_k"].shift(1) >= result["kd_d"].shift(1))
    ).fillna(False)
    result["kd_prior_5_max_k"] = result["kd_k"].shift(1).rolling(5, min_periods=5).max()
    result["kd_prior_5_k_above_80"] = (result["kd_prior_5_max_k"] > 80).fillna(False)
    result["kd_overbought_bearish_cross"] = (
        result["kd_bearish_cross"] & result["kd_prior_5_k_above_80"]
    )
    result["recent_5_close_max"] = result["close"].rolling(5, min_periods=5).max()
    return result


def add_resistance_kd_signals(
    bars: pd.DataFrame,
    hourly: pd.DataFrame,
    zones: pd.DataFrame,
    stop_atr_buffer: float = 0.10,
) -> pd.DataFrame:
    """Qualify overbought KD crosses and attach the latest causal stop structure."""
    result = bars.copy().sort_values("tick_end_id", kind="stable").reset_index(drop=True)
    result["resistance_id"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    result["resistance_bottom"] = np.nan
    result["resistance_top"] = np.nan
    result["hourly_stop_atr"] = np.nan
    result["stop_price"] = np.nan
    result["resistance_touch"] = False
    result["close_below_resistance_top"] = False
    result["short_signal"] = False
    result["short_signal_type"] = pd.Series([None] * len(result), dtype="object")
    result["short_structure_type"] = pd.Series([None] * len(result), dtype="object")
    result["short_structure_id"] = pd.Series(pd.NA, index=result.index, dtype="Int64")
    # Compatibility columns for the shared, already-tested tick execution engine.
    for column in (
        "resistance_holds", "support_as_resistance_holds", "support_holds",
        "resistance_as_support_holds", "green_exit_signal",
    ):
        result[column] = False

    resistances = []
    if not zones.empty:
        resistances = list(zones[zones["zone_type"] == "resistance"].itertuples(index=False))
    for index, bar in result.iterrows():
        result.at[index, "hourly_stop_atr"] = 0.0
        timestamp = bar["timestamp"]
        causal = []
        for zone in resistances:
            if not zone.created_time < timestamp:
                continue
            causal.append(zone)
            is_active = pd.isna(zone.broken_time) or timestamp < zone.broken_time
            if is_active and float(zone.bottom) <= float(bar["high"]) and float(zone.top) >= float(bar["low"]):
                result.at[index, "resistance_touch"] = True
        selected = max(causal, key=lambda zone: (zone.created_time, int(zone.zone_id))) if causal else None
        if selected is None:
            continue
        zone_id = int(selected.zone_id)
        top = float(selected.top)
        result.at[index, "resistance_id"] = zone_id
        result.at[index, "resistance_bottom"] = float(selected.bottom)
        result.at[index, "resistance_top"] = top
        result.at[index, "close_below_resistance_top"] = float(bar["close"]) < top
        if pd.notna(bar["recent_5_close_max"]):
            result.at[index, "stop_price"] = float(bar["recent_5_close_max"])
        if bool(bar["kd_overbought_bearish_cross"]) and float(bar["close"]) < top:
            result.at[index, "short_signal"] = True
            result.at[index, "short_signal_type"] = "kd_bearish_cross"
            result.at[index, "short_structure_type"] = "resistance"
            result.at[index, "short_structure_id"] = zone_id
    result["short_stop_anchor"] = result["recent_5_close_max"]
    return result


def add_zone_signal_counts(zones: pd.DataFrame, bars: pd.DataFrame) -> pd.DataFrame:
    result = zones.copy()
    counts = bars[bars["short_signal"]].groupby("resistance_id", dropna=True).size().to_dict()
    result["kd_signals"] = [int(counts.get(int(zone_id), 0)) for zone_id in result["zone_id"]]
    return result


def build_indicators(
    hourly_raw: pd.DataFrame,
    five_minute_raw: pd.DataFrame,
    args: argparse.Namespace,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    hourly = add_hourly_structure_atr(hourly_raw, args.stop_atr_length)
    hourly = add_adaptive_supertrend(
        hourly, args.atr_length, args.base_multiplier, args.min_multiplier,
        args.speed_lookback, args.low_speed, args.high_speed, args.smoothing_span,
    )
    zones = pine_style_zones(
        hourly_raw, args.pivot_lookback, args.volume_filter_length,
        args.zone_atr_length, args.zone_box_width,
    )
    bars = add_stochastic_kd(
        five_minute_raw, args.kd_length, args.kd_k_smoothing, args.kd_d_smoothing,
    )
    bars = add_resistance_kd_signals(bars, hourly, zones, args.stop_atr_buffer)
    zones = add_zone_signal_counts(zones, bars)
    return hourly, bars, zones


def load_diamond_comparison(output_dir: Path, period: str) -> dict[str, object] | None:
    bars_path = output_dir / f"{period}_5m_diamond_hourly_supertrend_bars.csv"
    trades_path = output_dir / f"{period}_5m_diamond_hourly_supertrend_trades.csv"
    if not bars_path.is_file() or not trades_path.is_file():
        return None
    diamond_bars = pd.read_csv(bars_path, usecols=["short_signal"])
    diamond_trades = pd.read_csv(trades_path)
    return {
        "signals": int(diamond_bars["short_signal"].sum()),
        "trades": len(diamond_trades),
        "net_pnl_usdt": (
            float(diamond_trades["net_pnl_usdt"].sum()) if not diamond_trades.empty else 0.0
        ),
    }


def write_chart(
    path: Path,
    zones: pd.DataFrame,
    bars: pd.DataFrame,
    hourly: pd.DataFrame,
    trades: pd.DataFrame,
    equity: pd.DataFrame,
    initial_equity_usdt: float,
    chart_sample_minutes: int,
) -> None:
    chart_bars = sample_bars(bars, chart_sample_minutes)
    figure = make_subplots(
        rows=4, cols=1, shared_xaxes=True, vertical_spacing=0.025,
        row_heights=[0.56, 0.18, 0.10, 0.16],
        subplot_titles=(
            "5-minute price, hourly Pine zones and adaptive Supertrend",
            "Stochastic KD", "Open position", "Marked-to-market equity",
        ),
    )
    figure.add_trace(go.Scatter(
        x=chart_bars["timestamp"], y=chart_bars["close"], mode="lines", name="5m close"
    ), row=1, col=1)
    figure.add_trace(go.Scatter(
        x=hourly["timestamp"], y=hourly["supertrend"], mode="lines",
        name="Hourly adaptive Supertrend", line={"color": "#7b1fa2"},
    ), row=1, col=1)
    chart_end = chart_bars["timestamp"].iloc[-1]
    for zone in zones.itertuples(index=False):
        resistance = zone.zone_type == "resistance"
        figure.add_shape(
            type="rect", x0=zone.created_time,
            x1=zone.broken_time if pd.notna(zone.broken_time) else chart_end,
            y0=zone.bottom, y1=zone.top,
            fillcolor="rgba(211,47,47,0.11)" if resistance else "rgba(32,202,38,0.11)",
            line={"color": "rgba(211,47,47,0.55)" if resistance else "rgba(32,202,38,0.55)", "width": 1},
            row=1, col=1,
        )
    crosses = bars[bars["kd_bearish_cross"]]
    qualified = bars[bars["short_signal"]]
    if not crosses.empty:
        figure.add_trace(go.Scatter(
            x=crosses["timestamp"], y=crosses["high"], mode="markers",
            name="All KD bearish crosses", marker={"symbol": "triangle-down-open", "size": 7, "color": "#757575"},
        ), row=1, col=1)
    if not qualified.empty:
        figure.add_trace(go.Scatter(
            x=qualified["timestamp"], y=qualified["high"], mode="markers",
            name="Resistance + KD signal",
            text=[f"Resistance {int(value)}" for value in qualified["resistance_id"]],
            hovertemplate="%{text}<br>%{x}<br>Price: %{y:,.2f}<extra></extra>",
            marker={"symbol": "diamond", "size": 10, "color": "#d32f2f"},
        ), row=1, col=1)
    figure.add_trace(go.Scatter(
        x=chart_bars["timestamp"], y=chart_bars["kd_k"], mode="lines", name="K", line={"color": "#1565c0"}
    ), row=2, col=1)
    figure.add_trace(go.Scatter(
        x=chart_bars["timestamp"], y=chart_bars["kd_d"], mode="lines", name="D", line={"color": "#ef6c00"}
    ), row=2, col=1)
    if not qualified.empty:
        figure.add_trace(go.Scatter(
            x=qualified["timestamp"], y=qualified["kd_k"], mode="markers", name="Qualified KD cross",
            marker={"symbol": "triangle-down", "size": 9, "color": "#d32f2f"},
        ), row=2, col=1)
    figure.add_hline(y=80, line_dash="dot", line_color="#9e9e9e", row=2, col=1)
    figure.add_hline(y=20, line_dash="dot", line_color="#9e9e9e", row=2, col=1)
    if not trades.empty:
        figure.add_trace(go.Scatter(
            x=trades["entry_time"], y=trades["entry_fill_price"], mode="markers", name="Short fill",
            marker={"symbol": "triangle-down", "size": 11, "color": "#8e0000"},
        ), row=1, col=1)
        styles = {
            "structure_stop": ("Structure stop", "#ef6c00"),
            "adaptive_hourly_supertrend_bullish_flip": ("Hourly ST exit", "#00897b"),
            "data_end": ("Data-end exit", "#546e7a"),
        }
        for reason, (label, color) in styles.items():
            exits = trades[trades["exit_reason"] == reason]
            if not exits.empty:
                figure.add_trace(go.Scatter(
                    x=exits["exit_time"], y=exits["exit_fill_price"], mode="markers", name=label,
                    marker={"symbol": "x", "size": 10, "color": color},
                ), row=1, col=1)
        for trade in trades.itertuples(index=False):
            figure.add_shape(
                type="line", x0=trade.entry_time, x1=trade.exit_time,
                y0=trade.stop_price, y1=trade.stop_price,
                line={"color": "#ef6c00", "dash": "dash", "width": 1}, row=1, col=1,
            )
    figure.add_trace(go.Scatter(
        x=equity["timestamp"], y=equity["open_positions"], mode="lines", line_shape="hv", name="Open position"
    ), row=3, col=1)
    figure.add_trace(go.Scatter(
        x=equity["timestamp"], y=equity["equity_usdt"], mode="lines", name="Equity"
    ), row=4, col=1)
    figure.add_hline(y=initial_equity_usdt, line_dash="dot", line_color="gray", row=4, col=1)
    figure.update_layout(title="BTCUSDT 5m KD + hourly resistance short backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="KD", range=[0, 100], row=2, col=1)
    figure.update_yaxes(title_text="Position", dtick=1, row=3, col=1)
    figure.update_yaxes(title_text="USDT", tickformat=",.0f", row=4, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def write_report(
    path: Path,
    args: argparse.Namespace,
    source_summary: dict[str, object],
    bars: pd.DataFrame,
    zones: pd.DataFrame,
    summary: dict[str, object],
    diamond: dict[str, object] | None,
) -> None:
    inputs = "\n".join(f"  - `{item}`" for item in source_summary["input_files"])
    supports = int((zones["zone_type"] == "support").sum()) if not zones.empty else 0
    resistances = int((zones["zone_type"] == "resistance").sum()) if not zones.empty else 0
    all_crosses = int(bars["kd_bearish_cross"].sum())
    overbought_crosses = int(bars["kd_overbought_bearish_cross"].sum())
    close_filter = int(
        (bars["kd_overbought_bearish_cross"] & bars["close_below_resistance_top"]).sum()
    )
    touches = int(bars["resistance_touch"].sum())
    qualified = int(bars["short_signal"].sum())
    if diamond is None:
        comparison = "現有 Diamond CSV 不存在，因此本次未列出 A/B 數字。"
    else:
        comparison = (
            f"| 5m Pine Diamond | {diamond['signals']} | {diamond['trades']} | US${diamond['net_pnl_usdt']:,.2f} |\n"
            f"| 5m KD | {qualified} | {summary['trades']} | US${summary['net_pnl_usdt']:,.2f} |"
        )
        comparison = "| 版本 | 合格訊號 | 交易 | 淨損益 |\n| --- | ---: | ---: | ---: |\n" + comparison
    text = f"""# BTCUSDT 5 分鐘 KD＋1 小時壓力箱空單回測

- 輸入：
{inputs}
- 資料範圍：{source_summary['first_timestamp']} 至 {source_summary['last_timestamp']}；raw aggTrades {source_summary['rows']:,} 筆。
- 已完成 5 分鐘 K：{len(bars):,} 根；支撐箱 {supports} 個、壓力箱 {resistances} 個。
- KD：Stochastic ({args.kd_length},{args.kd_k_smoothing},{args.kd_d_smoothing})；目前棒之前 5 根的 K 值至少一根嚴格大於 80，接著 K 向下穿越 D。
- 壓力箱：1 小時 close pivot {args.pivot_lookback}/{args.pivot_lookback}，寬度 ATR({args.zone_atr_length}) × {args.zone_box_width:g}。目前 5 分鐘 close 必須低於最新壓力箱頂。
- 進場：上述條件完成後，於下一筆 raw aggTrade 直接做空；不要求價格觸及壓力箱。
- 停損：KD 訊號確認時最近 5 根已完成 5 分鐘 K 的最高 close，不再使用壓力箱頂或 ATR(20) buffer。
- 出場：持倉後先見 1 小時 Adaptive Supertrend 空頭，再於空翻多後下一筆成交退出；raw 結構停損優先。
- 初始資金 US${args.initial_equity_usdt:,.2f}，部位 {args.position_btc:g} BTC；單邊手續費 {args.taker_fee_rate * 10_000:g} bps、單邊不利滑價 {args.slippage_bps:g} bps，不計 funding。

## A/B 比較

{comparison}

| 指標 | 數值 |
| --- | ---: |
| 全部 5 分鐘 KD 死叉 | {all_crosses} |
| 前 5 根至少一個 K > 80 的 KD 死叉 | {overbought_crosses} |
| 同時 close < 最新壓力箱頂 | {close_filter} |
| 壓力箱觸碰 K 棒 | {touches} |
| 具已確認停損結構的 KD 訊號 / 成交 | {qualified} / {summary['filled_entries']} |
| 持倉中或同 tick 忽略 | {summary['ignored_while_occupied']} |
| 停損資料未完成而略過 | {summary['skipped_missing_stop_atr']} |
| Supertrend 空翻多出場 | {summary['bullish_flip_exits']} |
| 結構停損出場 | {summary['structure_stop_exits']} |
| 資料結束出場 | {summary['data_end_exits']} |
| 交易 / 勝 / 負 | {summary['trades']} / {summary['wins']} / {summary['losses']} |
| 勝率 | {summary['win_rate_percent']:.2f}% |
| Profit factor | {format_profit_factor(summary['profit_factor'])} |
| Raw-price P&L | US${summary['raw_price_pnl_usdt']:,.2f} |
| 滑價成本 | US${summary['slippage_cost_usdt']:,.2f} |
| 手續費 | US${summary['fees_usdt']:,.2f} |
| 淨損益 | US${summary['net_pnl_usdt']:,.2f} |
| 最終權益 | US${summary['final_equity_usdt']:,.2f} |
| 報酬率 | {summary['return_percent']:.2f}% |
| 最大回撤 | US${summary['maximum_drawdown_usdt']:,.2f} |
| 平均持倉 | {summary['average_holding_hours']:.2f} 小時 |
| 市場曝險 | {summary['exposure_percent']:.2f}% |
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", type=Path, nargs="+", metavar="PATH")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--report-dir", type=Path, default=DEFAULT_REPORT_DIR)
    parser.add_argument("--cache-dir", type=Path)
    parser.add_argument("--refresh-cache", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--confirmation-minutes", type=int, choices=(5,), default=5)
    parser.add_argument("--volume-bar-notional", type=float, default=1_000_000,
                        help="Only used by the shared preprocessing cache.")
    parser.add_argument("--max-gap-seconds", type=float, default=60)
    parser.add_argument("--initial-equity-usdt", type=float, default=10_000)
    parser.add_argument("--position-btc", type=float, default=0.01)
    parser.add_argument("--taker-fee-rate", type=float, default=0.0005)
    parser.add_argument("--slippage-bps", type=float, default=2)
    parser.add_argument("--kd-length", type=int, default=9)
    parser.add_argument("--kd-k-smoothing", type=int, default=3)
    parser.add_argument("--kd-d-smoothing", type=int, default=3)
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--zone-atr-length", type=int, default=200)
    parser.add_argument("--zone-box-width", type=float, default=1.5)
    parser.add_argument("--stop-atr-length", type=int, default=20)
    parser.add_argument("--stop-atr-buffer", type=float, default=0.10)
    parser.add_argument("--atr-length", type=int, default=10)
    parser.add_argument("--base-multiplier", type=float, default=3.0)
    parser.add_argument("--min-multiplier", type=float, default=0.8)
    parser.add_argument("--speed-lookback", type=int, default=2)
    parser.add_argument("--low-speed", type=float, default=0.25)
    parser.add_argument("--high-speed", type=float, default=0.8)
    parser.add_argument("--smoothing-span", type=int, default=2)
    parser.add_argument("--chart-sample-minutes", type=int, default=5)
    parser.add_argument("--progress-rows", type=int, default=5_000_000)
    args = parser.parse_args()
    positives = (
        args.confirmation_minutes, args.volume_bar_notional, args.max_gap_seconds,
        args.initial_equity_usdt, args.position_btc, args.kd_length,
        args.kd_k_smoothing, args.kd_d_smoothing, args.pivot_lookback,
        args.volume_filter_length, args.zone_atr_length, args.stop_atr_length,
        args.atr_length, args.base_multiplier, args.min_multiplier,
        args.speed_lookback, args.smoothing_span, args.chart_sample_minutes,
    )
    if min(positives) <= 0:
        parser.error("bar sizes, capital, position size, and indicator periods must be positive")
    if args.min_multiplier > args.base_multiplier:
        parser.error("--min-multiplier must not exceed --base-multiplier")
    if args.high_speed <= args.low_speed:
        parser.error("--high-speed must be greater than --low-speed")
    if min(args.taker_fee_rate, args.slippage_bps, args.zone_box_width, args.stop_atr_buffer) < 0:
        parser.error("cost and width parameters must be non-negative")
    if args.refresh_cache and args.no_cache:
        parser.error("--refresh-cache and --no-cache cannot be combined")
    return args


def main() -> None:
    args = parse_args()
    input_paths = resolve_input_paths(args.input)
    args.output_dir = args.output_dir.resolve()
    args.report_dir = args.report_dir.resolve()
    hourly_raw, _unused_volume, source_summary = load_or_build_preprocessing(input_paths, args)
    five_minute_raw = load_or_build_time_bars(input_paths, args)
    hourly, bars, zones = build_indicators(hourly_raw, five_minute_raw, args)
    trades, equity, summary = backtest(
        iter_agg_trades(input_paths), bars, hourly,
        initial_equity_usdt=args.initial_equity_usdt,
        position_btc=args.position_btc,
        taker_fee_rate=args.taker_fee_rate,
        slippage_bps=args.slippage_bps,
        chart_sample_minutes=args.chart_sample_minutes,
    )
    period = output_stem(input_paths)
    stem = f"{period}_5m_kd_hourly_supertrend"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    paths = {
        "bars": args.output_dir / f"{stem}_bars.csv",
        "hourly": args.output_dir / f"{stem}_hourly.csv",
        "zones": args.output_dir / f"{stem}_zones.csv",
        "trades": args.output_dir / f"{stem}_trades.csv",
        "equity": args.output_dir / f"{stem}_equity.csv",
        "chart": args.output_dir / f"{stem}.html",
        "report": args.report_dir / f"{stem.lower()}.md",
    }
    bars.to_csv(paths["bars"], index=False, encoding="utf-8-sig")
    hourly.to_csv(paths["hourly"], index=False, encoding="utf-8-sig")
    zones.to_csv(paths["zones"], index=False, encoding="utf-8-sig")
    trades.to_csv(paths["trades"], index=False, encoding="utf-8-sig")
    equity.to_csv(paths["equity"], index=False, encoding="utf-8-sig")
    write_chart(
        paths["chart"], zones, bars, hourly, trades, equity,
        args.initial_equity_usdt, args.chart_sample_minutes,
    )
    diamond = load_diamond_comparison(args.output_dir, period)
    write_report(paths["report"], args, source_summary, bars, zones, summary, diamond)
    print(
        f"five_minute_bars={len(bars)} kd_crosses={int(bars['kd_bearish_cross'].sum())} "
        f"qualified_signals={int(bars['short_signal'].sum())} trades={summary['trades']} "
        f"net_pnl_usdt={summary['net_pnl_usdt']:.2f} final_equity_usdt={summary['final_equity_usdt']:.2f}"
    )
    print(f"report={paths['report']}")
    print(f"chart={paths['chart']}")


if __name__ == "__main__":
    main()
