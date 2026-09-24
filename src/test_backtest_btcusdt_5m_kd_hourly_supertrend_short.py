import numpy as np
import pandas as pd
import pytest

from backtest_btcusdt_5m_diamond_hourly_supertrend_short import backtest
from backtest_btcusdt_5m_kd_hourly_supertrend_short import (
    add_resistance_kd_signals,
    add_stochastic_kd,
)


def ts(minutes: int) -> pd.Timestamp:
    return pd.Timestamp("2026-08-01", tz="UTC") + pd.Timedelta(minutes=minutes)


def bars_from_closes(closes: list[float]) -> pd.DataFrame:
    count = len(closes)
    return pd.DataFrame({
        "bar_start_time": [ts(i * 5) for i in range(count)],
        "timestamp": [ts(i * 5 + 4) for i in range(count)],
        "open": closes, "high": [100.0] * count, "low": [0.0] * count,
        "close": closes, "volume": [1.0] * count,
        "tick_start_id": [i * 10 for i in range(count)],
        "tick_end_id": [i * 10 + 9 for i in range(count)],
        "session_id": ["continuous"] * count,
    })


def test_stochastic_sma_warmup_and_exact_bearish_cross() -> None:
    result = add_stochastic_kd(bars_from_closes([10, 20, 30, 40, 50, 40, 30]), 3, 2, 2)
    assert result["kd_k"].iloc[:3].isna().all()
    assert result.iloc[4]["kd_k"] == pytest.approx(45.0)
    assert result.iloc[4]["kd_d"] == pytest.approx(40.0)
    assert not bool(result.iloc[5]["kd_bearish_cross"])
    assert bool(result.iloc[6]["kd_bearish_cross"])
    assert result.iloc[6]["kd_k"] == pytest.approx(35.0)
    assert result.iloc[6]["kd_d"] == pytest.approx(40.0)
    assert not bool(result.iloc[6]["kd_overbought_bearish_cross"])


def test_entry_cross_requires_one_of_prior_five_k_values_above_80() -> None:
    closes = [10, 20, 30, 70, 90, 100, 90, 80, 70, 60, 80, 95, 100, 90, 70]
    result = add_stochastic_kd(bars_from_closes(closes), 3, 2, 2)
    assert bool(result.iloc[13]["kd_bearish_cross"])
    assert result.iloc[13]["kd_prior_5_max_k"] == pytest.approx(97.5)
    assert bool(result.iloc[13]["kd_prior_5_k_above_80"])
    assert bool(result.iloc[13]["kd_overbought_bearish_cross"])
    assert result.iloc[13]["recent_5_close_max"] == 100.0


def test_zero_stochastic_range_stays_nan_and_never_crosses() -> None:
    bars = bars_from_closes([50.0] * 12)
    bars["high"] = 50.0
    bars["low"] = 50.0
    result = add_stochastic_kd(bars, 9, 3, 3)
    assert result["kd_rsv"].isna().all()
    assert not result["kd_bearish_cross"].any()


def hourly(atr: float = 20.0) -> pd.DataFrame:
    return pd.DataFrame({"tick_end_id": [1], "structure_stop_atr": [atr]})


def zones() -> pd.DataFrame:
    return pd.DataFrame([
        {"zone_id": 1, "zone_type": "resistance", "created_time": ts(0),
         "bottom": 95.0, "top": 105.0, "broken_time": pd.NaT},
        {"zone_id": 2, "zone_type": "resistance", "created_time": ts(0),
         "bottom": 90.0, "top": 100.0, "broken_time": pd.NaT},
        {"zone_id": 3, "zone_type": "support", "created_time": ts(0),
         "bottom": 80.0, "top": 85.0, "broken_time": pd.NaT},
    ])


def one_signal_bar(*, high: float = 102.0, low: float = 92.0, cross: bool = True,
                   timestamp: pd.Timestamp | None = None) -> pd.DataFrame:
    return pd.DataFrame({
        "bar_start_time": [ts(5)], "timestamp": [timestamp or ts(9)],
        "open": [98.0], "high": [high], "low": [low], "close": [96.0],
        "volume": [1.0], "tick_start_id": [10], "tick_end_id": [19],
        "session_id": ["continuous"], "kd_rsv": [50.0], "kd_k": [40.0],
        "kd_d": [50.0], "kd_bearish_cross": [cross],
        "kd_prior_5_max_k": [90.0 if cross else 70.0],
        "kd_prior_5_k_above_80": [cross], "kd_overbought_bearish_cross": [cross],
        "recent_5_close_max": [105.0],
    })


def test_overbought_kd_cross_does_not_require_resistance_overlap() -> None:
    outside = add_resistance_kd_signals(
        one_signal_bar(high=89.0, low=86.0), hourly(), zones(), 0.10
    )
    assert bool(outside.iloc[0]["kd_bearish_cross"])
    assert not bool(outside.iloc[0]["resistance_touch"])
    assert bool(outside.iloc[0]["short_signal"])


def test_resistance_touch_requires_kd_cross() -> None:
    result = add_resistance_kd_signals(one_signal_bar(cross=False), hourly(), zones(), 0.10)
    assert bool(result.iloc[0]["resistance_touch"])
    assert not bool(result.iloc[0]["short_signal"])


def test_stop_uses_signal_bars_recent_five_close_max() -> None:
    result = add_resistance_kd_signals(one_signal_bar(), hourly(), zones(), 0.10).iloc[0]
    assert bool(result["short_signal"])
    assert result["resistance_id"] == 2
    assert result["resistance_bottom"] == 90.0
    assert result["short_stop_anchor"] == 105.0
    assert result["stop_price"] == 105.0


def test_broken_box_is_not_an_entry_filter_but_remains_latest_stop_structure() -> None:
    prior = zones()
    prior["broken_time"] = pd.Series(
        [ts(1) if value == "resistance" else pd.NaT for value in prior["zone_type"]],
        dtype="datetime64[ns, UTC]",
    )
    result = add_resistance_kd_signals(
        one_signal_bar(high=89.0, low=86.0), hourly(), prior, 0.10
    ).iloc[0]
    assert not bool(result["resistance_touch"])
    assert bool(result["short_signal"])
    assert result["resistance_id"] == 2
    assert result["stop_price"] == 105.0


def test_current_close_must_be_below_latest_resistance_top() -> None:
    bar = one_signal_bar()
    bar.loc[0, "close"] = 100.0
    result = add_resistance_kd_signals(bar, hourly(), zones(), 0.10).iloc[0]
    assert bool(result["kd_overbought_bearish_cross"])
    assert not bool(result["close_below_resistance_top"])
    assert not bool(result["short_signal"])


def test_zone_is_not_available_at_its_creation_confirmation_time() -> None:
    result = add_resistance_kd_signals(
        one_signal_bar(timestamp=ts(0)), hourly(), zones(), 0.10
    )
    assert not bool(result.iloc[0]["resistance_touch"])
    assert not bool(result.iloc[0]["short_signal"])


def test_kd_signal_fills_on_next_raw_trade_and_uses_shared_exit_rules() -> None:
    signal = add_resistance_kd_signals(one_signal_bar(), hourly(), zones(), 0.10)
    signal.loc[0, "tick_end_id"] = 2
    signal.loc[0, "timestamp"] = ts(2)
    hourly_supertrend = pd.DataFrame({
        "tick_end_id": [1, 4], "timestamp": [ts(1), ts(4)],
        "supertrend": [105.0, 95.0], "supertrend_direction": [-1.0, 1.0],
    })
    ticks = [(i, i, price, 1.0, int(ts(i).timestamp() * 1000))
             for i, price in enumerate([99, 99, 99, 99, 99, 99], 1)]
    trades, _, summary = backtest(ticks, signal, hourly_supertrend)
    assert len(trades) == 1
    assert trades.iloc[0]["entry_tick_id"] == 3
    assert trades.iloc[0]["exit_tick_id"] == 5
    assert trades.iloc[0]["exit_reason"] == "adaptive_hourly_supertrend_bullish_flip"
    assert summary["filled_entries"] == 1
