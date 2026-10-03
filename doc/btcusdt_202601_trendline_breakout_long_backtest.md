# BTCUSDT 1h trend-line breakout (LONG) — 2026-01

## Data & Setup

- Backtest month: `2026-01` (UTC); warm-up months: 2025-12.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 50 |
| Entry signals | 25 |

### Trend-line outcomes

- `unresolved`: 26
- `entered`: 24

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 25 |
| Wins / Losses / Breakeven | 6 / 19 / 0 |
| Win rate | 24.0% |
| Gross P&L | -7,255.31 USDT |
| Net P&L after costs | -9,511.40 USDT |
| Total fees | 1,804.87 USDT |
| Net profit factor | 0.30 |
| Average net P&L | -380.46 USDT |
| Maximum net drawdown | -11,611.49 USDT |

## Exit Reasons

- `initial_stop`: 19
- `target_2r`: 6

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-01-01 16:00 @ 87995.6 | 2026-01-01 16:59 @ 87862.9 | -203.03 | -1.07 | initial_stop |
| 2 | 2026-01-01 18:00 @ 88290.2 | 2026-01-02 08:59 @ 89118.4 | 757.18 | 1.98 | target_2r |
| 3 | 2026-01-03 02:00 @ 90241.8 | 2026-01-03 05:59 @ 89942.4 | -371.49 | -1.03 | initial_stop |
| 4 | 2026-01-03 13:00 @ 90010.9 | 2026-01-04 00:59 @ 90951.8 | 868.52 | 1.98 | target_2r |
| 5 | 2026-01-04 18:00 @ 91302.5 | 2026-01-04 18:59 @ 91087.3 | -288.19 | -1.04 | initial_stop |
| 6 | 2026-01-05 00:00 @ 91506.3 | 2026-01-05 00:59 @ 92304.0 | 724.14 | 1.98 | target_2r |
| 7 | 2026-01-06 11:00 @ 93545.8 | 2026-01-06 14:59 @ 94233.8 | 612.97 | 1.97 | target_2r |
| 8 | 2026-01-07 00:00 @ 93717.5 | 2026-01-07 14:59 @ 91538.4 | -2253.13 | -1.00 | initial_stop |
| 9 | 2026-01-07 23:00 @ 91152.6 | 2026-01-08 02:59 @ 90848.3 | -377.10 | -1.03 | initial_stop |
| 10 | 2026-01-08 16:00 @ 90739.2 | 2026-01-09 08:59 @ 89921.0 | -890.43 | -1.01 | initial_stop |
| 11 | 2026-01-11 01:00 @ 90609.2 | 2026-01-11 14:59 @ 91048.6 | 366.75 | 1.96 | target_2r |
| 12 | 2026-01-13 04:00 @ 91390.0 | 2026-01-13 05:59 @ 92149.7 | 686.24 | 1.98 | target_2r |
| 13 | 2026-01-16 01:00 @ 95599.2 | 2026-01-16 04:59 @ 95211.2 | -464.31 | -1.03 | initial_stop |
| 14 | 2026-01-17 00:00 @ 95513.4 | 2026-01-18 01:59 @ 94951.5 | -638.03 | -1.02 | initial_stop |
| 15 | 2026-01-18 10:00 @ 95242.9 | 2026-01-18 13:59 @ 94980.4 | -338.61 | -1.04 | initial_stop |
| 16 | 2026-01-19 11:00 @ 93030.5 | 2026-01-19 23:59 @ 92462.2 | -642.55 | -1.02 | initial_stop |
| 17 | 2026-01-21 15:00 @ 89764.7 | 2026-01-21 16:59 @ 88381.8 | -1454.17 | -1.01 | initial_stop |
| 18 | 2026-01-22 11:00 @ 90055.6 | 2026-01-22 13:59 @ 89763.6 | -363.91 | -1.03 | initial_stop |
| 19 | 2026-01-23 02:00 @ 89902.7 | 2026-01-23 08:59 @ 89213.2 | -761.16 | -1.01 | initial_stop |
| 20 | 2026-01-24 22:00 @ 89349.5 | 2026-01-24 22:59 @ 89277.1 | -143.91 | -1.14 | initial_stop |
| 21 | 2026-01-26 06:00 @ 87785.3 | 2026-01-26 16:59 @ 87224.4 | -630.90 | -1.02 | initial_stop |
| 22 | 2026-01-27 00:00 @ 88309.4 | 2026-01-27 15:59 @ 87586.5 | -793.25 | -1.01 | initial_stop |
| 23 | 2026-01-27 21:00 @ 89368.9 | 2026-01-29 14:59 @ 87501.6 | -1938.04 | -1.00 | initial_stop |
| 24 | 2026-01-30 06:00 @ 82881.8 | 2026-01-30 06:59 @ 82119.9 | -827.90 | -1.01 | initial_stop |
| 25 | 2026-01-30 09:00 @ 82633.6 | 2026-01-30 09:59 @ 82552.5 | -147.09 | -1.11 | initial_stop |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
