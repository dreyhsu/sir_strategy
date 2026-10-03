# BTCUSDT 1h KAMA(60) price-cross (LONG) — 2025-04

## Data & Setup

- Backtest month: `2025-04` (UTC); warm-up months: 2025-03.
- Simulated 1h bars (target month): 719.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- KAMA: Pine v4 "Kaufman Moving Average Adaptive" on the close, `length=60`, `fastLength=2`, `slowLength=30`; `alpha = (er × (2/(fast+1) − 2/(slow+1)) + 2/(slow+1))²`, seeded `nz(kama[1], src)`, so it is warmed by the preceding month(s).
- Entry: 1h close crosses **above** KAMA(60); long filled on the next 1h open.
- Exit: 1h close crosses **below** KAMA(60); filled on the next 1h open.
- No stop and no target — the cross is the only exit. R-multiples use hourly ATR(14) at the signal bar as the risk reference (`risk_reference`).

## Signals & Structure

| Item | Count |
| --- | ---: |
| Close cross-ups above KAMA | 27 |
| Close cross-downs below KAMA | 27 |
| Entry signals taken | 27 |
| Exit signals fired | 26 |
| Hours in position | 521 (72.5% of bars) |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 27 |
| Wins / Losses / Breakeven | 6 / 21 / 0 |
| Win rate | 22.2% |
| Gross P&L | 1,538.90 USDT |
| Net P&L after costs | -780.13 USDT |
| Total fees | 1,855.22 USDT |
| Net profit factor | 0.94 |
| Average net P&L | -28.89 USDT |
| Average holding time | 19.3 h |
| Maximum net drawdown | -6,366.41 USDT |

## Exit Reasons

- `kama_cross_down`: 26
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Hours | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---:|---|
| 1 | 2025-04-01 02:00 @ 82,679.3 | 2025-04-02 23:00 @ 82,775.9 | 45 | 30.47 | 0.16 | kama_cross_down |
| 2 | 2025-04-04 09:00 @ 84,381.2 | 2025-04-04 11:00 @ 82,526.2 | 2 | -1,921.75 | -2.93 | kama_cross_down |
| 3 | 2025-04-04 18:00 @ 84,442.2 | 2025-04-05 00:00 @ 83,853.0 | 6 | -656.55 | -0.60 | kama_cross_down |
| 4 | 2025-04-05 02:00 @ 83,957.5 | 2025-04-05 04:00 @ 83,577.2 | 2 | -447.27 | -0.48 | kama_cross_down |
| 5 | 2025-04-07 15:00 @ 79,007.2 | 2025-04-07 17:00 @ 77,387.1 | 2 | -1,682.70 | -1.18 | kama_cross_down |
| 6 | 2025-04-07 18:00 @ 79,040.3 | 2025-04-07 20:00 @ 78,085.9 | 2 | -1,017.26 | -0.67 | kama_cross_down |
| 7 | 2025-04-07 21:00 @ 78,914.9 | 2025-04-08 15:00 @ 78,432.6 | 18 | -545.27 | -0.36 | kama_cross_down |
| 8 | 2025-04-09 17:00 @ 78,235.8 | 2025-04-10 16:00 @ 78,722.6 | 23 | 424.02 | 0.48 | kama_cross_down |
| 9 | 2025-04-10 19:00 @ 79,459.0 | 2025-04-11 01:00 @ 79,002.8 | 6 | -519.63 | -0.46 | kama_cross_down |
| 10 | 2025-04-11 02:00 @ 80,413.8 | 2025-04-13 21:00 @ 83,464.4 | 67 | 2,984.96 | 3.53 | kama_cross_down |
| 11 | 2025-04-14 00:00 @ 83,722.2 | 2025-04-15 20:00 @ 83,946.1 | 44 | 156.87 | 0.31 | kama_cross_down |
| 12 | 2025-04-15 22:00 @ 84,145.5 | 2025-04-15 23:00 @ 83,778.5 | 1 | -434.16 | -0.68 | kama_cross_down |
| 13 | 2025-04-16 15:00 @ 84,568.5 | 2025-04-16 18:00 @ 83,229.3 | 3 | -1,406.30 | -2.37 | kama_cross_down |
| 14 | 2025-04-16 20:00 @ 84,294.4 | 2025-04-17 00:00 @ 83,981.7 | 4 | -380.04 | -0.43 | kama_cross_down |
| 15 | 2025-04-17 01:00 @ 84,185.1 | 2025-04-17 04:00 @ 83,944.9 | 3 | -307.47 | -0.39 | kama_cross_down |
| 16 | 2025-04-17 05:00 @ 84,126.0 | 2025-04-17 15:00 @ 84,041.6 | 10 | -151.68 | -0.15 | kama_cross_down |
| 17 | 2025-04-17 16:00 @ 84,504.0 | 2025-04-20 10:00 @ 84,491.6 | 66 | -80.10 | -0.02 | kama_cross_down |
| 18 | 2025-04-20 15:00 @ 84,593.0 | 2025-04-20 16:00 @ 84,296.2 | 1 | -364.34 | -1.06 | kama_cross_down |
| 19 | 2025-04-20 17:00 @ 84,578.5 | 2025-04-23 15:00 @ 92,883.1 | 70 | 8,233.67 | 28.80 | kama_cross_down |
| 20 | 2025-04-23 16:00 @ 93,149.5 | 2025-04-24 03:00 @ 93,043.8 | 11 | -180.20 | -0.13 | kama_cross_down |
| 21 | 2025-04-24 15:00 @ 93,065.1 | 2025-04-25 03:00 @ 92,932.5 | 12 | -207.00 | -0.23 | kama_cross_down |
| 22 | 2025-04-25 04:00 @ 93,272.3 | 2025-04-25 05:00 @ 92,995.6 | 1 | -351.23 | -0.47 | kama_cross_down |
| 23 | 2025-04-25 06:00 @ 93,169.3 | 2025-04-27 13:00 @ 93,686.7 | 55 | 442.67 | 0.91 | kama_cross_down |
| 24 | 2025-04-27 14:00 @ 94,021.8 | 2025-04-28 00:00 @ 93,687.6 | 10 | -409.25 | -0.94 | kama_cross_down |
| 25 | 2025-04-28 05:00 @ 93,991.3 | 2025-04-28 16:00 @ 93,763.3 | 11 | -303.08 | -0.54 | kama_cross_down |
| 26 | 2025-04-28 18:00 @ 94,047.3 | 2025-04-30 14:00 @ 92,968.9 | 44 | -1,153.21 | -1.80 | kama_cross_down |
| 27 | 2025-04-30 21:00 @ 94,525.4 | 2025-04-30 22:59 @ 94,066.5 | 2 | -534.30 | -0.78 | data_end |

## Notes

- Signals are read at the hourly close and filled at the next hourly open; no intrabar fills are assumed.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- KAMA is warmed with the preceding month(s); trades are counted only inside the target month.
- An open position at the end of the month's data exits at the final close (`data_end`).
- A cross on the final bar is discarded rather than filled, since no next open exists.
