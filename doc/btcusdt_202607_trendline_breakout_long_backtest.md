# BTCUSDT 1h trend-line breakout (LONG) — 2026-07

## Data & Setup

- Backtest month: `2026-07` (UTC); warm-up months: 2026-06.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 38 |
| Entry signals | 20 |

### Trend-line outcomes

- `unresolved`: 19
- `entered`: 19

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 20 |
| Wins / Losses / Breakeven | 6 / 14 / 0 |
| Win rate | 30.0% |
| Gross P&L | -2,264.93 USDT |
| Net P&L after costs | -3,537.07 USDT |
| Total fees | 1,017.71 USDT |
| Net profit factor | 0.58 |
| Average net P&L | -176.85 USDT |
| Maximum net drawdown | -5,560.61 USDT |

## Exit Reasons

- `initial_stop`: 14
- `target_2r`: 6

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-07-02 10:00 @ 61165.6 | 2026-07-04 17:59 @ 63238.9 | 2023.55 | 1.99 | target_2r |
| 2 | 2026-07-05 08:00 @ 63001.4 | 2026-07-05 09:59 @ 62710.1 | -341.56 | -1.02 | initial_stop |
| 3 | 2026-07-05 22:00 @ 63076.7 | 2026-07-06 11:59 @ 62595.0 | -531.94 | -1.01 | initial_stop |
| 4 | 2026-07-06 16:00 @ 63529.4 | 2026-07-08 09:59 @ 61727.4 | -1852.03 | -1.00 | initial_stop |
| 5 | 2026-07-09 20:00 @ 63229.3 | 2026-07-10 08:59 @ 64340.1 | 1059.78 | 1.99 | target_2r |
| 6 | 2026-07-11 07:00 @ 64193.1 | 2026-07-11 15:59 @ 63972.8 | -271.58 | -1.03 | initial_stop |
| 7 | 2026-07-12 12:00 @ 64000.2 | 2026-07-12 22:59 @ 63722.3 | -328.96 | -1.02 | initial_stop |
| 8 | 2026-07-13 12:00 @ 62887.7 | 2026-07-13 12:59 @ 62643.5 | -294.37 | -1.03 | initial_stop |
| 9 | 2026-07-14 00:00 @ 62313.2 | 2026-07-14 12:59 @ 63179.4 | 815.95 | 1.99 | target_2r |
| 10 | 2026-07-15 12:00 @ 64713.9 | 2026-07-15 12:59 @ 65079.1 | 313.32 | 1.96 | target_2r |
| 11 | 2026-07-16 16:00 @ 64684.2 | 2026-07-16 22:59 @ 63931.7 | -803.91 | -1.01 | initial_stop |
| 12 | 2026-07-17 12:00 @ 63279.4 | 2026-07-17 13:59 @ 62786.6 | -543.23 | -1.01 | initial_stop |
| 13 | 2026-07-17 15:00 @ 63148.8 | 2026-07-17 15:59 @ 63067.6 | -131.71 | -1.08 | initial_stop |
| 14 | 2026-07-18 12:00 @ 64039.6 | 2026-07-18 12:59 @ 64190.0 | 99.10 | 1.92 | target_2r |
| 15 | 2026-07-20 16:00 @ 65576.6 | 2026-07-24 13:59 @ 64308.6 | -1319.94 | -1.01 | initial_stop |
| 16 | 2026-07-24 22:00 @ 64118.6 | 2026-07-25 08:59 @ 63924.0 | -245.82 | -1.03 | initial_stop |
| 17 | 2026-07-25 14:00 @ 64143.2 | 2026-07-26 14:59 @ 64734.6 | 539.80 | 1.98 | target_2r |
| 18 | 2026-07-27 20:00 @ 64965.7 | 2026-07-27 22:59 @ 64510.6 | -506.84 | -1.01 | initial_stop |
| 19 | 2026-07-28 06:00 @ 63423.8 | 2026-07-28 13:59 @ 63141.9 | -332.58 | -1.02 | initial_stop |
| 20 | 2026-07-28 16:00 @ 63905.9 | 2026-07-31 14:59 @ 63072.6 | -884.09 | -1.01 | initial_stop |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
