"""Tests for ``trendln_btcusdt_1h_ohlc_chart``.

Kept small and fast: a synthetic OHLC frame drives the trendline computation and
figure building without reading large CSVs.
"""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import pytest

import trendln_btcusdt_1h_ohlc_chart as mod


def _synthetic_frame(n: int = 200) -> pd.DataFrame:
    """A gently oscillating uptrend so trendln finds multiple extrema."""
    rng = np.random.default_rng(42)
    t = np.arange(n)
    base = 100.0 + 0.3 * t + 8.0 * np.sin(t / 7.0)
    close = base + rng.normal(0, 0.5, n)
    open_ = np.r_[close[0], close[:-1]]
    high = np.maximum(open_, close) + rng.uniform(0.5, 2.0, n)
    low = np.minimum(open_, close) - rng.uniform(0.5, 2.0, n)
    timestamps = pd.date_range("2026-08-01", periods=n, freq="h", tz="UTC")
    return pd.DataFrame(
        {
            "timestamp": timestamps,
            "open": open_,
            "high": high,
            "low": low,
            "close": close,
            "volume": rng.uniform(1e6, 2e6, n),
        }
    )


@pytest.fixture(scope="module")
def frame() -> pd.DataFrame:
    return _synthetic_frame()


@pytest.fixture(scope="module")
def trendlines(frame: pd.DataFrame) -> dict:
    return mod.compute_trendlines(frame, window=50, accuracy=2)


def test_build_trendlines_returns_lines(trendlines: dict) -> None:
    assert trendlines["support"], "expected at least one support trendline"
    assert trendlines["resistance"], "expected at least one resistance trendline"
    for line in trendlines["support"] + trendlines["resistance"]:
        assert isinstance(line["x0"], pd.Timestamp)
        assert isinstance(line["x1"], pd.Timestamp)
        assert math.isfinite(line["y0"]) and math.isfinite(line["y1"])
        assert line["idx0"] < line["idx1"]


def test_line_values_match_slope_intercept(trendlines: dict) -> None:
    for line in trendlines["support"] + trendlines["resistance"]:
        expected_y0 = line["slope"] * line["idx0"] + line["intercept"]
        expected_y1 = line["slope"] * line["idx1"] + line["intercept"]
        assert line["y0"] == pytest.approx(expected_y0)
        assert line["y1"] == pytest.approx(expected_y1)


def test_figure_has_candlestick_and_lines(frame: pd.DataFrame, trendlines: dict) -> None:
    fig = mod.build_figure(frame, trendlines, title="test")
    candles = [t for t in fig.data if isinstance(t, go.Candlestick)]
    scatters = [t for t in fig.data if isinstance(t, go.Scatter)]
    assert len(candles) == 1
    assert len(scatters) >= 1


def test_write_html_creates_file(tmp_path, frame: pd.DataFrame, trendlines: dict) -> None:
    fig = mod.build_figure(frame, trendlines, title="test")
    out = tmp_path / "chart.html"
    fig.write_html(str(out), include_plotlyjs="cdn")
    assert out.is_file()
    text = out.read_text(encoding="utf-8")
    assert out.stat().st_size > 0
    assert "candlestick" in text.lower()


def test_default_output_path_single_vs_range() -> None:
    single = mod.default_output_path("2026-08", "2026-08")
    ranged = mod.default_output_path("2026-07", "2026-08")
    assert single.name == "BTCUSDT_2026-08_trendln_ohlc.html"
    assert ranged.name == "BTCUSDT_2026-07_to_2026-08_trendln_ohlc.html"
