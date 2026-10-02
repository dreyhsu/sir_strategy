# BTCUSDT Hourly-Support + 3m UT Bot Long — 2026-07

## Data & Setup

- Backtest month: `2026-07` (UTC); warm-up months: 2026-06.
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
| Initial-entry signals | 0 |
| Upside-exit initial signals | 2 |
| Re-entry signals | 0 |
| UT Bot BUY total | 442 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 2 |
| Wins / Losses / Breakeven | 1 / 1 / 0 |
| Win rate | 50.0% |
| Gross P&L | 406.35 USDT |
| Net P&L after costs | 279.93 USDT |
| Total fees | 101.14 USDT |
| Net profit factor | 1.39 |
| Average net P&L | 139.96 USDT |
| Maximum net drawdown | -712.55 USDT |

## Exit Reasons

- `initial_stop`: 1
- `atr_trailing_stop`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_upside_exit | 2026-07-08 08:48 @ 62260.2 | 2026-07-08 15:14 @ 61597.2 | -712.55 | -1.01 | initial_stop |
| 2 | initial_entry_after_upside_exit | 2026-07-24 14:57 @ 63972.3 | 2026-07-27 01:14 @ 65016.4 | 992.48 | 2.24 | atr_trailing_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
