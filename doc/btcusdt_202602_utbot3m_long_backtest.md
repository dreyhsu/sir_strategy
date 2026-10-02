# BTCUSDT Hourly-Support + 3m UT Bot Long — 2026-02

## Data & Setup

- Backtest month: `2026-02` (UTC); warm-up months: 2026-01.
- Hourly bars in span: 1,414; simulated 3m bars (target month): 13,439.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Pine support: close pivot `20/20`, volume filter `2`, ATR(200) × `1` (box extends downward).
- Entry: 3m UT Bot(a=2, ATR=10) BUY with close inside the zone; long on next 3m open.
- Initial stop: max(zone bottom, recent 20-bar swing low) − `0.5 × hourly ATR(20)` — anchored to the rejection low, not just the box bottom.
- Upside-exit entries only when the close is within `1.5 × hourly ATR(20)` above the zone top (no chasing far over the zone).
- Re-entry only after an initial stop; break below bottom then a UT Bot BUY back inside the zone within `15` min.
- Profit lock: once price trades above the zone top OR the trade reaches 1R, the stop ratchets to break-even net of round-trip fees (`breakeven_lock`), so a profitable long can't turn into a net loss.
- Support retired (no more longs) once a 3m close falls below the zone bottom by more than `1.5 × hourly ATR(20)` — a full breakdown, role reversal to resistance.
- Trend filter: no new longs while the hourly SMA(100) is falling faster than `0.5%` over `24h` (stand aside in strong downtrends).
- Approach band: price counts as reaching the zone when the low comes within `0.25 × hourly ATR(20)` of the top (captures rejections just above support).
- Adjust Supertrend dynamic multiplier `4.5–1.5`; long-confirmed + 1R reached enables `3 × ATR(20)` trailing.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Pine support IDs used | 8 |
| Dynamic bottom versions | 9 |
| Bottom adjustments | 1 |
| Zones invalidated (full breakdown) | 4 |
| Initial-entry signals | 5 |
| Upside-exit initial signals | 2 |
| Re-entry signals | 1 |
| UT Bot BUY total | 358 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 8 |
| Wins / Losses / Breakeven | 3 / 5 / 0 |
| Win rate | 37.5% |
| Gross P&L | 2,112.53 USDT |
| Net P&L after costs | 1,575.11 USDT |
| Total fees | 429.94 USDT |
| Net profit factor | 1.98 |
| Average net P&L | 196.89 USDT |
| Maximum net drawdown | -1,610.38 USDT |

## Exit Reasons

- `breakeven_lock`: 5
- `initial_stop`: 2
- `data_end`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_upside_exit | 2026-02-10 13:33 @ 68885.2 | 2026-02-10 14:41 @ 67965.0 | -974.95 | -1.01 | initial_stop |
| 2 | initial_entry | 2026-02-17 15:54 @ 67276.4 | 2026-02-17 17:11 @ 67330.3 | 0.00 | 0.07 | breakeven_lock |
| 3 | initial_entry | 2026-02-17 18:21 @ 67470.5 | 2026-02-17 20:08 @ 67524.5 | -0.00 | 0.06 | breakeven_lock |
| 4 | initial_entry | 2026-02-18 01:45 @ 67143.6 | 2026-02-18 11:11 @ 67197.4 | -0.00 | 0.09 | breakeven_lock |
| 5 | initial_entry | 2026-02-18 11:30 @ 67423.6 | 2026-02-18 11:38 @ 67477.6 | 0.00 | 0.09 | breakeven_lock |
| 6 | initial_entry | 2026-02-18 14:06 @ 67331.8 | 2026-02-18 14:50 @ 66750.0 | -635.43 | -1.01 | initial_stop |
| 7 | reentry_after_initial_stop | 2026-02-18 14:57 @ 67201.7 | 2026-02-18 15:11 @ 67255.5 | -0.00 | 0.08 | breakeven_lock |
| 8 | initial_entry_after_upside_exit | 2026-02-28 09:15 @ 63685.4 | 2026-02-28 23:56 @ 66923.1 | 3185.50 | 4.76 | data_end |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
