from __future__ import annotations

import numpy as np
import pandas as pd

from backtest_btcusdt_1h_trend_15m_macd_trendline_long import (
    add_15m_features,
    add_hourly_features,
    add_trend_filter,
    attach_hourly_features,
    backtest_strategy,
    macd,
    swing_high_flags,
    swing_low_flags,
)


FIFTEEN_MIN = pd.Timedelta(minutes=15)
ONE_HOUR = pd.Timedelta(hours=1)


# --------------------------------------------------------------------------------------
# Indicator helpers
# --------------------------------------------------------------------------------------
def test_macd_matches_manual_ewm_and_is_causal():
    close = pd.Series([100.0, 101, 102, 101, 100, 99, 100, 102, 104, 103, 101, 100])
    dif, dea = macd(close, fast=3, slow=6, signal=3)
    ema_fast = close.ewm(span=3, adjust=False).mean()
    ema_slow = close.ewm(span=6, adjust=False).mean()
    expected_dif = ema_fast - ema_slow
    expected_dea = expected_dif.ewm(span=3, adjust=False).mean()
    pd.testing.assert_series_equal(dif, expected_dif, check_names=False)
    pd.testing.assert_series_equal(dea, expected_dea, check_names=False)

    # Causality: changing a *future* close must not change an earlier DIF/DEA value.
    perturbed = close.copy()
    perturbed.iloc[-1] = 999.0
    dif2, dea2 = macd(perturbed, fast=3, slow=6, signal=3)
    assert np.allclose(dif.iloc[:-1], dif2.iloc[:-1])
    assert np.allclose(dea.iloc[:-1], dea2.iloc[:-1])


def test_swing_high_flags_strict_max_and_edges():
    high = np.array([1.0, 2, 5, 2, 1, 3, 9, 3, 1, 4, 4, 4], dtype=float)
    flags = swing_high_flags(high, k=2)
    assert flags[2]  # 5 is the strict max of indices 0..4
    assert flags[6]  # 9 is the strict max of indices 4..8
    assert not flags[0] and not flags[1]  # too close to the left edge to confirm
    assert not flags[-1] and not flags[-2]  # too close to the right edge
    # A flat top (ties) is not a strict swing high.
    assert not flags[9] and not flags[10]


def test_swing_low_flags_strict_min():
    low = np.array([9.0, 8, 3, 8, 9, 7, 1, 7, 9], dtype=float)
    flags = swing_low_flags(low, k=2)
    assert flags[2] and flags[6]
    assert not flags[0] and not flags[-1]


def test_trend_filter_requires_hourly_and_consecutive_15m_closes():
    # 10 bars, 1h MA fixed at 100, 1h close fixed at 101 (> MA).
    closes = [99, 99, 101, 101, 101, 101, 101, 101, 101, 101]  # first two below MA
    frame = pd.DataFrame(
        {"close": [float(c) for c in closes], "hourly_ma": 100.0, "hourly_close": 101.0}
    )
    out = add_trend_filter(frame, bars_above_window=7)
    ok = out["hourly_trend_ok"].tolist()
    # Need 7 consecutive 15m closes above MA. Run of above-MA starts at index 2, so the 7th
    # consecutive bar is index 8 → first True there.
    assert ok[:8] == [False] * 8
    assert ok[8] is True or ok[8] == True  # noqa: E712
    assert ok[9] == True  # noqa: E712
    # If the hourly close drops to/below MA, the filter is off regardless of the 15m run.
    frame2 = frame.copy()
    frame2["hourly_close"] = 100.0
    assert not add_trend_filter(frame2, bars_above_window=7)["hourly_trend_ok"].any()


# --------------------------------------------------------------------------------------
# Hand-built frame that deterministically drives the state machine to a long trade
# --------------------------------------------------------------------------------------
def _driven_frame() -> pd.DataFrame:
    n = 16
    base = pd.Timestamp("2026-02-10 00:14:59", tz="UTC")
    minute_start = pd.Timestamp("2026-02-10 00:00:00", tz="UTC")
    rows = []
    slope = -1.5  # line through H1(idx2,110) and H2(idx6,104): (104-110)/(6-2)
    for i in range(n):
        line_val = 110.0 + slope * (i - 2)
        high = low = open_ = close = 100.0
        if i == 2:          # H1 swing high
            high, open_, close, low = 110.0, 108.0, 109.0, 107.0
        elif i == 6:        # H2 swing high (lower than H1)
            high, open_, close, low = 104.0, 101.0, 102.0, 100.0
        elif 3 <= i <= 11:  # descending pullback, every close safely below the line
            close = line_val - 1.0
            open_ = close + 0.2
            high = close + 0.3
            low = min(close - 1.0, 94.0)
        elif i == 12:       # breakout close above line + buffer (line@12 = 95.0)
            close, open_, high, low = 96.0, 95.2, 96.2, 94.5
        elif i == 13:       # entry fills at this open
            open_, high, low, close = 96.0, 97.5, 95.8, 97.0
        elif i == 14:       # rallies into the 2R target
            open_, high, low, close = 97.0, 101.0, 96.8, 100.5
        elif i == 15:
            open_, high, low, close = 100.5, 101.0, 99.5, 100.0
        rows.append(
            {
                "timestamp": base + i * FIFTEEN_MIN,
                "minute_start": minute_start + i * FIFTEEN_MIN,
                "session_id": "continuous",
                "open": open_, "high": high, "low": low, "close": close,
                "atr15": 1.0,
                "dif": -0.5, "dea": -0.4,
                "cross_below_zero": i == 3,
                "cross_above_zero": False,
                "golden_cross_below": i == 9,
                "death_cross_below": False,
                "is_swing_high": i == 6,
                "is_swing_low": False,
                "hourly_ma": 90.0,
                "hourly_atr": 2.0,
                "hourly_trend_ok": True,
                "hourly_trend_invalidated": False,
            }
        )
    return pd.DataFrame(rows)


def test_end_to_end_long_entry_and_target():
    trades, state, lines = backtest_strategy(
        _driven_frame(), exit_mode="fixed_2r", swing_k=2, buffer_atr=0.15,
        slippage_bps=0.0, taker_fee_rate=0.0, position_btc=1.0,
    )
    assert len(trades) == 1
    trade = trades.iloc[0]
    # Entry is a long filled on the bar *after* the breakout (idx12 → idx13 open).
    assert trade["entry_time"] == pd.Timestamp("2026-02-10 03:15:00", tz="UTC")  # idx13 minute_start
    assert trade["raw_entry_price"] == 96.0
    assert trade["exit_reason"] == "fixed_target_2r"
    assert trade["net_usdt"] > 0
    assert trade["initial_risk"] > 0
    # Exactly one trend line was drawn and it is marked as the one we entered on.
    assert len(lines) == 1
    assert lines.iloc[0]["status"] == "entered"
    assert lines.iloc[0]["slope"] < 0
    assert bool(state["entry_signal"].sum() == 1)


def test_no_entry_when_prior_close_breaches_line():
    frame = _driven_frame()
    # Lift an in-between close above the trend line → the line is pre-breached, no entry.
    frame.loc[7, "close"] = 108.0
    trades, state, _ = backtest_strategy(frame, exit_mode="fixed_2r", swing_k=2)
    assert trades.empty
    assert int(state["entry_signal"].sum()) == 0


def test_hourly_filter_blocks_entry():
    frame = _driven_frame()
    frame["hourly_trend_ok"] = False
    trades, state, _ = backtest_strategy(frame, exit_mode="fixed_2r", swing_k=2)
    assert trades.empty
    assert int(state["entry_signal"].sum()) == 0


# --------------------------------------------------------------------------------------
# No-look-ahead: past signals are independent of future bars
# --------------------------------------------------------------------------------------
def _realistic_month() -> pd.DataFrame:
    rng = np.random.default_rng(7)
    n = 1500
    start = pd.Timestamp("2026-02-01 00:14:59", tz="UTC")
    minute0 = pd.Timestamp("2026-02-01 00:00:00", tz="UTC")
    drift = np.linspace(0, 40, n)
    noise = np.cumsum(rng.normal(0, 1.0, n))
    close = 100.0 + drift + noise
    high = close + rng.uniform(0.2, 1.2, n)
    low = close - rng.uniform(0.2, 1.2, n)
    open_ = np.r_[close[0], close[:-1]]
    bars = pd.DataFrame(
        {
            "timestamp": [start + i * FIFTEEN_MIN for i in range(n)],
            "minute_start": [minute0 + i * FIFTEEN_MIN for i in range(n)],
            "session_id": "continuous",
            "open": open_, "high": high, "low": low, "close": close,
            "volume": 1.0,
        }
    )
    hn = n // 4 + 5
    hstart = pd.Timestamp("2026-02-01 00:59:59", tz="UTC")
    hminute = pd.Timestamp("2026-02-01 00:00:00", tz="UTC")
    hclose = 100.0 + np.linspace(0, 40, hn) + np.cumsum(rng.normal(0, 1.0, hn))
    hourly = pd.DataFrame(
        {
            "timestamp": [hstart + i * ONE_HOUR for i in range(hn)],
            "hour_start": [hminute + i * ONE_HOUR for i in range(hn)],
            "session_id": "continuous",
            "open": hclose, "high": hclose + 1, "low": hclose - 1, "close": hclose, "volume": 1.0,
        }
    )
    feat = add_15m_features(bars, 12, 26, 9, 14, swing_k=2)
    hourly_feat = add_hourly_features(hourly, 20, 14)
    merged = attach_hourly_features(feat, hourly_feat).reset_index(drop=True)
    return add_trend_filter(merged, bars_above_window=7)


def test_entry_signals_do_not_depend_on_future_bars():
    frame = _realistic_month()
    cut = 1200
    swing_k = 2
    full_trades, full_state, _ = backtest_strategy(frame, swing_k=swing_k)
    truncated_trades, trunc_state, _ = backtest_strategy(frame.iloc[:cut].reset_index(drop=True), swing_k=swing_k)
    # Signals on bars safely before the cut (minus confirmation lag) must be identical.
    horizon = cut - swing_k - 1
    assert np.array_equal(
        full_state["entry_signal"].to_numpy()[:horizon],
        trunc_state["entry_signal"].to_numpy()[:horizon],
    )
    # Trades that both entered and exited before the horizon must match exactly.
    def closed_before(tr: pd.DataFrame) -> pd.DataFrame:
        if tr.empty:
            return tr
        return tr[tr["exit_time"] < frame.iloc[horizon]["timestamp"]].reset_index(drop=True)

    a, b = closed_before(full_trades), closed_before(truncated_trades)
    assert len(a) == len(b)
    if not a.empty:
        assert np.allclose(a["net_usdt"].to_numpy(), b["net_usdt"].to_numpy())
        assert np.array_equal(a["entry_time"].to_numpy(), b["entry_time"].to_numpy())


def test_trailing_mode_runs_and_produces_valid_schema():
    trades, _, _ = backtest_strategy(_realistic_month(), exit_mode="trailing_swinglow", swing_k=2)
    # Long P&L identity: net_points sign must agree with exit vs entry fills.
    if not trades.empty:
        recomputed = trades["exit_price"] - trades["entry_price"]
        assert np.allclose(recomputed.to_numpy(), trades["net_points"].to_numpy())
