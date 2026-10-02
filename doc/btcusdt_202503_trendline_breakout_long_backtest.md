# BTCUSDT 1h trend-line breakout (LONG) — 2025-03

## Data & Setup

- Backtest month: `2025-03` (UTC); warm-up months: 2025-02.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 53 |
| Entry signals | 22 |

### Trend-line outcomes

- `unresolved`: 31
- `entered`: 22

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 22 |
| Wins / Losses / Breakeven | 6 / 16 / 0 |
| Win rate | 27.3% |
| Gross P&L | -4,110.10 USDT |
| Net P&L after costs | -5,979.86 USDT |
| Total fees | 1,495.81 USDT |
| Net profit factor | 0.59 |
| Average net P&L | -271.81 USDT |
| Maximum net drawdown | -8,172.47 USDT |

## Exit Reasons

- `initial_stop`: 16
- `target_2r`: 6

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-03-05 07:00 @ 87456.8 | 2025-03-05 09:59 @ 88734.5 | 1207.14 | 1.99 | target_2r |
| 2 | 2025-03-05 21:00 @ 90457.6 | 2025-03-06 17:59 @ 88303.8 | -2225.38 | -1.00 | initial_stop |
| 3 | 2025-03-07 14:00 @ 89114.0 | 2025-03-07 16:59 @ 86949.8 | -2234.63 | -1.00 | initial_stop |
| 4 | 2025-03-08 00:00 @ 86762.5 | 2025-03-08 01:59 @ 86253.1 | -578.61 | -1.02 | initial_stop |
| 5 | 2025-03-08 15:00 @ 86331.9 | 2025-03-08 16:59 @ 85898.9 | -501.92 | -1.02 | initial_stop |
| 6 | 2025-03-09 01:00 @ 86388.1 | 2025-03-09 01:59 @ 86173.4 | -283.78 | -1.04 | initial_stop |
| 7 | 2025-03-10 05:00 @ 82594.2 | 2025-03-10 14:59 @ 80311.2 | -2348.15 | -1.00 | initial_stop |
| 8 | 2025-03-11 02:00 @ 79092.0 | 2025-03-11 11:59 @ 82026.4 | 2869.97 | 1.99 | target_2r |
| 9 | 2025-03-13 22:00 @ 80783.6 | 2025-03-14 07:59 @ 82273.3 | 1424.50 | 1.99 | target_2r |
| 10 | 2025-03-15 03:00 @ 84513.9 | 2025-03-15 07:59 @ 83931.4 | -649.82 | -1.01 | initial_stop |
| 11 | 2025-03-15 14:00 @ 84414.7 | 2025-03-16 01:59 @ 83788.6 | -693.40 | -1.01 | initial_stop |
| 12 | 2025-03-17 08:00 @ 83533.7 | 2025-03-17 12:59 @ 83080.6 | -519.71 | -1.02 | initial_stop |
| 13 | 2025-03-18 23:00 @ 82358.3 | 2025-03-19 13:59 @ 84208.8 | 1783.82 | 1.99 | target_2r |
| 14 | 2025-03-20 15:00 @ 86132.2 | 2025-03-20 15:59 @ 85127.1 | -1073.63 | -1.01 | initial_stop |
| 15 | 2025-03-21 00:00 @ 84192.0 | 2025-03-21 07:59 @ 83761.1 | -498.08 | -1.02 | initial_stop |
| 16 | 2025-03-22 04:00 @ 84222.5 | 2025-03-22 13:59 @ 84015.8 | -274.02 | -1.04 | initial_stop |
| 17 | 2025-03-23 03:00 @ 84199.8 | 2025-03-23 11:59 @ 84981.2 | 713.67 | 1.98 | target_2r |
| 18 | 2025-03-26 06:00 @ 87488.7 | 2025-03-26 07:59 @ 88216.2 | 657.19 | 1.98 | target_2r |
| 19 | 2025-03-27 01:00 @ 87247.7 | 2025-03-27 11:59 @ 86787.3 | -530.02 | -1.02 | initial_stop |
| 20 | 2025-03-27 22:00 @ 87531.0 | 2025-03-28 03:59 @ 86783.4 | -817.26 | -1.01 | initial_stop |
| 21 | 2025-03-28 23:00 @ 84451.8 | 2025-03-29 02:59 @ 83752.3 | -766.80 | -1.01 | initial_stop |
| 22 | 2025-03-29 20:00 @ 82731.2 | 2025-03-30 16:59 @ 82156.2 | -640.94 | -1.01 | initial_stop |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
