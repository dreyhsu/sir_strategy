from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest_tmf_hourly_pine_short import add_short_entry_signals, backtest_short_only


def make_bars(rows: list[dict[str, object]]) -> pd.DataFrame:
    starts = pd.date_range("2026-09-01 08:45:00", periods=len(rows), freq="1h")
    defaults: dict[str, object] = {
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 100.0,
        "atr": 10.0,
        "entry_signal": False,
        "entry_signal_type": None,
        "entry_stop_anchor": np.nan,
        "entry_structure_type": None,
        "entry_structure_id": pd.NA,
        "session_id": "2026-09-01 day",
    }
    records = []
    for index, values in enumerate(rows):
        record = defaults | values
        record["hour_start"] = starts[index]
        record["timestamp"] = starts[index] + pd.Timedelta(minutes=59)
        records.append(record)
    return pd.DataFrame(records)


def test_selects_resistance_hold_and_support_break_entries() -> None:
    bars = pd.DataFrame(
        {
            "resistance_holds": [True, False],
            "breakout_support": [False, True],
            "resistance_id": pd.array([1, pd.NA], dtype="Int64"),
            "support_id": pd.array([pd.NA, 2], dtype="Int64"),
            "resistance_top": [110.0, np.nan],
            "support_top": [np.nan, 98.0],
        }
    )

    result = add_short_entry_signals(bars)

    assert result["entry_signal"].tolist() == [True, True]
    assert result["entry_signal_type"].tolist() == ["resistance_holds", "breakout_support"]
    assert result["entry_stop_anchor"].tolist() == [110.0, 98.0]


def test_next_open_entry_and_two_r_target() -> None:
    bars = make_bars(
        [
            {
                "entry_signal": True,
                "entry_signal_type": "resistance_holds",
                "entry_stop_anchor": 110.0,
                "entry_structure_type": "resistance",
                "entry_structure_id": 1,
            },
            {"open": 100.0, "high": 105.0, "low": 75.0},
        ]
    )

    trades = backtest_short_only(bars, stop_atr_buffer=0.1, reward_risk=2.0, round_trip_cost_points=2.0)

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_price"] == 100.0
    assert trade["stop_price"] == 111.0
    assert trade["target_price"] == 78.0
    assert trade["exit_price"] == 78.0
    assert trade["gross_points"] == 22.0
    assert trade["net_points"] == 20.0
    assert trade["exit_reason"] == "profit_target"


def test_stop_wins_when_hourly_bar_touches_stop_and_target() -> None:
    bars = make_bars(
        [
            {
                "entry_signal": True,
                "entry_signal_type": "breakout_support",
                "entry_stop_anchor": 105.0,
                "entry_structure_type": "support",
                "entry_structure_id": 2,
            },
            {"open": 100.0, "high": 107.0, "low": 85.0},
        ]
    )

    trades = backtest_short_only(bars, stop_atr_buffer=0.0, reward_risk=2.0)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_price"] == 105.0
    assert trades.iloc[0]["exit_reason"] == "intrabar_stop"


def test_entry_is_cancelled_when_next_open_is_above_stop() -> None:
    bars = make_bars(
        [
            {
                "entry_signal": True,
                "entry_signal_type": "breakout_support",
                "entry_stop_anchor": 101.0,
                "entry_structure_type": "support",
                "entry_structure_id": 2,
            },
            {"open": 102.0, "high": 104.0, "low": 95.0},
        ]
    )

    assert backtest_short_only(bars, stop_atr_buffer=0.0).empty
