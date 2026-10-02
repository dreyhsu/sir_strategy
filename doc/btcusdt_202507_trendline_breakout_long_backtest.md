# BTCUSDT 1h trend-line breakout (LONG) — 2025-07

## Data & Setup

- Backtest month: `2025-07` (UTC); warm-up months: 2025-06.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 37 |
| Entry signals | 18 |

### Trend-line outcomes

- `unresolved`: 20
- `entered`: 17

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 18 |
| Wins / Losses / Breakeven | 9 / 9 / 0 |
| Win rate | 50.0% |
| Gross P&L | 8,548.90 USDT |
| Net P&L after costs | 6,460.44 USDT |
| Total fees | 1,670.77 USDT |
| Net profit factor | 1.99 |
| Average net P&L | 358.91 USDT |
| Maximum net drawdown | -3,462.43 USDT |

## Exit Reasons

- `target_2r`: 9
- `initial_stop`: 9

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-07-02 03:00 @ 105876.5 | 2025-07-02 06:59 @ 106946.4 | 984.75 | 1.98 | target_2r |
| 2 | 2025-07-05 01:00 @ 108143.9 | 2025-07-06 21:59 @ 109561.6 | 1330.59 | 1.98 | target_2r |
| 3 | 2025-07-08 08:00 @ 108451.5 | 2025-07-09 19:59 @ 110043.6 | 1504.68 | 1.99 | target_2r |
| 4 | 2025-07-10 03:00 @ 111189.5 | 2025-07-10 10:59 @ 110857.5 | -420.82 | -1.03 | initial_stop |
| 5 | 2025-07-12 04:00 @ 117741.8 | 2025-07-12 12:59 @ 117367.7 | -468.15 | -1.03 | initial_stop |
| 6 | 2025-07-13 00:00 @ 117401.1 | 2025-07-13 12:59 @ 118240.2 | 744.80 | 1.97 | target_2r |
| 7 | 2025-07-14 03:00 @ 119638.4 | 2025-07-14 05:59 @ 121977.9 | 2242.88 | 1.99 | target_2r |
| 8 | 2025-07-14 23:00 @ 120026.6 | 2025-07-15 00:59 @ 119593.6 | -528.81 | -1.03 | initial_stop |
| 9 | 2025-07-15 12:00 @ 117122.2 | 2025-07-15 12:59 @ 116753.2 | -462.54 | -1.03 | initial_stop |
| 10 | 2025-07-15 23:00 @ 117819.5 | 2025-07-17 21:59 @ 120626.4 | 2711.52 | 1.99 | target_2r |
| 11 | 2025-07-18 22:00 @ 117660.1 | 2025-07-19 10:59 @ 118372.6 | 618.08 | 1.97 | target_2r |
| 12 | 2025-07-20 03:00 @ 117969.6 | 2025-07-20 14:59 @ 118564.7 | 500.52 | 1.96 | target_2r |
| 13 | 2025-07-21 03:00 @ 118167.8 | 2025-07-21 18:59 @ 117204.3 | -1057.69 | -1.01 | initial_stop |
| 14 | 2025-07-22 02:00 @ 117711.9 | 2025-07-22 03:59 @ 116713.0 | -1092.61 | -1.01 | initial_stop |
| 15 | 2025-07-23 16:00 @ 118542.8 | 2025-07-23 17:59 @ 117325.0 | -1312.13 | -1.01 | initial_stop |
| 16 | 2025-07-25 17:00 @ 116155.1 | 2025-07-27 16:59 @ 118584.7 | 2335.67 | 1.99 | target_2r |
| 17 | 2025-07-29 21:00 @ 117490.5 | 2025-07-29 21:59 @ 117334.0 | -250.51 | -1.08 | initial_stop |
| 18 | 2025-07-30 22:00 @ 117291.6 | 2025-07-31 20:59 @ 116465.4 | -919.78 | -1.01 | initial_stop |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
