# BTCUSDT 1h KAMA(60) price-cross (LONG) — 2025-03

## Data & Setup

- Backtest month: `2025-03` (UTC); warm-up months: 2025-02.
- Simulated 1h bars (target month): 743.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- KAMA: Pine v4 "Kaufman Moving Average Adaptive" on the close, `length=60`, `fastLength=2`, `slowLength=30`; `alpha = (er × (2/(fast+1) − 2/(slow+1)) + 2/(slow+1))²`, seeded `nz(kama[1], src)`, so it is warmed by the preceding month(s).
- Entry: 1h close crosses **above** KAMA(60); long filled on the next 1h open.
- Exit: 1h close crosses **below** KAMA(60); filled on the next 1h open.
- No stop and no target — the cross is the only exit. R-multiples use hourly ATR(14) at the signal bar as the risk reference (`risk_reference`).

## Signals & Structure

| Item | Count |
| --- | ---: |
| Close cross-ups above KAMA | 41 |
| Close cross-downs below KAMA | 42 |
| Entry signals taken | 41 |
| Exit signals fired | 41 |
| Hours in position | 319 (42.9% of bars) |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 41 |
| Wins / Losses / Breakeven | 4 / 37 / 0 |
| Win rate | 9.8% |
| Gross P&L | -13,181.00 USDT |
| Net P&L after costs | -16,667.75 USDT |
| Total fees | 2,789.40 USDT |
| Net profit factor | 0.19 |
| Average net P&L | -406.53 USDT |
| Average holding time | 7.8 h |
| Maximum net drawdown | -16,667.75 USDT |

## Exit Reasons

- `kama_cross_down`: 41

## Trade Detail

| # | Entry | Exit | Hours | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---:|---|
| 1 | 2025-03-03 10:00 @ 91,817.2 | 2025-03-03 15:00 @ 89,231.0 | 5 | -2,658.62 | -2.30 | kama_cross_down |
| 2 | 2025-03-05 11:00 @ 89,889.4 | 2025-03-05 12:00 @ 89,768.6 | 1 | -192.63 | -0.10 | kama_cross_down |
| 3 | 2025-03-05 13:00 @ 90,329.3 | 2025-03-05 14:00 @ 89,413.6 | 1 | -987.67 | -0.80 | kama_cross_down |
| 4 | 2025-03-05 21:00 @ 90,457.6 | 2025-03-06 13:00 @ 90,052.6 | 16 | -477.26 | -0.33 | kama_cross_down |
| 5 | 2025-03-06 16:00 @ 90,787.0 | 2025-03-06 17:00 @ 89,271.0 | 1 | -1,588.03 | -1.42 | kama_cross_down |
| 6 | 2025-03-06 23:00 @ 90,275.0 | 2025-03-07 00:00 @ 89,878.9 | 1 | -468.18 | -0.35 | kama_cross_down |
| 7 | 2025-03-07 15:00 @ 90,420.6 | 2025-03-07 16:00 @ 88,416.2 | 1 | -2,076.02 | -1.54 | kama_cross_down |
| 8 | 2025-03-10 12:00 @ 83,548.7 | 2025-03-10 13:00 @ 83,199.7 | 1 | -415.67 | -0.33 | kama_cross_down |
| 9 | 2025-03-11 09:00 @ 81,091.8 | 2025-03-11 14:00 @ 80,856.0 | 5 | -300.57 | -0.21 | kama_cross_down |
| 10 | 2025-03-11 16:00 @ 81,198.8 | 2025-03-13 14:00 @ 81,722.3 | 46 | 458.34 | 0.42 | kama_cross_down |
| 11 | 2025-03-13 15:00 @ 81,974.8 | 2025-03-13 16:00 @ 81,007.9 | 1 | -1,032.09 | -1.13 | kama_cross_down |
| 12 | 2025-03-14 03:00 @ 82,203.9 | 2025-03-16 12:00 @ 82,361.2 | 57 | 91.42 | 0.20 | kama_cross_down |
| 13 | 2025-03-16 15:00 @ 83,342.5 | 2025-03-16 20:00 @ 83,056.0 | 5 | -353.10 | -0.63 | kama_cross_down |
| 14 | 2025-03-17 04:00 @ 83,649.5 | 2025-03-17 06:00 @ 83,080.5 | 2 | -635.66 | -0.95 | kama_cross_down |
| 15 | 2025-03-17 08:00 @ 83,533.7 | 2025-03-17 13:00 @ 83,000.8 | 5 | -599.47 | -0.94 | kama_cross_down |
| 16 | 2025-03-17 16:00 @ 83,507.4 | 2025-03-18 02:00 @ 83,118.9 | 10 | -455.21 | -0.59 | kama_cross_down |
| 17 | 2025-03-18 03:00 @ 83,333.6 | 2025-03-18 04:00 @ 83,099.3 | 1 | -300.92 | -0.39 | kama_cross_down |
| 18 | 2025-03-18 09:00 @ 83,255.8 | 2025-03-18 10:00 @ 82,804.6 | 1 | -517.63 | -0.78 | kama_cross_down |
| 19 | 2025-03-19 01:00 @ 83,078.2 | 2025-03-19 02:00 @ 82,554.1 | 1 | -590.32 | -0.89 | kama_cross_down |
| 20 | 2025-03-19 04:00 @ 83,016.7 | 2025-03-19 05:00 @ 82,914.6 | 1 | -168.47 | -0.18 | kama_cross_down |
| 21 | 2025-03-19 06:00 @ 83,211.2 | 2025-03-20 17:00 @ 83,761.1 | 35 | 483.11 | 1.03 | kama_cross_down |
| 22 | 2025-03-20 18:00 @ 84,066.6 | 2025-03-21 08:00 @ 83,881.1 | 14 | -252.67 | -0.24 | kama_cross_down |
| 23 | 2025-03-21 10:00 @ 84,103.7 | 2025-03-21 12:00 @ 83,997.5 | 2 | -173.45 | -0.19 | kama_cross_down |
| 24 | 2025-03-21 15:00 @ 84,208.4 | 2025-03-21 16:00 @ 83,517.5 | 1 | -757.96 | -1.16 | kama_cross_down |
| 25 | 2025-03-21 17:00 @ 84,075.3 | 2025-03-21 18:00 @ 83,968.4 | 1 | -174.12 | -0.17 | kama_cross_down |
| 26 | 2025-03-21 19:00 @ 84,078.8 | 2025-03-21 20:00 @ 83,916.6 | 1 | -229.40 | -0.27 | kama_cross_down |
| 27 | 2025-03-21 21:00 @ 84,179.1 | 2025-03-22 00:00 @ 84,041.9 | 3 | -204.51 | -0.24 | kama_cross_down |
| 28 | 2025-03-22 01:00 @ 84,162.3 | 2025-03-22 02:00 @ 84,015.8 | 1 | -213.79 | -0.29 | kama_cross_down |
| 29 | 2025-03-22 03:00 @ 84,146.7 | 2025-03-22 15:00 @ 83,962.2 | 12 | -251.75 | -0.39 | kama_cross_down |
| 30 | 2025-03-22 17:00 @ 84,106.3 | 2025-03-22 21:00 @ 83,887.5 | 4 | -286.00 | -0.77 | kama_cross_down |
| 31 | 2025-03-23 03:00 @ 84,199.8 | 2025-03-23 05:00 @ 84,056.5 | 2 | -210.63 | -0.57 | kama_cross_down |
| 32 | 2025-03-23 06:00 @ 84,191.2 | 2025-03-25 02:00 @ 87,034.8 | 44 | 2,775.09 | 12.29 | kama_cross_down |
| 33 | 2025-03-25 10:00 @ 87,181.2 | 2025-03-25 13:00 @ 87,035.3 | 3 | -215.61 | -0.28 | kama_cross_down |
| 34 | 2025-03-25 14:00 @ 87,555.9 | 2025-03-26 03:00 @ 87,276.6 | 13 | -349.22 | -0.51 | kama_cross_down |
| 35 | 2025-03-26 06:00 @ 87,488.7 | 2025-03-26 14:00 @ 86,783.3 | 8 | -775.14 | -1.38 | kama_cross_down |
| 36 | 2025-03-27 03:00 @ 87,538.9 | 2025-03-27 06:00 @ 87,269.0 | 3 | -339.80 | -0.50 | kama_cross_down |
| 37 | 2025-03-27 09:00 @ 87,404.9 | 2025-03-27 10:00 @ 87,360.7 | 1 | -114.18 | -0.10 | kama_cross_down |
| 38 | 2025-03-27 22:00 @ 87,531.0 | 2025-03-27 23:00 @ 87,292.3 | 1 | -308.61 | -0.46 | kama_cross_down |
| 39 | 2025-03-30 09:00 @ 83,347.9 | 2025-03-30 11:00 @ 83,075.3 | 2 | -339.21 | -0.66 | kama_cross_down |
| 40 | 2025-03-31 13:00 @ 82,744.2 | 2025-03-31 14:00 @ 82,453.8 | 1 | -356.50 | -0.48 | kama_cross_down |
| 41 | 2025-03-31 15:00 @ 83,457.8 | 2025-03-31 20:00 @ 82,418.6 | 5 | -1,105.64 | -1.50 | kama_cross_down |

## Notes

- Signals are read at the hourly close and filled at the next hourly open; no intrabar fills are assumed.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- KAMA is warmed with the preceding month(s); trades are counted only inside the target month.
- An open position at the end of the month's data exits at the final close (`data_end`).
- A cross on the final bar is discarded rather than filled, since no next open exists.
