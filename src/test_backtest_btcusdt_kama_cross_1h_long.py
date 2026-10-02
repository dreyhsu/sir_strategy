from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from backtest_btcusdt_kama_cross_1h_long import (
    add_kama_features,
    backtest_strategy,
    monthly_breakdown,
    performance_summary,
    pine_kama,
)


FAST_CONST = 2
SLOW_CONST = 30
FAST_ALPHA = 2.0 / (FAST_CONST + 1)
SLOW_ALPHA = 2.0 / (SLOW_CONST + 1)


def reference_kama(prices: list[float], length: int, fast: int = FAST_CONST, slow: int = SLOW_CONST) -> list[float]:
    """Independent re-derivation of the Pine recursion, written from the study source."""
    fast_alpha, slow_alpha = 2.0 / (fast + 1), 2.0 / (slow + 1)
    output: list[float] = []
    previous: float | None = None
    for index, price in enumerate(prices):
        if index >= length:
            momentum = abs(price - prices[index - length])
            volatility = sum(
                abs(prices[step] - prices[step - 1]) for step in range(index - length + 1, index + 1)
            )
            efficiency = momentum / volatility if volatility != 0 else 0.0
        else:
            efficiency = 0.0  # Pine's ternary takes the false branch while volatility is na
        alpha = (efficiency * (fast_alpha - slow_alpha) + slow_alpha) ** 2
        base = price if previous is None else previous
        previous = alpha * price + (1.0 - alpha) * base
        output.append(previous)
    return output


def make_hourly(rows: list[dict[str, object]]) -> pd.DataFrame:
    """Build a 1h frame shaped like data/btcusdt_bars/BTCUSDT_YYYY-MM_1h.csv."""
    starts = pd.date_range("2026-01-01 00:00:00", periods=len(rows), freq="1h", tz="UTC")
    defaults: dict[str, object] = {"open": 100.0, "high": 101.0, "low": 99.0, "close": 100.0, "volume": 1_000.0}
    frame = pd.DataFrame([{**defaults, **row} for row in rows])
    frame.insert(0, "timestamp", starts + pd.Timedelta(minutes=59, seconds=59))
    frame.insert(1, "hour_start", starts)
    frame.insert(2, "session_id", "continuous")
    return frame


# The bare crossover of the original spec: no stops, price-vs-MA gate. Tests that pin the
# unprotected behaviour pass this explicitly, since the module defaults now add protection.
BARE = {"trend_filter": "price", "trailing_atr": 0.0, "breakeven_after_r": 0.0, "min_entry_er": 0.0}


def synthetic_cross_frame(
    closes: list[float],
    kama_fast: list[float],
    kama_slow: list[float],
    ma200: list[float] | None = None,
    risk_atr: float = 10.0,
    highs: list[float] | None = None,
    lows: list[float] | None = None,
    opens: list[float] | None = None,
    ma200_slope: float | list[float] = 1.0,
    er_fast: float | list[float] = 1.0,
) -> pd.DataFrame:
    """A bar frame with the indicator columns written directly, to isolate the state machine."""
    frame = make_hourly([
        {
            "open": closes[i] if opens is None else opens[i],
            "high": closes[i] + 1.0 if highs is None else highs[i],
            "low": closes[i] - 1.0 if lows is None else lows[i],
            "close": closes[i],
        }
        for i in range(len(closes))
    ])
    frame["kama_fast"] = kama_fast
    frame["kama_slow"] = kama_slow
    frame["kama_spread"] = frame["kama_fast"] - frame["kama_slow"]
    frame["ma200"] = ma200 if ma200 is not None else [0.0] * len(closes)
    frame["above_ma200"] = frame["close"] > frame["ma200"]
    frame["ma200_slope"] = ma200_slope
    frame["er_fast"] = er_fast
    previous_fast, previous_slow = frame["kama_fast"].shift(1), frame["kama_slow"].shift(1)
    ready = previous_fast.notna() & previous_slow.notna()
    frame["kama_cross_up"] = ready & (frame["kama_fast"] > frame["kama_slow"]) & (previous_fast <= previous_slow)
    frame["kama_cross_down"] = ready & (frame["kama_fast"] < frame["kama_slow"]) & (previous_fast >= previous_slow)
    frame["risk_atr"] = risk_atr
    return frame


# --------------------------------------------------------------------------- KAMA


def test_kama_seeds_from_the_price_and_is_never_nan():
    prices = pd.Series([100.0, 103.0, 101.0, 107.0, 110.0, 108.0, 115.0, 120.0])
    kama, efficiency = pine_kama(prices, length=3)
    # nz(kama[1], src) -> bar 0 collapses to the price itself, not an SMA seed.
    assert kama.iloc[0] == pytest.approx(100.0)
    assert kama.notna().all()
    assert efficiency.notna().all()


def test_kama_warmup_uses_zero_efficiency_and_slow_alpha():
    prices = pd.Series([100.0 + 3.0 * step for step in range(12)])
    kama, efficiency = pine_kama(prices, length=5)
    # er is 0 while mom/volatility are na, so alpha pins to slowAlpha ** 2.
    assert (efficiency.iloc[:5] == 0.0).all()
    expected = 100.0 + (SLOW_ALPHA**2) * (prices.iloc[1] - 100.0)
    assert kama.iloc[1] == pytest.approx(expected)


def test_kama_constant_series_stays_constant_with_zero_efficiency():
    prices = pd.Series([250.0] * 20)
    kama, efficiency = pine_kama(prices, length=6)
    assert (efficiency == 0.0).all()  # the volatility != 0 guard
    assert kama.to_numpy() == pytest.approx(np.full(20, 250.0))


def test_kama_linear_ramp_reaches_full_efficiency_and_fast_alpha():
    prices = pd.Series([100.0 + 2.0 * step for step in range(30)])
    kama, efficiency = pine_kama(prices, length=8)
    assert efficiency.iloc[8:].to_numpy() == pytest.approx(1.0)
    # er == 1 -> alpha == fastAlpha ** 2; verify one realised step.
    step = kama.iloc[20] - kama.iloc[19]
    assert step == pytest.approx((FAST_ALPHA**2) * (prices.iloc[20] - kama.iloc[19]))


def test_kama_matches_independent_reference_recursion():
    rng = np.random.default_rng(20260101)
    prices = list(np.cumsum(rng.normal(0.0, 5.0, 120)) + 60_000.0)
    for length in (3, 20, 140):
        kama, _ = pine_kama(pd.Series(prices), length=length)
        assert kama.to_numpy() == pytest.approx(reference_kama(prices, length))


def test_kama_carries_forward_across_a_nan_price():
    kama, _ = pine_kama(pd.Series([100.0, 102.0, np.nan, 104.0]), length=2)
    assert kama.iloc[2] == pytest.approx(kama.iloc[1])
    assert kama.notna().all()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"length": 0},
        {"length": 5, "fast_length": 0},
        {"length": 5, "fast_length": 30, "slow_length": 30},
        {"length": 5, "fast_length": 40, "slow_length": 30},
    ],
)
def test_kama_rejects_invalid_lengths(kwargs):
    with pytest.raises(ValueError):
        pine_kama(pd.Series([1.0, 2.0, 3.0]), **kwargs)


# ------------------------------------------------------------------- cross flags


def test_cross_flags_fire_once_each_and_ignore_an_equality_touch():
    closes = [100.0] * 7
    frame = make_hourly([{"close": close, "open": close} for close in closes])
    # fast runs below, touches exactly, dips back, then genuinely crosses above.
    frame["kama_fast"] = [90.0, 95.0, 100.0, 95.0, 98.0, 105.0, 110.0]
    frame["kama_slow"] = [100.0] * 7
    previous_fast, previous_slow = frame["kama_fast"].shift(1), frame["kama_slow"].shift(1)
    ready = previous_fast.notna() & previous_slow.notna()
    cross_up = ready & (frame["kama_fast"] > frame["kama_slow"]) & (previous_fast <= previous_slow)
    cross_down = ready & (frame["kama_fast"] < frame["kama_slow"]) & (previous_fast >= previous_slow)
    assert cross_up.to_numpy().tolist() == [False, False, False, False, False, True, False]
    assert cross_down.to_numpy().tolist() == [False, False, False, True, False, False, False]


def test_add_kama_features_builds_ma_from_the_requested_source():
    rows = [{"open": 100.0 + step, "close": 500.0, "high": 600.0, "low": 50.0} for step in range(6)]
    frame = add_kama_features(
        make_hourly(rows), kama_fast_length=2, kama_slow_length=4,
        ma200_length=3, ma200_source="open", risk_atr_length=2,
    )
    # SMA(3) of open at index 2 == mean(100, 101, 102); a close-sourced MA would read 500.
    assert frame["ma200"].iloc[2] == pytest.approx(101.0)
    assert frame["ma200"].iloc[:2].isna().all()
    assert not frame["above_ma200"].iloc[:2].any()  # NaN ma200 closes the gate


def test_add_kama_features_rejects_bad_configuration():
    frame = make_hourly([{"close": 100.0} for _ in range(5)])
    with pytest.raises(ValueError):
        add_kama_features(frame, kama_fast_length=10, kama_slow_length=10)
    with pytest.raises(ValueError):
        add_kama_features(frame, kama_source="vwap")


# --------------------------------------------------------------- state machine


def test_entry_fills_next_open_and_exit_fills_next_open_with_costs():
    # cross up at index 1 -> fill at index 2 open; cross down at index 4 -> fill at index 5 open.
    closes = [100.0, 100.0, 110.0, 120.0, 130.0, 140.0, 140.0]
    frame = synthetic_cross_frame(
        closes,
        kama_fast=[90.0, 101.0, 102.0, 103.0, 95.0, 94.0, 93.0],
        kama_slow=[100.0, 100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
    )
    trades, bars = backtest_strategy(
        frame, warmup_bars=0, slippage_bps=1.0, taker_fee_rate=0.0004, position_btc=2.0, **BARE
    )
    assert len(trades) == 1
    trade = trades.iloc[0]
    slip = 1.0 / 10_000.0
    assert trade["signal_time"] == frame["timestamp"].iloc[1]
    assert trade["entry_time"] == frame["hour_start"].iloc[2]
    assert trade["raw_entry_price"] == pytest.approx(frame["open"].iloc[2])
    assert trade["entry_price"] == pytest.approx(frame["open"].iloc[2] * (1 + slip))
    assert trade["exit_time"] == frame["hour_start"].iloc[5]
    assert trade["exit_price"] == pytest.approx(frame["open"].iloc[5] * (1 - slip))
    assert trade["exit_reason"] == "kama_bearish_cross"
    assert trade["bars_held"] == 3
    assert trade["hours_held"] == pytest.approx(3.0)

    entry_fee = trade["entry_price"] * 2.0 * 0.0004
    exit_fee = trade["exit_price"] * 2.0 * 0.0004
    expected = (trade["exit_price"] - trade["entry_price"]) * 2.0 - entry_fee - exit_fee
    assert trade["net_usdt"] == pytest.approx(expected)
    assert trade["net_r"] == pytest.approx((trade["exit_price"] - trade["entry_price"]) / 10.0)
    assert bars["in_position"].tolist() == [False, False, True, True, True, False, False]


def test_ma200_filter_blocks_a_bullish_cross_below_the_gate():
    closes = [100.0] * 6
    kama_fast = [90.0, 105.0, 106.0, 107.0, 108.0, 109.0]
    kama_slow = [100.0] * 6
    blocked, _ = backtest_strategy(
        synthetic_cross_frame(closes, kama_fast, kama_slow, ma200=[200.0] * 6), warmup_bars=0, **BARE
    )
    allowed, _ = backtest_strategy(
        synthetic_cross_frame(closes, kama_fast, kama_slow, ma200=[50.0] * 6), warmup_bars=0, **BARE
    )
    assert blocked.empty
    assert len(allowed) == 1


def test_warmup_gate_blocks_entries_only():
    closes = [100.0] * 8
    kama_fast = [90.0, 105.0, 106.0, 90.0, 89.0, 105.0, 106.0, 107.0]
    kama_slow = [100.0] * 8
    frame = synthetic_cross_frame(closes, kama_fast, kama_slow)

    early, _ = backtest_strategy(frame, warmup_bars=4, **BARE)
    assert len(early) == 1  # only the index-5 cross survives the gate
    assert early.iloc[0]["entry_time"] == frame["hour_start"].iloc[6]

    # An exit must still fire for a position opened before the gate index.
    open_before, _ = backtest_strategy(frame, warmup_bars=0, **BARE)
    assert len(open_before) == 2
    assert open_before.iloc[0]["exit_reason"] == "kama_bearish_cross"


def test_no_stop_loss_survives_a_deep_drawdown():
    frame = synthetic_cross_frame(
        [100.0, 100.0, 100.0, 100.0, 100.0, 100.0],
        kama_fast=[90.0, 105.0, 106.0, 107.0, 108.0, 109.0],
        kama_slow=[100.0] * 6,
    )
    frame.loc[3, "low"] = 1.0  # a 99% intrabar collapse must not close the trade
    trades, _ = backtest_strategy(frame, warmup_bars=0, **BARE)
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "data_end"
    assert trades.iloc[0]["mae_points"] < -90.0


def test_open_position_closes_at_data_end_and_final_bar_signal_is_dropped():
    frame = synthetic_cross_frame(
        [100.0, 100.0, 100.0, 100.0],
        kama_fast=[90.0, 105.0, 106.0, 107.0],
        kama_slow=[100.0] * 4,
    )
    trades, bars = backtest_strategy(frame, warmup_bars=0, **BARE)
    assert trades.iloc[0]["exit_reason"] == "data_end"
    assert trades.iloc[0]["raw_exit_price"] == pytest.approx(frame["close"].iloc[-1])

    # A cross on the very last bar has no next open, so it must not be signalled.
    late = synthetic_cross_frame(
        [100.0, 100.0, 100.0], kama_fast=[90.0, 91.0, 105.0], kama_slow=[100.0] * 3
    )
    late_trades, late_bars = backtest_strategy(late, warmup_bars=0, **BARE)
    assert late["kama_cross_up"].iloc[2]
    assert not late_bars["entry_signal"].any()
    assert late_trades.empty


def test_bullish_cross_while_long_is_ignored():
    frame = synthetic_cross_frame(
        [100.0] * 8,
        kama_fast=[90.0, 105.0, 99.0, 106.0, 107.0, 108.0, 109.0, 110.0],
        kama_slow=[100.0] * 8,
    )
    trades, bars = backtest_strategy(frame, warmup_bars=0, **BARE)
    # index 1 crosses up (entry at 2), index 2 crosses down (exit at 3), index 3 crosses up again.
    assert len(trades) == 2
    assert int(bars["entry_signal"].sum()) == 2


def test_summary_and_monthly_breakdown_reconcile():
    frame = synthetic_cross_frame(
        [100.0, 100.0, 110.0, 120.0, 130.0, 140.0, 140.0],
        kama_fast=[90.0, 101.0, 102.0, 103.0, 95.0, 94.0, 93.0],
        kama_slow=[100.0] * 7,
    )
    trades, _ = backtest_strategy(frame, warmup_bars=0, **BARE)
    summary = performance_summary(trades)
    monthly = monthly_breakdown(trades)
    assert summary["trades"] == 1
    assert float(monthly["net_usdt"].sum()) == pytest.approx(summary["net_usdt"])
    assert monthly["month"].tolist() == ["2026-01"]


def test_empty_result_shapes_are_stable():
    frame = synthetic_cross_frame([100.0] * 4, kama_fast=[90.0] * 4, kama_slow=[100.0] * 4)
    trades, _ = backtest_strategy(frame, warmup_bars=0, **BARE)
    assert trades.empty
    assert performance_summary(trades) == {"trades": 0}
    assert monthly_breakdown(trades).empty


# ------------------------------------------------- protective stops (feature 1)


def _runner_frame(highs: list[float], lows: list[float], opens: list[float]) -> pd.DataFrame:
    """KAMA stays bullish throughout, so only a stop can close the trade."""
    closes = [100.0, 100.0] + opens[2:]
    return synthetic_cross_frame(
        closes,
        kama_fast=[90.0, 105.0] + [106.0] * (len(closes) - 2),
        kama_slow=[100.0] * len(closes),
        highs=highs, lows=lows, opens=opens, risk_atr=10.0,
    )


def test_trailing_stop_closes_the_trade_before_the_bearish_cross():
    # Entry at bar 2 open (100). Bar 2 runs to 130 -> 1R reached, trail = 130 - 1.5*10 = 115.
    frame = _runner_frame(
        highs=[101.0, 101.0, 130.0, 126.0, 126.0],
        lows=[99.0, 99.0, 99.0, 110.0, 110.0],
        opens=[100.0, 100.0, 100.0, 125.0, 125.0],
    )
    trades, bars = backtest_strategy(frame, warmup_bars=0, trailing_atr=1.5, breakeven_after_r=1.0, trend_filter="price", min_entry_er=0.0)
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["exit_reason"] == "atr_trailing_stop"
    assert trade["raw_exit_price"] == pytest.approx(115.0)  # 130 - 1.5 * ATR(10)
    assert trade["trailing_stop_at_exit"] == pytest.approx(115.0)
    assert trade["net_usdt"] > 0
    assert bars["stop_level"].max() == pytest.approx(115.0)


def test_trailing_stop_ratchets_up_only():
    frame = _runner_frame(
        highs=[101.0, 101.0, 130.0, 120.0, 118.0, 118.0],
        lows=[99.0, 99.0, 99.0, 116.0, 116.0, 110.0],
        opens=[100.0, 100.0, 100.0, 119.0, 117.0, 117.0],
    )
    trades, _ = backtest_strategy(frame, warmup_bars=0, trailing_atr=1.5, breakeven_after_r=0.0, trend_filter="price", min_entry_er=0.0)
    # Highs of 120/118 are below the 130 peak, so the stop must stay at 115, never fall.
    assert trades.iloc[0]["raw_exit_price"] == pytest.approx(115.0)


def test_breakeven_lock_stops_a_winner_becoming_a_loser():
    # Runs to 111 (just past 1R), then retraces through entry.
    frame = _runner_frame(
        highs=[101.0, 101.0, 111.0, 106.0],
        lows=[99.0, 99.0, 100.0, 99.0],
        opens=[100.0, 100.0, 100.0, 105.0],
    )
    trades, _ = backtest_strategy(
        frame, warmup_bars=0, trailing_atr=0.0, breakeven_after_r=1.0, trend_filter="price", min_entry_er=0.0,
        slippage_bps=1.0, taker_fee_rate=0.0004,
    )
    trade = trades.iloc[0]
    assert trade["exit_reason"] == "breakeven_lock"
    # The lock is defined as netting zero after both fees and both slippage legs.
    assert trade["net_usdt"] == pytest.approx(0.0, abs=1e-3)


def test_stop_gap_through_the_open_fills_at_the_open():
    frame = _runner_frame(
        highs=[101.0, 101.0, 130.0, 96.0],
        lows=[99.0, 99.0, 99.0, 90.0],
        opens=[100.0, 100.0, 100.0, 95.0],  # opens far below the 115 trailing stop
    )
    trades, _ = backtest_strategy(frame, warmup_bars=0, trailing_atr=1.5, breakeven_after_r=0.0, trend_filter="price", min_entry_er=0.0)
    trade = trades.iloc[0]
    assert trade["exit_reason"] == "atr_trailing_stop_gap"
    assert trade["raw_exit_price"] == pytest.approx(95.0)  # the open, not the stop level
    assert trade["exit_time"] == frame["hour_start"].iloc[3]


def test_a_stop_set_from_a_bar_cannot_also_trigger_on_that_bar():
    # Bar 2 makes the high that arms the stop AND a low beneath it; the stop must not fire there.
    frame = _runner_frame(
        highs=[101.0, 101.0, 130.0, 126.0],
        lows=[99.0, 99.0, 100.0, 110.0],  # bar 2 low of 100 sits below the 115 stop
        opens=[100.0, 100.0, 100.0, 125.0],
    )
    trades, _ = backtest_strategy(frame, warmup_bars=0, trailing_atr=1.5, breakeven_after_r=0.0, trend_filter="price", min_entry_er=0.0)
    # An intrabar stop is stamped at the bar close; a gap exit at the open.
    assert trades.iloc[0]["exit_time"] == frame["timestamp"].iloc[3]  # bar 3, not bar 2


def test_stops_disabled_reproduces_the_bare_crossover():
    frame = _runner_frame(
        highs=[101.0, 101.0, 130.0, 126.0],
        lows=[99.0, 99.0, 99.0, 110.0],
        opens=[100.0, 100.0, 100.0, 125.0],
    )
    trades, _ = backtest_strategy(frame, warmup_bars=0, **BARE)
    assert trades.iloc[0]["exit_reason"] == "data_end"
    assert pd.isna(trades.iloc[0]["trailing_stop_at_exit"])


# --------------------------------------------------- trend filter (feature 2)


def _cross_frame(ma200: float, slope: float) -> pd.DataFrame:
    return synthetic_cross_frame(
        [100.0] * 6,
        kama_fast=[90.0, 105.0, 106.0, 107.0, 108.0, 109.0],
        kama_slow=[100.0] * 6,
        ma200=[ma200] * 6,
        ma200_slope=slope,
    )


@pytest.mark.parametrize(
    "mode, ma200, slope, expected",
    [
        # close is 100 throughout; ma200 below means "price above MA".
        ("slope", 50.0, 1.0, 1),    # rising MA -> allowed
        ("slope", 50.0, -1.0, 0),   # falling MA -> blocked even though price is above it
        ("slope", 200.0, 1.0, 1),   # slope mode ignores price position
        ("price", 200.0, 1.0, 0),   # price mode blocks when below the MA
        ("price", 50.0, -1.0, 1),   # price mode ignores a falling MA
        ("both", 50.0, -1.0, 0),
        ("both", 50.0, 1.0, 1),
        ("none", 200.0, -1.0, 1),
    ],
)
def test_trend_filter_modes(mode, ma200, slope, expected):
    trades, _ = backtest_strategy(
        _cross_frame(ma200, slope), warmup_bars=0, trend_filter=mode,
        trailing_atr=0.0, breakeven_after_r=0.0, min_entry_er=0.0,
    )
    assert len(trades) == expected


def test_min_slope_threshold_is_respected():
    frame = _cross_frame(50.0, 0.4)
    assert len(backtest_strategy(frame, warmup_bars=0, trend_filter="slope", min_ma200_slope=0.2,
                                 trailing_atr=0.0, breakeven_after_r=0.0, min_entry_er=0.0)[0]) == 1
    assert len(backtest_strategy(frame, warmup_bars=0, trend_filter="slope", min_ma200_slope=0.8,
                                 trailing_atr=0.0, breakeven_after_r=0.0, min_entry_er=0.0)[0]) == 0


def test_nan_slope_blocks_entry_in_slope_mode():
    frame = _cross_frame(50.0, 1.0)
    frame["ma200_slope"] = np.nan
    trades, _ = backtest_strategy(frame, warmup_bars=0, trend_filter="slope",
                                  trailing_atr=0.0, breakeven_after_r=0.0, min_entry_er=0.0)
    assert trades.empty


def test_add_kama_features_computes_the_ma_slope():
    rows = [{"open": 100.0 + step, "close": 500.0, "high": 600.0, "low": 50.0} for step in range(8)]
    frame = add_kama_features(
        make_hourly(rows), kama_fast_length=2, kama_slow_length=4,
        ma200_length=3, ma200_source="open", ma200_slope_hours=2, risk_atr_length=2,
    )
    # SMA(3) of a +1/bar ramp rises 1.0 per bar; over 2 bars that is +2 on a base of 101.
    assert frame["ma200_slope"].iloc[4] == pytest.approx((103.0 / 101.0 - 1.0) * 100.0)
    assert frame["ma200_slope"].iloc[:4].isna().all()


@pytest.mark.parametrize("kwargs", [
    {"trend_filter": "sideways"}, {"trailing_atr": -1.0}, {"breakeven_after_r": -0.5},
])
def test_backtest_strategy_rejects_invalid_protection_settings(kwargs):
    frame = _cross_frame(50.0, 1.0)
    with pytest.raises(ValueError):
        backtest_strategy(frame, warmup_bars=0, **kwargs)


# ------------------------------------------------------- chop gate (er_fast)


def test_chop_gate_blocks_a_crossover_in_low_efficiency():
    closes = [100.0] * 6
    fast = [90.0, 105.0, 106.0, 107.0, 108.0, 109.0]
    slow = [100.0] * 6
    choppy = synthetic_cross_frame(closes, fast, slow, ma200=[50.0] * 6, er_fast=0.10)
    trending = synthetic_cross_frame(closes, fast, slow, ma200=[50.0] * 6, er_fast=0.55)
    assert backtest_strategy(choppy, warmup_bars=0, min_entry_er=0.30)[0].empty
    assert len(backtest_strategy(trending, warmup_bars=0, min_entry_er=0.30)[0]) == 1


def test_chop_gate_threshold_is_inclusive_and_disablable():
    frame = synthetic_cross_frame(
        [100.0] * 6, [90.0, 105.0, 106.0, 107.0, 108.0, 109.0], [100.0] * 6,
        ma200=[50.0] * 6, er_fast=0.30,
    )
    assert len(backtest_strategy(frame, warmup_bars=0, min_entry_er=0.30)[0]) == 1  # >=, not >
    assert backtest_strategy(frame, warmup_bars=0, min_entry_er=0.31)[0].empty
    assert len(backtest_strategy(frame, warmup_bars=0, min_entry_er=0.0)[0]) == 1


def test_chop_gate_does_not_block_exits():
    # Enters on a high-ER cross, then the market goes choppy and the bearish cross must still fire.
    frame = synthetic_cross_frame(
        [100.0] * 7,
        kama_fast=[90.0, 105.0, 106.0, 95.0, 94.0, 93.0, 92.0],
        kama_slow=[100.0] * 7,
        ma200=[50.0] * 7,
        er_fast=[1.0, 1.0, 0.01, 0.01, 0.01, 0.01, 0.01],
    )
    trades, _ = backtest_strategy(frame, warmup_bars=0, min_entry_er=0.30)
    assert len(trades) == 1
    assert trades.iloc[0]["exit_reason"] == "kama_bearish_cross"


def test_nan_er_blocks_entry_when_the_gate_is_armed():
    frame = synthetic_cross_frame(
        [100.0] * 6, [90.0, 105.0, 106.0, 107.0, 108.0, 109.0], [100.0] * 6, ma200=[50.0] * 6,
    )
    frame["er_fast"] = np.nan
    assert backtest_strategy(frame, warmup_bars=0, min_entry_er=0.30)[0].empty
    assert len(backtest_strategy(frame, warmup_bars=0, min_entry_er=0.0)[0]) == 1


@pytest.mark.parametrize("value", [-0.1, 1.1])
def test_backtest_strategy_rejects_out_of_range_er(value):
    frame = _cross_frame(50.0, 1.0)
    with pytest.raises(ValueError):
        backtest_strategy(frame, warmup_bars=0, min_entry_er=value)
