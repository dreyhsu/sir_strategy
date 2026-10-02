# BTCUSDT 1h trend-line breakout (LONG) — 2025-04

## Data & Setup

- Backtest month: `2025-04` (UTC); warm-up months: 2025-03.
- Simulated 1h bars (target month): 719.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 32 |
| Entry signals | 21 |

### Trend-line outcomes

- `entered`: 20
- `unresolved`: 12

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 21 |
| Wins / Losses / Breakeven | 7 / 14 / 0 |
| Win rate | 33.3% |
| Gross P&L | 2,842.01 USDT |
| Net P&L after costs | 995.08 USDT |
| Total fees | 1,477.54 USDT |
| Net profit factor | 1.10 |
| Average net P&L | 47.38 USDT |
| Maximum net drawdown | -3,628.29 USDT |

## Exit Reasons

- `initial_stop`: 14
- `target_2r`: 7

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-04-02 15:00 @ 85833.7 | 2025-04-02 20:59 @ 88435.4 | 2532.01 | 1.99 | target_2r |
| 2 | 2025-04-03 20:00 @ 81985.7 | 2025-04-03 20:59 @ 81788.0 | -263.19 | -1.04 | initial_stop |
| 3 | 2025-04-06 00:00 @ 83514.5 | 2025-04-06 08:59 @ 82810.4 | -770.56 | -1.01 | initial_stop |
| 4 | 2025-04-07 13:00 @ 77307.6 | 2025-04-09 01:59 @ 74773.9 | -2594.54 | -1.00 | initial_stop |
| 5 | 2025-04-09 14:00 @ 77656.7 | 2025-04-09 17:59 @ 80553.7 | 2833.79 | 1.99 | target_2r |
| 6 | 2025-04-10 12:00 @ 81847.3 | 2025-04-10 12:59 @ 81509.8 | -402.78 | -1.02 | initial_stop |
| 7 | 2025-04-12 14:00 @ 84421.4 | 2025-04-13 19:59 @ 83384.6 | -1104.00 | -1.01 | initial_stop |
| 8 | 2025-04-14 12:00 @ 84900.1 | 2025-04-14 13:59 @ 84396.0 | -571.85 | -1.02 | initial_stop |
| 9 | 2025-04-15 01:00 @ 84884.7 | 2025-04-15 05:59 @ 85732.9 | 779.95 | 1.98 | target_2r |
| 10 | 2025-04-16 09:00 @ 83708.4 | 2025-04-16 15:59 @ 84906.2 | 1130.40 | 1.99 | target_2r |
| 11 | 2025-04-17 01:00 @ 84185.1 | 2025-04-21 00:59 @ 86071.7 | 1818.52 | 1.99 | target_2r |
| 12 | 2025-04-22 12:00 @ 88581.7 | 2025-04-22 13:59 @ 89716.0 | 1063.02 | 1.98 | target_2r |
| 13 | 2025-04-23 05:00 @ 93615.6 | 2025-04-23 15:59 @ 92594.5 | -1095.51 | -1.01 | initial_stop |
| 14 | 2025-04-23 23:00 @ 93755.8 | 2025-04-24 00:59 @ 93427.0 | -403.69 | -1.03 | initial_stop |
| 15 | 2025-04-24 12:00 @ 92584.5 | 2025-04-24 23:59 @ 93773.0 | 1113.99 | 1.98 | target_2r |
| 16 | 2025-04-26 02:00 @ 94971.8 | 2025-04-26 04:59 @ 94540.5 | -507.06 | -1.02 | initial_stop |
| 17 | 2025-04-26 16:00 @ 94334.4 | 2025-04-26 16:59 @ 94086.2 | -323.61 | -1.04 | initial_stop |
| 18 | 2025-04-26 18:00 @ 94288.2 | 2025-04-26 18:59 @ 94086.2 | -277.39 | -1.05 | initial_stop |
| 19 | 2025-04-26 20:00 @ 94270.4 | 2025-04-26 20:59 @ 94086.2 | -259.58 | -1.05 | initial_stop |
| 20 | 2025-04-27 19:00 @ 94260.1 | 2025-04-27 22:59 @ 93824.8 | -510.54 | -1.02 | initial_stop |
| 21 | 2025-04-28 23:00 @ 94785.1 | 2025-04-30 13:59 @ 93668.1 | -1192.33 | -1.01 | initial_stop |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
