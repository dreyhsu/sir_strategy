import pandas as pd
import pytest

from backtest_btcusdt_5m_diamond_hourly_supertrend_short import (
    add_five_minute_diamonds,
    backtest,
    build_time_bars,
    compare_confirmation_timing,
)


def ts(minutes: int) -> pd.Timestamp:
    return pd.Timestamp("2026-08-01 00:00:00", tz="UTC") + pd.Timedelta(minutes=minutes)


def test_time_bars_use_utc_buckets_and_discard_unconfirmed_final_bar() -> None:
    ticks = [
        (1, 1, 100.0, 1.0, int(ts(1).timestamp() * 1000)),
        (2, 2, 102.0, 2.0, int(ts(4).timestamp() * 1000)),
        (3, 3, 101.0, 1.0, int(ts(5).timestamp() * 1000)),
    ]
    bars = build_time_bars(ticks, 5)
    assert len(bars) == 1
    assert bars.iloc[0]["bar_start_time"] == ts(0)
    assert bars.iloc[0]["tick_end_id"] == 2
    assert bars.iloc[0]["volume"] == pytest.approx(304.0)


def hourly_state(tick_end_id: int = 10) -> pd.DataFrame:
    return pd.DataFrame({
        "tick_end_id": [tick_end_id], "support_id": pd.array([1], dtype="Int64"),
        "support_top": [100.0], "support_bottom": [80.0],
        "resistance_id": pd.array([2], dtype="Int64"),
        "resistance_bottom": [80.0], "resistance_top": [110.0],
        "structure_stop_atr": [20.0],
    })


def five_bars() -> pd.DataFrame:
    highs = [85.0, 85.0, 75.0, 85.0, 75.0]
    return pd.DataFrame({
        "bar_start_time": [ts(i * 5) for i in range(5)],
        "timestamp": [ts(i * 5 + 4) for i in range(5)],
        "open": highs, "high": highs, "low": [70.0] * 5, "close": highs,
        "volume": [1.0] * 5, "tick_start_id": [10, 20, 30, 40, 50],
        "tick_end_id": [10, 20, 30, 40, 50], "session_id": ["continuous"] * 5,
    })


def test_hourly_state_is_strictly_prior_and_dual_red_uses_higher_anchor() -> None:
    result = add_five_minute_diamonds(five_bars(), hourly_state(), 0.10)
    # The hourly state ending on tick 10 cannot be read by the 5m bar ending on tick 10.
    assert pd.isna(result.iloc[0]["resistance_id"])
    # First support break arms role conversion. The later repeat is a dual red signal.
    dual = result.iloc[4]
    assert bool(dual["resistance_holds"])
    assert bool(dual["support_as_resistance_holds"])
    assert dual["short_signal_type"] == "resistance_holds+support_as_resistance_holds"
    assert dual["short_stop_anchor"] == 110.0
    assert dual["short_structure_type"] == "resistance"
    assert dual["stop_price"] == 112.0
    # No offset: the timestamp remains the actual confirmation bar.
    assert dual["timestamp"] == ts(24)


def test_all_four_pine_crossings_and_role_conversion() -> None:
    highs = [105, 105, 95, 120, 105, 120, 65, 75, 65]
    lows = [75, 75, 85, 115, 105, 115, 60, 65, 60]
    bars = pd.DataFrame({
        "bar_start_time": [ts(i * 5) for i in range(len(highs))],
        "timestamp": [ts(i * 5 + 4) for i in range(len(highs))],
        "open": highs, "high": highs, "low": lows, "close": highs,
        "volume": [1.0] * len(highs), "tick_start_id": [i * 10 for i in range(len(highs))],
        "tick_end_id": [i * 10 for i in range(len(highs))],
        "session_id": ["continuous"] * len(highs),
    })
    state = hourly_state(0)
    state.loc[0, ["support_top", "support_bottom", "resistance_bottom", "resistance_top"]] = [80, 70, 100, 110]
    result = add_five_minute_diamonds(bars, state, 0.10)
    assert bool(result.iloc[2]["resistance_holds"])
    assert bool(result.iloc[2]["support_holds"])
    assert bool(result.iloc[3]["breakout_resistance"])
    assert bool(result.iloc[5]["resistance_as_support_holds"])
    assert bool(result.iloc[6]["breakout_support"])
    assert bool(result.iloc[8]["support_as_resistance_holds"])


def signal_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "timestamp": [ts(1)], "tick_end_id": [2], "short_signal": [True],
        "short_signal_type": ["resistance_holds"],
        "short_structure_type": ["resistance"],
        "short_structure_id": pd.array([7], dtype="Int64"),
        "short_stop_anchor": [110.0], "hourly_stop_atr": [20.0], "stop_price": [112.0],
        "resistance_holds": [True], "support_as_resistance_holds": [False],
        "support_holds": [False], "resistance_as_support_holds": [False],
        "green_exit_signal": [False],
    })


def supertrend_frame() -> pd.DataFrame:
    return pd.DataFrame({
        "tick_end_id": [1, 4], "timestamp": [ts(0), ts(4)],
        "supertrend": [105.0, 95.0], "supertrend_direction": [-1.0, 1.0],
    })


def raw_ticks(prices: list[float]):
    return [(i, i, price, 1.0, int(ts(i).timestamp() * 1000)) for i, price in enumerate(prices, 1)]


def test_next_tick_entry_and_bearish_then_bullish_hourly_exit() -> None:
    trades, _, summary = backtest(
        raw_ticks([100, 100, 100, 100, 100, 100]), signal_frame(), supertrend_frame(),
        chart_sample_minutes=5,
    )
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["signal_tick_end_id"] == 2
    assert trade["entry_tick_id"] == 3
    assert trade["exit_tick_id"] == 5
    assert trade["exit_reason"] == "adaptive_hourly_supertrend_bullish_flip"
    assert trade["entry_fill_price"] == pytest.approx(99.98)
    assert trade["exit_fill_price"] == pytest.approx(100.02)
    assert summary["filled_entries"] == 1


def test_structure_stop_has_priority_over_hourly_flip() -> None:
    trades, _, summary = backtest(
        raw_ticks([100, 100, 100, 100, 113, 113]), signal_frame(), supertrend_frame(),
        chart_sample_minutes=5,
    )
    assert trades.iloc[0]["exit_tick_id"] == 5
    assert trades.iloc[0]["exit_reason"] == "structure_stop"
    assert summary["structure_stop_exits"] == 1
    assert summary["bullish_flip_exits"] == 0


def test_pending_final_signal_is_discarded() -> None:
    ticks = raw_ticks([100, 100])
    trades, _, summary = backtest(ticks, signal_frame(), supertrend_frame().iloc[:1])
    assert trades.empty
    assert summary["red_signals"] == 1
    assert summary["filled_entries"] == 0


def test_confirmation_comparison_uses_containing_hour_close() -> None:
    five = signal_frame().assign(bar_start_time=[ts(0)])
    hourly = pd.DataFrame({
        "hour_start": [ts(0)], "timestamp": [ts(59)], "short_signal": [False],
    })
    comparison = compare_confirmation_timing(five, hourly)
    assert len(comparison) == 1
    assert comparison.iloc[0]["lead_minutes"] == pytest.approx(58.0)
    assert not bool(comparison.iloc[0]["hourly_bar_also_has_red_diamond"])
