# BTCUSDT 1h trend-line breakout (LONG) — 2025-10

## Data & Setup

- Backtest month: `2025-10` (UTC); warm-up months: 2025-09.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 37 |
| Entry signals | 22 |

### Trend-line outcomes

- `entered`: 22
- `unresolved`: 15

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 22 |
| Wins / Losses / Breakeven | 10 / 12 / 0 |
| Win rate | 45.5% |
| Gross P&L | 573.57 USDT |
| Net P&L after costs | -1,976.42 USDT |
| Total fees | 2,040.00 USDT |
| Net profit factor | 0.90 |
| Average net P&L | -89.84 USDT |
| Maximum net drawdown | -9,602.64 USDT |

## Exit Reasons

- `initial_stop`: 12
- `target_2r`: 10

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-10-02 09:00 @ 118647.2 | 2025-10-02 12:59 @ 119270.2 | 527.83 | 1.96 | target_2r |
| 2 | 2025-10-03 10:00 @ 120269.9 | 2025-10-03 15:59 @ 121557.4 | 1190.76 | 1.98 | target_2r |
| 3 | 2025-10-04 14:00 @ 122347.7 | 2025-10-04 15:59 @ 121912.4 | -533.03 | -1.03 | initial_stop |
| 4 | 2025-10-04 23:00 @ 122243.2 | 2025-10-05 02:59 @ 123650.5 | 1308.92 | 1.98 | target_2r |
| 5 | 2025-10-05 22:00 @ 122694.6 | 2025-10-05 22:59 @ 122970.6 | 177.77 | 1.91 | target_2r |
| 6 | 2025-10-06 12:00 @ 124173.7 | 2025-10-06 18:59 @ 125844.0 | 1570.24 | 1.99 | target_2r |
| 7 | 2025-10-08 01:00 @ 121881.1 | 2025-10-08 17:59 @ 123954.9 | 1975.44 | 1.99 | target_2r |
| 8 | 2025-10-09 12:00 @ 122685.3 | 2025-10-09 14:59 @ 121190.3 | -1592.54 | -1.01 | initial_stop |
| 9 | 2025-10-10 06:00 @ 121541.8 | 2025-10-10 07:59 @ 120948.7 | -690.05 | -1.02 | initial_stop |
| 10 | 2025-10-12 05:00 @ 111497.2 | 2025-10-12 20:59 @ 115278.8 | 3690.86 | 1.99 | target_2r |
| 11 | 2025-10-13 14:00 @ 115302.9 | 2025-10-13 14:59 @ 114117.9 | -1276.81 | -1.01 | initial_stop |
| 12 | 2025-10-13 20:00 @ 115738.2 | 2025-10-14 02:59 @ 113962.2 | -1867.85 | -1.01 | initial_stop |
| 13 | 2025-10-14 16:00 @ 112834.2 | 2025-10-15 15:59 @ 110562.8 | -2360.70 | -1.00 | initial_stop |
| 14 | 2025-10-15 19:00 @ 111384.0 | 2025-10-15 20:59 @ 110682.3 | -790.53 | -1.02 | initial_stop |
| 15 | 2025-10-17 16:00 @ 106760.7 | 2025-10-20 06:59 @ 111295.9 | 4448.00 | 2.00 | target_2r |
| 16 | 2025-10-21 15:00 @ 112138.8 | 2025-10-22 07:59 @ 107638.9 | -4587.79 | -1.00 | initial_stop |
| 17 | 2025-10-23 01:00 @ 107826.4 | 2025-10-23 06:59 @ 109183.0 | 1269.84 | 1.98 | target_2r |
| 18 | 2025-10-25 02:00 @ 111037.8 | 2025-10-26 11:59 @ 113082.5 | 1955.05 | 1.99 | target_2r |
| 19 | 2025-10-26 23:00 @ 114643.2 | 2025-10-28 20:59 @ 113256.5 | -1477.85 | -1.01 | initial_stop |
| 20 | 2025-10-29 08:00 @ 113523.4 | 2025-10-29 14:59 @ 112371.3 | -1242.45 | -1.01 | initial_stop |
| 21 | 2025-10-30 07:00 @ 110731.2 | 2025-10-30 12:59 @ 108492.8 | -2326.01 | -1.00 | initial_stop |
| 22 | 2025-10-31 05:00 @ 110063.4 | 2025-10-31 16:59 @ 108805.4 | -1345.53 | -1.01 | initial_stop |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
