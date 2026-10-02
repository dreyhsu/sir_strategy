# BTCUSDT Hourly-Support + 3m UT Bot Long — 2026-06

## Data & Setup

- Backtest month: `2026-06` (UTC); warm-up months: 2026-05.
- Hourly bars in span: 1,462; simulated 3m bars (target month): 14,399.
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
| Pine support IDs used | 3 |
| Dynamic bottom versions | 3 |
| Bottom adjustments | 0 |
| Zones invalidated (full breakdown) | 2 |
| Initial-entry signals | 2 |
| Upside-exit initial signals | 0 |
| Re-entry signals | 0 |
| UT Bot BUY total | 401 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 2 |
| Wins / Losses / Breakeven | 0 / 2 / 0 |
| Win rate | 0.0% |
| Gross P&L | -482.25 USDT |
| Net P&L after costs | -617.70 USDT |
| Total fees | 108.36 USDT |
| Net profit factor | 0.00 |
| Average net P&L | -308.85 USDT |
| Maximum net drawdown | -617.70 USDT |

## Exit Reasons

- `initial_stop`: 2

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2026-06-01 10:54 @ 72752.9 | 2026-06-01 11:59 @ 72523.0 | -287.97 | -1.03 | initial_stop |
| 2 | initial_entry | 2026-06-23 06:42 @ 62956.5 | 2026-06-23 08:14 @ 62677.0 | -329.73 | -1.02 | initial_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
