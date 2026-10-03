# BTCUSDT 1h trend-line breakout (LONG) — 2026-03

## Data & Setup

- Backtest month: `2026-03` (UTC); warm-up months: 2026-02.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 51 |
| Entry signals | 20 |

### Trend-line outcomes

- `unresolved`: 31
- `entered`: 20

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 20 |
| Wins / Losses / Breakeven | 7 / 13 / 0 |
| Win rate | 35.0% |
| Gross P&L | 4,445.81 USDT |
| Net P&L after costs | 3,055.03 USDT |
| Total fees | 1,112.62 USDT |
| Net profit factor | 1.43 |
| Average net P&L | 152.75 USDT |
| Maximum net drawdown | -3,483.73 USDT |

## Exit Reasons

- `initial_stop`: 13
- `target_2r`: 6
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-03-03 17:00 @ 68144.6 | 2026-03-04 09:59 @ 71346.9 | 3146.50 | 2.00 | target_2r |
| 2 | 2026-03-05 11:00 @ 73354.2 | 2026-03-05 14:59 @ 72018.3 | -1394.09 | -1.01 | initial_stop |
| 3 | 2026-03-06 02:00 @ 71224.1 | 2026-03-06 04:59 @ 70847.7 | -433.24 | -1.02 | initial_stop |
| 4 | 2026-03-07 01:00 @ 68249.9 | 2026-03-07 02:59 @ 68071.4 | -233.06 | -1.04 | initial_stop |
| 5 | 2026-03-08 07:00 @ 67141.1 | 2026-03-08 22:59 @ 66596.0 | -598.57 | -1.01 | initial_stop |
| 6 | 2026-03-09 04:00 @ 67172.0 | 2026-03-10 02:59 @ 69640.5 | 2413.74 | 1.99 | target_2r |
| 7 | 2026-03-11 01:00 @ 70005.1 | 2026-03-11 02:59 @ 69646.9 | -414.03 | -1.02 | initial_stop |
| 8 | 2026-03-12 11:00 @ 70379.4 | 2026-03-13 12:59 @ 72645.2 | 2208.60 | 1.99 | target_2r |
| 9 | 2026-03-14 20:00 @ 70671.2 | 2026-03-14 23:59 @ 70897.2 | 169.42 | 1.94 | target_2r |
| 10 | 2026-03-18 23:00 @ 71125.0 | 2026-03-18 23:59 @ 71023.2 | -158.67 | -1.07 | initial_stop |
| 11 | 2026-03-19 18:00 @ 69827.0 | 2026-03-20 03:59 @ 70728.5 | 845.27 | 1.98 | target_2r |
| 12 | 2026-03-21 06:00 @ 70680.9 | 2026-03-21 15:59 @ 70423.3 | -314.05 | -1.03 | initial_stop |
| 13 | 2026-03-22 07:00 @ 69133.8 | 2026-03-22 07:59 @ 68874.6 | -314.40 | -1.03 | initial_stop |
| 14 | 2026-03-23 03:00 @ 68289.1 | 2026-03-23 07:59 @ 67635.7 | -707.76 | -1.01 | initial_stop |
| 15 | 2026-03-24 00:00 @ 70873.1 | 2026-03-24 00:59 @ 70640.0 | -289.66 | -1.03 | initial_stop |
| 16 | 2026-03-24 08:00 @ 71262.3 | 2026-03-24 13:59 @ 70242.6 | -1076.35 | -1.01 | initial_stop |
| 17 | 2026-03-25 06:00 @ 71087.2 | 2026-03-26 05:59 @ 70492.9 | -650.89 | -1.01 | initial_stop |
| 18 | 2026-03-28 04:00 @ 66198.4 | 2026-03-28 13:59 @ 66626.4 | 374.85 | 1.97 | target_2r |
| 19 | 2026-03-29 03:00 @ 66780.4 | 2026-03-29 15:59 @ 66328.2 | -505.45 | -1.01 | initial_stop |
| 20 | 2026-03-30 03:00 @ 67093.8 | 2026-03-31 22:59 @ 68134.8 | 986.89 | 0.82 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
