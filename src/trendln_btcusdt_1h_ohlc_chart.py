"""Render a BTCUSDT 1h OHLC candlestick chart with ``trendln`` trendlines to HTML.

``trendln`` only draws static matplotlib figures (its candlestick path also needs
``mpl_finance``, which is not installed here).  So this script uses ``trendln``
purely to *compute* the support/resistance trendlines, then draws an interactive
OHLC candlestick chart with those lines overlaid using Plotly and writes it to an
``.html`` file.

Data source
-----------
Reads ``data/btcusdt_bars/BTCUSDT_<YYYY-MM>_1h.csv`` (produced by
``preprocess_btcusdt_bars.py``), same convention as the 1h backtests.  Columns:
``timestamp, hour_start, session_id, open, high, low, close, volume``.

Environment notes
-----------------
Run inside the ``tss`` conda env::

    /opt/homebrew/Caskroom/miniconda/base/bin/conda run -n tss python \
        src/trendln_btcusdt_1h_ohlc_chart.py

* ``trendln``'s default ``METHOD_NUMDIFF`` extrema detector imports ``findiff`` ->
  ``scipy.sparse`` which fails to load on this machine, so we default to
  ``METHOD_NAIVECONSEC`` (no findiff dependency).
* ``trendln`` must receive plain numpy float arrays (positional integer indexing);
  passing a datetime-indexed Series breaks its internal windowing.
"""

from __future__ import annotations

import argparse
from pathlib import Path

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import trendln

# --------------------------------------------------------------------------------------
# Paths / defaults
# --------------------------------------------------------------------------------------
PROJECT_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_BARS_DIR = PROJECT_ROOT / "data" / "btcusdt_bars"
DEFAULT_OUTPUT_DIR = PROJECT_ROOT / "btcusdt_tick"
DEFAULT_MONTH = "2026-08"  # latest available 1h month

EXTMETHODS = {
    "naiveconsec": trendln.METHOD_NAIVECONSEC,
    "naive": trendln.METHOD_NAIVE,
}

SUPPORT_COLOR = "#2ca02c"  # green
RESISTANCE_COLOR = "#d62728"  # red


# --------------------------------------------------------------------------------------
# Data loading (mirrors backtest_btcusdt_1h_trendline_breakout_long.py)
# --------------------------------------------------------------------------------------
def parse_month(text: str) -> str:
    try:
        parsed = pd.Period(text, freq="M")
    except Exception as error:  # noqa: BLE001
        raise argparse.ArgumentTypeError(
            f"invalid month {text!r}; expected YYYY-MM"
        ) from error
    return f"{parsed.year:04d}-{parsed.month:02d}"


def month_range(start_month: str, end_month: str) -> list[str]:
    start, end = pd.Period(start_month, freq="M"), pd.Period(end_month, freq="M")
    if end < start:
        raise ValueError("--end-month must be on or after --start-month")
    return [f"{p.year:04d}-{p.month:02d}" for p in pd.period_range(start, end, freq="M")]


def load_bars(bars_dir: Path, month: str) -> pd.DataFrame:
    path = bars_dir / f"BTCUSDT_{month}_1h.csv"
    if not path.is_file():
        raise FileNotFoundError(f"missing bar file: {path}")
    frame = pd.read_csv(path)
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True, format="ISO8601")
    return frame


def load_span(bars_dir: Path, months: list[str]) -> pd.DataFrame:
    frames = [load_bars(bars_dir, month) for month in months]
    return (
        pd.concat(frames, ignore_index=True)
        .sort_values("timestamp", kind="stable")
        .reset_index(drop=True)
    )


# --------------------------------------------------------------------------------------
# Trendline computation via trendln
# --------------------------------------------------------------------------------------
def _lines_from_trend(trend, timestamps: pd.Series, kind: str) -> list[dict]:
    """Convert a trendln trend list into drawable line dicts.

    Each trend element is ``((idx0, idx1, ...), (slope, intercept, ..., corr))`` where
    the indices are positional (0..N-1) into the price array.  The line value at a
    positional ``x`` is ``slope * x + intercept``.
    """
    lines: list[dict] = []
    n = len(timestamps)
    for points, coefs in trend:
        slope = float(coefs[0])
        intercept = float(coefs[1])
        corr = float(coefs[-1]) if len(coefs) else float("nan")
        idxs = [int(p) for p in points]
        x0, x1 = min(idxs), max(idxs)
        if not (0 <= x0 < n and 0 <= x1 < n) or x0 == x1:
            continue
        lines.append(
            {
                "kind": kind,
                "x0": timestamps.iloc[x0],
                "x1": timestamps.iloc[x1],
                "y0": slope * x0 + intercept,
                "y1": slope * x1 + intercept,
                "slope": slope,
                "intercept": intercept,
                "corr": corr,
                "idx0": x0,
                "idx1": x1,
            }
        )
    return lines


def _bestfit_line(bestfit, timestamps: pd.Series, kind: str) -> dict | None:
    """Overall best-fit line (``bestfit_min``/``bestfit_max``) drawn across the span."""
    if bestfit is None:
        return None
    try:
        slope = float(bestfit[0])
        intercept = float(bestfit[1])
    except (TypeError, IndexError, ValueError):
        return None
    if not (np.isfinite(slope) and np.isfinite(intercept)):
        return None
    n = len(timestamps)
    x0, x1 = 0, n - 1
    return {
        "kind": kind,
        "x0": timestamps.iloc[x0],
        "x1": timestamps.iloc[x1],
        "y0": slope * x0 + intercept,
        "y1": slope * x1 + intercept,
        "slope": slope,
        "intercept": intercept,
        "corr": float(bestfit[-1]) if len(bestfit) else float("nan"),
        "idx0": x0,
        "idx1": x1,
    }


def compute_trendlines(
    frame: pd.DataFrame,
    *,
    window: int = 125,
    accuracy: int = 2,
    extmethod=trendln.METHOD_NAIVECONSEC,
    method=trendln.METHOD_NSQUREDLOGN,
) -> dict:
    """Compute support/resistance trendlines for ``frame`` using trendln.

    Returns a dict with ``support``/``resistance`` lists of line dicts and
    ``support_bestfit``/``resistance_bestfit`` single line dicts (or ``None``).
    """
    timestamps = frame["timestamp"].reset_index(drop=True)
    lows = frame["low"].to_numpy(dtype=float)
    highs = frame["high"].to_numpy(dtype=float)

    support, resistance = trendln.calc_support_resistance(
        (lows, highs),
        extmethod=extmethod,
        method=method,
        window=window,
        accuracy=accuracy,
    )
    _, bestfit_min, mintrend, _ = support
    _, bestfit_max, maxtrend, _ = resistance

    return {
        "support": _lines_from_trend(mintrend, timestamps, "support"),
        "resistance": _lines_from_trend(maxtrend, timestamps, "resistance"),
        "support_bestfit": _bestfit_line(bestfit_min, timestamps, "support"),
        "resistance_bestfit": _bestfit_line(bestfit_max, timestamps, "resistance"),
    }


# --------------------------------------------------------------------------------------
# Plotly figure
# --------------------------------------------------------------------------------------
def _add_line_group(
    fig: go.Figure,
    lines: list[dict],
    *,
    color: str,
    name: str,
    group: str,
) -> None:
    first = True
    for line in lines:
        fig.add_trace(
            go.Scatter(
                x=[line["x0"], line["x1"]],
                y=[line["y0"], line["y1"]],
                mode="lines",
                line=dict(color=color, width=1),
                opacity=0.35,
                legendgroup=group,
                name=name,
                showlegend=first,
                hovertemplate=(
                    f"{name}<br>slope=%{{customdata[0]:.2f}}"
                    "<br>corr=%{customdata[1]:.3f}<extra></extra>"
                ),
                customdata=[[line["slope"], line["corr"]]] * 2,
            )
        )
        first = False


def _add_bestfit(
    fig: go.Figure,
    line: dict | None,
    *,
    color: str,
    name: str,
) -> None:
    if line is None:
        return
    fig.add_trace(
        go.Scatter(
            x=[line["x0"], line["x1"]],
            y=[line["y0"], line["y1"]],
            mode="lines",
            line=dict(color=color, width=2.5, dash="dash"),
            opacity=1.0,
            name=name,
            hovertemplate=(
                f"{name}<br>slope=%{{customdata[0]:.2f}}"
                "<br>corr=%{customdata[1]:.3f}<extra></extra>"
            ),
            customdata=[[line["slope"], line["corr"]]] * 2,
        )
    )


def build_figure(frame: pd.DataFrame, trendlines: dict, *, title: str) -> go.Figure:
    fig = go.Figure()
    fig.add_trace(
        go.Candlestick(
            x=frame["timestamp"],
            open=frame["open"],
            high=frame["high"],
            low=frame["low"],
            close=frame["close"],
            name="BTCUSDT 1h",
            increasing_line_color="#26a69a",
            decreasing_line_color="#ef5350",
        )
    )

    _add_line_group(
        fig,
        trendlines["support"],
        color=SUPPORT_COLOR,
        name="support trendlines",
        group="support",
    )
    _add_line_group(
        fig,
        trendlines["resistance"],
        color=RESISTANCE_COLOR,
        name="resistance trendlines",
        group="resistance",
    )
    _add_bestfit(
        fig,
        trendlines["support_bestfit"],
        color=SUPPORT_COLOR,
        name="support best fit",
    )
    _add_bestfit(
        fig,
        trendlines["resistance_bestfit"],
        color=RESISTANCE_COLOR,
        name="resistance best fit",
    )

    fig.update_layout(
        title=title,
        template="plotly_dark",
        xaxis_rangeslider_visible=False,
        hovermode="x unified",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="left", x=0),
        margin=dict(l=40, r=20, t=70, b=40),
    )
    fig.update_yaxes(title_text="Price (USDT)")
    return fig


# --------------------------------------------------------------------------------------
# CLI
# --------------------------------------------------------------------------------------
def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description=(
            "Render a BTCUSDT 1h OHLC chart with trendln support/resistance "
            "trendlines to an interactive HTML file."
        )
    )
    parser.add_argument("--bars-dir", type=Path, default=DEFAULT_BARS_DIR)
    parser.add_argument("--start-month", type=parse_month, default=DEFAULT_MONTH)
    parser.add_argument("--end-month", type=parse_month, default=DEFAULT_MONTH)
    parser.add_argument("--window", type=int, default=125)
    parser.add_argument("--accuracy", type=int, default=2)
    parser.add_argument(
        "--extmethod",
        choices=sorted(EXTMETHODS),
        default="naiveconsec",
        help="extrema detection method (naiveconsec avoids the broken findiff path)",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="output HTML path (defaults into btcusdt_tick/)",
    )
    args = parser.parse_args(argv)
    if pd.Period(args.end_month, "M") < pd.Period(args.start_month, "M"):
        parser.error("--end-month must be on or after --start-month")
    if args.window <= 0 or args.accuracy <= 0:
        parser.error("--window and --accuracy must be positive")
    return args


def default_output_path(start_month: str, end_month: str) -> Path:
    if start_month == end_month:
        stem = f"BTCUSDT_{start_month}_trendln_ohlc"
    else:
        stem = f"BTCUSDT_{start_month}_to_{end_month}_trendln_ohlc"
    return DEFAULT_OUTPUT_DIR / f"{stem}.html"


def main(argv: list[str] | None = None) -> None:
    args = parse_args(argv)
    months = month_range(args.start_month, args.end_month)
    frame = load_span(args.bars_dir, months)

    trendlines = compute_trendlines(
        frame,
        window=args.window,
        accuracy=args.accuracy,
        extmethod=EXTMETHODS[args.extmethod],
    )

    span = args.start_month if args.start_month == args.end_month else (
        f"{args.start_month} to {args.end_month}"
    )
    title = f"BTCUSDT 1h OHLC + trendln trendlines ({span})"
    fig = build_figure(frame, trendlines, title=title)

    output = args.output or default_output_path(args.start_month, args.end_month)
    output.parent.mkdir(parents=True, exist_ok=True)
    fig.write_html(str(output), include_plotlyjs="cdn")

    print(
        f"wrote {output}\n"
        f"  bars={len(frame)}  "
        f"support_lines={len(trendlines['support'])}  "
        f"resistance_lines={len(trendlines['resistance'])}"
    )


if __name__ == "__main__":
    main()
