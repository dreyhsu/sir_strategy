from __future__ import annotations

import numpy as np
import pandas as pd

from backtest_btcusdt_1h_trendline_breakout_long import (
    add_features,
    backtest_strategy,
    load_span,  # noqa: F401  (import-smoke)
)


ONE_HOUR = pd.Timedelta(hours=1)


def _frame_from_prices(highs, lows, closes, opens=None) -> pd.DataFrame:
    n = len(closes)
    base = pd.Timestamp("2026-02-10 00:59:59", tz="UTC")
    hour0 = pd.Timestamp("2026-02-10 00:00:00", tz="UTC")
    opens = opens if opens is not None else [closes[0]] + list(closes[:-1])
    return pd.DataFrame(
        {
            "timestamp": [base + i * ONE_HOUR for i in range(n)],
            "hour_start": [hour0 + i * ONE_HOUR for i in range(n)],
            "session_id": "continuous",
            "open": [float(x) for x in opens],
            "high": [float(x) for x in highs],
            "low": [float(x) for x in lows],
            "close": [float(x) for x in closes],
            "volume": 1.0,
        }
    )


def _driven_frame() -> pd.DataFrame:
    """Two descending swing highs, a swing-low close, then a breakout + 2R run.

    Line through H1(idx3, 120) and H2(idx9, 112): slope = (112-120)/(9-3) = -1.333/bar.
    """
    n = 20
    highs = [100.0] * n
    closes = [104.0] * n
    highs[3] = 120.0          # H1 swing high (confirmed at idx5, k=2)
    highs[9] = 112.0          # H2 swing high, lower than H1 (confirmed at idx11)
    closes[12] = 100.0        # swing-low close (confirmed at idx14) → defines R
    closes[15] = 101.0        # last close below the line (line@15 ≈ 104.0)
    closes[16] = 112.0        # breakout close (line@16 ≈ 102.7)
    highs[16] = 113.0
    lows = [c - 1.0 for c in closes]  # lows never dip to the stop during the winning run
    lows[12] = 99.0
    opens = [closes[0]] + list(closes[:-1])
    opens[17] = 112.0         # entry fills on this open
    highs[17] = 118.0         # rallies toward the 2R target
    highs[18] = 140.0         # clears target 136
    return _frame_from_prices(highs, lows, closes, opens)


def test_end_to_end_breakout_long_hits_2r():
    frame = add_features(_driven_frame(), atr_length=14, swing_k=2)
    trades, state, lines = backtest_strategy(
        frame, lookback=48, swing_k=2, buffer_atr=0.0, max_line_slope=0.0,
        target_r=2.0, slippage_bps=0.0, taker_fee_rate=0.0, position_btc=1.0,
    )
    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["raw_entry_price"] == 112.0           # idx17 open
    assert trade["initial_stop"] == 100.0              # swing-low close at idx12
    assert np.isclose(trade["initial_risk"], 12.0)     # 112 - 100
    assert np.isclose(trade["target_price"], 136.0)    # 112 + 2*12
    assert trade["exit_reason"] == "target_2r"
    assert np.isclose(trade["net_r"], 2.0)
    assert lines.iloc[0]["slope"] < 0
    assert (lines["status"] == "entered").any()


def test_ascending_line_blocks_entry():
    # Later swing high is HIGHER than the earlier one → ascending line → no long breakout.
    n = 20
    highs = [100.0] * n
    lows = [90.0] * n
    closes = [95.0] * n
    highs[3] = 108.0   # H1
    highs[9] = 120.0   # H2 higher than H1 → slope > 0
    closes[16] = 125.0
    frame = add_features(_frame_from_prices(highs, lows, closes), atr_length=14, swing_k=2)
    trades, state, _ = backtest_strategy(frame, lookback=48, swing_k=2, max_line_slope=0.0)
    assert trades.empty
    assert int(state["entry_signal"].sum()) == 0


def _realistic_month() -> pd.DataFrame:
    rng = np.random.default_rng(11)
    n = 900
    base = pd.Timestamp("2026-02-01 00:59:59", tz="UTC")
    hour0 = pd.Timestamp("2026-02-01 00:00:00", tz="UTC")
    close = 100.0 + np.cumsum(rng.normal(0, 1.5, n))
    high = close + rng.uniform(0.3, 2.0, n)
    low = close - rng.uniform(0.3, 2.0, n)
    open_ = np.r_[close[0], close[:-1]]
    bars = pd.DataFrame(
        {
            "timestamp": [base + i * ONE_HOUR for i in range(n)],
            "hour_start": [hour0 + i * ONE_HOUR for i in range(n)],
            "session_id": "continuous",
            "open": open_, "high": high, "low": low, "close": close, "volume": 1.0,
        }
    )
    return add_features(bars, atr_length=14, swing_k=2)


def test_entry_signals_do_not_depend_on_future_bars():
    frame = _realistic_month()
    cut = 700
    swing_k = 2
    _, full_state, _ = backtest_strategy(frame, swing_k=swing_k)
    _, trunc_state, _ = backtest_strategy(frame.iloc[:cut].reset_index(drop=True), swing_k=swing_k)
    horizon = cut - swing_k - 1
    assert np.array_equal(
        full_state["entry_signal"].to_numpy()[:horizon],
        trunc_state["entry_signal"].to_numpy()[:horizon],
    )


def test_long_pnl_identity():
    trades, _, _ = backtest_strategy(_realistic_month(), swing_k=2)
    if not trades.empty:
        assert np.allclose(
            (trades["exit_price"] - trades["entry_price"]).to_numpy(),
            trades["net_points"].to_numpy(),
        )
