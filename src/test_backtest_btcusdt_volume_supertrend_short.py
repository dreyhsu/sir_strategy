from __future__ import annotations

import math

import pandas as pd

from backtest_btcusdt_volume_supertrend_short import (
    add_resistance_touch_signals,
    backtest_volume_supertrend_short,
)
from backtest_tmf_adaptive_hourly_resistance_short import add_adaptive_supertrend


def make_ticks(prices: list[float]) -> list[tuple[int, int, float, float, int]]:
    start_ms = 1_800_000_000_000
    return [
        (index, 10_000 + index, price, 1.0, start_ms + index * 1_000)
        for index, price in enumerate(prices)
    ]


def make_signal_bars(ticks: list[tuple[int, int, float, float, int]], states: dict[int, int]) -> pd.DataFrame:
    records = []
    for tick_id, direction in states.items():
        timestamp_ms = ticks[tick_id][4]
        price = ticks[tick_id][2]
        records.append(
            {
                "timestamp": pd.Timestamp(timestamp_ms, unit="ms", tz="UTC"),
                "bar_start_time": pd.Timestamp(timestamp_ms - 500, unit="ms", tz="UTC"),
                "open": price,
                "high": price + 1,
                "low": price - 1,
                "close": price,
                "volume": 1_000_000.0,
                "tick_end_id": tick_id,
                "supertrend": price + 2 if direction == -1 else price - 2,
                "supertrend_direction": float(direction),
                "atr": 2.0,
                "adaptive_multiplier": 3.0,
                "resistance_id": 7,
                "resistance_bottom": price - 2,
                "resistance_top": price + 10,
                "hourly_stop_atr": 10.0,
                "stop_price": price + 20,
                "resistance_touch": True,
                "resistance_supertrend_short": direction == -1,
                "resistance_signal_number": 1 if direction == -1 else pd.NA,
            }
        )
    return pd.DataFrame(records)


def test_entry_and_bullish_flip_fill_on_following_raw_trades() -> None:
    ticks = make_ticks([100.0, 99.0, 98.0, 97.0, 96.0])
    bars = make_signal_bars(ticks, {0: -1, 2: -1, 3: 1})

    trades, _samples, summary = backtest_volume_supertrend_short(
        ticks, bars, taker_fee_rate=0, slippage_bps=0
    )

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["signal_time"] == bars.iloc[0]["timestamp"]
    assert trade["entry_time"] == pd.Timestamp(ticks[1][4], unit="ms", tz="UTC")
    assert trade["entry_tick_id"] == 1
    assert trade["raw_entry_price"] == 99.0
    assert trade["exit_signal_time"] == bars.iloc[2]["timestamp"]
    assert trade["exit_time"] == pd.Timestamp(ticks[4][4], unit="ms", tz="UTC")
    assert trade["exit_tick_id"] == 4
    assert trade["raw_exit_price"] == 96.0
    assert trade["exit_reason"] == "adaptive_volume_supertrend_bullish_flip"
    assert summary["bearish_bars"] == 2
    assert summary["filled_entries"] == 1
    assert summary["bullish_flip_exits"] == 1


def test_repeated_bearish_bars_do_not_add_positions() -> None:
    ticks = make_ticks([100.0, 101.0, 102.0, 103.0, 104.0])
    bars = make_signal_bars(ticks, {0: -1, 1: -1, 2: -1, 3: 1})

    trades, samples, summary = backtest_volume_supertrend_short(
        ticks, bars, taker_fee_rate=0, slippage_bps=0
    )

    assert len(trades) == 1
    assert summary["entry_signals"] == 3
    assert summary["filled_entries"] == 1
    assert summary["ignored_while_occupied"] == 2
    assert samples["open_positions"].max() == 1


def test_bearish_supertrend_requires_active_resistance_touch() -> None:
    timestamps = pd.date_range("2026-08-01", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "tick_end_id": [10, 20, 30],
            "open": [100.0, 110.0, 105.0],
            "high": [101.0, 112.0, 106.0],
            "low": [99.0, 108.0, 104.0],
            "close": [100.0, 109.0, 105.0],
            "supertrend": [103.0, 113.0, 103.0],
            "supertrend_direction": [-1.0, -1.0, 1.0],
        }
    )
    hourly = pd.DataFrame({"tick_end_id": [5], "structure_stop_atr": [20.0]})
    zones = pd.DataFrame(
        {
            "zone_id": [1, 2],
            "zone_type": ["support", "resistance"],
            "created_time": [timestamps[0] - pd.Timedelta(hours=1)] * 2,
            "broken_time": [pd.NaT, pd.NaT],
            "bottom": [90.0, 108.0],
            "top": [95.0, 111.0],
        }
    )

    result = add_resistance_touch_signals(bars, hourly, zones, 0.10)

    assert not bool(result.iloc[0]["resistance_touch"])
    assert bool(result.iloc[1]["resistance_touch"])
    assert bool(result.iloc[1]["resistance_supertrend_short"])
    assert not bool(result.iloc[2]["resistance_supertrend_short"])
    assert result.iloc[1]["resistance_id"] == 2
    assert result.iloc[1]["stop_price"] == 113.0


def test_resistance_emits_once_per_bearish_cycle_and_caps_at_three() -> None:
    timestamps = pd.date_range("2026-08-01", periods=9, freq="min", tz="UTC")
    directions = [-1, -1, 1, -1, -1, 1, -1, 1, -1]
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "tick_end_id": list(range(10, 100, 10)),
            "open": [110.0] * 9,
            "high": [112.0] * 9,
            "low": [108.0] * 9,
            "close": [109.0] * 9,
            "supertrend": [113.0 if value == -1 else 107.0 for value in directions],
            "supertrend_direction": directions,
        }
    )
    hourly = pd.DataFrame({"tick_end_id": [5], "structure_stop_atr": [20.0]})
    zones = pd.DataFrame(
        {
            "zone_id": [2],
            "zone_type": ["resistance"],
            "created_time": [timestamps[0] - pd.Timedelta(hours=1)],
            "broken_time": [pd.NaT],
            "bottom": [108.0],
            "top": [111.0],
        }
    )

    result = add_resistance_touch_signals(bars, hourly, zones, 0.10, 3)
    signals = result[result["resistance_supertrend_short"]]

    assert signals.index.tolist() == [0, 3, 6]
    assert signals["resistance_signal_number"].tolist() == [1, 2, 3]


def test_leaving_box_without_bullish_state_does_not_rearm() -> None:
    timestamps = pd.date_range("2026-08-01", periods=3, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "tick_end_id": [10, 20, 30],
            "open": [110.0, 100.0, 110.0],
            "high": [112.0, 101.0, 112.0],
            "low": [108.0, 99.0, 108.0],
            "close": [109.0, 100.0, 109.0],
            "supertrend": [113.0] * 3,
            "supertrend_direction": [-1.0] * 3,
        }
    )
    hourly = pd.DataFrame({"tick_end_id": [5], "structure_stop_atr": [20.0]})
    zones = pd.DataFrame(
        {
            "zone_id": [2],
            "zone_type": ["resistance"],
            "created_time": [timestamps[0] - pd.Timedelta(hours=1)],
            "broken_time": [pd.NaT],
            "bottom": [108.0],
            "top": [111.0],
        }
    )

    result = add_resistance_touch_signals(bars, hourly, zones, 0.10, 3)

    assert result["resistance_supertrend_short"].tolist() == [True, False, False]


def test_resistance_boxes_have_independent_quotas_and_broken_box_stays_inactive() -> None:
    timestamps = pd.date_range("2026-08-01", periods=4, freq="min", tz="UTC")
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "tick_end_id": [10, 20, 30, 40],
            "open": [110.0, 210.0, 110.0, 110.0],
            "high": [112.0, 212.0, 112.0, 112.0],
            "low": [108.0, 208.0, 108.0, 108.0],
            "close": [109.0, 209.0, 109.0, 109.0],
            "supertrend": [113.0, 213.0, 107.0, 113.0],
            "supertrend_direction": [-1.0, -1.0, 1.0, -1.0],
        }
    )
    hourly = pd.DataFrame({"tick_end_id": [5], "structure_stop_atr": [20.0]})
    zones = pd.DataFrame(
        {
            "zone_id": [1, 2],
            "zone_type": ["resistance", "resistance"],
            "created_time": [timestamps[0] - pd.Timedelta(hours=1)] * 2,
            "broken_time": [timestamps[2], pd.NaT],
            "bottom": [108.0, 208.0],
            "top": [111.0, 211.0],
        }
    )

    result = add_resistance_touch_signals(bars, hourly, zones, 0.10, 3)
    signals = result[result["resistance_supertrend_short"]]

    assert signals["resistance_id"].tolist() == [1, 2]
    assert not bool(result.iloc[3]["resistance_touch"])


def test_structure_stop_has_priority_over_queued_bullish_flip() -> None:
    ticks = make_ticks([100.0, 99.0, 104.0, 106.0])
    bars = make_signal_bars(ticks, {0: -1, 2: 1})
    bars.loc[0, "resistance_top"] = 104.0
    bars.loc[0, "hourly_stop_atr"] = 10.0
    bars.loc[0, "stop_price"] = 105.0

    trades, _samples, summary = backtest_volume_supertrend_short(
        ticks, bars, taker_fee_rate=0, slippage_bps=0
    )

    trade = trades.iloc[0]
    assert trade["exit_reason"] == "resistance_structure_stop"
    assert trade["raw_exit_price"] == 106.0
    assert summary["structure_stop_exits"] == 1
    assert summary["bullish_flip_exits"] == 0


def test_costs_and_short_pnl_are_applied_on_both_sides() -> None:
    ticks = make_ticks([101.0, 100.0, 95.0, 90.0])
    bars = make_signal_bars(ticks, {0: -1, 2: 1})

    trades, _samples, summary = backtest_volume_supertrend_short(
        ticks,
        bars,
        initial_equity_usdt=1_000,
        position_btc=0.01,
        taker_fee_rate=0.0005,
        slippage_bps=2,
    )

    trade = trades.iloc[0]
    expected_entry_fill = 100.0 * (1 - 2 / 10_000)
    expected_exit_fill = 90.0 * (1 + 2 / 10_000)
    expected_gross = (expected_entry_fill - expected_exit_fill) * 0.01
    expected_fees = (expected_entry_fill + expected_exit_fill) * 0.01 * 0.0005
    assert math.isclose(trade["entry_fill_price"], expected_entry_fill)
    assert math.isclose(trade["exit_fill_price"], expected_exit_fill)
    assert math.isclose(trade["gross_pnl_usdt"], expected_gross)
    assert math.isclose(trade["net_pnl_usdt"], expected_gross - expected_fees)
    assert math.isclose(summary["final_equity_usdt"], 1_000 + trade["net_pnl_usdt"])


def test_open_trade_closes_at_data_end_and_final_signal_is_not_filled() -> None:
    ticks = make_ticks([100.0, 99.0, 98.0])
    bars = make_signal_bars(ticks, {0: -1})

    trades, _samples, summary = backtest_volume_supertrend_short(
        ticks, bars, taker_fee_rate=0, slippage_bps=0
    )

    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "data_end"
    assert trades.iloc[0]["raw_exit_price"] == 98.0
    assert summary["data_end_exits"] == 1

    final_bar = make_signal_bars(ticks, {2: -1})
    no_trades, _samples, final_summary = backtest_volume_supertrend_short(
        ticks, final_bar, taker_fee_rate=0, slippage_bps=0
    )
    assert no_trades.empty
    assert final_summary["entry_signals"] == 1
    assert final_summary["filled_entries"] == 0


def test_adaptive_supertrend_is_continuous_across_month_boundary() -> None:
    timestamps = pd.date_range("2026-08-31 23:59:55", periods=8, freq="s", tz="UTC")
    closes = [100.0, 101.0, 100.0, 99.0, 98.0, 99.0, 100.0, 101.0]
    bars = pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": closes,
            "high": [value + 1 for value in closes],
            "low": [value - 1 for value in closes],
            "close": closes,
            "session_id": ["continuous"] * len(closes),
        }
    )

    result = add_adaptive_supertrend(bars, 3, 3.0, 0.8, 2, 0.25, 0.8, 2)

    september = result[result["timestamp"].dt.month == 9]
    assert september.iloc[0]["atr"] == 2.0
    assert not pd.isna(september.iloc[0]["supertrend_direction"])
