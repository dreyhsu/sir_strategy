from __future__ import annotations

import pandas as pd

from snr.src.backtest_tmf_adaptive_hourly_resistance_short_ab import (
    backtest_strategy_b,
    build_session_volume_bars,
    performance_summary,
)


def make_ticks(times: list[str], prices: list[float], quantities: list[float], sessions: list[str]) -> pd.DataFrame:
    timestamps = pd.to_datetime(times)
    return pd.DataFrame(
        {
            "tick_id": range(len(times)),
            "timestamp": timestamps,
            "price": prices,
            "quantity": quantities,
            "session_id": sessions,
            "session_type": [value.split()[1] for value in sessions],
            "session_date": [pd.Timestamp(value.split()[0]) for value in sessions],
        }
    )


def make_hourly(timestamp: str, atr: float = 10.0, direction: float = 1.0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "timestamp": [pd.Timestamp(timestamp)],
            "atr": [atr],
            "supertrend_direction": [direction],
        }
    )


def make_signal_bar(end_tick_id: int = 0) -> pd.DataFrame:
    return pd.DataFrame(
        {
            "tick_end_id": [end_tick_id],
            "timestamp": [pd.Timestamp("2026-09-01 09:00:00")],
            "high": [105.0],
            "close": [100.0],
            "session_id": ["2026-09-01 day"],
            "resistance_reversal": [True],
            "resistance_id": [1],
            "resistance_top": [104.0],
        }
    )


def test_session_volume_bars_discard_incomplete_volume_at_boundary() -> None:
    ticks = make_ticks(
        ["2026-09-01 13:44:59", "2026-09-01 15:00:00", "2026-09-01 15:00:01"],
        [100.0, 110.0, 111.0],
        [600.0, 600.0, 500.0],
        ["2026-09-01 day", "2026-09-02 night", "2026-09-02 night"],
    )

    bars = build_session_volume_bars(ticks, 1000.0)

    assert len(bars) == 1
    assert bars.iloc[0]["session_id"] == "2026-09-02 night"
    assert bars.iloc[0]["tick_start_id"] == 1
    assert bars.iloc[0]["tick_end_id"] == 2
    assert bars.iloc[0]["volume"] == 1100.0


def test_initial_stop_uses_next_tick_and_adverse_slippage() -> None:
    ticks = make_ticks(
        ["2026-09-01 09:00:00", "2026-09-01 09:00:01", "2026-09-01 09:00:02", "2026-09-01 09:00:03"],
        [100.0, 100.0, 111.0, 112.0],
        [1.0] * 4,
        ["2026-09-01 day"] * 4,
    )

    trades = backtest_strategy_b(ticks, make_signal_bar(), make_hourly("2026-09-01 08:59:59"), 2.0, 0.5, 12, 120, 1.5)

    trade = trades.iloc[0]
    assert trade["entry_fill_price"] == 98.0
    assert trade["initial_stop"] == 110.0
    assert trade["raw_exit_price"] == 112.0
    assert trade["exit_fill_price"] == 114.0
    assert trade["pnl_points"] == -16.0
    assert trade["exit_reason"] == "initial_stop"


def test_confirmation_timeout_uses_elapsed_clock_time() -> None:
    ticks = make_ticks(
        ["2026-09-01 09:00:00", "2026-09-01 09:00:01", "2026-09-01 21:00:01"],
        [100.0, 100.0, 90.0],
        [1.0] * 3,
        ["2026-09-01 day", "2026-09-01 day", "2026-09-02 night"],
    )

    trades = backtest_strategy_b(ticks, make_signal_bar(), make_hourly("2026-09-01 08:59:59", atr=100.0), 2.0, 0.5, 12, 120, 1.5)

    trade = trades.iloc[0]
    assert trade["exit_time"] == pd.Timestamp("2026-09-01 21:00:01")
    assert trade["exit_reason"] == "supertrend_confirmation_timeout"


def test_max_drawdown_starts_from_zero() -> None:
    trades = pd.DataFrame(
        {
            "pnl_points": [-100.0, 40.0, -20.0],
            "entry_time": pd.to_datetime(["2026-09-01"] * 3),
            "exit_time": pd.to_datetime(["2026-09-02"] * 3),
            "cross_session": [False] * 3,
        }
    )

    summary = performance_summary(trades, "pnl_points")

    assert summary["max_drawdown"] == -100.0
