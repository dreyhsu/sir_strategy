from __future__ import annotations

import pandas as pd
import pytest

from backtest_tmf_adaptive_hourly_resistance_short_ab import build_session_volume_bars
from backtest_tmf_tick_two_position_legacy_exit import (
    add_optimized_layer_signals,
    backtest_two_position_short,
    prepare_ticks,
)


def make_ticks(prices, sessions=None, start="2026-09-09 09:00:00") -> pd.DataFrame:
    timestamps = pd.date_range(start, periods=len(prices), freq="s")
    if sessions is None:
        sessions = ["2026-09-09_day"] * len(prices)
    return pd.DataFrame(
        {
            "tick_id": range(len(prices)),
            "timestamp": timestamps,
            "price": prices,
            "quantity": [1.0] * len(prices),
            "session_id": sessions,
            "session_type": [value.rsplit("_", 1)[-1] for value in sessions],
            "session_date": [pd.Timestamp(value[:10]).date() for value in sessions],
        }
    )


def make_signals(ticks: pd.DataFrame, tick_ids) -> pd.DataFrame:
    records = []
    for resistance_id, tick_id in enumerate(tick_ids, start=1):
        tick = ticks.iloc[tick_id]
        records.append(
            {
                "tick_end_id": tick_id,
                "timestamp": tick["timestamp"],
                "session_id": tick["session_id"],
                "resistance_reversal": True,
                "entry_layer": "early" if resistance_id == 1 else "balanced",
                "open": 101.0,
                "high": 102.0,
                "low": 99.0,
                "close": 100.0,
                "volume": 2_000.0,
                "close_position": 1.0 / 3.0,
                "resistance_id": resistance_id,
                "resistance_bottom": 99.0,
                "resistance_top": 101.0,
            }
        )
    return pd.DataFrame(records)


def test_same_second_source_order_and_session_volume_reset() -> None:
    timestamp = pd.Timestamp("2026-09-09 09:00:00")
    raw = pd.DataFrame(
        {
            "timestamp": [timestamp, timestamp, timestamp + pd.Timedelta(hours=6)],
            "source_file": ["b.csv", "a.csv", "a.csv"],
            "source_sequence": [2, 1, 0],
            "price": [102.0, 101.0, 103.0],
            "quantity": [1_200.0, 1_000.0, 1_500.0],
            "session_id": ["2026-09-09_day", "2026-09-09_day", "2026-09-09_night"],
            "session_type": ["day", "day", "night"],
            "session_date": [pd.Timestamp("2026-09-09").date()] * 3,
        }
    )
    ticks = prepare_ticks(raw)
    assert ticks["price"].tolist() == [101.0, 102.0, 103.0]
    bars = build_session_volume_bars(ticks, 2_000)
    assert len(bars) == 1
    assert bars.iloc[0]["session_id"] == "2026-09-09_day"
    assert bars.iloc[0]["volume"] == pytest.approx(2_200.0)


def test_sep9_style_layer_sequence_starts_after_hourly_touch_confirmation() -> None:
    session_id = "2026-09-09_day"
    bars = pd.DataFrame(
        {
            "tick_end_id": range(4),
            "timestamp": pd.to_datetime(
                ["2026-09-09 09:34:22", "2026-09-09 09:51:12", "2026-09-09 10:49:45", "2026-09-09 10:55:28"]
            ),
            "open": [47496.0, 47546.0, 47565.0, 47514.0],
            "high": [47504.0, 47550.0, 47586.0, 47517.0],
            "low": [47469.0, 47495.0, 47534.0, 47463.0],
            "close": [47477.0, 47497.0, 47535.0, 47475.0],
            "volume": [2000.0] * 4,
            "session_id": [session_id] * 4,
        }
    )
    hourly = pd.DataFrame(
        {
            "timestamp": pd.to_datetime(["2026-09-09 09:44:59", "2026-09-09 10:44:59"]),
            "high": [47504.0, 47590.0],
            "low": [47058.0, 47387.0],
            "session_id": [session_id, session_id],
        }
    )
    zones = pd.DataFrame(
        {
            "zone_id": [7],
            "zone_type": ["resistance"],
            "created_time": [pd.Timestamp("2026-09-08 11:44:59")],
            "broken_time": [pd.NaT],
            "bottom": [47500.0],
            "top": [47691.5],
        }
    )
    result = add_optimized_layer_signals(bars, hourly, zones, 0.35)
    signals = result[result["resistance_reversal"]]
    assert signals["timestamp"].tolist() == list(pd.to_datetime(
        ["2026-09-09 09:51:12", "2026-09-09 10:49:45", "2026-09-09 10:55:28"]
    ))
    assert signals["entry_layer"].tolist() == ["early", "balanced", "conservative"]


def test_two_entries_ignore_third_and_exit_as_one_group() -> None:
    ticks = make_ticks([100.0, 100.0, 100.0, 100.0, 110.0, 90.0, 90.0])
    signals = make_signals(ticks, [0, 2, 4])
    hourly = pd.DataFrame(
        {
            "timestamp": [ticks.iloc[0]["timestamp"] - pd.Timedelta(seconds=1), ticks.iloc[4]["timestamp"]],
            "supertrend_direction": [-1, 1],
        }
    )
    contracts, groups, _, summary = backtest_two_position_short(ticks, signals, hourly)

    assert contracts["slot"].tolist() == [1, 2]
    assert contracts["entry_time"].tolist() == [ticks.iloc[1]["timestamp"], ticks.iloc[3]["timestamp"]]
    assert contracts["entry_fill_price"].tolist() == [98.0, 98.0]
    assert contracts["exit_time"].nunique() == 1
    assert contracts.iloc[0]["exit_time"] == ticks.iloc[5]["timestamp"]
    assert contracts["exit_fill_price"].tolist() == [92.0, 92.0]
    assert contracts["net_ntd"].tolist() == [60.0, 60.0]
    assert groups.iloc[0]["contract_count"] == 2
    assert groups.iloc[0]["net_ntd"] == pytest.approx(120.0)
    assert summary["ignored_at_capacity"] == 1
    assert summary["peak_positions"] == 2
    assert summary["minimum_equity_ntd"] == pytest.approx(399_760.0)
    assert summary["maximum_drawdown_ntd"] == pytest.approx(240.0)
    assert summary["final_equity_ntd"] == pytest.approx(400_120.0)


def test_exit_has_priority_over_signal_on_same_tick() -> None:
    ticks = make_ticks([100.0, 100.0, 95.0, 94.0])
    signals = make_signals(ticks, [0, 2])
    hourly = pd.DataFrame(
        {
            "timestamp": [ticks.iloc[0]["timestamp"] - pd.Timedelta(seconds=1), ticks.iloc[1]["timestamp"]],
            "supertrend_direction": [-1, 1],
        }
    )
    contracts, groups, _, summary = backtest_two_position_short(ticks, signals, hourly)
    assert len(contracts) == 1
    assert len(groups) == 1
    assert contracts.iloc[0]["exit_time"] == ticks.iloc[2]["timestamp"]
    assert contracts.iloc[0]["exit_reason"] == "adaptive_hourly_supertrend_bullish_flip"
    assert summary["filled_entries"] == 1


def test_pending_entry_is_canceled_at_session_boundary() -> None:
    sessions = ["2026-09-09_day", "2026-09-09_night"]
    ticks = make_ticks([100.0, 99.0], sessions=sessions)
    contracts, groups, _, summary = backtest_two_position_short(
        ticks, make_signals(ticks, [0]), pd.DataFrame(columns=["timestamp", "supertrend_direction"])
    )
    assert contracts.empty
    assert groups.empty
    assert summary["filled_entries"] == 0
    assert summary["canceled_session"] == 1


def test_data_end_exit_slippage_and_tick_mtm() -> None:
    ticks = make_ticks([100.0, 100.0, 90.0])
    contracts, groups, samples, summary = backtest_two_position_short(
        ticks, make_signals(ticks, [0]), pd.DataFrame(columns=["timestamp", "supertrend_direction"]),
    )
    trade = contracts.iloc[0]
    assert trade["raw_entry_price"] == 100.0
    assert trade["entry_fill_price"] == 98.0
    assert trade["raw_exit_price"] == 90.0
    assert trade["exit_fill_price"] == 92.0
    assert trade["gross_points"] == 10.0
    assert trade["net_points"] == 6.0
    assert trade["net_ntd"] == 60.0
    assert trade["mfe_points"] == 8.0
    assert trade["mae_points"] == -2.0
    assert trade["exit_reason"] == "data_end"
    assert groups.iloc[0]["net_ntd"] == 60.0
    assert samples.iloc[-1]["equity_ntd"] == 400_060.0
    assert summary["final_equity_ntd"] == 400_060.0
