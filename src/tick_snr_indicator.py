#!/usr/bin/env python
"""Find support and resistance zones from TMF 2,000-contract volume bars."""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "txf_tick" / "TMF_202608_transactions.csv"
DEFAULT_EVENTS = Path(__file__).resolve().parents[1] / "txf_tick" / "TMF_202608_volume_bar_snr.csv"
DEFAULT_CHART = Path(__file__).resolve().parents[1] / "txf_tick" / "TMF_202608_volume_bar_snr.html"
REQUIRED_COLUMNS = ["trade_date", "trade_time", "trade_price", "trade_quantity_b_s"]


def load_ticks(source: Path, encoding: str) -> pd.DataFrame:
    ticks = pd.read_csv(source, encoding=encoding, dtype=str)
    missing = [column for column in REQUIRED_COLUMNS if column not in ticks.columns]
    if missing:
        raise ValueError(f"Missing required columns: {missing}")

    ticks["trade_time"] = ticks["trade_time"].str.strip().str.zfill(6)
    ticks["timestamp"] = pd.to_datetime(
        ticks["trade_date"].str.strip() + ticks["trade_time"],
        format="%Y%m%d%H%M%S",
        errors="coerce",
    )
    ticks["price"] = pd.to_numeric(ticks["trade_price"].str.strip(), errors="coerce")
    ticks["quantity"] = pd.to_numeric(ticks["trade_quantity_b_s"].str.strip(), errors="coerce")
    ticks = ticks.dropna(subset=["timestamp", "price", "quantity"]).copy()
    ticks = ticks.sort_values("timestamp", kind="stable").reset_index(drop=True)
    if ticks.empty:
        raise ValueError("The input CSV has no valid tick rows.")

    price_change = ticks["price"].diff()
    direction = np.sign(price_change).replace(0, np.nan).ffill().fillna(1)
    ticks["signed_quantity"] = ticks["quantity"] * direction
    return ticks


def infer_tick_size(prices: pd.Series) -> float:
    differences = np.diff(np.sort(prices.unique()))
    positive = differences[differences > 0]
    if len(positive) == 0:
        raise ValueError("Cannot infer tick size from a constant price series.")
    return float(np.min(positive))


def build_volume_bars(
    ticks: pd.DataFrame,
    volume_bar_size: float,
    min_completed_bars: int = 100,
) -> pd.DataFrame:
    bars: list[dict] = []
    volume = 0.0
    signed_volume = 0.0
    bar_start_time: pd.Timestamp | None = None
    open_price = high_price = low_price = close_price = 0.0
    tick_count = 0

    for tick in ticks.itertuples(index=False):
        if bar_start_time is None:
            bar_start_time = tick.timestamp
            open_price = high_price = low_price = close_price = float(tick.price)
        high_price = max(high_price, float(tick.price))
        low_price = min(low_price, float(tick.price))
        close_price = float(tick.price)
        volume += float(tick.quantity)
        signed_volume += float(tick.signed_quantity)
        tick_count += 1

        if volume >= volume_bar_size:
            bars.append(
                {
                    "bar_start_time": bar_start_time,
                    "timestamp": tick.timestamp,
                    "open": open_price,
                    "high": high_price,
                    "low": low_price,
                    "close": close_price,
                    "volume": volume,
                    "signed_volume": signed_volume,
                    "tick_count": tick_count,
                }
            )
            volume = 0.0
            signed_volume = 0.0
            bar_start_time = None
            tick_count = 0

    bars_frame = pd.DataFrame(bars)
    if len(bars_frame) < min_completed_bars:
        raise ValueError("Not enough completed volume bars to calculate the indicator.")
    return bars_frame


def detect_pivots(
    bars: pd.DataFrame,
    tick_size: float,
    threshold_span: int,
    threshold_multiplier: float,
    min_reversal_ticks: float,
) -> list[dict]:
    prices = bars["close"].to_numpy(dtype=float)
    thresholds = (
        bars["close"].ewm(span=threshold_span, min_periods=100).std().fillna(0).to_numpy()
        * threshold_multiplier
    )
    thresholds = np.maximum(thresholds, tick_size * min_reversal_ticks)

    trend = 1
    extreme_price = prices[0]
    extreme_index = 0
    events: list[dict] = []

    for index in range(1, len(prices)):
        price = prices[index]
        threshold = thresholds[index]
        if trend > 0:
            if price >= extreme_price:
                extreme_price = price
                extreme_index = index
            elif price <= extreme_price - threshold:
                events.append(
                    {
                        "event_type": "swing_high",
                        "pivot_index": extreme_index,
                        "confirmation_index": index,
                        "pivot_price": extreme_price,
                        "threshold": threshold,
                    }
                )
                trend = -1
                extreme_price = price
                extreme_index = index
        else:
            if price <= extreme_price:
                extreme_price = price
                extreme_index = index
            elif price >= extreme_price + threshold:
                events.append(
                    {
                        "event_type": "swing_low",
                        "pivot_index": extreme_index,
                        "confirmation_index": index,
                        "pivot_price": extreme_price,
                        "threshold": threshold,
                    }
                )
                trend = 1
                extreme_price = price
                extreme_index = index
    return events


def build_zones(
    bars: pd.DataFrame,
    pivot_events: list[dict],
    tick_size: float,
    volume_window: int,
) -> tuple[list[dict], list[dict]]:
    prices = bars["close"].to_numpy(dtype=float)
    quantities = bars["volume"].to_numpy(dtype=float)
    signed_quantities = bars["signed_volume"].to_numpy(dtype=float)
    zones: list[dict] = []
    events: list[dict] = []

    for pivot_number, pivot in enumerate(pivot_events, start=1):
        pivot_index = pivot["pivot_index"]
        confirmation_index = pivot["confirmation_index"]
        width = max(2 * tick_size, pivot["threshold"] * 0.25)
        zone_low = pivot["pivot_price"] - width if pivot["event_type"] == "swing_low" else pivot["pivot_price"]
        zone_high = pivot["pivot_price"] + width if pivot["event_type"] == "swing_high" else pivot["pivot_price"]
        start = max(0, confirmation_index - volume_window)
        window = np.abs(prices[start : confirmation_index + 1] - pivot["pivot_price"]) <= width
        zone_volume = float(quantities[start : confirmation_index + 1][window].sum())
        signed_volume = float(signed_quantities[start : confirmation_index + 1][window].sum())

        matching_zone = next(
            (
                zone
                for zone in zones
                if pivot["pivot_price"] <= zone["high"] + width
                and pivot["pivot_price"] >= zone["low"] - width
            ),
            None,
        )
        if matching_zone is None:
            zone = {
                "zone_id": len(zones) + 1,
                "zone_type": "support" if pivot["event_type"] == "swing_low" else "resistance",
                "low": zone_low,
                "high": zone_high,
                "pivot_price": pivot["pivot_price"],
                "zone_volume": zone_volume,
                "signed_volume": signed_volume,
                "touches": 1,
                "broken": False,
                "created_index": confirmation_index,
                "created_time": bars.iloc[confirmation_index]["timestamp"],
            }
            zones.append(zone)
        else:
            total_volume = matching_zone["zone_volume"] + zone_volume
            if total_volume > 0:
                matching_zone["pivot_price"] = (
                    matching_zone["pivot_price"] * matching_zone["zone_volume"]
                    + pivot["pivot_price"] * zone_volume
                ) / total_volume
            matching_zone["low"] = min(matching_zone["low"], zone_low)
            matching_zone["high"] = max(matching_zone["high"], zone_high)
            matching_zone["zone_volume"] = total_volume
            matching_zone["signed_volume"] += signed_volume
            matching_zone["touches"] += 1
            zone = matching_zone

        events.append(
            {
                "event_type": pivot["event_type"],
                "zone_id": zone["zone_id"],
                "event_time": bars.iloc[confirmation_index]["timestamp"],
                "pivot_time": bars.iloc[pivot_index]["timestamp"],
                "price": pivot["pivot_price"],
                "zone_low": zone["low"],
                "zone_high": zone["high"],
                "threshold": pivot["threshold"],
                "zone_volume": zone["zone_volume"],
                "signed_volume": zone["signed_volume"],
                "touches": zone["touches"],
            }
        )

    return zones, events


def add_breakouts(bars: pd.DataFrame, zones: list[dict], events: list[dict], confirmation_bars: int) -> None:
    prices = bars["close"].to_numpy(dtype=float)
    times = bars["timestamp"].to_numpy()
    for zone in zones:
        start_index = zone["created_index"]
        outer = zone["high"] if zone["zone_type"] == "resistance" else zone["low"]
        crossed = prices[start_index:] > outer if zone["zone_type"] == "resistance" else prices[start_index:] < outer
        crossed_indices = np.flatnonzero(crossed)
        if len(crossed_indices) == 0:
            continue
        relative_index = int(crossed_indices[0])
        breakout_index = start_index + relative_index
        end_index = min(len(prices), breakout_index + confirmation_bars)
        beyond = prices[breakout_index:end_index] > outer if zone["zone_type"] == "resistance" else prices[breakout_index:end_index] < outer
        if len(beyond) < confirmation_bars or not bool(np.all(beyond)):
            continue
        events.append(
            {
                "event_type": "breakout",
                "zone_id": zone["zone_id"],
                "event_time": pd.Timestamp(times[breakout_index]),
                "pivot_time": pd.NaT,
                "price": prices[breakout_index],
                "zone_low": zone["low"],
                "zone_high": zone["high"],
                "threshold": np.nan,
                "zone_volume": zone["zone_volume"],
                "signed_volume": zone["signed_volume"],
                "touches": zone["touches"],
            }
        )


def save_chart(bars: pd.DataFrame, events: pd.DataFrame, zones: list[dict], output: Path, volume_bar_size: float) -> None:
    figure = go.Figure(
        go.Candlestick(
            x=bars["timestamp"],
            open=bars["open"],
            high=bars["high"],
            low=bars["low"],
            close=bars["close"],
            name=f"TMF {volume_bar_size:,.0f}-contract bars",
        )
    )
    chart_end_time = bars["timestamp"].iloc[-1]
    for zone in zones:
        color = "rgba(0, 150, 136, 0.16)" if zone["zone_type"] == "support" else "rgba(239, 83, 80, 0.16)"
        figure.add_shape(
            type="rect",
            xref="x",
            yref="y",
            x0=zone["created_time"],
            x1=chart_end_time,
            y0=zone["low"],
            y1=zone["high"],
            fillcolor=color,
            line_color=color.replace("0.16", "0.8"),
            line_width=1,
        )
        figure.add_annotation(
            x=zone["created_time"],
            y=zone["high"],
            text=f"{zone['zone_type']} {zone['zone_id']}",
            showarrow=False,
            xanchor="left",
            yanchor="bottom",
            font={"size": 10},
        )
    for event_type, color, symbol in (
        ("swing_low", "#00897b", "triangle-up"),
        ("swing_high", "#d32f2f", "triangle-down"),
        ("breakout", "#f9a825", "x"),
    ):
        subset = events[events["event_type"] == event_type]
        if not subset.empty:
            figure.add_trace(
                go.Scatter(
                    x=subset["event_time"],
                    y=subset["price"],
                    mode="markers",
                    name=event_type,
                    marker={"color": color, "size": 9, "symbol": symbol},
                )
            )
    figure.update_layout(
        title=f"TMF SNR ({volume_bar_size:,.0f}-contract volume bars)",
        xaxis_title="Time",
        yaxis_title="Price",
        xaxis_rangeslider_visible=False,
    )
    output.parent.mkdir(parents=True, exist_ok=True)
    figure.write_html(output, include_plotlyjs=True)


def run(args: argparse.Namespace) -> tuple[int, int]:
    ticks = load_ticks(args.source, args.input_encoding)
    tick_size = infer_tick_size(ticks["price"])
    bars = build_volume_bars(ticks, args.volume_bar_size)
    pivot_events = detect_pivots(
        bars,
        tick_size,
        args.threshold_span,
        args.threshold_multiplier,
        args.min_reversal_ticks,
    )
    zones, events = build_zones(bars, pivot_events, tick_size, args.volume_window)
    add_breakouts(bars, zones, events, args.confirmation_bars)
    events_frame = pd.DataFrame(events).sort_values("event_time", kind="stable")
    args.events.parent.mkdir(parents=True, exist_ok=True)
    events_frame.to_csv(args.events, index=False, encoding=args.output_encoding)
    save_chart(bars, events_frame, zones, args.chart, args.volume_bar_size)
    print(f"tick_size={tick_size:g}")
    print(f"ticks={len(ticks)} volume_bars={len(bars)} pivots={len(pivot_events)} zones={len(zones)} events={len(events_frame)}")
    print(f"events_csv={args.events}")
    print(f"chart_html={args.chart}")
    return len(pivot_events), len(events_frame)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Generate volume-bar support and resistance signals from TMF tick data.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE)
    parser.add_argument("--events", type=Path, default=DEFAULT_EVENTS)
    parser.add_argument("--chart", type=Path, default=DEFAULT_CHART)
    parser.add_argument("--input-encoding", default="utf-8-sig")
    parser.add_argument("--output-encoding", default="utf-8-sig")
    parser.add_argument("--threshold-span", type=int, default=2000)
    parser.add_argument("--threshold-multiplier", type=float, default=2.5)
    parser.add_argument("--min-reversal-ticks", type=float, default=5)
    parser.add_argument("--volume-bar-size", type=float, default=2000)
    parser.add_argument("--volume-window", type=int, default=20, help="Completed volume bars used for zone volume.")
    parser.add_argument("--confirmation-bars", type=int, default=2, help="Completed bars required to confirm a breakout.")
    return parser.parse_args()


if __name__ == "__main__":
    run(parse_args())
