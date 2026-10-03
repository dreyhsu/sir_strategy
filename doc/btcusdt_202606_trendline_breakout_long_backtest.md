# BTCUSDT 1h trend-line breakout (LONG) — 2026-06

## Data & Setup

- Backtest month: `2026-06` (UTC); warm-up months: 2026-05.
- Simulated 1h bars (target month): 719.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 39 |
| Entry signals | 14 |

### Trend-line outcomes

- `unresolved`: 25
- `entered`: 14

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 14 |
| Wins / Losses / Breakeven | 3 / 11 / 0 |
| Win rate | 21.4% |
| Gross P&L | -3,494.17 USDT |
| Net P&L after costs | -4,382.71 USDT |
| Total fees | 710.84 USDT |
| Net profit factor | 0.56 |
| Average net P&L | -313.05 USDT |
| Maximum net drawdown | -5,294.21 USDT |

## Exit Reasons

- `initial_stop`: 11
- `target_2r`: 3

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-06-01 20:00 @ 71578.2 | 2026-06-01 21:59 @ 71092.3 | -542.94 | -1.01 | initial_stop |
| 2 | 2026-06-03 06:00 @ 67296.9 | 2026-06-03 16:59 @ 65811.8 | -1538.35 | -1.00 | initial_stop |
| 3 | 2026-06-04 13:00 @ 63744.6 | 2026-06-05 03:59 @ 62385.4 | -1409.66 | -1.00 | initial_stop |
| 4 | 2026-06-05 21:00 @ 61592.3 | 2026-06-15 11:59 @ 66045.8 | 4402.46 | 2.00 | target_2r |
| 5 | 2026-06-15 12:00 @ 66198.6 | 2026-06-16 14:59 @ 65553.3 | -697.98 | -1.01 | initial_stop |
| 6 | 2026-06-18 07:00 @ 64061.3 | 2026-06-18 07:59 @ 64477.3 | 364.55 | 1.97 | target_2r |
| 7 | 2026-06-19 00:00 @ 62930.3 | 2026-06-19 03:59 @ 62331.6 | -648.83 | -1.01 | initial_stop |
| 8 | 2026-06-19 13:00 @ 62805.7 | 2026-06-20 00:59 @ 63704.7 | 848.38 | 1.99 | target_2r |
| 9 | 2026-06-21 04:00 @ 64405.2 | 2026-06-21 20:59 @ 63770.0 | -686.49 | -1.01 | initial_stop |
| 10 | 2026-06-22 02:00 @ 64581.0 | 2026-06-23 06:59 @ 63280.8 | -1351.33 | -1.00 | initial_stop |
| 11 | 2026-06-25 02:00 @ 60899.0 | 2026-06-25 13:59 @ 59357.8 | -1589.33 | -1.00 | initial_stop |
| 12 | 2026-06-27 07:00 @ 60351.2 | 2026-06-27 22:59 @ 59913.1 | -486.23 | -1.01 | initial_stop |
| 13 | 2026-06-28 08:00 @ 60198.4 | 2026-06-28 13:59 @ 59950.6 | -295.87 | -1.02 | initial_stop |
| 14 | 2026-06-29 03:00 @ 59737.8 | 2026-06-29 14:59 @ 59034.2 | -751.09 | -1.01 | initial_stop |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
