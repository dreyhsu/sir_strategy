#!/usr/bin/env python
"""Backtest Pine-style resistance rejection and support-break shorts on TMF 1-hour bars."""

from __future__ import annotations

import argparse
from dataclasses import dataclass
from datetime import date
from pathlib import Path

import numpy as np
import pandas as pd

try:
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_diamond_short import add_pine_diamond_signals, performance_summary
    from .backtest_tmf_hourly_support_long import build_hourly_bars
except ImportError:
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_diamond_short import add_pine_diamond_signals, performance_summary
    from backtest_tmf_hourly_support_long import build_hourly_bars


ROOT = Path(__file__).resolve().parents[1]
DEFAULT_INPUT_DIR = ROOT / "data" / "txf"
DEFAULT_OUTPUT_DIR = ROOT / "txf_tick"
DEFAULT_DOC_DIR = ROOT / "doc"
DEFAULT_START = date(2026, 8, 5)
DEFAULT_END = date(2026, 9, 15)
DEFAULT_PERIOD = "2026-08-05_to_2026-09-15"


@dataclass
class ShortPosition:
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    entry_price: float
    stop_price: float
    target_price: float
    risk_points: float
    signal_type: str
    structure_type: str
    structure_id: int
    stop_anchor: float
    atr_at_signal: float
    lowest_price: float
    highest_price: float


TRADE_COLUMNS = [
    "trade_number",
    "signal_time",
    "entry_time",
    "exit_time",
    "entry_session",
    "exit_session",
    "entry_price",
    "exit_price",
    "stop_anchor",
    "atr_at_signal",
    "stop_price",
    "target_price",
    "risk_points",
    "signal_type",
    "structure_type",
    "structure_id",
    "gross_points",
    "round_trip_cost_points",
    "net_points",
    "gross_r",
    "net_r",
    "mfe_points",
    "mae_points",
    "exit_reason",
    "cross_session",
    "cumulative_gross_points",
    "cumulative_net_points",
    "gross_drawdown_points",
    "net_drawdown_points",
]


def add_short_entry_signals(bars: pd.DataFrame) -> pd.DataFrame:
    """Select the two short entries described in the strategy specification.

    - ``resistance_holds``: the bar high crosses below resistance's lower edge.
    - ``breakout_support``: the bar high crosses below support's lower edge.

    If both occur on the same bar, the higher stop anchor is used so the resulting
    stop contains both structures.
    """
    result = bars.copy()
    result["entry_signal"] = False
    result["entry_signal_type"] = pd.Series([None] * len(result), index=result.index, dtype="object")
    result["entry_structure_type"] = pd.Series([None] * len(result), index=result.index, dtype="object")
    result["entry_structure_id"] = pd.Series(pd.array([pd.NA] * len(result), dtype="Int64"), index=result.index)
    result["entry_stop_anchor"] = np.nan

    for index, bar in result.iterrows():
        candidates: list[tuple[float, str, str, int]] = []
        if bool(bar["resistance_holds"]) and pd.notna(bar["resistance_id"]):
            candidates.append(
                (float(bar["resistance_top"]), "resistance_holds", "resistance", int(bar["resistance_id"]))
            )
        if bool(bar["breakout_support"]) and pd.notna(bar["support_id"]):
            candidates.append(
                (float(bar["support_top"]), "breakout_support", "support", int(bar["support_id"]))
            )
        if not candidates:
            continue
        stop_anchor, _, structure_type, structure_id = max(candidates, key=lambda item: item[0])
        result.at[index, "entry_signal"] = True
        result.at[index, "entry_signal_type"] = "+".join(item[1] for item in candidates)
        result.at[index, "entry_structure_type"] = structure_type
        result.at[index, "entry_structure_id"] = structure_id
        result.at[index, "entry_stop_anchor"] = stop_anchor
    return result


def _trade_record(
    position: ShortPosition,
    bar: pd.Series,
    exit_time: pd.Timestamp,
    exit_price: float,
    exit_reason: str,
    round_trip_cost_points: float,
) -> dict[str, object]:
    gross = position.entry_price - exit_price
    net = gross - round_trip_cost_points
    return {
        "signal_time": position.signal_time,
        "entry_time": position.entry_time,
        "exit_time": exit_time,
        "entry_session": position.entry_session,
        "exit_session": str(bar["session_id"]),
        "entry_price": position.entry_price,
        "exit_price": exit_price,
        "stop_anchor": position.stop_anchor,
        "atr_at_signal": position.atr_at_signal,
        "stop_price": position.stop_price,
        "target_price": position.target_price,
        "risk_points": position.risk_points,
        "signal_type": position.signal_type,
        "structure_type": position.structure_type,
        "structure_id": position.structure_id,
        "gross_points": gross,
        "round_trip_cost_points": round_trip_cost_points,
        "net_points": net,
        "gross_r": gross / position.risk_points,
        "net_r": net / position.risk_points,
        "mfe_points": position.entry_price - position.lowest_price,
        "mae_points": position.entry_price - position.highest_price,
        "exit_reason": exit_reason,
        "cross_session": position.entry_session != str(bar["session_id"]),
    }


def backtest_short_only(
    bars: pd.DataFrame,
    stop_atr_buffer: float = 0.10,
    reward_risk: float = 2.0,
    round_trip_cost_points: float = 0.0,
) -> pd.DataFrame:
    """Enter next-hour open; use a structure stop and fixed-R profit target.

    With hourly OHLC the intrabar price path is unknown.  If stop and target are
    both touched in one bar, this implementation conservatively executes the stop.
    """
    if stop_atr_buffer < 0 or reward_risk <= 0 or round_trip_cost_points < 0:
        raise ValueError("buffer/cost must be non-negative and reward_risk must be positive")

    frame = bars.copy().sort_values("timestamp", kind="stable").reset_index(drop=True)
    trades: list[dict[str, object]] = []
    position: ShortPosition | None = None
    pending_entry: dict[str, object] | None = None

    for index, bar in frame.iterrows():
        occupied_at_open = position is not None
        open_price = float(bar["open"])

        if position is not None and open_price >= position.stop_price:
            position.highest_price = max(position.highest_price, open_price)
            trades.append(
                _trade_record(
                    position, bar, pd.Timestamp(bar["hour_start"]), open_price, "stop_gap", round_trip_cost_points
                )
            )
            position = None
        elif position is not None and open_price <= position.target_price:
            position.lowest_price = min(position.lowest_price, open_price)
            trades.append(
                _trade_record(
                    position, bar, pd.Timestamp(bar["hour_start"]), open_price, "target_gap", round_trip_cost_points
                )
            )
            position = None

        if position is None and not occupied_at_open and pending_entry is not None:
            stop_price = float(pending_entry["stop_price"])
            risk_points = stop_price - open_price
            if risk_points > 0:
                target_price = open_price - reward_risk * risk_points
                position = ShortPosition(
                    signal_time=pd.Timestamp(pending_entry["signal_time"]),
                    entry_time=pd.Timestamp(bar["hour_start"]),
                    entry_session=str(bar["session_id"]),
                    entry_price=open_price,
                    stop_price=stop_price,
                    target_price=target_price,
                    risk_points=risk_points,
                    signal_type=str(pending_entry["signal_type"]),
                    structure_type=str(pending_entry["structure_type"]),
                    structure_id=int(pending_entry["structure_id"]),
                    stop_anchor=float(pending_entry["stop_anchor"]),
                    atr_at_signal=float(pending_entry["atr"]),
                    lowest_price=open_price,
                    highest_price=open_price,
                )
            pending_entry = None

        if position is not None:
            if float(bar["high"]) >= position.stop_price:
                position.highest_price = max(position.highest_price, position.stop_price)
                trades.append(
                    _trade_record(
                        position,
                        bar,
                        pd.Timestamp(bar["timestamp"]),
                        position.stop_price,
                        "intrabar_stop",
                        round_trip_cost_points,
                    )
                )
                position = None
            elif float(bar["low"]) <= position.target_price:
                position.lowest_price = min(position.lowest_price, position.target_price)
                position.highest_price = max(position.highest_price, float(bar["high"]))
                trades.append(
                    _trade_record(
                        position,
                        bar,
                        pd.Timestamp(bar["timestamp"]),
                        position.target_price,
                        "profit_target",
                        round_trip_cost_points,
                    )
                )
                position = None
            else:
                position.lowest_price = min(position.lowest_price, float(bar["low"]))
                position.highest_price = max(position.highest_price, float(bar["high"]))

        if position is None and not occupied_at_open and pending_entry is None and bool(bar["entry_signal"]):
            required = (bar["entry_stop_anchor"], bar["atr"], bar["entry_structure_id"])
            if all(pd.notna(value) for value in required) and index < len(frame) - 1:
                pending_entry = {
                    "signal_time": bar["timestamp"],
                    "signal_type": bar["entry_signal_type"],
                    "structure_type": bar["entry_structure_type"],
                    "structure_id": int(bar["entry_structure_id"]),
                    "stop_anchor": float(bar["entry_stop_anchor"]),
                    "atr": float(bar["atr"]),
                    "stop_price": float(bar["entry_stop_anchor"]) + stop_atr_buffer * float(bar["atr"]),
                }

    if position is not None:
        last = frame.iloc[-1]
        position.lowest_price = min(position.lowest_price, float(last["low"]))
        position.highest_price = max(position.highest_price, float(last["high"]))
        trades.append(
            _trade_record(
                position,
                last,
                pd.Timestamp(last["timestamp"]),
                float(last["close"]),
                "data_end",
                round_trip_cost_points,
            )
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


def write_report(
    path: Path,
    args: argparse.Namespace,
    source_count: int,
    tick_count: int,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    signal_counts = bars.loc[bars["entry_signal"], "entry_signal_type"].value_counts()
    signal_lines = "\n".join(f"- `{name}`：{count}" for name, count in signal_counts.items()) or "- 無訊號"
    rows = "| - | - | - | - | - | - | No trade |"
    if not trades.empty:
        rows = "\n".join(
            f"| {trade.trade_number} | {trade.signal_time:%Y-%m-%d %H:%M:%S} | "
            f"{trade.entry_time:%Y-%m-%d %H:%M:%S} @ {trade.entry_price:.0f} | "
            f"{trade.exit_time:%Y-%m-%d %H:%M:%S} @ {trade.exit_price:.0f} | "
            f"{trade.signal_type} | {trade.net_points:.1f} | {trade.exit_reason} |"
            for trade in trades.itertuples(index=False)
        )
    metric = lambda name, default=0: summary.get(name, default)
    text = f"""# {args.product} {args.contract_month}：1 小時 Pine 支撐壓力純放空回測

## 設定

- 期間：`{args.start_date}` 至 `{args.end_date}`；來源 {source_count} 檔、有效 tick {tick_count:,} 筆、1 小時 K {len(bars):,} 根。
- Pine 參數：pivot `{args.pivot_lookback}/{args.pivot_lookback}`、volume filter `{args.volume_filter_length}`、ATR `{args.atr_length}`、box width `{args.box_width:g} ATR`。
- 停損：訊號結構上緣加 `{args.stop_atr_buffer:g} ATR`；停利 `{args.reward_risk:g}R`；每筆完整交易成本 `{args.round_trip_cost_points:g}` 點。
- 日盤以 08:45、夜盤以 15:00 起算 60 分 K；結構與持倉可跨盤延續。

## 規則

- `resistance_holds`：壓力守住，訊號 K 收盤確認後，下一根 1 小時 K 開盤放空。
- `breakout_support`：整根 K 棒跌到支撐區下方，訊號 K 收盤確認後，下一根開盤放空。
- 同時最多一口，不加碼；下一根開盤已在停損之上時取消進場。
- 同一根 1 小時 K 同時觸及停損與停利時，因無法知道盤中順序，保守地先算停損。
- 訊號使用實際確認時間，不採用原 Pine 圖形的 `offset=-1` 顯示位置。

## 訊號數量

{signal_lines}

## 結果

| 指標 | 結果 |
| --- | ---: |
| Trades | {metric('trades')} |
| Wins / Losses / Breakeven | {metric('wins')} / {metric('losses')} / {metric('breakeven')} |
| Win rate | {float(metric('win_rate')):.1f}% |
| Gross P&L | {float(metric('gross_points')):.1f} points |
| Net P&L | {float(metric('net_points')):.1f} points |
| Net profit factor | {metric('profit_factor', 'n/a')} |
| Average net P&L | {float(metric('average_net_points')):.1f} points |
| Maximum net drawdown | {float(metric('max_net_drawdown')):.1f} points |

## 交易明細

| # | Signal | Entry | Exit | Type | Net | Exit reason |
|---:|---|---|---|---|---:|---|
{rows}

## 限制

- 只有 1 小時 OHLC，無法還原同一根 K 棒內的實際成交順序。
- 固定成本以點數扣除，尚未逐項換算契約乘數、手續費、交易稅與滑價。
- Pivot 必須等待右側 K 棒確認；歷史圖回畫的區塊不能視為當時已知。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _zone_spans(
    bars: pd.DataFrame,
    id_column: str,
    lower_column: str,
    upper_column: str,
) -> list[dict[str, object]]:
    """Collapse repeated latest-zone columns into drawable time spans."""
    spans: list[dict[str, object]] = []
    valid = bars[bars[id_column].notna()]
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


def write_html_report(
    path: Path,
    args: argparse.Namespace,
    bars: pd.DataFrame,
    trades: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    """Write an interactive candlestick, equity, and trade-ledger report."""
    import plotly.graph_objects as go
    from plotly.subplots import make_subplots

    metric = lambda name, default=0: summary.get(name, default)
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=False,
        vertical_spacing=0.055,
        row_heights=[0.64, 0.17, 0.19],
        specs=[[{"type": "xy"}], [{"type": "xy"}], [{"type": "table"}]],
        subplot_titles=("TMF 1-hour bars and Pine zones", "Closed-trade net equity", "Trade ledger"),
    )
    figure.add_trace(
        go.Candlestick(
            x=bars["timestamp"],
            open=bars["open"],
            high=bars["high"],
            low=bars["low"],
            close=bars["close"],
            name="TMF 1-hour",
        ),
        row=1,
        col=1,
    )

    for span in _zone_spans(bars, "support_id", "support_bottom", "support_top"):
        figure.add_shape(
            type="rect",
            x0=span["start"],
            x1=span["end"],
            y0=span["lower"],
            y1=span["upper"],
            fillcolor="rgba(32,202,38,0.14)",
            line={"color": "rgba(32,202,38,0.65)", "width": 1},
            layer="below",
            row=1,
            col=1,
        )
    for span in _zone_spans(bars, "resistance_id", "resistance_bottom", "resistance_top"):
        figure.add_shape(
            type="rect",
            x0=span["start"],
            x1=span["end"],
            y0=span["lower"],
            y1=span["upper"],
            fillcolor="rgba(233,41,41,0.12)",
            line={"color": "rgba(233,41,41,0.65)", "width": 1},
            layer="below",
            row=1,
            col=1,
        )

    rejection = bars[bars["entry_signal_type"].fillna("").str.contains("resistance_holds")]
    breakdown = bars[bars["entry_signal_type"].fillna("").str.contains("breakout_support")]
    figure.add_trace(
        go.Scatter(
            x=rejection["timestamp"],
            y=rejection["high"],
            mode="markers",
            name="Resistance holds",
            marker={"symbol": "diamond", "size": 10, "color": "#d32f2f"},
            customdata=rejection[["entry_stop_anchor"]],
            hovertemplate="Resistance holds<br>%{x}<br>High %{y}<br>Stop anchor %{customdata[0]:.1f}<extra></extra>",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=breakdown["timestamp"],
            y=breakdown["low"],
            mode="markers",
            name="Support breakout",
            marker={"symbol": "triangle-down", "size": 11, "color": "#fb8c00"},
            customdata=breakdown[["entry_stop_anchor"]],
            hovertemplate="Support breakout<br>%{x}<br>Low %{y}<br>Stop anchor %{customdata[0]:.1f}<extra></extra>",
        ),
        row=1,
        col=1,
    )

    if trades.empty:
        table_values: list[list[object]] = [["-"], ["No trade"], ["-"], ["-"], ["-"], ["-"]]
    else:
        figure.add_trace(
            go.Scatter(
                x=trades["entry_time"],
                y=trades["entry_price"],
                mode="markers",
                name="Short entry",
                marker={"symbol": "triangle-down", "size": 14, "color": "#6a1b9a"},
                text=trades["signal_type"],
                hovertemplate="Short entry<br>%{x}<br>%{y:.1f}<br>%{text}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"],
                y=trades["exit_price"],
                mode="markers",
                name="Exit",
                marker={"symbol": "x", "size": 12, "color": "#00897b"},
                text=trades["exit_reason"],
                hovertemplate="Exit<br>%{x}<br>%{y:.1f}<br>%{text}<extra></extra>",
            ),
            row=1,
            col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=trades["exit_time"],
                y=trades["cumulative_net_points"],
                mode="lines+markers",
                name="Cumulative net points",
                line={"color": "#3949ab", "width": 2},
                fill="tozeroy",
                fillcolor="rgba(57,73,171,0.10)",
                hovertemplate="%{x}<br>Net equity %{y:.1f} points<extra></extra>",
            ),
            row=2,
            col=1,
        )
        table_values = [
            trades["trade_number"].tolist(),
            trades["signal_type"].tolist(),
            trades["entry_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["exit_time"].dt.strftime("%Y-%m-%d %H:%M").tolist(),
            trades["net_points"].map(lambda value: f"{value:.1f}").tolist(),
            trades["exit_reason"].tolist(),
        ]

    figure.add_trace(
        go.Table(
            header={
                "values": ["#", "Signal", "Entry", "Exit", "Net points", "Exit reason"],
                "fill_color": "#263238",
                "font": {"color": "white", "size": 12},
                "align": "left",
            },
            cells={
                "values": table_values,
                "fill_color": [["#f7f9fb", "#eef2f5"] * max(1, len(trades))] * 6,
                "align": "left",
                "height": 25,
            },
        ),
        row=3,
        col=1,
    )

    title = (
        f"TMF {args.contract_month} Pine Short-only Backtest | "
        f"Trades {metric('trades')} · Win rate {float(metric('win_rate')):.1f}% · "
        f"Net {float(metric('net_points')):,.1f} pts · PF {metric('profit_factor', 'n/a')}"
    )
    figure.update_layout(
        title={"text": title, "x": 0.5},
        template="plotly_white",
        height=1120,
        hovermode="x unified",
        legend={"orientation": "h", "y": 1.02, "x": 0},
        margin={"l": 65, "r": 35, "t": 105, "b": 35},
    )
    figure.update_xaxes(rangeslider_visible=False, row=1, col=1)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Net points", zeroline=True, row=2, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True, full_html=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest two Pine-style TMF short entries on 1-hour bars.")
    parser.add_argument("--input-dir", type=Path, default=DEFAULT_INPUT_DIR)
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START)
    parser.add_argument("--end-date", type=parse_date, default=DEFAULT_END)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--pivot-lookback", type=int, default=20)
    parser.add_argument("--volume-filter-length", type=int, default=2)
    parser.add_argument("--atr-length", type=int, default=200)
    parser.add_argument("--box-width", type=float, default=1.0)
    parser.add_argument("--stop-atr-buffer", type=float, default=0.10)
    parser.add_argument("--reward-risk", type=float, default=2.0)
    parser.add_argument("--round-trip-cost-points", type=float, default=0.0)
    parser.add_argument(
        "--hourly-output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_hourly_pine_short_bars_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--trades-output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_hourly_pine_short_trades_{DEFAULT_PERIOD}.csv",
    )
    parser.add_argument(
        "--report-output",
        type=Path,
        default=DEFAULT_DOC_DIR / f"tmf_202609_hourly_pine_short_backtest_{DEFAULT_PERIOD}.md",
    )
    parser.add_argument(
        "--html-output",
        type=Path,
        default=DEFAULT_OUTPUT_DIR / f"TMF_202609_hourly_pine_short_backtest_{DEFAULT_PERIOD}.html",
    )
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    if min(args.pivot_lookback, args.volume_filter_length, args.atr_length) < 1:
        parser.error("lookback and length parameters must be positive")
    if min(args.box_width, args.stop_atr_buffer, args.round_trip_cost_points) < 0 or args.reward_risk <= 0:
        parser.error("width/buffer/cost must be non-negative and reward-risk must be positive")
    return args


def main() -> None:
    args = parse_args()
    sources = discover_daily_sources(args.input_dir, args.start_date, args.end_date)
    if not sources:
        raise ValueError("No matching Daily_YYYY_MM_DD.csv or .zip files were found.")
    ticks = add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip()))
    hourly = build_hourly_bars(ticks)
    hourly = add_pine_diamond_signals(
        hourly,
        lookback=args.pivot_lookback,
        volume_length=args.volume_filter_length,
        atr_length=args.atr_length,
        box_width=args.box_width,
    )
    hourly = add_short_entry_signals(hourly)
    trades = backtest_short_only(
        hourly,
        stop_atr_buffer=args.stop_atr_buffer,
        reward_risk=args.reward_risk,
        round_trip_cost_points=args.round_trip_cost_points,
    )
    summary = performance_summary(trades)
    for output in (args.hourly_output, args.trades_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    hourly.to_csv(args.hourly_output, index=False, encoding="utf-8-sig")
    trades.to_csv(args.trades_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, args, len(sources), len(ticks), hourly, trades, summary)
    write_html_report(args.html_output, args, hourly, trades, summary)
    print(
        f"ticks={len(ticks)} hourly_bars={len(hourly)} signals={int(hourly['entry_signal'].sum())} "
        f"trades={summary['trades']} net_points={float(summary.get('net_points', 0)):.1f}"
    )
    print(f"report={args.report_output}")
    print(f"html={args.html_output}")


if __name__ == "__main__":
    main()
