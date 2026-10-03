# BTCUSDT 1h trend-line breakout (LONG) — 2025-09

## Data & Setup

- Backtest month: `2025-09` (UTC); warm-up months: 2025-08.
- Simulated 1h bars (target month): 719.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 38 |
| Entry signals | 22 |

### Trend-line outcomes

- `entered`: 22
- `unresolved`: 16

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 22 |
| Wins / Losses / Breakeven | 6 / 16 / 0 |
| Win rate | 27.3% |
| Gross P&L | -1,016.34 USDT |
| Net P&L after costs | -3,480.77 USDT |
| Total fees | 1,971.55 USDT |
| Net profit factor | 0.68 |
| Average net P&L | -158.22 USDT |
| Maximum net drawdown | -8,274.40 USDT |

## Exit Reasons

- `initial_stop`: 16
- `target_2r`: 5
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-09-01 19:00 @ 109199.3 | 2025-09-01 20:59 @ 108721.7 | -564.76 | -1.02 | initial_stop |
| 2 | 2025-09-02 00:00 @ 109198.8 | 2025-09-03 14:59 @ 112096.2 | 2808.91 | 1.99 | target_2r |
| 3 | 2025-09-04 21:00 @ 110361.0 | 2025-09-05 07:59 @ 112302.1 | 1851.97 | 1.99 | target_2r |
| 4 | 2025-09-06 03:00 @ 111181.1 | 2025-09-06 15:59 @ 110533.0 | -736.76 | -1.02 | initial_stop |
| 5 | 2025-09-07 08:00 @ 110721.9 | 2025-09-08 09:59 @ 111924.6 | 1113.69 | 1.98 | target_2r |
| 6 | 2025-09-09 06:00 @ 112163.4 | 2025-09-09 15:59 @ 111268.9 | -983.92 | -1.01 | initial_stop |
| 7 | 2025-09-10 00:00 @ 111511.1 | 2025-09-10 00:59 @ 111230.8 | -369.47 | -1.04 | initial_stop |
| 8 | 2025-09-11 14:00 @ 114589.7 | 2025-09-12 00:59 @ 116042.4 | 1360.46 | 1.98 | target_2r |
| 9 | 2025-09-13 21:00 @ 115848.8 | 2025-09-14 13:59 @ 115275.1 | -666.16 | -1.02 | initial_stop |
| 10 | 2025-09-14 20:00 @ 115608.9 | 2025-09-14 23:59 @ 115150.7 | -550.48 | -1.03 | initial_stop |
| 11 | 2025-09-16 05:00 @ 115469.9 | 2025-09-16 13:59 @ 114952.9 | -609.21 | -1.02 | initial_stop |
| 12 | 2025-09-17 23:00 @ 116519.7 | 2025-09-19 19:59 @ 115172.6 | -1439.75 | -1.01 | initial_stop |
| 13 | 2025-09-20 03:00 @ 115556.0 | 2025-09-22 00:59 @ 115070.9 | -577.31 | -1.02 | initial_stop |
| 14 | 2025-09-23 05:00 @ 112388.9 | 2025-09-23 18:59 @ 111749.2 | -729.37 | -1.02 | initial_stop |
| 15 | 2025-09-24 06:00 @ 112607.3 | 2025-09-25 04:59 @ 111628.5 | -1068.42 | -1.01 | initial_stop |
| 16 | 2025-09-25 16:00 @ 111549.6 | 2025-09-25 16:59 @ 110947.4 | -691.15 | -1.02 | initial_stop |
| 17 | 2025-09-26 07:00 @ 109309.8 | 2025-09-26 07:59 @ 108923.6 | -473.52 | -1.03 | initial_stop |
| 18 | 2025-09-26 14:00 @ 109632.3 | 2025-09-26 14:59 @ 108837.3 | -882.33 | -1.01 | initial_stop |
| 19 | 2025-09-27 03:00 @ 109359.4 | 2025-09-27 09:59 @ 109105.0 | -341.83 | -1.04 | initial_stop |
| 20 | 2025-09-27 16:00 @ 109351.7 | 2025-09-27 17:59 @ 109194.3 | -244.87 | -1.07 | initial_stop |
| 21 | 2025-09-27 19:00 @ 109394.2 | 2025-09-28 00:59 @ 109683.7 | 201.88 | 1.93 | target_2r |
| 22 | 2025-09-30 19:00 @ 113669.4 | 2025-09-30 22:59 @ 113872.0 | 111.63 | 0.23 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
