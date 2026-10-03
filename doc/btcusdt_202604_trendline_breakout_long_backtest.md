# BTCUSDT 1h trend-line breakout (LONG) — 2026-04

## Data & Setup

- Backtest month: `2026-04` (UTC); warm-up months: 2026-03.
- Simulated 1h bars (target month): 719.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 52 |
| Entry signals | 35 |

### Trend-line outcomes

- `entered`: 34
- `unresolved`: 18

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 35 |
| Wins / Losses / Breakeven | 17 / 18 / 0 |
| Win rate | 48.6% |
| Gross P&L | 8,140.76 USDT |
| Net P&L after costs | 5,565.35 USDT |
| Total fees | 2,060.33 USDT |
| Net profit factor | 1.60 |
| Average net P&L | 159.01 USDT |
| Maximum net drawdown | -2,268.38 USDT |

## Exit Reasons

- `initial_stop`: 17
- `target_2r`: 17
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-04-01 16:00 @ 68883.8 | 2026-04-01 18:59 @ 68084.6 | -853.98 | -1.01 | initial_stop |
| 2 | 2026-04-02 01:00 @ 68572.1 | 2026-04-02 01:59 @ 68047.4 | -579.31 | -1.01 | initial_stop |
| 3 | 2026-04-02 10:00 @ 66435.3 | 2026-04-02 10:59 @ 66293.6 | -194.86 | -1.05 | initial_stop |
| 4 | 2026-04-03 07:00 @ 66768.8 | 2026-04-03 12:59 @ 67290.4 | 468.00 | 1.97 | target_2r |
| 5 | 2026-04-03 20:00 @ 66863.7 | 2026-04-04 15:59 @ 67295.1 | 377.78 | 1.97 | target_2r |
| 6 | 2026-04-05 16:00 @ 67278.9 | 2026-04-05 22:59 @ 68327.1 | 993.98 | 1.99 | target_2r |
| 7 | 2026-04-06 10:00 @ 69706.4 | 2026-04-06 22:59 @ 68951.8 | -810.03 | -1.01 | initial_stop |
| 8 | 2026-04-07 09:00 @ 68914.0 | 2026-04-07 10:59 @ 68533.1 | -435.82 | -1.02 | initial_stop |
| 9 | 2026-04-07 17:00 @ 68214.0 | 2026-04-07 17:59 @ 68973.2 | 704.27 | 1.98 | target_2r |
| 10 | 2026-04-08 09:00 @ 71783.2 | 2026-04-08 13:59 @ 72823.0 | 982.03 | 1.99 | target_2r |
| 11 | 2026-04-08 21:00 @ 71344.1 | 2026-04-08 22:59 @ 71057.8 | -343.30 | -1.03 | initial_stop |
| 12 | 2026-04-10 04:00 @ 71844.5 | 2026-04-10 04:59 @ 72025.4 | 123.42 | 1.92 | target_2r |
| 13 | 2026-04-10 12:00 @ 72100.0 | 2026-04-10 20:59 @ 73370.3 | 1212.09 | 1.99 | target_2r |
| 14 | 2026-04-11 17:00 @ 72998.6 | 2026-04-11 19:59 @ 73764.0 | 706.72 | 1.98 | target_2r |
| 15 | 2026-04-13 13:00 @ 71050.1 | 2026-04-13 14:59 @ 71853.5 | 746.26 | 1.98 | target_2r |
| 16 | 2026-04-14 07:00 @ 74492.5 | 2026-04-14 13:59 @ 75214.3 | 661.89 | 1.98 | target_2r |
| 17 | 2026-04-15 19:00 @ 74356.5 | 2026-04-16 13:59 @ 73790.1 | -625.67 | -1.01 | initial_stop |
| 18 | 2026-04-16 19:00 @ 75007.6 | 2026-04-17 14:59 @ 77503.2 | 2434.64 | 1.99 | target_2r |
| 19 | 2026-04-19 01:00 @ 75635.0 | 2026-04-19 01:59 @ 75596.1 | -99.32 | -1.24 | initial_stop |
| 20 | 2026-04-19 05:00 @ 75631.3 | 2026-04-19 06:59 @ 75442.6 | -249.14 | -1.04 | initial_stop |
| 21 | 2026-04-19 14:00 @ 75885.6 | 2026-04-19 17:59 @ 74967.1 | -978.83 | -1.01 | initial_stop |
| 22 | 2026-04-20 04:00 @ 74601.4 | 2026-04-20 18:59 @ 76279.6 | 1617.94 | 1.99 | target_2r |
| 23 | 2026-04-21 08:00 @ 76057.6 | 2026-04-21 15:59 @ 75532.4 | -585.80 | -1.01 | initial_stop |
| 24 | 2026-04-21 23:00 @ 75606.2 | 2026-04-22 02:59 @ 76833.6 | 1166.46 | 1.99 | target_2r |
| 25 | 2026-04-22 11:00 @ 78125.6 | 2026-04-22 16:59 @ 79417.9 | 1229.26 | 1.99 | target_2r |
| 26 | 2026-04-23 13:00 @ 77834.6 | 2026-04-23 13:59 @ 77355.2 | -541.49 | -1.02 | initial_stop |
| 27 | 2026-04-23 15:00 @ 78140.7 | 2026-04-23 17:59 @ 77355.2 | -847.75 | -1.01 | initial_stop |
| 28 | 2026-04-24 12:00 @ 78202.7 | 2026-04-24 17:59 @ 77489.5 | -775.55 | -1.01 | initial_stop |
| 29 | 2026-04-25 01:00 @ 77427.7 | 2026-04-25 09:59 @ 77686.5 | 196.67 | 1.94 | target_2r |
| 30 | 2026-04-25 10:00 @ 77680.4 | 2026-04-25 15:59 @ 77442.2 | -300.26 | -1.03 | initial_stop |
| 31 | 2026-04-25 23:00 @ 77521.1 | 2026-04-26 05:59 @ 78128.5 | 545.23 | 1.97 | target_2r |
| 32 | 2026-04-26 15:00 @ 78061.3 | 2026-04-26 21:59 @ 77787.7 | -335.92 | -1.03 | initial_stop |
| 33 | 2026-04-28 20:00 @ 76301.1 | 2026-04-29 03:59 @ 77055.7 | 693.21 | 1.98 | target_2r |
| 34 | 2026-04-29 22:00 @ 75890.7 | 2026-04-30 02:59 @ 75462.6 | -488.68 | -1.02 | initial_stop |
| 35 | 2026-04-30 14:00 @ 76378.0 | 2026-04-30 22:59 @ 76190.3 | -248.78 | -0.50 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
