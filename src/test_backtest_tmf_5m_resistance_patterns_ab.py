from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import pytest

from backtest_tmf_5m_resistance_patterns_ab import (
    TRADE_COLUMNS,
    add_resistance_pattern_signals,
    backtest_single_position_short,
    build_five_minute_bars,
    write_chart,
    write_report,
)


def make_ticks(times, prices, session_id="2026-09-09 day") -> pd.DataFrame:
    timestamps = pd.to_datetime(times)
    return pd.DataFrame(
        {
            "tick_id": range(len(times)),
            "timestamp": timestamps,
            "price": prices,
            "quantity": [1.0] * len(times),
            "session_id": [session_id] * len(times),
            "session_type": [session_id.split()[1]] * len(times),
            "session_date": [pd.Timestamp(session_id.split()[0]).date()] * len(times),
        }
    )


def make_bars(opens, highs, lows, closes, start="2026-09-09 09:00:00", session_id="2026-09-09 day"):
    starts = pd.date_range(start, periods=len(opens), freq="5min")
    return pd.DataFrame(
        {
            "bar_start": starts,
            "timestamp": starts + pd.Timedelta(minutes=5),
            "open": opens,
            "high": highs,
            "low": lows,
            "close": closes,
            "volume": [10.0] * len(opens),
            "tick_start_id": range(len(opens)),
            "tick_end_id": range(len(opens)),
            "session_id": [session_id] * len(opens),
            "session_type": [session_id.split()[1]] * len(opens),
            "session_date": [pd.Timestamp(session_id.split()[0]).date()] * len(opens),
        }
    )


def make_zone(created="2026-09-09 08:00:00", broken=pd.NaT, bottom=100.0, top=110.0):
    return pd.DataFrame(
        {
            "zone_id": [7], "zone_type": ["resistance"], "created_time": [pd.Timestamp(created)],
            "broken_time": [broken], "bottom": [bottom], "top": [top],
        }
    )


def make_signal_bars(pattern="A", signal_time="2026-09-09 09:05:00", stop=110.0, close=100.0):
    start = pd.Timestamp(signal_time) - pd.Timedelta(minutes=5)
    return pd.DataFrame(
        {
            "bar_start": [start], "timestamp": [pd.Timestamp(signal_time)], "open": [101.0],
            "high": [105.0], "low": [99.0], "close": [close], "volume": [10.0],
            "tick_start_id": [0], "tick_end_id": [0], "session_id": ["2026-09-09 day"],
            "short_signal": [True], "pattern_type": [pattern], "zone_id": [7],
            "resistance_low": [100.0], "resistance_high": [110.0], "initial_stop": [stop],
            "h1": [120.0 if pattern == "B" else np.nan], "l1": [100.0 if pattern == "B" else np.nan],
            "h2": [105.0 if pattern == "B" else np.nan],
            "strongest_red_time": [pd.Timestamp("2026-09-09 08:55:00") if pattern == "A" else pd.NaT],
            "strongest_red_low": [101.0 if pattern == "A" else np.nan],
            "strongest_red_body": [3.0 if pattern == "A" else np.nan],
        }
    )


def test_build_five_minute_bars_aligns_sessions_and_discards_partial_tail() -> None:
    day = make_ticks(
        ["2026-09-09 08:45:01", "2026-09-09 08:49:59", "2026-09-09 08:50:01", "2026-09-09 08:52:00"],
        [100.0, 102.0, 101.0, 103.0],
    )
    night = make_ticks(
        ["2026-09-09 15:00:01", "2026-09-09 15:05:01"], [200.0, 201.0], "2026-09-10 night"
    )
    ticks = pd.concat([day, night], ignore_index=True)
    ticks["tick_id"] = range(len(ticks))

    bars = build_five_minute_bars(ticks)

    assert bars["bar_start"].tolist() == list(pd.to_datetime(["2026-09-09 08:45:00", "2026-09-09 15:00:00"]))
    assert bars["session_id"].tolist() == ["2026-09-09 day", "2026-09-10 night"]
    assert bars.iloc[0][["open", "high", "low", "close"]].tolist() == [100.0, 102.0, 100.0, 102.0]


def test_pattern_a_can_confirm_on_breakout_bar_and_uses_prior_bars_only() -> None:
    bars = make_bars(
        [100, 101, 102, 103, 104, 112], [102, 103, 106, 105, 106, 116],
        [99, 100, 101, 102, 103, 98], [101, 102, 105, 104, 105, 100],
    )

    result = add_resistance_pattern_signals(bars, make_zone(), failure_window_bars=3)
    signal = result.iloc[-1]

    assert bool(signal["short_signal"])
    assert signal["pattern_type"] == "A"
    assert signal["strongest_red_low"] == 101.0
    assert signal["strongest_red_body"] == 3.0
    assert signal["initial_stop"] == 121.0


def test_pattern_a_requires_zone_confirmed_before_bar_start_and_a_red_bar() -> None:
    bars = make_bars(
        [105, 105, 105, 105, 105, 112], [106, 106, 106, 106, 106, 116],
        [103, 103, 103, 103, 103, 98], [104, 104, 104, 104, 104, 100],
    )
    unavailable = make_zone(created=str(bars.iloc[-1]["bar_start"]))

    result = add_resistance_pattern_signals(bars, unavailable)

    assert not bool(result["short_signal"].any())
    assert not bool(add_resistance_pattern_signals(bars, make_zone())["short_signal"].any())


def test_pattern_a_body_percent_can_select_a_different_red_bar() -> None:
    bars = make_bars(
        [100, 200, 100, 100, 100, 112], [111, 219, 103, 103, 103, 116],
        [90, 180, 98, 98, 98, 85], [110, 218, 102, 102, 102, 89],
    )
    by_body = add_resistance_pattern_signals(bars, make_zone(), strongest_red_mode="body").iloc[-1]
    by_percent = add_resistance_pattern_signals(bars, make_zone(), strongest_red_mode="body_percent").iloc[-1]

    assert by_body["strongest_red_body"] == 18.0
    assert by_percent["strongest_red_body"] == 10.0


@pytest.mark.parametrize("window,expected", [(1, False), (2, False), (3, True), (4, True)])
def test_pattern_a_failure_window_includes_breakout_bar(window: int, expected: bool) -> None:
    bars = make_bars(
        [100, 101, 102, 103, 104, 112, 108, 107],
        [102, 103, 106, 105, 106, 116, 111, 109],
        [99, 100, 101, 102, 103, 106, 104, 98],
        [101, 102, 105, 104, 105, 110, 108, 100],
    )
    result = add_resistance_pattern_signals(bars, make_zone(), failure_window_bars=window)
    assert bool(result.iloc[-1]["short_signal"]) is expected


def test_pattern_b_waits_for_h2_right_confirmation_then_breaks_l1() -> None:
    bars = make_bars(
        [108, 115, 110, 105, 106, 108, 105],
        [110, 120, 115, 108, 110, 112, 109],
        [105, 110, 107, 100, 104, 106, 98],
        [108, 115, 110, 105, 106, 108, 99],
    )

    result = add_resistance_pattern_signals(
        bars, make_zone(), strongest_red_lookback=3, pivot_strength=1,
        lower_high_min_difference=5, pattern_b_window_bars=7,
    )

    assert not bool(result.iloc[:-1]["short_signal"].any())
    signal = result.iloc[-1]
    assert signal["pattern_type"] == "B"
    assert (signal["h1"], signal["l1"], signal["h2"], signal["initial_stop"]) == (120.0, 100.0, 112.0, 117.0)


def test_pattern_b_expires_and_unconfirmed_h2_never_signals() -> None:
    bars = make_bars(
        [108, 115, 110, 105, 106, 108], [110, 120, 115, 108, 110, 112],
        [105, 110, 107, 100, 104, 106], [108, 115, 110, 105, 106, 99],
    )
    result = add_resistance_pattern_signals(
        bars, make_zone(), strongest_red_lookback=3, pivot_strength=1,
        lower_high_min_difference=5, pattern_b_window_bars=6,
    )
    assert not bool(result["short_signal"].any())


def test_backtest_enters_next_bar_open_and_exits_at_two_r_target() -> None:
    ticks = make_ticks(
        ["2026-09-09 09:04:59", "2026-09-09 09:05:00", "2026-09-09 09:06:00"],
        [101.0, 100.0, 79.0],
    )
    trades, groups, _, summary = backtest_single_position_short(ticks, make_signal_bars())

    trade = trades.iloc[0]
    assert trade["entry_time"] == pd.Timestamp("2026-09-09 09:05:00")
    assert trade["raw_entry_price"] == 100.0
    assert trade["entry_fill_price"] == 98.0
    assert trade["target_price"] == 80.0
    assert trade["exit_fill_price"] == 81.0
    assert trade["net_ntd"] == 170.0
    assert trade["exit_reason"] == "risk_reward_target"
    assert len(groups) == 1
    assert summary["target_exits"] == 1


def test_backtest_cancels_entry_when_open_has_breached_stop() -> None:
    ticks = make_ticks(["2026-09-09 09:04:59", "2026-09-09 09:05:00"], [100.0, 110.0])
    trades, _, _, summary = backtest_single_position_short(ticks, make_signal_bars(stop=110.0))
    assert trades.empty
    assert summary["canceled_stop_breached"] == 1


def test_pending_entry_is_canceled_at_session_boundary() -> None:
    day = make_ticks(["2026-09-09 13:44:59"], [100.0])
    night = make_ticks(["2026-09-09 15:00:00"], [99.0], "2026-09-10 night")
    ticks = pd.concat([day, night], ignore_index=True)
    ticks["tick_id"] = range(len(ticks))
    signal = make_signal_bars(signal_time="2026-09-09 13:45:00")

    trades, _, _, summary = backtest_single_position_short(ticks, signal)

    assert trades.empty
    assert summary["canceled_session"] == 1


def test_reclaim_close_exits_at_next_five_minute_open_and_ignores_same_bar_signal() -> None:
    ticks = make_ticks(
        ["2026-09-09 09:04:59", "2026-09-09 09:05:00", "2026-09-09 09:09:59", "2026-09-09 09:10:00"],
        [101.0, 100.0, 108.0, 109.0],
    )
    bars = pd.concat([make_signal_bars(), make_signal_bars("B", "2026-09-09 09:10:00", stop=120.0, close=111.0)], ignore_index=True)
    trades, _, _, summary = backtest_single_position_short(ticks, bars)

    assert len(trades) == 1
    assert trades.iloc[0]["exit_time"] == pd.Timestamp("2026-09-09 09:10:00")
    assert trades.iloc[0]["exit_reason"] == "resistance_reclaimed"
    assert summary["ignored_while_occupied"] == 1


def test_empty_outputs_and_report_chart_are_generated(tmp_path) -> None:
    ticks = make_ticks(["2026-09-09 09:00:00", "2026-09-09 09:01:00"], [100.0, 100.0])
    bars = make_signal_bars().assign(short_signal=False)
    trades, groups, samples, summary = backtest_single_position_short(ticks, bars)
    args = argparse.Namespace(
        product="TMF", contract_month="202609", start_date=pd.Timestamp("2026-09-09").date(),
        end_date=pd.Timestamp("2026-09-09").date(), initial_capital_ntd=400_000.0,
        point_value_ntd=10.0, slippage_points=2.0, breakout_points=5.0,
        failure_window_bars=3, strongest_red_lookback=5, strongest_red_mode="body",
        stop_buffer_points=5.0, pattern_b_window_bars=12, pivot_strength=2,
        lower_high_min_difference=5.0, risk_reward=2.0,
    )
    report = tmp_path / "report.md"
    chart = tmp_path / "chart.html"

    write_report(report, args, [], ticks, pd.DataFrame(), bars, trades, groups, summary)
    write_chart(chart, make_zone(), trades, samples, 400_000.0)

    assert list(trades.columns) == TRADE_COLUMNS
    assert "Pattern A / B signals | 0 / 0" in report.read_text(encoding="utf-8")
    assert chart.stat().st_size > 0
