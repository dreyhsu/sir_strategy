from __future__ import annotations

from datetime import date

import numpy as np
import pandas as pd

from snr.src.backtest_tmf_dense_long import add_adaptive_supertrend, backtest_long_only, discover_daily_sources


def test_discover_daily_sources_accepts_csv_and_zip_and_prefers_zip(tmp_path) -> None:
    for name in [
        "Daily_2026_08_04.csv",
        "Daily_2026_08_05.csv",
        "Daily_2026_08_06.csv",
        "Daily_2026_08_06.zip",
        "Daily_2026_08_07.zip",
        "Daily_invalid.csv",
    ]:
        (tmp_path / name).touch()

    sources = discover_daily_sources(tmp_path, date(2026, 8, 5), date(2026, 8, 7))

    assert [path.name for path in sources] == [
        "Daily_2026_08_05.csv",
        "Daily_2026_08_06.zip",
        "Daily_2026_08_07.zip",
    ]


def make_bars(
    lows: list[float],
    closes: list[float],
    directions: list[float],
    signals: list[bool] | None = None,
    session_ids: list[str] | None = None,
) -> pd.DataFrame:
    count = len(lows)
    timestamps = pd.date_range("2026-09-01 09:00:00", periods=count, freq="min")
    opens = [100.0] * count
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "bar_start_time": timestamps - pd.Timedelta(seconds=30),
            "open": opens,
            "high": [max(open_price, close) + 2 for open_price, close in zip(opens, closes)],
            "low": lows,
            "close": closes,
            "session_id": session_ids or ["2026-09-01 day"] * count,
            "bullish_reversal": signals or [False] * count,
            "supertrend": [99.0 if direction == 1 else 105.0 for direction in directions],
            "supertrend_direction": directions,
            "adaptive_multiplier": [3.0] * count,
        }
    )


def test_entry_bar_low_activates_on_following_bar_and_stop_has_priority() -> None:
    bars = make_bars(
        lows=[98.0, 95.0, 94.0],
        closes=[101.0, 102.0, 96.0],
        directions=[1.0, 1.0, -1.0],
        signals=[True, False, False],
    )

    trades = backtest_long_only(bars)

    assert len(trades) == 1
    trade = trades.iloc[0]
    assert trade["entry_bar_low"] == 95.0
    assert trade["initial_stop"] == 95.0
    assert trade["exit_price"] == 95.0
    assert trade["exit_reason"] == "entry_bar_low_stop"
    assert trade["exit_time"] == bars.iloc[2]["timestamp"]


def test_bearish_supertrend_flip_exits_at_flip_bar_close() -> None:
    bars = make_bars(
        lows=[98.0, 95.0, 96.0],
        closes=[101.0, 102.0, 104.0],
        directions=[1.0, 1.0, -1.0],
        signals=[True, False, False],
    )

    trade = backtest_long_only(bars).iloc[0]

    assert trade["exit_reason"] == "adaptive_volume_supertrend_bearish_flip"
    assert trade["exit_price"] == 104.0
    assert trade["exit_time"] == bars.iloc[2]["timestamp"]


def test_position_is_closed_at_session_end() -> None:
    bars = make_bars(
        lows=[98.0, 95.0, 98.0],
        closes=[101.0, 103.0, 110.0],
        directions=[1.0, 1.0, 1.0],
        signals=[True, False, False],
        session_ids=["2026-09-01 day", "2026-09-01 day", "2026-09-02 night"],
    )

    trade = backtest_long_only(bars).iloc[0]

    assert trade["session_id"] == "2026-09-01 day"
    assert trade["exit_reason"] == "session_end"
    assert trade["exit_price"] == 103.0


def test_zero_risk_trade_keeps_trade_and_reports_nan_r() -> None:
    bars = make_bars(
        lows=[98.0, 100.0],
        closes=[101.0, 102.0],
        directions=[1.0, 1.0],
        signals=[True, False],
    )

    trade = backtest_long_only(bars).iloc[0]

    assert trade["risk_r"] == 0.0
    assert np.isnan(trade["pnl_r"])


def test_adaptive_supertrend_resets_at_each_session() -> None:
    first_times = pd.date_range("2026-09-01 09:00:00", periods=5, freq="min")
    second_times = pd.date_range("2026-09-01 15:00:00", periods=5, freq="min")
    closes = [100.0, 101.0, 102.0, 103.0, 104.0] * 2
    bars = pd.DataFrame(
        {
            "timestamp": first_times.append(second_times),
            "open": closes,
            "high": [value + 2 for value in closes],
            "low": [value - 2 for value in closes],
            "close": closes,
            "session_id": ["2026-09-01 day"] * 5 + ["2026-09-02 night"] * 5,
        }
    )

    result = add_adaptive_supertrend(bars, 3, 3.0, 0.8, 2, 0.25, 0.8, 2)
    second = result[result["session_id"] == "2026-09-02 night"].reset_index(drop=True)

    assert second.loc[:1, "atr"].isna().all()
    assert second.loc[:1, "supertrend_direction"].isna().all()
    pd.testing.assert_series_equal(
        result.loc[:4, "supertrend"].reset_index(drop=True),
        second["supertrend"],
        check_names=False,
    )
