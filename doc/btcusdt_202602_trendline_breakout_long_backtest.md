# BTCUSDT 1h trend-line breakout (LONG) — 2026-02

## Data & Setup

- Backtest month: `2026-02` (UTC); warm-up months: 2026-01.
- Simulated 1h bars (target month): 671.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 42 |
| Entry signals | 23 |

### Trend-line outcomes

- `entered`: 21
- `unresolved`: 21

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 23 |
| Wins / Losses / Breakeven | 8 / 15 / 0 |
| Win rate | 34.8% |
| Gross P&L | 1,847.74 USDT |
| Net P&L after costs | 253.41 USDT |
| Total fees | 1,275.47 USDT |
| Net profit factor | 1.02 |
| Average net P&L | 11.02 USDT |
| Maximum net drawdown | -4,965.99 USDT |

## Exit Reasons

- `initial_stop`: 15
- `target_2r`: 7
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-02-01 10:00 @ 79004.8 | 2026-02-01 10:59 @ 78255.1 | -812.63 | -1.01 | initial_stop |
| 2 | 2026-02-02 10:00 @ 77673.8 | 2026-02-03 17:59 @ 75442.1 | -2292.96 | -1.00 | initial_stop |
| 3 | 2026-02-04 02:00 @ 76399.7 | 2026-02-04 02:59 @ 75664.9 | -795.63 | -1.01 | initial_stop |
| 4 | 2026-02-04 04:00 @ 76668.8 | 2026-02-04 11:59 @ 75664.9 | -1064.77 | -1.01 | initial_stop |
| 5 | 2026-02-06 06:00 @ 66371.9 | 2026-02-06 17:59 @ 70832.5 | 4405.71 | 2.00 | target_2r |
| 6 | 2026-02-07 18:00 @ 69161.1 | 2026-02-08 08:59 @ 70244.5 | 1027.64 | 1.99 | target_2r |
| 7 | 2026-02-09 06:00 @ 71021.2 | 2026-02-09 06:59 @ 70281.1 | -796.65 | -1.01 | initial_stop |
| 8 | 2026-02-10 14:00 @ 68988.7 | 2026-02-10 14:59 @ 68483.1 | -560.64 | -1.01 | initial_stop |
| 9 | 2026-02-12 10:00 @ 67524.4 | 2026-02-12 15:59 @ 66983.2 | -594.95 | -1.01 | initial_stop |
| 10 | 2026-02-13 09:00 @ 66679.7 | 2026-02-13 14:59 @ 67729.2 | 995.80 | 1.99 | target_2r |
| 11 | 2026-02-14 19:00 @ 69748.1 | 2026-02-15 01:59 @ 69423.2 | -380.59 | -1.02 | initial_stop |
| 12 | 2026-02-16 01:00 @ 68817.3 | 2026-02-16 02:59 @ 68256.8 | -615.34 | -1.01 | initial_stop |
| 13 | 2026-02-16 04:00 @ 68399.4 | 2026-02-16 04:59 @ 68664.3 | 209.99 | 1.95 | target_2r |
| 14 | 2026-02-16 10:00 @ 68967.9 | 2026-02-16 11:59 @ 68343.3 | -679.56 | -1.01 | initial_stop |
| 15 | 2026-02-17 19:00 @ 68070.1 | 2026-02-18 14:59 @ 66840.0 | -1284.06 | -1.01 | initial_stop |
| 16 | 2026-02-19 19:00 @ 67009.9 | 2026-02-21 14:59 @ 68487.7 | 1423.55 | 1.99 | target_2r |
| 17 | 2026-02-22 07:00 @ 68013.1 | 2026-02-22 12:59 @ 67864.7 | -202.74 | -1.05 | initial_stop |
| 18 | 2026-02-24 01:00 @ 64916.7 | 2026-02-24 01:59 @ 64267.5 | -700.89 | -1.01 | initial_stop |
| 19 | 2026-02-24 11:00 @ 63256.3 | 2026-02-24 11:59 @ 63044.1 | -262.75 | -1.03 | initial_stop |
| 20 | 2026-02-25 13:00 @ 66045.3 | 2026-02-25 15:59 @ 67400.4 | 1301.69 | 1.99 | target_2r |
| 21 | 2026-02-26 04:00 @ 68194.2 | 2026-02-26 04:59 @ 68670.8 | 421.82 | 1.97 | target_2r |
| 22 | 2026-02-27 04:00 @ 67564.2 | 2026-02-27 10:59 @ 67183.6 | -434.47 | -1.02 | initial_stop |
| 23 | 2026-02-28 14:00 @ 65076.0 | 2026-02-28 22:59 @ 67074.7 | 1945.82 | 1.05 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
