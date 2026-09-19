#!/usr/bin/env python
"""Backtest the four Pine diamond signals on exchange-anchored 60-minute bars."""

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
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_support_long import build_hourly_bars
except ImportError:
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_support_long import build_hourly_bars


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "txf_tick"
DOC_DIR = ROOT / "doc"
DEFAULT_START = date(2026, 8, 5)
DEFAULT_END = date(2026, 9, 15)
OUTPUT_PERIOD = "2026-08-05_to_2026-09-15"
DEFAULT_HOURLY = OUTPUT_DIR / f"TMF_202609_hourly_diamond_signals_{OUTPUT_PERIOD}.csv"
DEFAULT_TRADES = OUTPUT_DIR / f"TMF_202609_hourly_diamond_short_trades_{OUTPUT_PERIOD}.csv"
DEFAULT_CHART = OUTPUT_DIR / f"TMF_202609_hourly_diamond_short_backtest_{OUTPUT_PERIOD}.html"
DEFAULT_REPORT = DOC_DIR / f"tmf_202609_hourly_diamond_short_backtest_{OUTPUT_PERIOD}.md"


@dataclass
class ShortPosition:
    entry_index: int
    signal_index: int
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    entry_price: float
    stop_price: float
    risk_points: float
    signal_type: str
    structure_type: str
    structure_id: int
    stop_anchor: float
    atr_at_signal: float
    lowest_price: float
    highest_price: float


def pine_rma(values: pd.Series, length: int) -> pd.Series:
    """Pine-compatible RMA: SMA seed followed by Wilder's recursive average."""
    if length < 1:
        raise ValueError("length must be at least 1")
    source = pd.to_numeric(values, errors="coerce").astype(float)
    output = pd.Series(np.nan, index=source.index, dtype=float)
    if len(source) < length:
        return output
    for index in range(length - 1, len(source)):
        window = source.iloc[index - length + 1 : index + 1]
        if window.notna().all():
            output.iloc[index] = float(window.mean())
            start = index + 1
            break
    else:
        return output
    for index in range(start, len(source)):
        value = source.iloc[index]
        previous = output.iloc[index - 1]
        if pd.isna(value) or pd.isna(previous):
            continue
        output.iloc[index] = (previous * (length - 1) + value) / length
    return output


def pine_atr(bars: pd.DataFrame, length: int) -> pd.Series:
    previous_close = bars["close"].shift(1)
    true_range = pd.concat(
        [
            bars["high"] - bars["low"],
            (bars["high"] - previous_close).abs(),
            (bars["low"] - previous_close).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return pine_rma(true_range, length)


def _cross_over(current_a: float, previous_a: float, current_b: float, previous_b: float) -> bool:
    values = (current_a, previous_a, current_b, previous_b)
    return bool(all(pd.notna(value) for value in values) and current_a > current_b and previous_a <= previous_b)


def _cross_under(current_a: float, previous_a: float, current_b: float, previous_b: float) -> bool:
    values = (current_a, previous_a, current_b, previous_b)
    return bool(all(pd.notna(value) for value in values) and current_a < current_b and previous_a >= previous_b)


def add_pine_diamond_signals(
    bars: pd.DataFrame,
    lookback: int = 20,
    volume_length: int = 2,
    atr_length: int = 200,
    box_width: float = 1.0,
) -> pd.DataFrame:
    """Recreate the latest-zone state and the four diamonds from pine_script.txt.

    Signal columns are stamped on the bar that actually confirms the condition.
    Pine's visual-only ``offset=-1`` is deliberately not reproduced.
    """
    if lookback < 1 or volume_length < 1 or atr_length < 1:
        raise ValueError("lookback, volume_length, and atr_length must be positive")
    if box_width < 0:
        raise ValueError("box_width must be non-negative")

    result = bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    required = {"timestamp", "hour_start", "open", "high", "low", "close", "volume", "session_id"}
    missing = required.difference(result.columns)
    if missing:
        raise ValueError(f"Missing hourly columns: {sorted(missing)}")

    is_buy = True
    delta_volume: list[float] = []
    for bar in result.itertuples(index=False):
        if bar.close > bar.open:
            is_buy = True
        elif bar.close < bar.open:
            is_buy = False
        delta_volume.append(float(bar.volume) if is_buy else -float(bar.volume))
    result["delta_volume"] = delta_volume
    result["atr"] = pine_atr(result, atr_length)
    scaled_volume = result["delta_volume"] / 2.5
    result["volume_high_filter"] = scaled_volume.rolling(volume_length, min_periods=volume_length).max()
    result["volume_low_filter"] = scaled_volume.rolling(volume_length, min_periods=volume_length).min()

    float_columns = [
        "support_top", "support_bottom", "resistance_bottom", "resistance_top", "short_stop_anchor"
    ]
    for column in float_columns:
        result[column] = np.nan
    for column in ("support_id", "resistance_id", "short_structure_id"):
        result[column] = pd.Series(pd.array([pd.NA] * len(result), dtype="Int64"))
    bool_columns = [
        "breakout_resistance", "resistance_holds", "support_holds", "breakout_support",
        "resistance_as_support_holds", "support_as_resistance_holds", "short_signal", "green_exit_signal",
    ]
    for column in bool_columns:
        result[column] = False
    result["short_signal_type"] = pd.Series([None] * len(result), dtype="object")
    result["short_structure_type"] = pd.Series([None] * len(result), dtype="object")
    result["green_exit_signal_type"] = pd.Series([None] * len(result), dtype="object")

    support_top = support_bottom = np.nan
    resistance_bottom = resistance_top = np.nan
    support_id: int | None = None
    resistance_id: int | None = None
    next_structure_id = 0
    resistance_is_support: bool | None = None
    support_is_resistance: bool | None = None

    for index in range(len(result)):
        atr = result.at[index, "atr"]
        if index >= 2 * lookback and pd.notna(atr):
            candidate_index = index - lookback
            window = result["close"].iloc[candidate_index - lookback : candidate_index + lookback + 1]
            candidate_close = float(result.at[candidate_index, "close"])
            delta = float(result.at[index, "delta_volume"])
            volume_high = result.at[index, "volume_high_filter"]
            volume_low = result.at[index, "volume_low_filter"]
            width = float(atr) * box_width
            if pd.notna(volume_high) and candidate_close == float(window.min()) and delta > float(volume_high):
                next_structure_id += 1
                support_id = next_structure_id
                support_top = candidate_close
                support_bottom = candidate_close - width
            if pd.notna(volume_low) and candidate_close == float(window.max()) and delta < float(volume_low):
                next_structure_id += 1
                resistance_id = next_structure_id
                resistance_bottom = candidate_close
                resistance_top = candidate_close + width

        result.at[index, "support_top"] = support_top
        result.at[index, "support_bottom"] = support_bottom
        result.at[index, "resistance_bottom"] = resistance_bottom
        result.at[index, "resistance_top"] = resistance_top
        if support_id is not None:
            result.at[index, "support_id"] = support_id
        if resistance_id is not None:
            result.at[index, "resistance_id"] = resistance_id

        if index == 0:
            continue
        current_low = float(result.at[index, "low"])
        previous_low = float(result.at[index - 1, "low"])
        current_high = float(result.at[index, "high"])
        previous_high = float(result.at[index - 1, "high"])
        previous_resistance_top = result.at[index - 1, "resistance_top"]
        previous_resistance_bottom = result.at[index - 1, "resistance_bottom"]
        previous_support_top = result.at[index - 1, "support_top"]
        previous_support_bottom = result.at[index - 1, "support_bottom"]

        breakout_resistance = _cross_over(current_low, previous_low, resistance_top, previous_resistance_top)
        resistance_holds = _cross_under(current_high, previous_high, resistance_bottom, previous_resistance_bottom)
        support_holds = _cross_over(current_low, previous_low, support_top, previous_support_top)
        breakout_support = _cross_under(current_high, previous_high, support_bottom, previous_support_bottom)
        resistance_as_support = breakout_resistance and resistance_is_support is True
        support_as_resistance = breakout_support and support_is_resistance is True

        result.at[index, "breakout_resistance"] = breakout_resistance
        result.at[index, "resistance_holds"] = resistance_holds
        result.at[index, "support_holds"] = support_holds
        result.at[index, "breakout_support"] = breakout_support
        result.at[index, "resistance_as_support_holds"] = resistance_as_support
        result.at[index, "support_as_resistance_holds"] = support_as_resistance

        red_types: list[str] = []
        anchors: list[tuple[float, str, int]] = []
        if resistance_holds and resistance_id is not None:
            red_types.append("resistance_holds")
            anchors.append((float(resistance_top), "resistance", resistance_id))
        if support_as_resistance and support_id is not None:
            red_types.append("support_as_resistance_holds")
            anchors.append((float(support_top), "support_as_resistance", support_id))
        if red_types:
            anchor, structure_type, structure_id = max(anchors, key=lambda item: item[0])
            result.at[index, "short_signal"] = True
            result.at[index, "short_signal_type"] = "+".join(red_types)
            result.at[index, "short_stop_anchor"] = anchor
            result.at[index, "short_structure_type"] = structure_type
            result.at[index, "short_structure_id"] = structure_id

        green_types: list[str] = []
        if support_holds:
            green_types.append("support_holds")
        if resistance_as_support:
            green_types.append("resistance_as_support_holds")
        if green_types:
            result.at[index, "green_exit_signal"] = True
            result.at[index, "green_exit_signal_type"] = "+".join(green_types)

        # Pine's switch uses the first true branch and otherwise retains state.
        if breakout_resistance:
            resistance_is_support = True
        elif resistance_holds:
            resistance_is_support = False
        if breakout_support:
            support_is_resistance = True
        elif support_holds:
            support_is_resistance = False

    return result


TRADE_COLUMNS = [
    "trade_number", "signal_index", "signal_time", "entry_time", "exit_time", "entry_session", "exit_session",
    "entry_price", "exit_price", "stop_anchor", "atr_at_signal", "stop_price", "risk_points", "signal_type",
    "structure_type", "structure_id", "green_exit_signal_type", "gross_points", "round_trip_cost_points",
    "net_points", "gross_r", "net_r", "mfe_points", "mae_points", "exit_reason", "cross_session",
    "cumulative_gross_points", "cumulative_net_points", "gross_drawdown_points", "net_drawdown_points",
]


def _trade_record(
    position: ShortPosition,
    exit_bar: pd.Series,
    exit_time: pd.Timestamp,
    exit_price: float,
    reason: str,
    round_trip_cost_points: float,
    green_exit_type: str | None = None,
) -> dict[str, object]:
    gross = position.entry_price - exit_price
    net = gross - round_trip_cost_points
    return {
        "signal_index": position.signal_index,
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": exit_time,
        "entry_session": position.entry_session,
        "exit_session": str(exit_bar["session_id"]),
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "stop_anchor": position.stop_anchor,
        "atr_at_signal": position.atr_at_signal,
        "stop_price": position.stop_price,
        "risk_points": position.risk_points,
        "signal_type": position.signal_type,
        "structure_type": position.structure_type,
        "structure_id": position.structure_id,
        "green_exit_signal_type": green_exit_type,
        "gross_points": gross,
        "round_trip_cost_points": round_trip_cost_points,
        "net_points": net,
        "gross_r": gross / position.risk_points,
        "net_r": net / position.risk_points,
        "mfe_points": position.entry_price - position.lowest_price,
        "mae_points": position.entry_price - position.highest_price,
        "exit_reason": reason,
        "cross_session": position.entry_session != str(exit_bar["session_id"]),
    }


def backtest_short_only(
    bars: pd.DataFrame,
    stop_atr_buffer: float = 0.10,
    round_trip_cost_points: float = 0.0,
) -> pd.DataFrame:
    """Trade confirmed red diamonds at the next open and exit on stop/green diamonds."""
    if stop_atr_buffer < 0 or round_trip_cost_points < 0:
        raise ValueError("stop_atr_buffer and round_trip_cost_points must be non-negative")
    frame = bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    trades: list[dict[str, object]] = []
    position: ShortPosition | None = None
    pending_entry: dict[str, object] | None = None
    pending_green_exit: str | None = None

    for index, bar in frame.iterrows():
        occupied_this_bar = position is not None
        open_price = float(bar["open"])

        if position is not None and open_price >= position.stop_price:
            position.highest_price = max(position.highest_price, open_price)
            trades.append(
                _trade_record(position, bar, pd.Timestamp(bar["hour_start"]), open_price, "stop_gap", round_trip_cost_points)
            )
            position = None
            pending_green_exit = None
        elif position is not None and pending_green_exit is not None:
            position.lowest_price = min(position.lowest_price, open_price)
            position.highest_price = max(position.highest_price, open_price)
            trades.append(
                _trade_record(
                    position, bar, pd.Timestamp(bar["hour_start"]), open_price, "green_diamond",
                    round_trip_cost_points, pending_green_exit,
                )
            )
            position = None
            pending_green_exit = None

        if position is None and not occupied_this_bar and pending_entry is not None:
            stop_price = float(pending_entry["stop_price"])
            if open_price < stop_price:
                position = ShortPosition(
                    entry_index=index,
                    signal_index=int(pending_entry["signal_index"]),
                    signal_time=pd.Timestamp(pending_entry["signal_time"]),
                    entry_time=pd.Timestamp(bar["hour_start"]),
                    entry_session=str(bar["session_id"]),
                    entry_price=open_price,
                    stop_price=stop_price,
                    risk_points=stop_price - open_price,
                    signal_type=str(pending_entry["signal_type"]),
                    structure_type=str(pending_entry["structure_type"]),
                    structure_id=int(pending_entry["structure_id"]),
                    stop_anchor=float(pending_entry["stop_anchor"]),
                    atr_at_signal=float(pending_entry["atr"]),
                    lowest_price=open_price,
                    highest_price=open_price,
                )
                occupied_this_bar = True
            pending_entry = None

        if position is not None:
            if float(bar["high"]) >= position.stop_price:
                # With hourly OHLC the path inside the bar is unknowable.  For a
                # stop bar, record only the known stop excursion rather than
                # pretending the later/earlier full-bar extremes were tradable.
                position.highest_price = max(position.highest_price, position.stop_price)
                trades.append(
                    _trade_record(
                        position, bar, pd.Timestamp(bar["timestamp"]), position.stop_price,
                        "intrabar_stop", round_trip_cost_points,
                    )
                )
                position = None
                pending_green_exit = None
            else:
                position.lowest_price = min(position.lowest_price, float(bar["low"]))
                position.highest_price = max(position.highest_price, float(bar["high"]))
                if bool(bar["green_exit_signal"]):
                    pending_green_exit = str(bar["green_exit_signal_type"])

        if position is None and not occupied_this_bar and pending_entry is None and bool(bar["short_signal"]):
            values = (bar["short_stop_anchor"], bar["atr"], bar["short_structure_id"])
            if all(pd.notna(value) for value in values) and index < len(frame) - 1:
                pending_entry = {
                    "signal_index": index,
                    "signal_time": bar["timestamp"],
                    "signal_type": bar["short_signal_type"],
                    "structure_type": bar["short_structure_type"],
                    "structure_id": int(bar["short_structure_id"]),
                    "stop_anchor": float(bar["short_stop_anchor"]),
                    "atr": float(bar["atr"]),
                    "stop_price": float(bar["short_stop_anchor"]) + stop_atr_buffer * float(bar["atr"]),
                }

    if position is not None:
        last = frame.iloc[-1]
        exit_price = float(last["close"])
        position.lowest_price = min(position.lowest_price, float(last["low"]))
        position.highest_price = max(position.highest_price, float(last["high"]))
        trades.append(
            _trade_record(position, last, pd.Timestamp(last["timestamp"]), exit_price, "data_end", round_trip_cost_points)
        )

    if not trades:
        return pd.DataFrame(columns=TRADE_COLUMNS)
    result = pd.DataFrame(trades)
    result.insert(0, "trade_number", range(1, len(result) + 1))
    result["cumulative_gross_points"] = result["gross_points"].cumsum()
    result["cumulative_net_points"] = result["net_points"].cumsum()
    gross_peak = np.maximum.accumulate(np.r_[0.0, result["cumulative_gross_points"].to_numpy()])[1:]
    net_peak = np.maximum.accumulate(np.r_[0.0, result["cumulative_net_points"].to_numpy()])[1:]
    result["gross_drawdown_points"] = result["cumulative_gross_points"] - gross_peak
    result["net_drawdown_points"] = result["cumulative_net_points"] - net_peak
    return result.reindex(columns=TRADE_COLUMNS)


def performance_summary(trades: pd.DataFrame) -> dict[str, float | int | str]:
    if trades.empty:
        return {"trades": 0}
    winners = trades[trades["net_points"] > 0]
    losers = trades[trades["net_points"] < 0]
    gross_profit = float(winners["net_points"].sum())
    gross_loss = float(losers["net_points"].sum())
    return {
        "trades": len(trades),
        "wins": len(winners),
        "losses": len(losers),
        "breakeven": int((trades["net_points"] == 0).sum()),
        "win_rate": len(winners) / len(trades) * 100,
        "gross_points": float(trades["gross_points"].sum()),
        "net_points": float(trades["net_points"].sum()),
        "profit_factor": "n/a" if gross_loss == 0 else f"{gross_profit / abs(gross_loss):.2f}",
        "average_net_points": float(trades["net_points"].mean()),
        "max_net_drawdown": float(trades["net_drawdown_points"].min()),
        "cross_session": int(trades["cross_session"].sum()),
    }


def _metric(summary: dict[str, object], name: str, default: object = 0) -> object:
    return summary.get(name, default)


def write_report(
    path: Path,
    args: argparse.Namespace,
    sources: list[Path],
    ticks: pd.DataFrame,
    hourly: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    trade_rows = "| - | - | - | - | - | - | - | No trade |"
    if not trades.empty:
        trade_rows = "\n".join(
            f"| {trade.trade_number} | {trade.signal_time:%Y-%m-%d %H:%M:%S} | "
            f"{trade.entry_time:%Y-%m-%d %H:%M:%S} @ {trade.entry_price:.0f} | "
            f"{trade.exit_time:%Y-%m-%d %H:%M:%S} @ {trade.exit_price:.0f} | {trade.signal_type} | "
            f"{trade.gross_points:.1f} | {trade.net_points:.1f} | {trade.exit_reason} |"
            for trade in trades.itertuples(index=False)
        )
    text = f"""# {args.product} {args.contract_month}：60 分 K 紅綠菱形純放空回測

## 資料與設定

- 日期：`{args.start_date}` 至 `{args.end_date}`；來源檔 {len(sources)} 個，有效 tick {len(ticks):,} 筆，60 分 K {len(hourly):,} 根。
- 日盤從 `08:45`、夜盤從 `15:00` 起算 60 分 K；指標與部位允許跨盤延續。
- Pine 參數：close pivot `{args.pivot_lookback}/{args.pivot_lookback}`、delta-volume length `{args.volume_filter_length}`、ATR `{args.atr_length}`、箱體寬度 `{args.box_width:g} ATR`。
- 結構停損：觸發箱體上緣加 `{args.stop_atr_buffer:g} ATR`；每筆完整交易成本 `{args.round_trip_cost_points:g}` 點。

## 交易規則

- `Resistance Holds` 或 `Support as Resistance Holds` 紅菱形於 60 分 K 收盤確認，下一根開盤放空。
- 開盤已越過停損則取消進場；持倉後跳空越過停損按開盤價出場，盤中 high 觸價則按停損價出場。
- `Support Holds` 或 `Resistance as Support Holds` 綠菱形收盤確認後，下一根開盤平空；停損優先於綠菱形。
- 同時最多一口、不加碼、不設停利或時間停損；資料結尾仍持倉則按最後收盤結算。
- 訊號使用實際確認 K，不採用原圖 `offset=-1` 的顯示位置。

## 結果

| Metric | Value |
| --- | ---: |
| Red diamond signals | {int(hourly['short_signal'].sum())} |
| Green diamond signals | {int(hourly['green_exit_signal'].sum())} |
| Trades | {_metric(summary, 'trades')} |
| Wins / Losses / Breakeven | {_metric(summary, 'wins')} / {_metric(summary, 'losses')} / {_metric(summary, 'breakeven')} |
| Win rate | {float(_metric(summary, 'win_rate')):.1f}% |
| Gross P&L | {float(_metric(summary, 'gross_points')):.1f} points |
| Net P&L | {float(_metric(summary, 'net_points')):.1f} points |
| Net profit factor | {_metric(summary, 'profit_factor', 'n/a')} |
| Average net P&L | {float(_metric(summary, 'average_net_points')):.1f} points |
| Maximum net drawdown | {float(_metric(summary, 'max_net_drawdown')):.1f} points |
| Cross-session trades | {_metric(summary, 'cross_session')} |

## Trade Ledger

| # | Signal | Entry | Exit | Type | Gross | Net | Exit reason |
|---:|---|---|---|---|---:|---:|---|
{trade_rows}

## 回測限制

- 盤中停損只有 60 分 OHLC，無法得知該小時內的精確觸價秒數；成交價依上述停損規則模擬。
- MFE/MAE 使用持倉涵蓋之完整 60 分 K 高低點；停損 K 因盤中先後順序不可知，保守地只計入已知停損成交價。
- 淨損益只扣指定的固定每筆點數成本，未換算契約乘數或逐項估算手續費、稅與滑價。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _zone_spans(hourly: pd.DataFrame, id_column: str, lower_column: str, upper_column: str) -> list[dict[str, object]]:
    spans: list[dict[str, object]] = []
    valid = hourly[hourly[id_column].notna()]
    for structure_id, group in valid.groupby(id_column, sort=True):
        spans.append(
            {
                "id": int(structure_id),
                "start": group.iloc[0]["timestamp"],
                "end": group.iloc[-1]["timestamp"],
                "lower": float(group.iloc[0][lower_column]),
                "upper": float(group.iloc[0][upper_column]),
            }
        )
    return spans


def write_chart(path: Path, hourly: pd.DataFrame, trades: pd.DataFrame) -> None:
    figure = make_subplots(
        rows=2, cols=1, shared_xaxes=True, vertical_spacing=0.04, row_heights=[0.78, 0.22],
        subplot_titles=("60-minute Pine diamond short strategy", "Closed-trade net equity"),
    )
    figure.add_trace(
        go.Candlestick(
            x=hourly["timestamp"], open=hourly["open"], high=hourly["high"], low=hourly["low"],
            close=hourly["close"], name="60-minute bars",
        ), row=1, col=1,
    )
    for span in _zone_spans(hourly, "support_id", "support_bottom", "support_top"):
        figure.add_shape(
            type="rect", x0=span["start"], x1=span["end"], y0=span["lower"], y1=span["upper"],
            fillcolor="rgba(32,202,38,0.15)", line={"color": "rgba(32,202,38,0.7)", "width": 1}, row=1, col=1,
        )
    for span in _zone_spans(hourly, "resistance_id", "resistance_bottom", "resistance_top"):
        figure.add_shape(
            type="rect", x0=span["start"], x1=span["end"], y0=span["lower"], y1=span["upper"],
            fillcolor="rgba(233,41,41,0.13)", line={"color": "rgba(233,41,41,0.7)", "width": 1}, row=1, col=1,
        )
    red = hourly[hourly["short_signal"]]
    green = hourly[hourly["green_exit_signal"]]
    figure.add_trace(
        go.Scatter(x=red["timestamp"], y=red["high"], mode="markers", name="Red diamond",
                   marker={"symbol": "diamond", "size": 9, "color": "#e92929"}, text=red["short_signal_type"]), row=1, col=1,
    )
    figure.add_trace(
        go.Scatter(x=green["timestamp"], y=green["low"], mode="markers", name="Green diamond",
                   marker={"symbol": "diamond", "size": 9, "color": "#20ca26"}, text=green["green_exit_signal_type"]), row=1, col=1,
    )
    if not trades.empty:
        figure.add_trace(
            go.Scatter(x=trades["entry_time"], y=trades["entry_price"], mode="markers", name="Short entry",
                       marker={"symbol": "triangle-down", "size": 13, "color": "#6a1b9a"}), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(x=trades["exit_time"], y=trades["exit_price"], mode="markers", name="Exit",
                       marker={"symbol": "x", "size": 11, "color": "#00897b"}, text=trades["exit_reason"]), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(x=trades["exit_time"], y=trades["cumulative_net_points"], mode="lines+markers",
                       name="Net cumulative P&L", line={"color": "#3949ab"}), row=2, col=1,
        )
    figure.update_layout(title="60-minute Red/Green Diamond Short-only Backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Net points", row=2, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest Pine red/green diamonds as a 60-minute short-only strategy.")
    parser.add_argument("--input-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START)
    parser.add_argument("--end-date", type=parse_date, default=DEFAULT_END)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--atr-length", type=int, default=200)
    parser.add_argument("--box-width", type=float, default=1.0)
    parser.add_argument("--stop-atr-buffer", type=float, default=0.10)
    parser.add_argument("--round-trip-cost-points", type=float, default=0.0)
    parser.add_argument("--hourly-output", type=Path, default=DEFAULT_HOURLY)
    parser.add_argument("--trades-output", type=Path, default=DEFAULT_TRADES)
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    if min(args.pivot_lookback, args.volume_filter_length, args.atr_length) < 1:
        parser.error("lookback and length parameters must be positive")
    if min(args.box_width, args.stop_atr_buffer, args.round_trip_cost_points) < 0:
        parser.error("width, buffer, and cost parameters must be non-negative")
    return args


def main() -> None:
    args = parse_args()
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    ticks = add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip()))
    hourly = build_hourly_bars(ticks)
    hourly = add_pine_diamond_signals(
        hourly, args.pivot_lookback, args.volume_filter_length, args.atr_length, args.box_width
    )
    trades = backtest_short_only(hourly, args.stop_atr_buffer, args.round_trip_cost_points)
    summary = performance_summary(trades)
    for output in (args.hourly_output, args.trades_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(args.hourly_output, index=False, encoding="utf-8-sig")
    trades.to_csv(args.trades_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, args, sources, ticks, hourly, trades, summary)
    write_chart(args.chart_output, hourly, trades)
    print(
        f"ticks={len(ticks)} hourly_bars={len(hourly)} red_signals={int(hourly['short_signal'].sum())} "
        f"green_signals={int(hourly['green_exit_signal'].sum())}"
    )
    print(
        f"trades={summary['trades']} gross_points={float(summary.get('gross_points', 0)):.1f} "
        f"net_points={float(summary.get('net_points', 0)):.1f}"
    )
    print(f"report={args.report_output}")


if __name__ == "__main__":
    main()
