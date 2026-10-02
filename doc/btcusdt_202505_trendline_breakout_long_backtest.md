# BTCUSDT 1h trend-line breakout (LONG) — 2025-05

## Data & Setup

- Backtest month: `2025-05` (UTC); warm-up months: 2025-04.
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

- `entered`: 20
- `unresolved`: 18

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 20 |
| Wins / Losses / Breakeven | 7 / 13 / 0 |
| Win rate | 35.0% |
| Gross P&L | 2,258.18 USDT |
| Net P&L after costs | 196.62 USDT |
| Total fees | 1,649.25 USDT |
| Net profit factor | 1.02 |
| Average net P&L | 9.83 USDT |
| Maximum net drawdown | -3,678.05 USDT |

## Exit Reasons

- `initial_stop`: 13
- `target_2r`: 6
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-05-02 15:00 @ 97699.9 | 2025-05-03 03:59 @ 96292.4 | -1485.10 | -1.01 | initial_stop |
| 2 | 2025-05-03 14:00 @ 96297.6 | 2025-05-03 17:59 @ 95844.1 | -530.37 | -1.02 | initial_stop |
| 3 | 2025-05-04 20:00 @ 95543.6 | 2025-05-04 22:59 @ 95291.3 | -328.62 | -1.04 | initial_stop |
| 4 | 2025-05-05 18:00 @ 94468.0 | 2025-05-06 11:59 @ 93716.6 | -826.69 | -1.01 | initial_stop |
| 5 | 2025-05-06 16:00 @ 94522.7 | 2025-05-06 23:59 @ 96427.5 | 1828.48 | 1.99 | target_2r |
| 6 | 2025-05-08 01:00 @ 97734.8 | 2025-05-08 15:59 @ 100945.0 | 3130.78 | 1.99 | target_2r |
| 7 | 2025-05-09 20:00 @ 103155.8 | 2025-05-10 23:59 @ 104563.8 | 1324.88 | 1.99 | target_2r |
| 8 | 2025-05-11 10:00 @ 104323.5 | 2025-05-12 14:59 @ 103317.6 | -1089.02 | -1.01 | initial_stop |
| 9 | 2025-05-12 23:00 @ 102822.8 | 2025-05-13 03:59 @ 101573.5 | -1331.00 | -1.01 | initial_stop |
| 10 | 2025-05-13 05:00 @ 102710.3 | 2025-05-15 09:59 @ 101573.5 | -1218.44 | -1.01 | initial_stop |
| 11 | 2025-05-15 16:00 @ 103221.6 | 2025-05-18 23:59 @ 106128.6 | 2823.29 | 1.99 | target_2r |
| 12 | 2025-05-19 12:00 @ 102922.4 | 2025-05-19 12:59 @ 102156.2 | -848.24 | -1.01 | initial_stop |
| 13 | 2025-05-20 16:00 @ 105305.0 | 2025-05-20 19:59 @ 107113.4 | 1723.38 | 1.99 | target_2r |
| 14 | 2025-05-22 19:00 @ 111701.9 | 2025-05-22 20:59 @ 110841.5 | -949.37 | -1.01 | initial_stop |
| 15 | 2025-05-23 18:00 @ 109372.0 | 2025-05-23 18:59 @ 108881.5 | -577.83 | -1.02 | initial_stop |
| 16 | 2025-05-24 09:00 @ 108216.2 | 2025-05-25 00:59 @ 107260.8 | -1041.64 | -1.01 | initial_stop |
| 17 | 2025-05-25 19:00 @ 107372.2 | 2025-05-25 22:59 @ 108250.1 | 791.60 | 1.98 | target_2r |
| 18 | 2025-05-26 16:00 @ 109974.3 | 2025-05-26 16:59 @ 109538.2 | -523.86 | -1.03 | initial_stop |
| 19 | 2025-05-27 08:00 @ 109499.0 | 2025-05-28 10:59 @ 108209.2 | -1376.95 | -1.01 | initial_stop |
| 20 | 2025-05-31 05:00 @ 103772.1 | 2025-05-31 22:59 @ 104556.7 | 701.34 | 1.26 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
