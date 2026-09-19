#!/usr/bin/env python
"""Tick-ordered TMF short backtest with two entries and a shared legacy exit."""

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
    from .backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from .backtest_tmf_adaptive_hourly_resistance_short_ab import build_session_volume_bars
    from .backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from .backtest_tmf_hourly_resistance_short import assign_resistance_entries
    from .backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones, zone_active
except ImportError:
    from backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend
    from backtest_tmf_adaptive_hourly_resistance_short_ab import build_session_volume_bars
    from backtest_tmf_dense_long import add_sessions, discover_daily_sources, load_daily_ticks, parse_date
    from backtest_tmf_hourly_resistance_short import assign_resistance_entries
    from backtest_tmf_hourly_support_long import build_hourly_bars, pine_style_zones, zone_active


ROOT = Path(__file__).resolve().parents[1]
DATA_DIR = ROOT / "data"
OUTPUT_DIR = ROOT / "txf_tick"
DOC_DIR = ROOT / "doc"
DEFAULT_START = date(2026, 8, 5)
DEFAULT_END = date(2026, 9, 15)
OUTPUT_PERIOD = "2026-08-05_to_2026-09-15"
DEFAULT_CONTRACT_TRADES = OUTPUT_DIR / f"TMF_202609_tick_two_position_contracts_{OUTPUT_PERIOD}.csv"
DEFAULT_GROUP_TRADES = OUTPUT_DIR / f"TMF_202609_tick_two_position_groups_{OUTPUT_PERIOD}.csv"
DEFAULT_CHART = OUTPUT_DIR / f"TMF_202609_tick_two_position_legacy_exit_{OUTPUT_PERIOD}.html"
DEFAULT_REPORT = DOC_DIR / f"tmf_202609_tick_two_position_legacy_exit_{OUTPUT_PERIOD}.md"


@dataclass
class OpenLot:
    group_id: int
    slot: int
    signal_time: pd.Timestamp
    entry_time: pd.Timestamp
    entry_session: str
    raw_entry_price: float
    entry_fill_price: float
    entry_layer: str
    signal_tick_end_id: int
    signal_open: float
    signal_high: float
    signal_low: float
    signal_close: float
    signal_volume: float
    signal_close_position: float
    resistance_id: int
    resistance_bottom: float
    resistance_top: float
    lowest_price: float
    highest_price: float


CONTRACT_COLUMNS = [
    "trade_number", "group_id", "slot", "signal_time", "entry_time", "exit_time", "entry_session",
    "exit_session", "raw_entry_price", "entry_fill_price", "raw_exit_price", "exit_fill_price",
    "entry_layer", "signal_tick_end_id", "signal_open", "signal_high", "signal_low", "signal_close", "signal_volume",
    "signal_close_position", "resistance_id", "resistance_bottom", "resistance_top", "gross_points", "net_points", "gross_ntd",
    "net_ntd", "mfe_points", "mae_points", "holding_hours", "exit_reason", "cross_session",
    "cumulative_net_ntd",
]

GROUP_COLUMNS = [
    "group_id", "contract_count", "first_entry_time", "last_entry_time", "exit_time", "entry_session",
    "exit_session", "average_raw_entry_price", "average_entry_fill_price", "raw_exit_price", "exit_fill_price",
    "resistance_ids", "gross_contract_points", "net_contract_points", "gross_ntd", "net_ntd",
    "holding_hours", "exit_reason", "cross_session", "cumulative_net_ntd",
]


def prepare_ticks(ticks: pd.DataFrame) -> pd.DataFrame:
    """Assign a stable event id after filtering ticks into valid trading sessions."""
    ordering = [column for column in ("timestamp", "source_file", "source_sequence") if column in ticks.columns]
    result = ticks.sort_values(ordering, kind="stable").reset_index(drop=True)
    result["tick_id"] = np.arange(len(result), dtype=np.int64)
    return result


def add_optimized_layer_signals(
    bars: pd.DataFrame,
    hourly: pd.DataFrame,
    zones: pd.DataFrame,
    close_position_max: float,
) -> pd.DataFrame:
    """Create causal Early, Balanced, and Conservative resistance entries.

    A completed hourly bar first arms a touched resistance. Early is the first
    bearish bottom-close volume bar after that confirmation. Balanced requires
    a later completed hour to set a higher test high and then a lower-high
    bearish volume bar. Conservative is the next bearish bottom-close bar that
    closes below the resistance floor.
    """
    result = bars.copy()
    price_range = (result["high"] - result["low"]).replace(0, np.nan)
    result["close_position"] = (result["close"] - result["low"]) / price_range
    result["bearish_rejection"] = (
        (result["close"] < result["open"])
        & (result["close_position"] <= close_position_max)
    )
    result = assign_resistance_entries(result, zones)
    result["entry_layer"] = pd.NA
    result["resistance_reversal"] = False
    resistances = zones[zones["zone_type"] == "resistance"] if not zones.empty else zones

    for session_id, session_bars in result.groupby("session_id", sort=False):
        session_hourly = hourly[hourly["session_id"] == session_id].sort_values("timestamp", kind="stable")
        hourly_rows = list(session_hourly.itertuples(index=False))
        hourly_index = -1
        setup: dict[str, object] | None = None

        for index, bar in session_bars.sort_values("tick_end_id", kind="stable").iterrows():
            while hourly_index + 1 < len(hourly_rows) and hourly_rows[hourly_index + 1].timestamp < bar["timestamp"]:
                hourly_index += 1
                hour = hourly_rows[hourly_index]
                candidates = resistances[
                    resistances.apply(lambda zone: zone_active(zone, hour.timestamp), axis=1)
                    & (resistances["bottom"] <= float(hour.high))
                    & (resistances["top"] >= float(hour.low))
                ]
                if candidates.empty:
                    continue
                selected = candidates.sort_values("bottom").iloc[0]
                resistance_id = int(selected["zone_id"])
                if setup is None or int(setup["resistance_id"]) != resistance_id:
                    setup = {
                        "resistance_id": resistance_id,
                        "peak_high": float(hour.high),
                        "stage": 0,
                        "balanced_armed": False,
                    }
                else:
                    previous_peak = float(setup["peak_high"])
                    if int(setup["stage"]) >= 1 and float(hour.high) > previous_peak:
                        setup["balanced_armed"] = True
                    setup["peak_high"] = max(previous_peak, float(hour.high))

            if setup is None or pd.isna(bar["resistance_id"]):
                continue
            if int(bar["resistance_id"]) != int(setup["resistance_id"]):
                continue

            stage = int(setup["stage"])
            layer: str | None = None
            if stage == 0:
                layer = "early"
                setup["stage"] = 1
            elif stage == 1 and bool(setup["balanced_armed"]) and float(bar["high"]) < float(setup["peak_high"]):
                layer = "balanced"
                setup["stage"] = 2
            elif stage == 2 and float(bar["close"]) < float(bar["resistance_bottom"]):
                layer = "conservative"
                setup["stage"] = 3

            if layer is not None:
                result.at[index, "entry_layer"] = layer
                result.at[index, "resistance_reversal"] = True

    return result


def _close_group(
    positions: list[OpenLot],
    tick: object,
    reason: str,
    slippage_points: float,
    point_value_ntd: float,
) -> tuple[list[dict[str, object]], dict[str, object], float]:
    raw_exit = float(tick.price)
    exit_fill = raw_exit + slippage_points
    contract_records: list[dict[str, object]] = []
    for lot in positions:
        lot.lowest_price = min(lot.lowest_price, raw_exit)
        lot.highest_price = max(lot.highest_price, raw_exit)
        gross_points = lot.raw_entry_price - raw_exit
        net_points = lot.entry_fill_price - exit_fill
        contract_records.append(
            {
                "group_id": lot.group_id,
                "slot": lot.slot,
                "signal_time": lot.signal_time,
                "entry_time": lot.entry_time,
                "exit_time": tick.timestamp,
                "entry_session": lot.entry_session,
                "exit_session": tick.session_id,
                "raw_entry_price": lot.raw_entry_price,
                "entry_fill_price": lot.entry_fill_price,
                "raw_exit_price": raw_exit,
                "exit_fill_price": exit_fill,
                "entry_layer": lot.entry_layer,
                "signal_tick_end_id": lot.signal_tick_end_id,
                "signal_open": lot.signal_open,
                "signal_high": lot.signal_high,
                "signal_low": lot.signal_low,
                "signal_close": lot.signal_close,
                "signal_volume": lot.signal_volume,
                "signal_close_position": lot.signal_close_position,
                "resistance_id": lot.resistance_id,
                "resistance_bottom": lot.resistance_bottom,
                "resistance_top": lot.resistance_top,
                "gross_points": gross_points,
                "net_points": net_points,
                "gross_ntd": gross_points * point_value_ntd,
                "net_ntd": net_points * point_value_ntd,
                "mfe_points": lot.entry_fill_price - lot.lowest_price,
                "mae_points": lot.entry_fill_price - lot.highest_price,
                "holding_hours": (tick.timestamp - lot.entry_time).total_seconds() / 3600,
                "exit_reason": reason,
                "cross_session": lot.entry_session != tick.session_id,
            }
        )

    first = min(positions, key=lambda lot: lot.entry_time)
    group_net_ntd = float(sum(record["net_ntd"] for record in contract_records))
    group_record = {
        "group_id": first.group_id,
        "contract_count": len(positions),
        "first_entry_time": min(lot.entry_time for lot in positions),
        "last_entry_time": max(lot.entry_time for lot in positions),
        "exit_time": tick.timestamp,
        "entry_session": first.entry_session,
        "exit_session": tick.session_id,
        "average_raw_entry_price": float(np.mean([lot.raw_entry_price for lot in positions])),
        "average_entry_fill_price": float(np.mean([lot.entry_fill_price for lot in positions])),
        "raw_exit_price": raw_exit,
        "exit_fill_price": exit_fill,
        "resistance_ids": ",".join(str(lot.resistance_id) for lot in positions),
        "gross_contract_points": float(sum(record["gross_points"] for record in contract_records)),
        "net_contract_points": float(sum(record["net_points"] for record in contract_records)),
        "gross_ntd": float(sum(record["gross_ntd"] for record in contract_records)),
        "net_ntd": group_net_ntd,
        "holding_hours": (tick.timestamp - first.entry_time).total_seconds() / 3600,
        "exit_reason": reason,
        "cross_session": first.entry_session != tick.session_id,
    }
    return contract_records, group_record, group_net_ntd


def backtest_two_position_short(
    ticks: pd.DataFrame,
    signal_bars: pd.DataFrame,
    hourly: pd.DataFrame,
    initial_capital_ntd: float = 400_000.0,
    max_positions: int = 2,
    point_value_ntd: float = 10.0,
    slippage_points: float = 2.0,
    chart_sample_minutes: int = 5,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, dict[str, object]]:
    """Run tick fills, two-lot scaling, a shared Supertrend exit, and account MTM."""
    if initial_capital_ntd <= 0 or max_positions < 1 or point_value_ntd <= 0:
        raise ValueError("capital, max positions, and point value must be positive")
    if slippage_points < 0 or chart_sample_minutes < 1:
        raise ValueError("slippage must be non-negative and chart sampling must be positive")

    ordered_ticks = ticks.sort_values("tick_id", kind="stable").reset_index(drop=True)
    completed_bars = {int(row.tick_end_id): row for row in signal_bars.itertuples(index=False)}
    hourly_rows = list(
        hourly[["timestamp", "supertrend_direction"]]
        .sort_values("timestamp", kind="stable")
        .itertuples(index=False)
    )
    hourly_index = -1
    current_direction: int | None = None
    group_last_direction: int | None = None
    group_seen_bearish = False
    next_group_id = 0
    positions: list[OpenLot] = []
    pending_entry: object | None = None
    contract_records: list[dict[str, object]] = []
    group_records: list[dict[str, object]] = []
    equity_samples: list[dict[str, object]] = []
    realized_ntd = 0.0
    peak_equity = initial_capital_ntd
    minimum_equity = initial_capital_ntd
    maximum_drawdown = 0.0
    maximum_drawdown_percent = 0.0
    peak_positions = 0
    signals = filled_entries = ignored_at_capacity = canceled_session = 0
    previous_time: pd.Timestamp | None = None
    previous_exposure = 0
    exposure_seconds = {count: 0.0 for count in range(max_positions + 1)}
    sample_delta = pd.Timedelta(minutes=chart_sample_minutes)
    next_sample_time: pd.Timestamp | None = None
    last_tick: object | None = None

    for tick in ordered_ticks.itertuples(index=False):
        last_tick = tick
        if previous_time is not None:
            elapsed = max(0.0, (tick.timestamp - previous_time).total_seconds())
            exposure_seconds[previous_exposure] += elapsed
        previous_time = tick.timestamp

        bullish_flip = False
        while hourly_index + 1 < len(hourly_rows) and hourly_rows[hourly_index + 1].timestamp < tick.timestamp:
            hourly_index += 1
            direction_value = hourly_rows[hourly_index].supertrend_direction
            new_direction = None if pd.isna(direction_value) else int(direction_value)
            if positions and new_direction is not None:
                if new_direction == -1:
                    group_seen_bearish = True
                if group_seen_bearish and group_last_direction == -1 and new_direction == 1:
                    bullish_flip = True
                group_last_direction = new_direction
            current_direction = new_direction

        exited_this_tick = False
        if positions and bullish_flip:
            records, group_record, group_net = _close_group(
                positions, tick, "adaptive_hourly_supertrend_bullish_flip", slippage_points, point_value_ntd
            )
            contract_records.extend(records)
            group_records.append(group_record)
            realized_ntd += group_net
            positions = []
            pending_entry = None
            group_last_direction = None
            group_seen_bearish = False
            exited_this_tick = True

        if not exited_this_tick and pending_entry is not None:
            signal = pending_entry
            pending_entry = None
            if tick.session_id == signal.session_id and len(positions) < max_positions:
                if not positions:
                    next_group_id += 1
                    group_last_direction = current_direction
                    group_seen_bearish = current_direction == -1
                raw_entry = float(tick.price)
                positions.append(
                    OpenLot(
                        group_id=next_group_id,
                        slot=len(positions) + 1,
                        signal_time=signal.timestamp,
                        entry_time=tick.timestamp,
                        entry_session=tick.session_id,
                        raw_entry_price=raw_entry,
                        entry_fill_price=raw_entry - slippage_points,
                        entry_layer=str(getattr(signal, "entry_layer", "legacy")),
                        signal_tick_end_id=int(signal.tick_end_id),
                        signal_open=float(signal.open),
                        signal_high=float(signal.high),
                        signal_low=float(signal.low),
                        signal_close=float(signal.close),
                        signal_volume=float(signal.volume),
                        signal_close_position=float(signal.close_position),
                        resistance_id=int(signal.resistance_id),
                        resistance_bottom=float(signal.resistance_bottom),
                        resistance_top=float(signal.resistance_top),
                        lowest_price=raw_entry,
                        highest_price=raw_entry,
                    )
                )
                filled_entries += 1
                peak_positions = max(peak_positions, len(positions))
            else:
                canceled_session += 1

        price = float(tick.price)
        for lot in positions:
            lot.lowest_price = min(lot.lowest_price, price)
            lot.highest_price = max(lot.highest_price, price)

        completed_bar = completed_bars.get(int(tick.tick_id))
        if completed_bar is not None and bool(completed_bar.resistance_reversal):
            signals += 1
            if exited_this_tick:
                pass
            elif len(positions) >= max_positions:
                ignored_at_capacity += 1
            elif pending_entry is None:
                pending_entry = completed_bar

        unrealized_ntd = sum((lot.entry_fill_price - price) * point_value_ntd for lot in positions)
        equity = initial_capital_ntd + realized_ntd + unrealized_ntd
        peak_equity = max(peak_equity, equity)
        minimum_equity = min(minimum_equity, equity)
        maximum_drawdown = min(maximum_drawdown, equity - peak_equity)
        maximum_drawdown_percent = max(
            maximum_drawdown_percent, (peak_equity - equity) / peak_equity * 100 if peak_equity else 0.0
        )

        force_sample = exited_this_tick or completed_bar is not None and bool(completed_bar.resistance_reversal)
        if next_sample_time is None or tick.timestamp >= next_sample_time or force_sample:
            equity_samples.append(
                {
                    "timestamp": tick.timestamp,
                    "price": price,
                    "equity_ntd": equity,
                    "realized_ntd": realized_ntd,
                    "unrealized_ntd": unrealized_ntd,
                    "open_positions": len(positions),
                    "drawdown_ntd": equity - peak_equity,
                }
            )
            next_sample_time = tick.timestamp.floor(f"{chart_sample_minutes}min") + sample_delta
        previous_exposure = len(positions)

    if positions and last_tick is not None:
        records, group_record, group_net = _close_group(
            positions, last_tick, "data_end", slippage_points, point_value_ntd
        )
        contract_records.extend(records)
        group_records.append(group_record)
        realized_ntd += group_net
        positions = []
        final_equity = initial_capital_ntd + realized_ntd
        peak_equity = max(peak_equity, final_equity)
        minimum_equity = min(minimum_equity, final_equity)
        maximum_drawdown = min(maximum_drawdown, final_equity - peak_equity)
        maximum_drawdown_percent = max(
            maximum_drawdown_percent,
            (peak_equity - final_equity) / peak_equity * 100 if peak_equity else 0.0,
        )
        equity_samples.append(
            {
                "timestamp": last_tick.timestamp,
                "price": float(last_tick.price),
                "equity_ntd": final_equity,
                "realized_ntd": realized_ntd,
                "unrealized_ntd": 0.0,
                "open_positions": 0,
                "drawdown_ntd": final_equity - peak_equity,
            }
        )

    contracts = pd.DataFrame(contract_records)
    if contracts.empty:
        contracts = pd.DataFrame(columns=CONTRACT_COLUMNS)
    else:
        contracts.insert(0, "trade_number", range(1, len(contracts) + 1))
        contracts["cumulative_net_ntd"] = contracts["net_ntd"].cumsum()
        contracts = contracts.reindex(columns=CONTRACT_COLUMNS)
    groups = pd.DataFrame(group_records)
    if groups.empty:
        groups = pd.DataFrame(columns=GROUP_COLUMNS)
    else:
        groups["cumulative_net_ntd"] = groups["net_ntd"].cumsum()
        groups = groups.reindex(columns=GROUP_COLUMNS)
    samples = pd.DataFrame(equity_samples).drop_duplicates(subset=["timestamp"], keep="last")

    final_equity = initial_capital_ntd + realized_ntd
    elapsed_seconds = sum(exposure_seconds.values())
    summary: dict[str, object] = {
        "signals": signals,
        "filled_entries": filled_entries,
        "ignored_at_capacity": ignored_at_capacity,
        "canceled_session": canceled_session,
        "contract_trades": len(contracts),
        "groups": len(groups),
        "winning_contracts": int((contracts["net_ntd"] > 0).sum()) if not contracts.empty else 0,
        "losing_contracts": int((contracts["net_ntd"] < 0).sum()) if not contracts.empty else 0,
        "winning_groups": int((groups["net_ntd"] > 0).sum()) if not groups.empty else 0,
        "losing_groups": int((groups["net_ntd"] < 0).sum()) if not groups.empty else 0,
        "gross_ntd": float(contracts["gross_ntd"].sum()) if not contracts.empty else 0.0,
        "net_ntd": realized_ntd,
        "contract_win_rate_percent": (
            float((contracts["net_ntd"] > 0).mean() * 100) if not contracts.empty else 0.0
        ),
        "group_win_rate_percent": float((groups["net_ntd"] > 0).mean() * 100) if not groups.empty else 0.0,
        "group_profit_factor": (
            float(groups.loc[groups["net_ntd"] > 0, "net_ntd"].sum())
            / abs(float(groups.loc[groups["net_ntd"] < 0, "net_ntd"].sum()))
            if not groups.empty and float(groups.loc[groups["net_ntd"] < 0, "net_ntd"].sum()) < 0
            else float("inf") if not groups.empty and bool((groups["net_ntd"] > 0).any()) else 0.0
        ),
        "initial_equity_ntd": initial_capital_ntd,
        "final_equity_ntd": final_equity,
        "return_percent": (final_equity / initial_capital_ntd - 1) * 100,
        "minimum_equity_ntd": minimum_equity,
        "maximum_drawdown_ntd": -maximum_drawdown,
        "maximum_drawdown_percent": maximum_drawdown_percent,
        "peak_positions": peak_positions,
        "exposure_hours": {count: seconds / 3600 for count, seconds in exposure_seconds.items()},
        "exposure_percent": {
            count: (seconds / elapsed_seconds * 100 if elapsed_seconds else 0.0)
            for count, seconds in exposure_seconds.items()
        },
    }
    return contracts, groups, samples, summary


def write_report(
    path: Path,
    args: argparse.Namespace,
    sources: list[Path],
    ticks: pd.DataFrame,
    hourly: pd.DataFrame,
    signal_bars: pd.DataFrame,
    contracts: pd.DataFrame,
    groups: pd.DataFrame,
    summary: dict[str, object],
) -> None:
    group_rows = "| - | - | - | - | - | - | No trade |"
    if not groups.empty:
        group_rows = "\n".join(
            f"| {row.group_id} | {row.contract_count} | {row.first_entry_time:%Y-%m-%d %H:%M:%S} | "
            f"{row.exit_time:%Y-%m-%d %H:%M:%S} | {row.average_entry_fill_price:.1f} | "
            f"{row.net_ntd:,.0f} | {row.exit_reason} |"
            for row in groups.itertuples(index=False)
        )
    exposure_hours = summary["exposure_hours"]
    exposure_percent = summary["exposure_percent"]
    profit_factor = summary["group_profit_factor"]
    profit_factor_text = "∞" if np.isinf(profit_factor) else f"{profit_factor:.2f}"
    text = f"""# {args.product} {args.contract_month}：Tick 兩口空單＋Legacy Supertrend 出場回測

## 資料與設定

- 日期：`{args.start_date}` 至 `{args.end_date}`；來源檔 {len(sources)} 個、有效 tick {len(ticks):,} 筆、60 分 K {len(hourly):,} 根。
- 起始權益：NT${args.initial_capital_ntd:,.0f}；TMF 每點 NT${args.point_value_ntd:g}；最多同時 {args.max_positions} 口。
- 進出場每邊使用 {args.slippage_points:g} 點不利滑價；未計手續費與期交稅；不模擬追繳或強制平倉。
- 2,000 口量 K 每個日／夜盤重新累積，時段尾端不足量直接丟棄。

## 交易規則

- 完整小時 K 確認碰到有效壓力後啟動分層進場；量 K 必須接觸該壓力、收黑，且收盤位置不高於 {args.close_position_max:.0%}。
- `Early` 是確認後第一個合格反轉；之後完整小時 K 若形成更高測試點，第一個 lower-high 合格反轉為 `Balanced`；再往後首次收回壓力下緣為 `Conservative`。
- 訊號後同一交易時段的下一筆 tick 放空一口；持有一口時，下個有效訊號再加一口，滿兩口後忽略其他訊號。
- 兩口視為同一組。自適應 60 分 Supertrend 曾呈空頭後翻多，於第一筆可用 tick 同時平倉。
- 不設初始停損、移動停利、保本、壓力失效、確認逾時或最大持倉時間；資料結束時以最後 tick 平倉。
- 60 分狀態只在其完成時間嚴格早於當前 tick 時使用，保留同秒成交的原始列順序。

## 帳戶結果

| Metric | Value |
| --- | ---: |
| Valid signals / filled entries | {summary['signals']} / {summary['filled_entries']} |
| Ignored at two-contract capacity | {summary['ignored_at_capacity']} |
| Contract trades / position groups | {summary['contract_trades']} / {summary['groups']} |
| Winning / losing contracts | {summary['winning_contracts']} / {summary['losing_contracts']} |
| Winning / losing groups | {summary['winning_groups']} / {summary['losing_groups']} |
| Contract / group win rate | {summary['contract_win_rate_percent']:.1f}% / {summary['group_win_rate_percent']:.1f}% |
| Group profit factor | {profit_factor_text} |
| Gross P&L | NT${summary['gross_ntd']:,.0f} |
| Net P&L after slippage | NT${summary['net_ntd']:,.0f} |
| Final equity | NT${summary['final_equity_ntd']:,.0f} |
| Return | {summary['return_percent']:.2f}% |
| Minimum tick-level equity | NT${summary['minimum_equity_ntd']:,.0f} |
| Maximum tick-level drawdown | NT${summary['maximum_drawdown_ntd']:,.0f} ({summary['maximum_drawdown_percent']:.2f}%) |
| Peak open contracts | {summary['peak_positions']} |
| Flat exposure | {exposure_hours.get(0, 0):.1f} h ({exposure_percent.get(0, 0):.1f}%) |
| One-contract exposure | {exposure_hours.get(1, 0):.1f} h ({exposure_percent.get(1, 0):.1f}%) |
| Two-contract exposure | {exposure_hours.get(2, 0):.1f} h ({exposure_percent.get(2, 0):.1f}%) |

## Group Ledger

| Group | Lots | First entry | Exit | Average fill | Net NTD | Exit reason |
|---:|---:|---|---|---:|---:|---|
{group_rows}

## 風險說明

本版本依選定的 Legacy 行為，不會在獲利時移動停損，也沒有虧損上限。NT$400,000 僅作為權益基準；回測不會因權益或保證金不足自動平倉。
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def write_chart(
    path: Path,
    zones: pd.DataFrame,
    contracts: pd.DataFrame,
    samples: pd.DataFrame,
    initial_capital_ntd: float,
) -> None:
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.035,
        row_heights=[0.62, 0.16, 0.22],
        subplot_titles=("Sampled tick price and entries", "Open TMF contracts", "Marked-to-market account equity"),
    )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["price"], mode="lines", name="Tick price (sampled)"), row=1, col=1
    )
    chart_end = samples["timestamp"].iloc[-1]
    if not zones.empty:
        for zone in zones[zones["zone_type"] == "resistance"].itertuples(index=False):
            end = zone.broken_time if pd.notna(zone.broken_time) else chart_end
            figure.add_shape(
                type="rect", x0=zone.created_time, x1=end, y0=zone.bottom, y1=zone.top,
                fillcolor="rgba(211,47,47,0.12)", line={"color": "rgba(211,47,47,0.55)", "width": 1}, row=1, col=1,
            )
    if not contracts.empty:
        common_exits = contracts.drop_duplicates(subset=["group_id"], keep="last")
        figure.add_trace(
            go.Scatter(
                x=contracts["entry_time"], y=contracts["entry_fill_price"], mode="markers", name="Short entry",
                marker={"symbol": "triangle-down", "size": 12, "color": "#6a1b9a"},
                text=[f"Group {g}, slot {s}" for g, s in zip(contracts["group_id"], contracts["slot"])],
            ), row=1, col=1,
        )
        figure.add_trace(
            go.Scatter(
                x=common_exits["exit_time"], y=common_exits["exit_fill_price"], mode="markers", name="Shared exit",
                marker={"symbol": "x", "size": 10, "color": "#00897b"}, text=common_exits["exit_reason"],
            ), row=1, col=1,
        )
    figure.add_trace(
        go.Scatter(
            x=samples["timestamp"], y=samples["open_positions"], mode="lines", line_shape="hv", name="Open contracts"
        ), row=2, col=1,
    )
    figure.add_trace(
        go.Scatter(x=samples["timestamp"], y=samples["equity_ntd"], mode="lines", name="Account equity"), row=3, col=1
    )
    figure.add_hline(y=initial_capital_ntd, line_dash="dot", line_color="gray", row=3, col=1)
    figure.update_layout(title="TMF Tick-Level Two-Position Short Backtest", xaxis_rangeslider_visible=False)
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Contracts", dtick=1, row=2, col=1)
    figure.update_yaxes(title_text="NTD", tickformat=",.0f", row=3, col=1)
    path.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(path, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Backtest two TMF tick entries with a shared legacy Supertrend exit.")
    parser.add_argument("--input-dir", type=Path, default=DATA_DIR)
    parser.add_argument("--start-date", type=parse_date, default=DEFAULT_START)
    parser.add_argument("--end-date", type=parse_date, default=DEFAULT_END)
    parser.add_argument("--product", default="TMF")
    parser.add_argument("--contract-month", default="202609")
    parser.add_argument("--initial-capital-ntd", type=float, default=400_000)
    parser.add_argument("--max-positions", type=int, default=2)
    parser.add_argument("--point-value-ntd", type=float, default=10)
    parser.add_argument("--slippage-points", type=float, default=2)
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
    parser.add_argument("--chart-sample-minutes", type=int, default=5)
    parser.add_argument("--contract-trades-output", type=Path, default=DEFAULT_CONTRACT_TRADES)
    parser.add_argument("--group-trades-output", type=Path, default=DEFAULT_GROUP_TRADES)
    parser.add_argument("--chart-output", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--report-output", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    if args.end_date < args.start_date:
        parser.error("--end-date must be on or after --start-date")
    positive = (
        args.initial_capital_ntd, args.max_positions, args.point_value_ntd, args.volume_bar_size,
        args.tick_lookback, args.pivot_lookback, args.volume_filter_length, args.zone_atr_length,
        args.atr_length, args.speed_lookback, args.smoothing_span, args.chart_sample_minutes,
    )
    if min(positive) <= 0:
        parser.error("capital, position count, bar sizes, and lookbacks must be positive")
    if args.slippage_points < 0 or args.zone_box_width < 0:
        parser.error("slippage and zone width must be non-negative")
    if not 0 < args.close_position_max <= 1:
        parser.error("--close-position-max must be in (0, 1]")
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
    ticks = prepare_ticks(add_sessions(load_daily_ticks(sources, args.product.strip(), args.contract_month.strip())))
    hourly = build_hourly_bars(ticks)
    hourly = add_adaptive_supertrend(
        hourly, args.atr_length, args.base_multiplier, args.min_multiplier, args.speed_lookback,
        args.low_speed, args.high_speed, args.smoothing_span,
    )
    zones = pine_style_zones(
        hourly, args.pivot_lookback, args.volume_filter_length, args.zone_atr_length, args.zone_box_width
    )
    signal_bars = build_session_volume_bars(ticks, args.volume_bar_size)
    signal_bars = add_optimized_layer_signals(signal_bars, hourly, zones, args.close_position_max)
    contracts, groups, samples, summary = backtest_two_position_short(
        ticks, signal_bars, hourly, args.initial_capital_ntd, args.max_positions, args.point_value_ntd,
        args.slippage_points, args.chart_sample_minutes,
    )
    for output in (args.contract_trades_output, args.group_trades_output):
        output.parent.mkdir(parents=True, exist_ok=True)
    contracts.to_csv(args.contract_trades_output, index=False, encoding="utf-8-sig")
    groups.to_csv(args.group_trades_output, index=False, encoding="utf-8-sig")
    write_report(args.report_output, args, sources, ticks, hourly, signal_bars, contracts, groups, summary)
    write_chart(args.chart_output, zones, contracts, samples, args.initial_capital_ntd)
    print(
        f"ticks={len(ticks)} hourly_bars={len(hourly)} volume_bars={len(signal_bars)} "
        f"signals={summary['signals']} filled_entries={summary['filled_entries']}"
    )
    print(
        f"contracts={summary['contract_trades']} groups={summary['groups']} "
        f"net_ntd={summary['net_ntd']:.0f} final_equity_ntd={summary['final_equity_ntd']:.0f}"
    )
    print(f"report={args.report_output}")


if __name__ == "__main__":
    main()
