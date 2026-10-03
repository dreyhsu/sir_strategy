# BTCUSDT 1h trend-line breakout (LONG) — 2026-08

## Data & Setup

- Backtest month: `2026-08` (UTC); warm-up months: 2026-07.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend line: two most recent confirmed swing highs (k=2) within the last `48` 1h bars; slope ≤ `0` (descending).
- Entry: 1h close crosses above line + `0 × ATR(14)`; long filled on the next 1h open.
- Risk: R = entry − most recent confirmed swing-low *close*; stop at that close (−1R), target `2R`.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 48 |
| Entry signals | 24 |

### Trend-line outcomes

- `unresolved`: 24
- `entered`: 24

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 23 |
| Wins / Losses / Breakeven | 11 / 12 / 0 |
| Win rate | 47.8% |
| Gross P&L | 5,785.30 USDT |
| Net P&L after costs | 4,205.74 USDT |
| Total fees | 1,263.65 USDT |
| Net profit factor | 2.00 |
| Average net P&L | 182.86 USDT |
| Maximum net drawdown | -1,995.67 USDT |

## Exit Reasons

- `target_2r`: 11
- `initial_stop`: 11
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2026-08-02 00:00 @ 62798.6 | 2026-08-02 02:59 @ 63385.2 | 536.15 | 1.98 | target_2r |
| 2 | 2026-08-03 13:00 @ 62676.2 | 2026-08-03 13:59 @ 62997.4 | 270.96 | 1.96 | target_2r |
| 3 | 2026-08-04 19:00 @ 64277.2 | 2026-08-04 20:59 @ 63922.5 | -406.00 | -1.02 | initial_stop |
| 4 | 2026-08-07 09:00 @ 64582.8 | 2026-08-07 12:59 @ 65290.1 | 655.44 | 1.98 | target_2r |
| 5 | 2026-08-08 04:00 @ 65006.5 | 2026-08-09 01:59 @ 64874.1 | -184.34 | -1.05 | initial_stop |
| 6 | 2026-08-09 11:00 @ 64934.0 | 2026-08-09 13:59 @ 65210.5 | 224.41 | 1.95 | target_2r |
| 7 | 2026-08-10 07:00 @ 65279.6 | 2026-08-10 09:59 @ 64939.9 | -391.81 | -1.02 | initial_stop |
| 8 | 2026-08-10 23:00 @ 63993.9 | 2026-08-11 00:59 @ 63860.0 | -185.03 | -1.05 | initial_stop |
| 9 | 2026-08-11 10:00 @ 64287.3 | 2026-08-11 14:59 @ 63933.6 | -405.01 | -1.02 | initial_stop |
| 10 | 2026-08-12 01:00 @ 63723.6 | 2026-08-12 14:59 @ 63346.2 | -428.23 | -1.02 | initial_stop |
| 11 | 2026-08-13 00:00 @ 63460.9 | 2026-08-13 00:59 @ 63656.5 | 144.68 | 1.94 | target_2r |
| 12 | 2026-08-13 22:00 @ 63451.0 | 2026-08-14 06:59 @ 63115.1 | -386.58 | -1.02 | initial_stop |
| 13 | 2026-08-15 02:00 @ 63017.1 | 2026-08-16 16:59 @ 63331.4 | 263.73 | 1.96 | target_2r |
| 14 | 2026-08-18 15:00 @ 64690.0 | 2026-08-19 06:59 @ 64134.1 | -607.41 | -1.01 | initial_stop |
| 15 | 2026-08-19 11:00 @ 64430.3 | 2026-08-19 12:59 @ 64866.3 | 384.28 | 1.97 | target_2r |
| 16 | 2026-08-20 07:00 @ 69845.8 | 2026-08-20 08:59 @ 71163.2 | 1261.05 | 1.99 | target_2r |
| 17 | 2026-08-22 16:00 @ 77003.3 | 2026-08-22 16:59 @ 76968.0 | -96.89 | -1.28 | initial_stop |
| 18 | 2026-08-23 12:00 @ 77303.8 | 2026-08-24 15:59 @ 79862.9 | 2496.21 | 1.99 | target_2r |
| 19 | 2026-08-25 23:00 @ 78857.9 | 2026-08-26 12:59 @ 78161.0 | -759.71 | -1.01 | initial_stop |
| 20 | 2026-08-26 22:00 @ 78690.8 | 2026-08-27 15:59 @ 80535.5 | 1780.99 | 1.99 | target_2r |
| 21 | 2026-08-29 14:00 @ 77677.9 | 2026-08-29 18:59 @ 78151.0 | 410.79 | 1.97 | target_2r |
| 22 | 2026-08-30 07:00 @ 78261.6 | 2026-08-30 08:59 @ 78043.0 | -281.15 | -1.04 | initial_stop |
| 23 | 2026-08-31 15:00 @ 78581.8 | 2026-08-31 22:59 @ 78553.8 | -90.77 | -0.02 | data_end |

## Notes

- 1h OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, and swing pivots are consumed only after their k-bar confirmation.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
