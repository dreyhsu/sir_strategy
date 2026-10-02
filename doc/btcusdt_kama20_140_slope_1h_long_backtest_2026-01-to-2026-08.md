# BTCUSDT KAMA(20)/KAMA(140) Crossover Long — 2026-01 → 2026-08

## Data & Setup

- Span: `2026-01 → 2026-08` (UTC), simulated as **one continuous series**, so no trade is force-closed at a month boundary.
- Hourly bars: 5,824; warm-up bars (no entries): 340; first tradable bar: 2026-01-15 04:00 UTC.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Entry: KAMA(20) crosses **above** KAMA(140) on the hourly close and the trend gate below is open; filled at the next hourly open.
- Exit: KAMA(20) crosses **below** KAMA(140); filled at the next hourly open.
- Trend gate: `slope` — SMA(200) of `open` must be rising at least `0%` over `24h`.
- Break-even lock: disabled.
- Trailing stop: disabled — the bearish cross is the only exit.
- KAMA: Pine v4 port (everget, GPL-3.0) on `close`, `fastLength=2`, `slowLength=30`; `alpha = (er × (2/(fast+1) − 2/(slow+1)) + 2/(slow+1))²`, seeded `nz(kama[1], src)`.
- Because of that seed both KAMAs start at the first bar's price and creep at `slowAlpha²` until index `length`, so the first `340` bars are excluded from entry consideration as seeding artifacts.
- R-multiples use hourly ATR(20) at the signal bar as the risk reference (`risk_reference`) — there is no stop distance to define 1R.
- One position at a time; a bullish cross while already long is ignored. An open position at the end of data exits at the final close (`data_end`).

## Signals & Structure

| Item | Count |
| --- | ---: |
| KAMA bullish crosses (all) | 32 |
| KAMA bearish crosses (all) | 32 |
| Bullish crosses inside warm-up (discarded) | 1 |
| Bullish crosses rejected by the `slope` trend gate | 17 |
| Entry signals taken | 14 |
| Exit signals fired | 14 |
| Hours in position | 1038 (17.8% of bars) |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 14 |
| Wins / Losses / Breakeven | 6 / 8 / 0 |
| Win rate | 42.9% |
| Gross P&L | -2,817.20 USDT |
| Net P&L after costs | -3,843.55 USDT |
| Total fees | 821.08 USDT |
| Net profit factor | 0.52 |
| Average net P&L | -274.54 USDT |
| Largest win / loss | 2,347.89 / -2,267.93 USDT |
| Average holding time | 74.1 h |
| Maximum net drawdown | -7,333.57 USDT |
| Buy & hold over the same window | -17,468.65 USDT |
| Strategy vs buy & hold | 13,625.10 USDT |

## Monthly Breakdown

Each trade is attributed to the month it **exited** in, so a trade opened late in one month
lands in the next. Month figures therefore sum to the headline net P&L.

| Month | Trades | Wins | Win rate | Net USDT |
| --- | ---: | ---: | ---: | ---: |
| 2026-02 | 1 | 0 | 0.0% | -359.04 |
| 2026-03 | 1 | 1 | 100.0% | 714.36 |
| 2026-04 | 3 | 3 | 100.0% | 3,134.69 |
| 2026-05 | 1 | 0 | 0.0% | -1,045.65 |
| 2026-07 | 3 | 1 | 33.3% | -2,776.66 |
| 2026-08 | 5 | 1 | 20.0% | -3,511.26 |

## Exit Reasons

- `kama_bearish_cross`: 14

## Trade Detail

| # | Entry | Exit | Hours | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---:|---|
| 1 | 2026-02-22 12:00 @ 68,190.2 | 2026-02-22 13:00 @ 67,885.6 | 1 | -359.04 | -1.09 | kama_bearish_cross |
| 2 | 2026-03-10 09:00 @ 70,658.0 | 2026-03-18 16:00 @ 71,429.2 | 199 | 714.36 | 1.14 | kama_bearish_cross |
| 3 | 2026-04-06 00:00 @ 69,004.8 | 2026-04-12 11:00 @ 71,408.9 | 155 | 2,347.89 | 7.45 | kama_bearish_cross |
| 4 | 2026-04-13 23:00 @ 74,607.5 | 2026-04-19 18:00 @ 74,734.8 | 139 | 67.63 | 0.24 | kama_bearish_cross |
| 5 | 2026-04-20 21:00 @ 76,237.6 | 2026-04-27 23:00 @ 77,018.1 | 170 | 719.17 | 1.51 | kama_bearish_cross |
| 6 | 2026-05-10 14:00 @ 80,940.4 | 2026-05-12 17:00 @ 79,959.1 | 51 | -1,045.65 | -4.59 | kama_bearish_cross |
| 7 | 2026-07-10 03:00 @ 63,941.4 | 2026-07-13 12:00 @ 62,875.1 | 81 | -1,117.01 | -2.63 | kama_bearish_cross |
| 8 | 2026-07-18 11:00 @ 63,987.6 | 2026-07-24 14:00 @ 64,122.5 | 147 | 83.64 | 0.59 | kama_bearish_cross |
| 9 | 2026-07-27 06:00 @ 65,440.7 | 2026-07-27 23:00 @ 63,749.1 | 17 | -1,743.29 | -8.35 | kama_bearish_cross |
| 10 | 2026-08-22 15:00 @ 77,026.3 | 2026-08-23 19:00 @ 77,310.0 | 28 | 221.93 | 0.39 | kama_bearish_cross |
| 11 | 2026-08-25 06:00 @ 80,717.9 | 2026-08-25 09:00 @ 79,891.0 | 3 | -891.10 | -1.22 | kama_bearish_cross |
| 12 | 2026-08-25 13:00 @ 78,957.9 | 2026-08-26 00:00 @ 78,497.6 | 11 | -523.23 | -0.66 | kama_bearish_cross |
| 13 | 2026-08-26 10:00 @ 78,423.0 | 2026-08-26 12:00 @ 78,434.9 | 2 | -50.93 | 0.02 | kama_bearish_cross |
| 14 | 2026-08-27 09:00 @ 79,730.7 | 2026-08-28 19:00 @ 77,525.6 | 34 | -2,267.93 | -4.45 | kama_bearish_cross |

## Notes

- Signals are read at the hourly close and filled at the next hourly open; no intrabar fills are assumed.
- When a stop is armed, 1h OHLC cannot resolve whether the bar's high or low came first. A stop is checked against the open (gap) and then the low, and is only *updated* from this bar's high afterwards, so a stop derived from a bar can never also be triggered by that same bar.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- A cross on the final bar is discarded rather than filled, since no next open exists.
