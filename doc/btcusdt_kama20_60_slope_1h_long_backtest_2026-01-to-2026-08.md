# BTCUSDT KAMA(20)/KAMA(60) Crossover Long — 2026-01 → 2026-08

## Data & Setup

- Span: `2026-01 → 2026-08` (UTC), simulated as **one continuous series**, so no trade is force-closed at a month boundary.
- Hourly bars: 5,824; warm-up bars (no entries): 260; first tradable bar: 2026-01-11 20:00 UTC.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Entry: KAMA(20) crosses **above** KAMA(60) on the hourly close and the trend gate below is open; filled at the next hourly open.
- Exit: KAMA(20) crosses **below** KAMA(60); filled at the next hourly open.
- Trend gate: `slope` — SMA(200) of `open` must be rising at least `0%` over `24h`.
- Break-even lock: disabled.
- Trailing stop: disabled — the bearish cross is the only exit.
- KAMA: Pine v4 port (everget, GPL-3.0) on `close`, `fastLength=2`, `slowLength=30`; `alpha = (er × (2/(fast+1) − 2/(slow+1)) + 2/(slow+1))²`, seeded `nz(kama[1], src)`.
- Because of that seed both KAMAs start at the first bar's price and creep at `slowAlpha²` until index `length`, so the first `260` bars are excluded from entry consideration as seeding artifacts.
- R-multiples use hourly ATR(20) at the signal bar as the risk reference (`risk_reference`) — there is no stop distance to define 1R.
- One position at a time; a bullish cross while already long is ignored. An open position at the end of data exits at the final close (`data_end`).

## Signals & Structure

| Item | Count |
| --- | ---: |
| KAMA bullish crosses (all) | 48 |
| KAMA bearish crosses (all) | 47 |
| Bullish crosses inside warm-up (discarded) | 1 |
| Bullish crosses rejected by the `slope` trend gate | 30 |
| Entry signals taken | 17 |
| Exit signals fired | 16 |
| Hours in position | 1365 (23.4% of bars) |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 17 |
| Wins / Losses / Breakeven | 8 / 9 / 0 |
| Win rate | 47.1% |
| Gross P&L | 17,473.80 USDT |
| Net P&L after costs | 16,250.90 USDT |
| Total fees | 978.32 USDT |
| Net profit factor | 2.97 |
| Average net P&L | 955.94 USDT |
| Largest win / loss | 11,261.04 / -1,847.56 USDT |
| Average holding time | 80.3 h |
| Maximum net drawdown | -2,962.62 USDT |
| Buy & hold over the same window | -12,167.60 USDT |
| Strategy vs buy & hold | 28,418.50 USDT |

## Monthly Breakdown

Each trade is attributed to the month it **exited** in, so a trade opened late in one month
lands in the next. Month figures therefore sum to the headline net P&L.

| Month | Trades | Wins | Win rate | Net USDT |
| --- | ---: | ---: | ---: | ---: |
| 2026-01 | 1 | 1 | 100.0% | 3,407.58 |
| 2026-03 | 1 | 1 | 100.0% | 5,661.76 |
| 2026-04 | 5 | 3 | 60.0% | 1,497.09 |
| 2026-05 | 1 | 0 | 0.0% | -364.68 |
| 2026-06 | 1 | 1 | 100.0% | 420.42 |
| 2026-07 | 4 | 1 | 25.0% | -2,862.24 |
| 2026-08 | 4 | 1 | 25.0% | 8,490.97 |

## Exit Reasons

- `kama_bearish_cross`: 16
- `data_end`: 1

## Trade Detail

| # | Entry | Exit | Hours | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---:|---|
| 1 | 2026-01-12 06:00 @ 92,075.9 | 2026-01-16 10:00 @ 95,558.5 | 100 | 3,407.58 | 9.38 | kama_bearish_cross |
| 2 | 2026-03-08 16:00 @ 67,181.3 | 2026-03-18 12:00 @ 72,899.1 | 236 | 5,661.76 | 12.98 | kama_bearish_cross |
| 3 | 2026-04-06 00:00 @ 69,004.8 | 2026-04-07 15:00 @ 67,824.3 | 39 | -1,235.21 | -3.66 | kama_bearish_cross |
| 4 | 2026-04-07 23:00 @ 71,487.0 | 2026-04-12 12:00 @ 71,427.9 | 109 | -116.36 | -0.11 | kama_bearish_cross |
| 5 | 2026-04-13 20:00 @ 73,279.4 | 2026-04-19 02:00 @ 75,569.8 | 126 | 2,230.88 | 4.77 | kama_bearish_cross |
| 6 | 2026-04-20 20:00 @ 76,260.1 | 2026-04-27 21:00 @ 76,908.1 | 169 | 586.72 | 1.25 | kama_bearish_cross |
| 7 | 2026-04-29 17:00 @ 75,782.3 | 2026-04-30 04:00 @ 75,874.0 | 11 | 31.07 | 0.22 | kama_bearish_cross |
| 8 | 2026-05-10 05:00 @ 80,725.8 | 2026-05-12 14:00 @ 80,425.6 | 57 | -364.68 | -1.24 | kama_bearish_cross |
| 9 | 2026-06-20 16:00 @ 64,145.8 | 2026-06-22 12:00 @ 64,617.7 | 44 | 420.42 | 1.29 | kama_bearish_cross |
| 10 | 2026-07-07 01:00 @ 64,181.5 | 2026-07-08 07:00 @ 62,622.2 | 30 | -1,610.00 | -3.61 | kama_bearish_cross |
| 11 | 2026-07-10 02:00 @ 63,733.1 | 2026-07-13 05:00 @ 62,643.4 | 75 | -1,140.19 | -2.67 | kama_bearish_cross |
| 12 | 2026-07-18 11:00 @ 63,987.6 | 2026-07-23 16:00 @ 64,933.9 | 125 | 894.74 | 4.16 | kama_bearish_cross |
| 13 | 2026-07-26 18:00 @ 64,669.8 | 2026-07-28 00:00 @ 63,714.3 | 30 | -1,006.79 | -6.17 | kama_bearish_cross |
| 14 | 2026-08-12 20:00 @ 63,401.1 | 2026-08-14 06:00 @ 63,351.5 | 34 | -100.38 | -0.22 | kama_bearish_cross |
| 15 | 2026-08-19 15:00 @ 65,902.1 | 2026-08-21 13:00 @ 77,220.4 | 46 | 11,261.04 | 45.90 | kama_bearish_cross |
| 16 | 2026-08-24 13:00 @ 79,154.2 | 2026-08-28 21:00 @ 77,369.3 | 104 | -1,847.56 | -2.97 | kama_bearish_cross |
| 17 | 2026-08-30 17:00 @ 79,312.8 | 2026-08-31 22:59 @ 78,553.8 | 30 | -822.13 | -2.59 | data_end |

## Notes

- Signals are read at the hourly close and filled at the next hourly open; no intrabar fills are assumed.
- When a stop is armed, 1h OHLC cannot resolve whether the bar's high or low came first. A stop is checked against the open (gap) and then the low, and is only *updated* from this bar's high afterwards, so a stop derived from a bar can never also be triggered by that same bar.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- A cross on the final bar is discarded rather than filled, since no next open exists.
