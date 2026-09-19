#!/usr/bin/env python
"""Chart high-trade-rate reversal bars from TMF 2,000-contract volume bars."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
from plotly.subplots import make_subplots

try:
    from .tick_snr_indicator import DEFAULT_SOURCE, build_volume_bars, load_ticks
except ImportError:
    from tick_snr_indicator import DEFAULT_SOURCE, build_volume_bars, load_ticks


DEFAULT_CHART = Path(__file__).resolve().parents[1] / "txf_tick" / "TMF_202608_dense_reversal_bars.html"


def detect_dense_reversals(
    bars: pd.DataFrame,
    reversal_lookback_bars: int,
    density_window: int,
    density_quantile: float,
) -> pd.DataFrame:
    result = bars.copy()
    result["duration_seconds"] = (
        result["timestamp"] - result["bar_start_time"]
    ).dt.total_seconds().clip(lower=1)
    result["contracts_per_second"] = result["volume"] / result["duration_seconds"]
    result["density_threshold"] = (
        result["contracts_per_second"]
        .rolling(density_window, min_periods=density_window)
        .quantile(density_quantile)
        .shift(1)
    )
    result["dense"] = result["contracts_per_second"] >= result["density_threshold"]
    result["close_position"] = (result["close"] - result["low"]) / (result["high"] - result["low"]).replace(0, np.nan)
    result["recent_low"] = result["low"] <= result["low"].rolling(
        reversal_lookback_bars,
        min_periods=reversal_lookback_bars,
    ).min()
    result["recent_high"] = result["high"] >= result["high"].rolling(
        reversal_lookback_bars,
        min_periods=reversal_lookback_bars,
    ).max()
    result["bullish_reversal"] = (
        result["dense"]
        & result["recent_low"]
        & (result["close"] > result["open"])
        & (result["close_position"] >= 0.5)
    )
    result["bearish_reversal"] = (
        result["dense"]
        & result["recent_high"]
        & (result["close"] < result["open"])
        & (result["close_position"] <= 0.5)
    )
    return result


def save_chart(bars: pd.DataFrame, output: Path, volume_bar_size: float) -> None:
    figure = make_subplots(
        rows=2,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.04,
        row_heights=[0.75, 0.25],
        subplot_titles=("Price and dense reversals", "Trade rate"),
    )
    figure.add_trace(
        go.Candlestick(
            x=bars["timestamp"],
            open=bars["open"],
            high=bars["high"],
            low=bars["low"],
            close=bars["close"],
            name=f"{volume_bar_size:,.0f}-contract bars",
        ),
        row=1,
        col=1,
    )
    figure.add_trace(
        go.Bar(
            x=bars["timestamp"],
            y=bars["contracts_per_second"],
            name="Contracts per second",
            marker_color="#607d8b",
        ),
        row=2,
        col=1,
    )
    figure.add_trace(
        go.Scatter(
            x=bars["timestamp"],
            y=bars["density_threshold"],
            mode="lines",
            name="Prior density threshold",
            line={"color": "#f9a825", "width": 1.5},
        ),
        row=2,
        col=1,
    )

    for column, color, symbol, y_column, name in (
        ("bullish_reversal", "#00897b", "triangle-up", "low", "Bullish dense reversal"),
        ("bearish_reversal", "#d32f2f", "triangle-down", "high", "Bearish dense reversal"),
    ):
        subset = bars[bars[column]]
        figure.add_trace(
            go.Scatter(
                x=subset["timestamp"],
                y=subset[y_column],
                mode="markers",
                name=name,
                marker={"color": color, "size": 12, "symbol": symbol},
                customdata=np.column_stack(
                    [
                        subset["duration_seconds"],
                        subset["contracts_per_second"],
                        subset["density_threshold"],
                        subset["close_position"],
                    ]
                ),
                hovertemplate=(
                    "Time: %{x}<br>Price: %{y}<br>Bar duration: %{customdata[0]:.0f}s"
                    "<br>Trade rate: %{customdata[1]:.1f} contracts/s"
                    "<br>Prior threshold: %{customdata[2]:.1f} contracts/s"
                    "<br>Close position: %{customdata[3]:.2f}<extra></extra>"
                ),
            ),
            row=1,
            col=1,
        )

    figure.update_layout(
        title=f"TMF Dense Trade Reversals ({volume_bar_size:,.0f}-contract volume bars)",
        xaxis_rangeslider_visible=False,
        barmode="overlay",
    )
    figure.update_yaxes(title_text="Price", row=1, col=1)
    figure.update_yaxes(title_text="Contracts / second", row=2, col=1)
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(output, include_plotlyjs=True)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a dense-trade reversal chart from TMF ticks.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--chart", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--input-encoding", default="utf-8-sig")
    parser.add_argument("--volume-bar-size", type=float, default=2000)
    parser.add_argument("--lookback-bars", type=int, default=5)
    parser.add_argument("--density-window", type=int, default=50)
    parser.add_argument("--density-quantile", type=float, default=0.75)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    ticks = load_ticks(args.source, args.input_encoding)
    bars = build_volume_bars(ticks, args.volume_bar_size)
    bars = detect_dense_reversals(
        bars,
        args.lookback_bars,
        args.density_window,
        args.density_quantile,
    )
    save_chart(bars, args.chart, args.volume_bar_size)
    bullish = int(bars["bullish_reversal"].sum())
    bearish = int(bars["bearish_reversal"].sum())
    print(f"volume_bars={len(bars)} bullish_reversals={bullish} bearish_reversals={bearish}")
    print(f"chart_html={args.chart}")


if __name__ == "__main__":
    main()
