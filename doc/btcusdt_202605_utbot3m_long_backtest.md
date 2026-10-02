# BTCUSDT Hourly-Support + 3m UT Bot Long — 2026-05

## Data & Setup

- Backtest month: `2026-05` (UTC); warm-up months: 2026-04.
- Hourly bars in span: 1,462; simulated 3m bars (target month): 14,879.
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
| Zones invalidated (full breakdown) | 3 |
| Initial-entry signals | 6 |
| Upside-exit initial signals | 1 |
| Re-entry signals | 0 |
| UT Bot BUY total | 448 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 7 |
| Wins / Losses / Breakeven | 1 / 6 / 0 |
| Win rate | 14.3% |
| Gross P&L | 1,264.83 USDT |
| Net P&L after costs | 714.35 USDT |
| Total fees | 440.38 USDT |
| Net profit factor | 2.48 |
| Average net P&L | 102.05 USDT |
| Maximum net drawdown | -481.76 USDT |

## Exit Reasons

- `breakeven_lock`: 3
- `breakeven_lock_gap`: 2
- `atr_trailing_stop`: 1
- `initial_stop`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_upside_exit | 2026-05-13 16:30 @ 79027.9 | 2026-05-14 03:08 @ 79091.1 | -0.00 | 0.32 | breakeven_lock |
| 2 | initial_entry | 2026-05-14 03:30 @ 79289.5 | 2026-05-14 11:26 @ 79353.0 | -0.00 | 0.14 | breakeven_lock |
| 3 | initial_entry | 2026-05-14 12:12 @ 79356.6 | 2026-05-15 05:02 @ 80616.7 | 1196.12 | 3.50 | atr_trailing_stop |
| 4 | initial_entry | 2026-05-15 14:15 @ 79234.0 | 2026-05-15 18:20 @ 79297.4 | -0.00 | 0.14 | breakeven_lock |
| 5 | initial_entry | 2026-05-15 21:15 @ 79156.7 | 2026-05-16 04:35 @ 78804.1 | -415.80 | -1.02 | initial_stop |
| 6 | initial_entry | 2026-05-22 15:06 @ 76921.9 | 2026-05-22 15:33 @ 76953.8 | -29.64 | 0.07 | breakeven_lock_gap |
| 7 | initial_entry | 2026-05-22 16:30 @ 76909.2 | 2026-05-22 16:51 @ 76934.4 | -36.32 | 0.05 | breakeven_lock_gap |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
