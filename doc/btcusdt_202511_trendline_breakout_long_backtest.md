# BTCUSDT 1h trend-line breakout (LONG) — 2025-11

## Data & Setup

- Backtest month: `2025-11` (UTC); warm-up months: 2025-10.
- Simulated 1h bars (target month): 719.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 28 |
| Entry signals | 17 |

### Trend-line outcomes

- `entered`: 16
- `unresolved`: 12

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 16 |
| Wins / Losses / Breakeven | 2 / 14 / 0 |
| Win rate | 12.5% |
| Gross P&L | -8,363.74 USDT |
| Net P&L after costs | -9,887.95 USDT |
| Total fees | 1,219.37 USDT |
| Net profit factor | 0.38 |
| Average net P&L | -618.00 USDT |
| Maximum net drawdown | -13,662.95 USDT |

## Exit Reasons

- `initial_stop`: 13
- `target_2r`: 2
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-11-04 04:00 @ 107107.8 | 2025-11-04 05:59 @ 106418.2 | -775.06 | -1.02 | initial_stop |
| 2 | 2025-11-04 15:00 @ 104468.8 | 2025-11-04 15:59 @ 103776.6 | -775.52 | -1.02 | initial_stop |
| 3 | 2025-11-05 02:00 @ 100736.2 | 2025-11-05 02:59 @ 101650.2 | 833.02 | 1.98 | target_2r |
| 4 | 2025-11-05 13:00 @ 102632.9 | 2025-11-06 16:59 @ 101342.4 | -1372.09 | -1.01 | initial_stop |
| 5 | 2025-11-07 18:00 @ 102364.9 | 2025-11-13 17:59 @ 99598.9 | -2846.78 | -1.00 | initial_stop |
| 6 | 2025-11-14 03:00 @ 99583.3 | 2025-11-14 03:59 @ 98931.1 | -731.56 | -1.02 | initial_stop |
| 7 | 2025-11-14 17:00 @ 96982.3 | 2025-11-14 18:59 @ 95199.5 | -1859.69 | -1.01 | initial_stop |
| 8 | 2025-11-15 03:00 @ 96462.0 | 2025-11-16 15:59 @ 94535.4 | -2003.00 | -1.00 | initial_stop |
| 9 | 2025-11-17 01:00 @ 95263.9 | 2025-11-17 16:59 @ 93463.6 | -1875.86 | -1.01 | initial_stop |
| 10 | 2025-11-19 12:00 @ 91381.4 | 2025-11-19 15:59 @ 90406.7 | -1047.49 | -1.01 | initial_stop |
| 11 | 2025-11-21 02:00 @ 87026.1 | 2025-11-21 02:59 @ 86592.6 | -502.91 | -1.02 | initial_stop |
| 12 | 2025-11-21 05:00 @ 86025.3 | 2025-11-21 07:59 @ 85387.9 | -706.01 | -1.01 | initial_stop |
| 13 | 2025-11-21 15:00 @ 84809.5 | 2025-11-26 18:59 @ 90042.0 | 5162.61 | 2.00 | target_2r |
| 14 | 2025-11-28 11:00 @ 91811.9 | 2025-11-28 16:59 @ 90861.1 | -1023.84 | -1.01 | initial_stop |
| 15 | 2025-11-29 14:00 @ 90747.6 | 2025-11-29 17:59 @ 90501.1 | -318.92 | -1.04 | initial_stop |
| 16 | 2025-11-30 09:00 @ 91141.7 | 2025-11-30 22:59 @ 91169.8 | -44.86 | 0.07 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
