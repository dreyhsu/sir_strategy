#!/usr/bin/env python
"""A/B test the legacy adaptive-hourly short strategy against Strategy B."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .backtest_tmf_adaptive_hourly_resistance_short import (
        DATA_DIR,
        TICK_DIR,
        add_adaptive_supertrend,
        attach_hourly_state,
        backtest as backtest_legacy,
        build_continuous_volume_bars,
    )
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_resistance_short import add_bearish_rejection_signals, assign_resistance_entries
    from .backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones
    from .dense_reversal_bars import detect_dense_reversals
except ImportError:
    from backtest_tmf_adaptive_hourly_resistance_short import (
        DATA_DIR,
        TICK_DIR,
        add_adaptive_supertrend,
        attach_hourly_state,
        backtest as backtest_legacy,
        build_continuous_volume_bars,
    )
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_resistance_short import add_bearish_rejection_signals, assign_resistance_entries
    from backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones
    from dense_reversal_bars import detect_dense_reversals


ROOT = Path(__file__).resolve().parents[1]
DOC_DIR = ROOT / "doc"


@dataclass
class StrategyBPosition:
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    raw_entry_price: float
    entry_fill_price: float
    resistance_id: int
    resistance_top: float
    entry_hourly_atr: float
    initial_stop: float
    confirmation_deadline: pd.Timestamp
    maximum_holding_deadline: pd.Timestamp
    confirmed: bool
    confirmation_time: pd.Timestamp | None
    last_direction: int | None
    lowest_price: float
    highest_price: float
    trailing_stop: float | None = None


def build_session_volume_bars(ticks: pd.DataFrame, size: float) -> pd.DataFrame:
    """Build completed volume bars independently inside every trading session."""
    records: list[dict[str, object]] = []
    for session_id, session_ticks in ticks.groupby("session_id", sort=False):
        frame = session_ticks.sort_values("tick_id", kind="stable")
        direction = np.sign(frame["price"].diff()).replace(0, np.nan).ffill().fillna(1)
        signed_quantity = frame["quantity"] * direction
        volume = signed_volume = 0.0
        start_id: int | None = None
        start_time: pd.Timestamp | None = None
        open_price = high_price = low_price = close_price = 0.0
        tick_count = 0
        for tick, signed in zip(frame.itertuples(index=False), signed_quantity, strict=True):
            if start_id is None:
                start_id = int(tick.tick_id)
                start_time = tick.timestamp
                open_price = high_price = low_price = close_price = float(tick.price)
            price = float(tick.price)
            high_price = max(high_price, price)
            low_price = min(low_price, price)
            close_price = price
            volume += float(tick.quantity)
            signed_volume += float(signed)
            tick_count += 1
            if volume >= size:
                records.append(
                    {
                        "bar_start_time": start_time,
                        "timestamp": tick.timestamp,
                        "open": open_price,
                        "high": high_price,
                        "low": low_price,
                        "close": close_price,
                        "volume": volume,
                        "signed_volume": signed_volume,
                        "tick_count": tick_count,
                        "tick_start_id": start_id,
                        "tick_end_id": int(tick.tick_id),
                        "session_id": session_id,
                        "session_type": tick.session_type,
                        "session_date": tick.session_date,
                    }
                )
                volume = signed_volume = 0.0
                start_id = None
                start_time = None
                tick_count = 0
    if not records:
        raise ValueError("No completed session-reset volume bars were generated.")
    return pd.DataFrame(records).sort_values("tick_end_id", kind="stable").reset_index(drop=True)


def add_strategy_b_signals(bars: pd.DataFrame, lookback: int, close_position_max: float) -> pd.DataFrame:
    groups: list[pd.DataFrame] = []
    for _, frame in bars.groupby("session_id", sort=False):
        detected = detect_dense_reversals(frame, lookback, 50, 0.75)
        groups.append(add_bearish_rejection_signals(detected, close_position_max))
    return pd.concat(groups, ignore_index=True).sort_values("tick_end_id", kind="stable").reset_index(drop=True)


def attach_strategy_b_hourly_state(bars: pd.DataFrame, hourly: pd.DataFrame) -> pd.DataFrame:
    state = hourly[["timestamp", "atr", "supertrend", "supertrend_direction", "adaptive_multiplier"]].rename(
        columns={
            "timestamp": "hourly_confirmation_time",
            "atr": "hourly_atr",
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
    ).sort_values("tick_end_id", kind="stable").reset_index(drop=True)


def _optional_int(value: object) -> int | None:
    return None if pd.isna(value) else int(value)


def _complete_trade(
    position: StrategyBPosition,
    tick: object,
    reason: str,
    slippage: float,
    final_trailing_stop: float | None,
) -> dict[str, object]:
    raw_exit = float(tick.price)
    exit_fill = raw_exit + slippage
    gross = position.raw_entry_price - raw_exit
    net = position.entry_fill_price - exit_fill
    return {
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": tick.timestamp,
        "entry_session": position.entry_session,
        "exit_session": tick.session_id,
        "raw_entry_price": position.raw_entry_price,
        "entry_fill_price": position.entry_fill_price,
        "raw_exit_price": raw_exit,
        "exit_fill_price": exit_fill,
        "entry_slippage_points": slippage,
        "exit_slippage_points": slippage,
        "entry_hourly_atr": position.entry_hourly_atr,
        "initial_stop": position.initial_stop,
        "resistance_id": position.resistance_id,
        "resistance_top": position.resistance_top,
        "confirmation_deadline": position.confirmation_deadline,
        "confirmation_time": position.confirmation_time,
        "maximum_holding_deadline": position.maximum_holding_deadline,
        "final_trailing_stop": final_trailing_stop,
        "gross_pnl_points": gross,
        "pnl_points": net,
        "mfe_points": position.entry_fill_price - position.lowest_price,
        "mae_points": position.entry_fill_price - position.highest_price,
        "holding_hours": (tick.timestamp - position.entry_time).total_seconds() / 3600,
        "exit_reason": reason,
        "cross_session": position.entry_session != tick.session_id,
    }


def backtest_strategy_b(
    ticks: pd.DataFrame,
    bars: pd.DataFrame,
    hourly: pd.DataFrame,
    slippage: float,
    initial_stop_atr_multiplier: float,
    confirmation_timeout_hours: float,
    maximum_holding_hours: float,
    trailing_atr_multiplier: float,
) -> pd.DataFrame:
    """Run Strategy B with tick-ordered fills and risk management."""
    ordered_ticks = ticks.sort_values("tick_id", kind="stable").reset_index(drop=True)
    bar_events = {int(row.tick_end_id): row for row in bars.itertuples(index=False)}
    hourly_state = hourly.sort_values("timestamp", kind="stable").reset_index(drop=True)
    hourly_index = -1
    current_direction: int | None = None
    current_atr: float | None = None
    current_hourly_time: pd.Timestamp | None = None
    position: StrategyBPosition | None = None
    pending_entry: object | None = None
    pending_exit: str | None = None
    trades: list[dict[str, object]] = []
    last_tick: object | None = None

    for tick in ordered_ticks.itertuples(index=False):
        last_tick = tick
        hourly_changed = False
        while hourly_index + 1 < len(hourly_state) and hourly_state.iloc[hourly_index + 1]["timestamp"] < tick.timestamp:
            hourly_index += 1
            state = hourly_state.iloc[hourly_index]
            current_direction = _optional_int(state["supertrend_direction"])
            current_atr = None if pd.isna(state["atr"]) else float(state["atr"])
            current_hourly_time = state["timestamp"]
            hourly_changed = True

        if position is not None and pending_exit is not None:
            trades.append(_complete_trade(position, tick, pending_exit, slippage, position.trailing_stop))
            position = None
            pending_exit = None
            pending_entry = None
            continue

        if position is None and pending_entry is not None:
            signal = pending_entry
            pending_entry = None
            if tick.session_id == signal.session_id and current_atr is not None:
                raw_entry = float(tick.price)
                entry_fill = raw_entry - slippage
                initial_stop = max(float(signal.high), float(signal.resistance_top)) + initial_stop_atr_multiplier * current_atr
                if entry_fill < initial_stop:
                    confirmed = current_direction == -1
                    position = StrategyBPosition(
                        signal_time=signal.timestamp,
                        entry_time=tick.timestamp,
                        entry_session=tick.session_id,
                        raw_entry_price=raw_entry,
                        entry_fill_price=entry_fill,
                        resistance_id=int(signal.resistance_id),
                        resistance_top=float(signal.resistance_top),
                        entry_hourly_atr=current_atr,
                        initial_stop=initial_stop,
                        confirmation_deadline=tick.timestamp + pd.Timedelta(hours=confirmation_timeout_hours),
                        maximum_holding_deadline=tick.timestamp + pd.Timedelta(hours=maximum_holding_hours),
                        confirmed=confirmed,
                        confirmation_time=current_hourly_time if confirmed else None,
                        last_direction=current_direction,
                        lowest_price=raw_entry,
                        highest_price=raw_entry,
                    )
                    if confirmed:
                        position.trailing_stop = raw_entry + trailing_atr_multiplier * current_atr

        exited_this_tick = False
        if position is not None:
            price = float(tick.price)
            position.lowest_price = min(position.lowest_price, price)
            position.highest_price = max(position.highest_price, price)

            bullish_flip = False
            if hourly_changed and current_direction is not None:
                if not position.confirmed and current_direction == -1:
                    if current_hourly_time is not None and current_hourly_time <= position.confirmation_deadline:
                        position.confirmed = True
                        position.confirmation_time = current_hourly_time
                elif position.confirmed and position.last_direction == -1 and current_direction == 1:
                    bullish_flip = True
                position.last_direction = current_direction

            if price >= position.initial_stop:
                pending_exit = "initial_stop"
            elif position.trailing_stop is not None and price >= position.trailing_stop:
                pending_exit = "atr_trailing_stop"
            else:
                completed_bar = bar_events.get(int(tick.tick_id))
                if completed_bar is not None and float(completed_bar.close) > position.resistance_top:
                    pending_exit = "resistance_invalidated"

            if pending_exit is None and not position.confirmed and tick.timestamp >= position.confirmation_deadline:
                trades.append(_complete_trade(position, tick, "supertrend_confirmation_timeout", slippage, position.trailing_stop))
                position = None
                exited_this_tick = True
            elif pending_exit is None and tick.timestamp >= position.maximum_holding_deadline:
                trades.append(_complete_trade(position, tick, "maximum_holding_time", slippage, position.trailing_stop))
                position = None
                exited_this_tick = True
            elif pending_exit is None and bullish_flip:
                trades.append(_complete_trade(position, tick, "adaptive_hourly_supertrend_bullish_flip", slippage, position.trailing_stop))
                position = None
                exited_this_tick = True

            if position is not None and position.confirmed and current_atr is not None:
                candidate = position.lowest_price + trailing_atr_multiplier * current_atr
                position.trailing_stop = candidate if position.trailing_stop is None else min(position.trailing_stop, candidate)

        completed_bar = bar_events.get(int(tick.tick_id))
        if position is None and not exited_this_tick and pending_entry is None and completed_bar is not None:
            if bool(completed_bar.resistance_reversal):
                pending_entry = completed_bar

    if position is not None and last_tick is not None:
        reason = pending_exit or "data_end"
        trades.append(_complete_trade(position, last_tick, reason, slippage, position.trailing_stop))

    columns = [
        "trade_number", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
        "raw_entry_price", "entry_fill_price", "raw_exit_price", "exit_fill_price", "entry_slippage_points",
        "exit_slippage_points", "entry_hourly_atr", "initial_stop", "resistance_id", "resistance_top",
        "confirmation_deadline", "confirmation_time", "maximum_holding_deadline", "final_trailing_stop",
        "gross_pnl_points", "pnl_points", "mfe_points", "mae_points", "holding_hours", "exit_reason",
        "cross_session", "cumulative_gross_points", "cumulative_points", "drawdown_points",
    ]
    result = pd.DataFrame(trades)
    if result.empty:
        return pd.DataFrame(columns=columns)
    result.insert(0, "trade_number", range(1, len(result) + 1))
    result["cumulative_gross_points"] = result["gross_pnl_points"].cumsum()
    result["cumulative_points"] = result["pnl_points"].cumsum()
    equity = pd.concat([pd.Series([0.0]), result["cumulative_points"]], ignore_index=True)
    result["drawdown_points"] = (equity - equity.cummax()).iloc[1:].to_numpy()
    return result[columns]


def performance_summary(trades: pd.DataFrame, pnl_column: str) -> dict[str, float | int | str]:
    if trades.empty:
        return {"trades": 0, "wins": 0, "losses": 0, "win_rate": 0.0, "net": 0.0, "profit_factor": "n/a", "max_drawdown": 0.0}
    pnl = trades[pnl_column].astype(float)
    winners = pnl[pnl > 0]
    losers = pnl[pnl < 0]
    equity = pd.concat([pd.Series([0.0]), pnl.cumsum()], ignore_index=True)
    drawdown = equity - equity.cummax()
    return {
        "trades": len(pnl),
        "wins": len(winners),
        "losses": len(losers),
        "win_rate": len(winners) / len(pnl) * 100,
        "net": float(pnl.sum()),
        "profit_factor": "n/a" if losers.empty else f"{float(winners.sum() / abs(losers.sum())):.2f}",
        "max_drawdown": float(drawdown.min()),
        "average_holding_hours": float(trades.get("holding_hours", pd.Series(dtype=float)).mean()) if "holding_hours" in trades else float((pd.to_datetime(trades["exit_time"]) - pd.to_datetime(trades["entry_time"])).dt.total_seconds().mean() / 3600),
        "maximum_holding_hours": float(trades.get("holding_hours", pd.Series(dtype=float)).max()) if "holding_hours" in trades else float((pd.to_datetime(trades["exit_time"]) - pd.to_datetime(trades["entry_time"])).dt.total_seconds().max() / 3600),
        "best_trade": float(pnl.max()),
        "worst_trade": float(pnl.min()),
        "cross_session": int(trades["cross_session"].sum()),
    }


def write_comparison_report(
    path: Path,
    args: argparse.Namespace,
    ticks: pd.DataFrame,
    legacy: pd.DataFrame,
    strategy_b: pd.DataFrame,
) -> None:
    legacy = legacy.copy()
    legacy["cost_adjusted_pnl"] = legacy["pnl_points"] - 2 * args.slippage_points
    summaries = {
        "Legacy A gross": performance_summary(legacy, "pnl_points"),
        "Legacy A cost-adjusted": performance_summary(legacy, "cost_adjusted_pnl"),
        "Strategy B gross": performance_summary(strategy_b, "gross_pnl_points"),
        "Strategy B net": performance_summary(strategy_b, "pnl_points"),
    }
    text = f"""# TMF 202609 自適應壓力反轉空單 A/B Test

## 資料與假設

- 日檔範圍：`{args.start_date}` 至 `{args.end_date}`；實際資料截止 `{ticks['timestamp'].max():%Y-%m-%d %H:%M:%S}`。
- 有效 tick：{len(ticks):,} 筆。
- Legacy A：`backtest_tmf_adaptive_hourly_resistance_short.py` 原始交易邏輯。
- Strategy B：session-reset {args.volume_bar_size:,.0f} 口 volume bar、逐筆成交、ATR 風控與鐘錶時間限制。
- A/B cost-adjusted / net 統一使用進出場每邊 `{args.slippage_points:g}` 點不利滑價。

## 績效比較

| Variant | Trades | Wins / Losses | Win rate | Net P&L | Profit factor | Max drawdown | Avg hold | Max hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
"""
    for name, summary in summaries.items():
        text += (
            f"| {name} | {summary['trades']} | {summary['wins']} / {summary['losses']} | "
            f"{summary['win_rate']:.1f}% | {summary['net']:.1f} | {summary['profit_factor']} | "
            f"{summary['max_drawdown']:.1f} | {summary.get('average_holding_hours', 0):.1f} h | "
            f"{summary.get('maximum_holding_hours', 0):.1f} h |\n"
        )
    text += "\n## Strategy B 出場原因\n\n| Exit reason | Trades | Net P&L |\n| --- | ---: | ---: |\n"
    if strategy_b.empty:
        text += "| No eligible trade | 0 | 0.0 |\n"
    else:
        reasons = strategy_b.groupby("exit_reason")["pnl_points"].agg(["count", "sum"])
        for reason, row in reasons.iterrows():
            text += f"| {reason} | {int(row['count'])} | {row['sum']:.1f} |\n"
    text += f"""

## Strategy B 參數

- Initial stop：`max(signal high, resistance top) + ATR × {args.initial_stop_atr_multiplier:g}`
- Supertrend confirmation timeout：`{args.confirmation_timeout_hours:g}` 小時
- Maximum holding：`{args.maximum_holding_hours:g}` 小時
- ATR trailing：確認翻空後使用 `lowest price + ATR × {args.trailing_atr_multiplier:g}`，只可向下收緊

結果未包含手續費、期交稅與買賣價差。最大回撤從初始權益 0 開始計算。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_comparison_chart(path: Path, hourly: pd.DataFrame, legacy: pd.DataFrame, strategy_b: pd.DataFrame, slippage: float) -> None:
    figure = make_subplots(rows=2, cols=1, shared_xaxes=True, row_heights=[0.7, 0.3], vertical_spacing=0.06, subplot_titles=("Hourly price and A/B trades", "Gross and cost-adjusted equity"))
    figure.add_trace(go.Candlestick(x=hourly["timestamp"], open=hourly["open"], high=hourly["high"], low=hourly["low"], close=hourly["close"], name="60-minute bars"), row=1, col=1)
    if not legacy.empty:
        figure.add_trace(go.Scatter(x=legacy["entry_time"], y=legacy["entry_price"], mode="markers", name="Legacy A entry", marker={"symbol": "triangle-down", "color": "#6a1b9a", "size": 9}), row=1, col=1)
        legacy_net = legacy["pnl_points"] - 2 * slippage
        figure.add_trace(go.Scatter(x=legacy["exit_time"], y=legacy["pnl_points"].cumsum(), mode="lines+markers", name="A gross", line={"color": "#7b1fa2"}), row=2, col=1)
        figure.add_trace(go.Scatter(x=legacy["exit_time"], y=legacy_net.cumsum(), mode="lines+markers", name="A cost-adjusted", line={"color": "#ab47bc", "dash": "dot"}), row=2, col=1)
    if not strategy_b.empty:
        figure.add_trace(go.Scatter(x=strategy_b["entry_time"], y=strategy_b["entry_fill_price"], mode="markers", name="Strategy B entry", marker={"symbol": "triangle-down", "color": "#d32f2f", "size": 10}), row=1, col=1)
        figure.add_trace(go.Scatter(x=strategy_b["exit_time"], y=strategy_b["exit_fill_price"], mode="markers", name="Strategy B exit", marker={"symbol": "x", "color": "#00897b", "size": 9}, text=strategy_b["exit_reason"]), row=1, col=1)
        figure.add_trace(go.Scatter(x=strategy_b["exit_time"], y=strategy_b["gross_pnl_points"].cumsum(), mode="lines+markers", name="B gross", line={"color": "#ef6c00"}), row=2, col=1)
        figure.add_trace(go.Scatter(x=strategy_b["exit_time"], y=strategy_b["pnl_points"].cumsum(), mode="lines+markers", name="B net", line={"color": "#1565c0", "dash": "dot"}), row=2, col=1)
    figure.update_layout(title="TMF 202609 Adaptive Hourly Resistance Short A/B Test", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Points", row=2, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="A/B test Legacy A and session-risk Strategy B.")
    parser.add_argument("--input-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--start-date", type=parse_date, required=True)
    parser.add_argument("--end-date", type=parse_date, required=True)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--strategy-variant", choices=("legacy", "session-risk", "both"), default="both")
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
    parser.add_argument("--output-dir", type=Path, default=TICK_DIR)
    parser.add_argument("--report-output", type=Path)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    positive = (args.volume_bar_size, args.atr_length, args.initial_stop_atr_multiplier, args.confirmation_timeout_hours, args.maximum_holding_hours, args.trailing_atr_multiplier)
    if any(value <= 0 for value in positive) or args.slippage_points < 0:
        parser.error("bar, ATR, timeout, holding, trailing, and stop parameters must be positive; slippage cannot be negative")
    return args


def main() -> None:
    args = parse_args()
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    ticks = add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip())).reset_index(drop=True)
    ticks.insert(0, "tick_id", np.arange(len(ticks), dtype=np.int64))
    hourly = add_adaptive_supertrend(build_hourly_bars(ticks), args.atr_length, args.base_multiplier, args.min_multiplier, args.speed_lookback, args.low_speed, args.high_speed, args.smoothing_span)
    zones = pine_style_zones(hourly, args.pivot_lookback, args.volume_filter_length, args.zone_atr_length, args.zone_box_width)
    legacy = pd.DataFrame()
    strategy_b = pd.DataFrame()
    if args.strategy_variant in ("legacy", "both"):
        legacy_bars = build_continuous_volume_bars(ticks, args.volume_bar_size)
        legacy_bars = detect_dense_reversals(legacy_bars, args.tick_lookback, 50, 0.75)
        legacy_bars = attach_hourly_state(assign_resistance_entries(add_bearish_rejection_signals(legacy_bars, args.close_position_max), zones), hourly)
        legacy = backtest_legacy(legacy_bars)
    if args.strategy_variant in ("session-risk", "both"):
        strategy_b_bars = build_session_volume_bars(ticks, args.volume_bar_size)
        strategy_b_bars = add_strategy_b_signals(strategy_b_bars, args.tick_lookback, args.close_position_max)
        strategy_b_bars = assign_resistance_entries(strategy_b_bars, zones)
        strategy_b_bars = attach_strategy_b_hourly_state(strategy_b_bars, hourly)
        strategy_b = backtest_strategy_b(ticks, strategy_b_bars, hourly, args.slippage_points, args.initial_stop_atr_multiplier, args.confirmation_timeout_hours, args.maximum_holding_hours, args.trailing_atr_multiplier)

    period = f"{args.start_date:%Y-%m-%d}_to_{args.end_date:%Y-%m-%d}"
    legacy_path = args.output_dir / f"TMF_{args.contract_month}_adaptive_hourly_short_legacy_trades_{period}.csv"
    strategy_b_path = args.output_dir / f"TMF_{args.contract_month}_adaptive_hourly_short_strategy_b_trades_{period}.csv"
    chart_path = args.output_dir / f"TMF_{args.contract_month}_adaptive_hourly_short_ab_comparison_{period}.html"
    report_path = args.report_output or DOC_DIR / f"tmf_{args.contract_month}_adaptive_hourly_short_ab_comparison_{period}.md"
    args.output_dir.mkdir(parents=True, exist_ok=True)
    legacy.to_csv(legacy_path, index=False, encoding="utf-8-sig")
    strategy_b.to_csv(strategy_b_path, index=False, encoding="utf-8-sig")
    write_comparison_report(report_path, args, ticks, legacy, strategy_b)
    write_comparison_chart(chart_path, hourly, legacy, strategy_b, args.slippage_points)
    print(f"ticks={len(ticks)} legacy_trades={len(legacy)} strategy_b_trades={len(strategy_b)}")
    print(f"legacy={legacy_path}\nstrategy_b={strategy_b_path}\nreport={report_path}\nchart={chart_path}")


if __name__ == "__main__":
    main()
