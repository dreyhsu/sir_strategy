# BTCUSDT 1h trend-line breakout (LONG) — 2026-05

## Data & Setup

- Backtest month: `2026-05` (UTC); warm-up months: 2026-04.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 44 |
| Entry signals | 25 |

### Trend-line outcomes

- `entered`: 25
- `unresolved`: 19

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 25 |
| Wins / Losses / Breakeven | 9 / 16 / 0 |
| Win rate | 36.0% |
| Gross P&L | -1,853.02 USDT |
| Net P&L after costs | -3,787.43 USDT |
| Total fees | 1,547.53 USDT |
| Net profit factor | 0.55 |
| Average net P&L | -151.50 USDT |
| Maximum net drawdown | -6,846.10 USDT |

## Exit Reasons

- `initial_stop`: 15
- `target_2r`: 9
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-05-02 14:00 @ 78339.7 | 2026-05-02 21:59 @ 78799.9 | 397.33 | 1.97 | target_2r |
| 2 | 2026-05-03 20:00 @ 78737.0 | 2026-05-03 20:59 @ 78964.8 | 164.77 | 1.93 | target_2r |
| 3 | 2026-05-05 02:00 @ 80318.9 | 2026-05-05 13:59 @ 81296.5 | 912.89 | 1.98 | target_2r |
| 4 | 2026-05-06 09:00 @ 81911.9 | 2026-05-06 14:59 @ 81269.7 | -707.49 | -1.01 | initial_stop |
| 5 | 2026-05-08 08:00 @ 79643.0 | 2026-05-08 09:59 @ 80021.5 | 314.66 | 1.96 | target_2r |
| 6 | 2026-05-08 22:00 @ 80230.2 | 2026-05-10 15:59 @ 81145.2 | 850.38 | 1.98 | target_2r |
| 7 | 2026-05-11 09:00 @ 80731.7 | 2026-05-11 09:59 @ 80800.1 | 3.85 | 1.79 | target_2r |
| 8 | 2026-05-12 19:00 @ 80649.4 | 2026-05-13 12:59 @ 79959.1 | -754.50 | -1.01 | initial_stop |
| 9 | 2026-05-13 21:00 @ 79679.4 | 2026-05-14 16:59 @ 81440.6 | 1696.74 | 1.99 | target_2r |
| 10 | 2026-05-15 23:00 @ 79077.9 | 2026-05-16 06:59 @ 78719.9 | -421.10 | -1.02 | initial_stop |
| 11 | 2026-05-16 20:00 @ 78231.6 | 2026-05-16 22:59 @ 78151.4 | -142.79 | -1.11 | initial_stop |
| 12 | 2026-05-17 11:00 @ 78430.8 | 2026-05-17 14:59 @ 78042.9 | -450.54 | -1.02 | initial_stop |
| 13 | 2026-05-18 08:00 @ 77047.2 | 2026-05-18 10:59 @ 76801.7 | -307.02 | -1.03 | initial_stop |
| 14 | 2026-05-19 08:00 @ 77208.1 | 2026-05-19 11:59 @ 76578.5 | -691.09 | -1.01 | initial_stop |
| 15 | 2026-05-20 06:00 @ 77178.0 | 2026-05-22 15:59 @ 76646.8 | -592.71 | -1.01 | initial_stop |
| 16 | 2026-05-23 11:00 @ 74695.2 | 2026-05-23 13:59 @ 74931.8 | 176.79 | 1.94 | target_2r |
| 17 | 2026-05-24 07:00 @ 76963.7 | 2026-05-24 08:59 @ 76695.1 | -330.03 | -1.03 | initial_stop |
| 18 | 2026-05-24 20:00 @ 76746.2 | 2026-05-24 21:59 @ 76336.1 | -471.34 | -1.02 | initial_stop |
| 19 | 2026-05-26 11:00 @ 77406.4 | 2026-05-26 15:59 @ 76621.3 | -846.71 | -1.01 | initial_stop |
| 20 | 2026-05-28 10:00 @ 73521.4 | 2026-05-28 13:59 @ 72952.6 | -627.34 | -1.01 | initial_stop |
| 21 | 2026-05-28 19:00 @ 73633.8 | 2026-05-29 13:59 @ 72891.8 | -800.56 | -1.01 | initial_stop |
| 22 | 2026-05-29 17:00 @ 74029.5 | 2026-05-29 18:59 @ 73058.5 | -1029.84 | -1.01 | initial_stop |
| 23 | 2026-05-30 02:00 @ 73631.0 | 2026-05-30 04:59 @ 73378.0 | -311.80 | -1.03 | initial_stop |
| 24 | 2026-05-30 11:00 @ 73622.8 | 2026-05-30 14:59 @ 73877.7 | 195.93 | 1.94 | target_2r |
| 25 | 2026-05-31 22:00 @ 73867.9 | 2026-05-31 22:59 @ 73911.1 | -15.89 | 0.12 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
