# BTCUSDT 1h trend-line breakout (LONG) — 2025-06

## Data & Setup

- Backtest month: `2025-06` (UTC); warm-up months: 2025-05.
- Simulated 1h bars (target month): 719.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 30 |
| Entry signals | 16 |

### Trend-line outcomes

- `entered`: 16
- `unresolved`: 14

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 16 |
| Wins / Losses / Breakeven | 7 / 9 / 0 |
| Win rate | 43.8% |
| Gross P&L | 1,456.05 USDT |
| Net P&L after costs | -230.34 USDT |
| Total fees | 1,349.11 USDT |
| Net profit factor | 0.97 |
| Average net P&L | -14.40 USDT |
| Maximum net drawdown | -3,879.11 USDT |

## Exit Reasons

- `initial_stop`: 8
- `target_2r`: 7
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-06-01 14:00 @ 104226.3 | 2025-06-01 16:59 @ 104892.9 | 582.91 | 1.97 | target_2r |
| 2 | 2025-06-02 17:00 @ 104245.1 | 2025-06-02 22:59 @ 105196.2 | 867.35 | 1.98 | target_2r |
| 3 | 2025-06-04 09:00 @ 105402.2 | 2025-06-04 09:59 @ 105696.5 | 209.87 | 1.93 | target_2r |
| 4 | 2025-06-05 01:00 @ 104949.5 | 2025-06-05 05:59 @ 104548.4 | -484.85 | -1.03 | initial_stop |
| 5 | 2025-06-05 13:00 @ 105611.4 | 2025-06-05 13:59 @ 104602.7 | -1092.71 | -1.01 | initial_stop |
| 6 | 2025-06-07 07:00 @ 105282.7 | 2025-06-09 10:59 @ 107357.4 | 1989.66 | 1.99 | target_2r |
| 7 | 2025-06-10 10:00 @ 109486.3 | 2025-06-12 11:59 @ 106960.3 | -2612.62 | -1.00 | initial_stop |
| 8 | 2025-06-12 14:00 @ 107026.5 | 2025-06-12 14:59 @ 107343.0 | 230.72 | 1.93 | target_2r |
| 9 | 2025-06-14 19:00 @ 104853.3 | 2025-06-14 20:59 @ 104390.4 | -546.62 | -1.02 | initial_stop |
| 10 | 2025-06-16 00:00 @ 105545.3 | 2025-06-16 14:59 @ 107247.4 | 1617.06 | 1.99 | target_2r |
| 11 | 2025-06-17 19:00 @ 104369.9 | 2025-06-18 17:59 @ 103563.8 | -889.27 | -1.01 | initial_stop |
| 12 | 2025-06-20 00:00 @ 104617.6 | 2025-06-20 04:59 @ 104192.2 | -508.90 | -1.03 | initial_stop |
| 13 | 2025-06-21 09:00 @ 103777.6 | 2025-06-21 14:59 @ 103329.1 | -531.35 | -1.02 | initial_stop |
| 14 | 2025-06-22 12:00 @ 102704.0 | 2025-06-22 13:59 @ 102147.8 | -638.13 | -1.02 | initial_stop |
| 15 | 2025-06-24 17:00 @ 106170.6 | 2025-06-29 11:59 @ 108441.0 | 2184.54 | 1.99 | target_2r |
| 16 | 2025-06-30 17:00 @ 107562.6 | 2025-06-30 22:59 @ 107040.4 | -608.00 | -0.65 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
