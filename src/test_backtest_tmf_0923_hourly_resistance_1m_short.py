from __future__ import annotations

import numpy as np
import pandas as pd

from src.backtest_tmf_0923_hourly_resistance_1m_short import (
    add_adjust_supertrend,
    adjusted_resistance_top,
    backtest_strategy,
)


def make_minutes(rows: list[dict[str, object]]) -> pd.DataFrame:
    starts = pd.date_range("2026-09-23 09:00:00", periods=len(rows), freq="1min")
    defaults: dict[str, object] = {
        "open": 99.0, "high": 100.0, "low": 98.0, "close": 99.0, "volume": 100,
        "session_id": "2026-09-23 day", "resistance_id": 1, "resistance_bottom": 100.0,
        "resistance_top": 110.0, "risk_atr": 10.0, "sma9": 95.0, "sma9_rising": True,
        "adjust_supertrend_direction": -1,
    }
    records = []
    for index, values in enumerate(rows):
        record = defaults | values
        record["minute_start"] = starts[index]
        record["timestamp"] = starts[index] + pd.Timedelta(seconds=59)
        records.append(record)
    return pd.DataFrame(records)


def test_dynamic_top_moves_halfway_to_breakout_peak() -> None:
    assert adjusted_resistance_top(110.0, 130.0, 0.5) == 120.0


def test_initial_entry_requires_rising_sma_and_entry_from_below() -> None:
    bars = make_minutes(
        [
            {"close": 99.0},
            {"open": 100.0, "close": 105.0, "high": 106.0},
            {"open": 104.0, "high": 106.0, "low": 90.0, "close": 91.0},
        ]
    )
    trades, state, _ = backtest_strategy(bars, slippage_per_side=0.0)

    assert bool(state.iloc[1]["entry_signal"])
    assert state.iloc[1]["entry_signal_type"] == "initial_entry"
    assert len(trades) == 1
    assert trades.iloc[0]["entry_time"] == bars.iloc[2]["minute_start"]


def test_reentry_requires_timely_return_and_raises_top_only_after_entry() -> None:
    bars = make_minutes(
        [
            {"close": 99.0},
            {"open": 100.0, "close": 105.0, "high": 106.0},
            {"open": 104.0, "high": 116.0, "low": 103.0, "close": 114.0},
            {"open": 113.0, "high": 120.0, "low": 109.0, "close": 109.0, "sma9_rising": False},
            {"open": 108.0, "high": 109.0, "low": 90.0, "close": 91.0, "sma9_rising": False},
        ]
    )
    trades, state, zones = backtest_strategy(bars, slippage_per_side=0.0, top_adjust_ratio=0.5)

    assert len(trades) == 2
    assert trades.iloc[0]["exit_reason"] == "initial_stop"
    assert not bool(state.iloc[3]["top_adjusted"])
    assert state.iloc[3]["dynamic_resistance_top"] == 110.0
    assert state.iloc[3]["entry_signal_type"] == "reentry_after_initial_stop"
    assert bool(state.iloc[4]["top_adjusted"])
    assert state.iloc[4]["dynamic_resistance_top"] == 115.0
    assert trades.iloc[1]["entry_type"] == "reentry_after_initial_stop"
    assert trades.iloc[1]["resistance_top"] == 115.0
    assert trades.iloc[1]["initial_stop"] == 120.0
    assert zones["zone_version"].max() == 2


def test_return_after_ten_minute_window_does_not_reenter_or_raise_top() -> None:
    rows = [
        {"close": 99.0},
        {"open": 100.0, "close": 105.0, "high": 106.0},
        {"open": 104.0, "high": 116.0, "low": 103.0, "close": 114.0},
    ]
    rows.extend(
        {"open": 114.0, "high": 114.0, "low": 111.0, "close": 113.0, "sma9_rising": False}
        for _ in range(10)
    )
    rows.extend(
        [
            {"open": 112.0, "high": 113.0, "low": 108.0, "close": 109.0, "sma9_rising": False},
            {"open": 108.0, "high": 109.0, "low": 90.0, "close": 91.0, "sma9_rising": False},
        ]
    )
    bars = make_minutes(rows)

    trades, state, zones = backtest_strategy(
        bars, slippage_per_side=0.0, top_adjust_ratio=0.5, reentry_timeout_minutes=10
    )

    assert len(trades) == 1
    assert not state["top_adjusted"].any()
    assert not (state["entry_signal_type"] == "reentry_after_initial_stop").any()
    assert state["dynamic_resistance_top"].dropna().eq(110.0).all()
    assert zones["zone_version"].max() == 1


def test_adjust_supertrend_uses_smoothed_absolute_price_speed() -> None:
    starts = pd.date_range("2026-09-01", periods=8, freq="1h")
    bars = pd.DataFrame(
        {
            "timestamp": starts, "hour_start": starts,
            "open": [100, 101, 102, 104, 108, 109, 107, 104],
            "high": [102, 103, 105, 109, 111, 110, 108, 105],
            "low": [99, 100, 101, 103, 107, 106, 103, 100],
            "close": [101, 102, 104, 108, 109, 107, 104, 101],
            "volume": [100] * 8, "session_id": ["s"] * 8,
        }
    )
    result = add_adjust_supertrend(
        bars, atr_length=2, speed_lookback=1, speed_smoothing=1,
        low_speed=0.0, high_speed=1.0,
    )

    expected = (result["close"] - result["close"].shift(1)).abs() / result["adjust_atr"]
    assert np.allclose(result["raw_price_speed"].dropna(), expected.dropna())
    assert np.allclose(result["price_speed"].dropna(), expected.dropna())
    assert "raw_acceleration" not in result.columns
    assert result["adjust_multiplier"].between(0.8, 3.0).all()
