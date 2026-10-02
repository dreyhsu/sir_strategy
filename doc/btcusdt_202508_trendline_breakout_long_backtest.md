# BTCUSDT 1h trend-line breakout (LONG) — 2025-08

## Data & Setup

- Backtest month: `2025-08` (UTC); warm-up months: 2025-07.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 46 |
| Entry signals | 22 |

### Trend-line outcomes

- `unresolved`: 24
- `entered`: 22

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 22 |
| Wins / Losses / Breakeven | 8 / 14 / 0 |
| Win rate | 36.4% |
| Gross P&L | -3,681.93 USDT |
| Net P&L after costs | -6,200.55 USDT |
| Total fees | 2,014.90 USDT |
| Net profit factor | 0.62 |
| Average net P&L | -281.84 USDT |
| Maximum net drawdown | -8,454.37 USDT |

## Exit Reasons

- `initial_stop`: 14
- `target_2r`: 7
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-08-01 12:00 @ 115258.0 | 2025-08-01 13:59 @ 114540.8 | -809.10 | -1.02 | initial_stop |
| 2 | 2025-08-02 01:00 @ 113774.0 | 2025-08-02 14:59 @ 113074.9 | -789.82 | -1.02 | initial_stop |
| 3 | 2025-08-03 01:00 @ 112913.6 | 2025-08-03 18:59 @ 114378.3 | 1373.82 | 1.98 | target_2r |
| 4 | 2025-08-04 14:00 @ 114881.5 | 2025-08-05 04:59 @ 114190.3 | -782.84 | -1.02 | initial_stop |
| 5 | 2025-08-05 11:00 @ 114811.2 | 2025-08-05 12:59 @ 113913.3 | -989.36 | -1.01 | initial_stop |
| 6 | 2025-08-05 23:00 @ 113921.4 | 2025-08-07 10:59 @ 116009.0 | 1995.61 | 1.99 | target_2r |
| 7 | 2025-08-07 20:00 @ 117419.2 | 2025-08-08 15:59 @ 116187.6 | -1325.10 | -1.01 | initial_stop |
| 8 | 2025-08-08 21:00 @ 116861.7 | 2025-08-10 03:59 @ 118269.4 | 1313.69 | 1.98 | target_2r |
| 9 | 2025-08-12 05:00 @ 119035.9 | 2025-08-12 05:59 @ 118630.0 | -500.93 | -1.03 | initial_stop |
| 10 | 2025-08-12 13:00 @ 119237.7 | 2025-08-13 13:59 @ 120981.3 | 1647.46 | 1.99 | target_2r |
| 11 | 2025-08-14 23:00 @ 118241.9 | 2025-08-15 04:59 @ 119091.5 | 754.60 | 1.97 | target_2r |
| 12 | 2025-08-16 13:00 @ 117711.1 | 2025-08-16 22:59 @ 117248.4 | -556.68 | -1.03 | initial_stop |
| 13 | 2025-08-17 05:00 @ 118035.3 | 2025-08-18 00:59 @ 117192.5 | -936.91 | -1.01 | initial_stop |
| 14 | 2025-08-20 18:00 @ 114161.4 | 2025-08-21 15:59 @ 112621.4 | -1630.69 | -1.01 | initial_stop |
| 15 | 2025-08-22 00:00 @ 112473.4 | 2025-08-22 02:59 @ 113103.4 | 539.75 | 1.96 | target_2r |
| 16 | 2025-08-22 15:00 @ 115756.1 | 2025-08-24 19:59 @ 112261.6 | -3585.71 | -1.00 | initial_stop |
| 17 | 2025-08-25 03:00 @ 113377.6 | 2025-08-25 04:59 @ 112587.5 | -880.48 | -1.01 | initial_stop |
| 18 | 2025-08-26 11:00 @ 110180.0 | 2025-08-26 11:59 @ 109938.4 | -329.66 | -1.05 | initial_stop |
| 19 | 2025-08-26 19:00 @ 110661.1 | 2025-08-28 04:59 @ 112722.7 | 1972.30 | 1.99 | target_2r |
| 20 | 2025-08-28 05:00 @ 112942.4 | 2025-08-29 05:59 @ 111183.8 | -1848.26 | -1.01 | initial_stop |
| 21 | 2025-08-29 13:00 @ 110678.7 | 2025-08-29 13:59 @ 109568.7 | -1198.02 | -1.01 | initial_stop |
| 22 | 2025-08-30 04:00 @ 108378.8 | 2025-08-31 22:59 @ 108831.5 | 365.79 | 0.46 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
