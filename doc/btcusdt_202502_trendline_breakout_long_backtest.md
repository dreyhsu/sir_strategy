# BTCUSDT 1h trend-line breakout (LONG) — 2025-02

## Data & Setup

- Backtest month: `2025-02` (UTC); warm-up months: 2025-01.
- Simulated 1h bars (target month): 671.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 16 |
| Entry signals | 6 |

### Trend-line outcomes

- `unresolved`: 10
- `entered`: 6

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 6 |
| Wins / Losses / Breakeven | 2 / 4 / 0 |
| Win rate | 33.3% |
| Gross P&L | -4,060.09 USDT |
| Net P&L after costs | -4,616.66 USDT |
| Total fees | 445.26 USDT |
| Net profit factor | 0.27 |
| Average net P&L | -769.44 USDT |
| Maximum net drawdown | -6,348.18 USDT |

## Exit Reasons

- `initial_stop`: 4
- `target_2r`: 1
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-02-01 13:00 @ 102239.5 | 2025-02-01 19:59 @ 101587.4 | -733.61 | -1.02 | initial_stop |
| 2 | 2025-02-02 15:00 @ 99168.1 | 2025-02-02 16:59 @ 98114.6 | -1132.44 | -1.01 | initial_stop |
| 3 | 2025-02-03 15:00 @ 96549.7 | 2025-02-24 22:59 @ 92755.9 | -3869.45 | -1.00 | initial_stop |
| 4 | 2025-02-25 06:00 @ 92044.6 | 2025-02-25 06:59 @ 91505.3 | -612.67 | -1.02 | initial_stop |
| 5 | 2025-02-27 01:00 @ 84698.6 | 2025-02-27 06:59 @ 86423.1 | 1656.05 | 1.99 | target_2r |
| 6 | 2025-02-28 16:00 @ 83956.5 | 2025-02-28 22:59 @ 84099.2 | 75.47 | 0.03 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
