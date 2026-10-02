# BTCUSDT Hourly-Support + 3m UT Bot Long — 2026-08

## Data & Setup

- Backtest month: `2026-08` (UTC); warm-up months: 2026-07.
- Hourly bars in span: 1,486; simulated 3m bars (target month): 14,879.
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
| Pine support IDs used | 6 |
| Dynamic bottom versions | 6 |
| Bottom adjustments | 0 |
| Zones invalidated (full breakdown) | 1 |
| Initial-entry signals | 5 |
| Upside-exit initial signals | 1 |
| Re-entry signals | 0 |
| UT Bot BUY total | 475 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 6 |
| Wins / Losses / Breakeven | 1 / 5 / 0 |
| Win rate | 16.7% |
| Gross P&L | 234.14 USDT |
| Net P&L after costs | -160.80 USDT |
| Total fees | 315.95 USDT |
| Net profit factor | 0.71 |
| Average net P&L | -26.80 USDT |
| Maximum net drawdown | -558.67 USDT |

## Exit Reasons

- `breakeven_lock_gap`: 2
- `initial_stop`: 2
- `atr_trailing_stop`: 1
- `breakeven_lock`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2026-08-01 19:00 @ 62558.9 | 2026-08-02 11:53 @ 63007.0 | 397.87 | 1.54 | atr_trailing_stop |
| 2 | initial_entry | 2026-08-03 08:54 @ 62465.0 | 2026-08-03 09:00 @ 62506.1 | -8.89 | 0.13 | breakeven_lock_gap |
| 3 | initial_entry | 2026-08-10 17:15 @ 63980.1 | 2026-08-10 18:38 @ 63822.1 | -209.12 | -1.04 | initial_stop |
| 4 | initial_entry | 2026-08-10 19:51 @ 64012.9 | 2026-08-11 06:56 @ 63823.8 | -240.20 | -1.03 | initial_stop |
| 5 | initial_entry | 2026-08-11 14:09 @ 64192.9 | 2026-08-11 14:18 @ 64143.8 | -100.47 | -0.18 | breakeven_lock_gap |
| 6 | initial_entry_after_upside_exit | 2026-08-31 00:03 @ 77654.3 | 2026-08-31 12:41 @ 77716.4 | -0.00 | 0.07 | breakeven_lock |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
