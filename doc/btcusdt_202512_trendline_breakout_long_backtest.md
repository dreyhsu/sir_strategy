# BTCUSDT 1h trend-line breakout (LONG) — 2025-12

## Data & Setup

- Backtest month: `2025-12` (UTC); warm-up months: 2025-11.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 35 |
| Entry signals | 16 |

### Trend-line outcomes

- `unresolved`: 19
- `entered`: 16

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 16 |
| Wins / Losses / Breakeven | 8 / 8 / 0 |
| Win rate | 50.0% |
| Gross P&L | 3,107.77 USDT |
| Net P&L after costs | 1,671.27 USDT |
| Total fees | 1,149.20 USDT |
| Net profit factor | 1.20 |
| Average net P&L | 104.45 USDT |
| Maximum net drawdown | -6,644.39 USDT |

## Exit Reasons

- `initial_stop`: 8
- `target_2r`: 7
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-12-01 22:00 @ 86388.7 | 2025-12-02 15:59 @ 90076.6 | 3617.28 | 2.00 | target_2r |
| 2 | 2025-12-03 02:00 @ 92224.7 | 2025-12-03 22:59 @ 94166.5 | 1867.27 | 1.99 | target_2r |
| 3 | 2025-12-05 02:00 @ 92331.3 | 2025-12-05 03:59 @ 92025.5 | -379.58 | -1.03 | initial_stop |
| 4 | 2025-12-05 22:00 @ 89154.0 | 2025-12-06 14:59 @ 89938.0 | 712.40 | 1.98 | target_2r |
| 5 | 2025-12-06 15:00 @ 89957.7 | 2025-12-06 19:59 @ 89229.4 | -799.99 | -1.01 | initial_stop |
| 6 | 2025-12-08 09:00 @ 91791.2 | 2025-12-09 05:59 @ 89542.8 | -2320.87 | -1.00 | initial_stop |
| 7 | 2025-12-09 08:00 @ 90458.9 | 2025-12-09 15:59 @ 91652.5 | 1120.68 | 1.98 | target_2r |
| 8 | 2025-12-10 20:00 @ 92923.2 | 2025-12-11 00:59 @ 91784.8 | -1212.25 | -1.01 | initial_stop |
| 9 | 2025-12-12 07:00 @ 92477.9 | 2025-12-12 15:59 @ 91511.8 | -1039.69 | -1.01 | initial_stop |
| 10 | 2025-12-13 04:00 @ 90313.1 | 2025-12-13 10:59 @ 90545.9 | 160.46 | 1.93 | target_2r |
| 11 | 2025-12-13 22:00 @ 90146.9 | 2025-12-13 22:59 @ 90013.5 | -205.48 | -1.07 | initial_stop |
| 12 | 2025-12-15 10:00 @ 89824.7 | 2025-12-15 14:59 @ 88110.0 | -1785.87 | -1.01 | initial_stop |
| 13 | 2025-12-15 22:00 @ 86218.3 | 2025-12-16 01:59 @ 85725.7 | -561.37 | -1.02 | initial_stop |
| 14 | 2025-12-16 07:00 @ 86466.7 | 2025-12-16 15:59 @ 87791.7 | 1255.21 | 1.99 | target_2r |
| 15 | 2025-12-17 12:00 @ 86947.9 | 2025-12-17 14:59 @ 88102.9 | 1084.96 | 1.98 | target_2r |
| 16 | 2025-12-19 07:00 @ 87458.7 | 2025-12-31 22:59 @ 87686.9 | 158.13 | 0.11 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
