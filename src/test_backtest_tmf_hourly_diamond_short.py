from __future__ import annotations

import numpy as np
import pandas as pd

from snr.src.backtest_tmf_hourly_diamond_short import (
    add_pine_diamond_signals,
    backtest_short_only,
    pine_rma,
)


def make_hourly(
    closes: list[float],
    opens: list[float],
    highs: list[float],
    lows: list[float],
    volumes: list[float] | None = None,
) -> pd.DataFrame:
    starts = pd.date_range("2026-09-01 08:45:00", periods=len(closes), freq="1h")
    return pd.DataFrame(
        {
            "timestamp": starts + pd.Timedelta(minutes=59),
            "hour_start": starts,
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": volumes or [100.0] * len(closes),
            "session_id": ["2026-09-01 day"] * len(closes),
        }
    )


def make_backtest_bars(rows: list[dict[str, object]]) -> pd.DataFrame:
    starts = pd.date_range("2026-09-01 08:45:00", periods=len(rows), freq="1h")
    defaults: dict[str, object] = {
        "open": 100.0,
        "high": 105.0,
        "low": 95.0,
        "close": 100.0,
        "atr": 10.0,
        "short_signal": False,
        "short_signal_type": None,
        "short_stop_anchor": np.nan,
        "short_structure_type": None,
        "short_structure_id": pd.NA,
        "green_exit_signal": False,
        "green_exit_signal_type": None,
        "session_id": "2026-09-01 day",
    }
    records = []
    for index, overrides in enumerate(rows):
        record = defaults | overrides
        record["hour_start"] = starts[index]
        record["timestamp"] = starts[index] + pd.Timedelta(minutes=59)
        records.append(record)
    return pd.DataFrame(records)


def test_pine_rma_uses_sma_seed() -> None:
    result = pine_rma(pd.Series([1.0, 2.0, 3.0, 4.0]), 3)

    assert result.iloc[:2].isna().all()
    assert result.iloc[2] == 2.0
    assert result.iloc[3] == 8.0 / 3.0


def test_delta_volume_carries_direction_across_doji_and_atr_warms_up() -> None:
    bars = make_hourly(
        closes=[11, 11, 10], opens=[10, 11, 11], highs=[12, 12, 12], lows=[9, 9, 9], volumes=[5, 7, 9]
    )
    result = add_pine_diamond_signals(bars, lookback=1, volume_length=1, atr_length=2, box_width=0)

    assert result["delta_volume"].tolist() == [5.0, 7.0, -9.0]
    assert pd.isna(result.iloc[0]["atr"])
    assert pd.notna(result.iloc[1]["atr"])


def test_resistance_holds_and_resistance_as_support_diamonds() -> None:
    bars = make_hourly(
        closes=[9, 12, 10, 9, 14, 12, 14],
        opens=[8, 11, 11, 10, 13, 11, 13],
        highs=[10, 13, 13, 11, 15, 13, 15],
        lows=[8, 10, 9, 8, 13, 11, 13],
    )
    result = add_pine_diamond_signals(bars, lookback=1, volume_length=1, atr_length=1, box_width=0)

    assert result.iloc[:2]["resistance_id"].isna().all()
    assert result.iloc[2]["resistance_id"] == 1
    assert bool(result.iloc[3]["resistance_holds"])
    assert bool(result.iloc[3]["short_signal"])
    assert result.iloc[3]["short_signal_type"] == "resistance_holds"
    assert bool(result.iloc[4]["breakout_resistance"])
    assert not bool(result.iloc[4]["resistance_as_support_holds"])
    assert bool(result.iloc[6]["resistance_as_support_holds"])
    assert bool(result.iloc[6]["green_exit_signal"])


def test_support_holds_and_support_as_resistance_diamonds() -> None:
    support_hold_bars = make_hourly(
        closes=[12, 9, 11, 12],
        opens=[11, 10, 10, 11],
        highs=[13, 10, 12, 13],
        lows=[11, 8, 8, 10],
    )
    support_hold = add_pine_diamond_signals(
        support_hold_bars, lookback=1, volume_length=1, atr_length=1, box_width=0
    )
    assert bool(support_hold.iloc[3]["support_holds"])
    assert bool(support_hold.iloc[3]["green_exit_signal"])

    role_change_bars = make_hourly(
        closes=[9, 12, 10, 9, 14, 12, 14, 10, 11, 9],
        opens=[8, 11, 11, 10, 13, 11, 13, 11, 12, 10],
        highs=[10, 13, 13, 11, 15, 13, 15, 11, 13, 11],
        lows=[8, 10, 9, 8, 13, 11, 13, 9, 10, 8],
    )
    role_change = add_pine_diamond_signals(
        role_change_bars, lookback=1, volume_length=1, atr_length=1, box_width=0
    )
    assert bool(role_change.iloc[7]["breakout_support"])
    assert not bool(role_change.iloc[7]["support_as_resistance_holds"])
    assert bool(role_change.iloc[9]["support_as_resistance_holds"])
    assert role_change.iloc[9]["short_signal_type"] == "support_as_resistance_holds"


def test_entry_next_open_and_green_exit_next_open_with_cost() -> None:
    bars = make_backtest_bars(
        [
            {
                "short_signal": True,
                "short_signal_type": "resistance_holds",
                "short_stop_anchor": 110.0,
                "short_structure_type": "resistance",
                "short_structure_id": 3,
            },
            {"open": 100.0, "high": 105.0, "low": 95.0, "green_exit_signal": True,
             "green_exit_signal_type": "support_holds"},
            {"open": 90.0, "high": 92.0, "low": 88.0, "session_id": "2026-09-02 night"},
        ]
    )
    trades = backtest_short_only(bars, stop_atr_buffer=0.1, round_trip_cost_points=2.0)

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_price"] == 100.0
    assert trade["stop_price"] == 111.0
    assert trade["exit_price"] == 90.0
    assert trade["exit_reason"] == "green_diamond"
    assert trade["gross_points"] == 10.0
    assert trade["net_points"] == 8.0
    assert bool(trade["cross_session"])


def test_intrabar_stop_precedes_green_signal() -> None:
    bars = make_backtest_bars(
        [
            {
                "short_signal": True,
                "short_signal_type": "resistance_holds",
                "short_stop_anchor": 110.0,
                "short_structure_type": "resistance",
                "short_structure_id": 1,
            },
            {"open": 100.0, "high": 112.0, "low": 95.0, "green_exit_signal": True,
             "green_exit_signal_type": "support_holds"},
            {"open": 90.0, "high": 92.0, "low": 88.0},
        ]
    )
    trades = backtest_short_only(bars, stop_atr_buffer=0.1)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_price"] == 111.0
    assert trades.iloc[0]["exit_reason"] == "intrabar_stop"
    assert trades.iloc[0]["mae_points"] == -11.0
    assert pd.isna(trades.iloc[0]["green_exit_signal_type"])


def test_gap_stop_has_priority_over_pending_green_exit() -> None:
    bars = make_backtest_bars(
        [
            {
                "short_signal": True,
                "short_signal_type": "resistance_holds",
                "short_stop_anchor": 110.0,
                "short_structure_type": "resistance",
                "short_structure_id": 1,
            },
            {"open": 100.0, "high": 105.0, "low": 95.0, "green_exit_signal": True,
             "green_exit_signal_type": "support_holds"},
            {"open": 115.0, "high": 118.0, "low": 112.0},
        ]
    )
    trades = backtest_short_only(bars, stop_atr_buffer=0.1)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_price"] == 115.0
    assert trades.iloc[0]["exit_reason"] == "stop_gap"
    assert pd.isna(trades.iloc[0]["green_exit_signal_type"])


def test_entry_is_cancelled_when_next_open_is_above_stop() -> None:
    bars = make_backtest_bars(
        [
            {
                "short_signal": True,
                "short_signal_type": "resistance_holds",
                "short_stop_anchor": 110.0,
                "short_structure_type": "resistance",
                "short_structure_id": 1,
            },
            {"open": 112.0, "high": 115.0, "low": 108.0},
        ]
    )

    assert backtest_short_only(bars, stop_atr_buffer=0.1).empty


def test_red_signal_during_an_open_trade_does_not_add_a_position() -> None:
    bars = make_backtest_bars(
        [
            {
                "short_signal": True,
                "short_signal_type": "resistance_holds",
                "short_stop_anchor": 110.0,
                "short_structure_type": "resistance",
                "short_structure_id": 1,
            },
            {
                "open": 100.0,
                "short_signal": True,
                "short_signal_type": "resistance_holds",
                "short_stop_anchor": 109.0,
                "short_structure_type": "resistance",
                "short_structure_id": 2,
            },
            {"green_exit_signal": True, "green_exit_signal_type": "support_holds"},
            {"open": 90.0, "high": 92.0, "low": 88.0},
        ]
    )
    trades = backtest_short_only(bars, stop_atr_buffer=0.1)

    assert len(trades) == 1
    assert trades.iloc[0]["structure_id"] == 1
    assert trades.iloc[0]["exit_reason"] == "green_diamond"


def test_open_position_is_settled_at_data_end() -> None:
    bars = make_backtest_bars(
        [
            {
                "short_signal": True,
                "short_signal_type": "resistance_holds",
                "short_stop_anchor": 110.0,
                "short_structure_type": "resistance",
                "short_structure_id": 1,
            },
            {"open": 100.0, "high": 105.0, "low": 90.0, "close": 92.0},
        ]
    )
    trades = backtest_short_only(bars, stop_atr_buffer=0.1)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "data_end"
    assert trades.iloc[0]["gross_points"] == 8.0
