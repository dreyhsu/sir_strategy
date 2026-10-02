# BTCUSDT Hourly-Support + 3m UT Bot Long — 2026-04

## Data & Setup

- Backtest month: `2026-04` (UTC); warm-up months: 2026-03.
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
| Pine support IDs used | 7 |
| Dynamic bottom versions | 7 |
| Bottom adjustments | 0 |
| Zones invalidated (full breakdown) | 1 |
| Initial-entry signals | 4 |
| Upside-exit initial signals | 3 |
| Re-entry signals | 0 |
| UT Bot BUY total | 402 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 7 |
| Wins / Losses / Breakeven | 1 / 6 / 0 |
| Win rate | 14.3% |
| Gross P&L | -879.29 USDT |
| Net P&L after costs | -1,397.64 USDT |
| Total fees | 414.67 USDT |
| Net profit factor | 0.00 |
| Average net P&L | -199.66 USDT |
| Maximum net drawdown | -1,397.64 USDT |

## Exit Reasons

- `breakeven_lock`: 4
- `initial_stop`: 3

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_upside_exit | 2026-04-02 05:03 @ 66433.8 | 2026-04-02 13:17 @ 65886.8 | -599.94 | -1.01 | initial_stop |
| 2 | initial_entry_after_upside_exit | 2026-04-12 15:45 @ 70846.9 | 2026-04-12 22:02 @ 70903.6 | -0.00 | 0.12 | breakeven_lock |
| 3 | initial_entry_after_upside_exit | 2026-04-16 14:45 @ 73939.2 | 2026-04-16 17:08 @ 73998.4 | -0.00 | 0.06 | breakeven_lock |
| 4 | initial_entry | 2026-04-27 17:27 @ 76839.7 | 2026-04-27 19:32 @ 76564.2 | -336.80 | -1.03 | initial_stop |
| 5 | initial_entry | 2026-04-27 22:30 @ 76934.1 | 2026-04-28 01:47 @ 76995.7 | 0.00 | 0.18 | breakeven_lock |
| 6 | initial_entry | 2026-04-28 03:00 @ 76852.6 | 2026-04-28 05:35 @ 76914.1 | -0.00 | 0.24 | breakeven_lock |
| 7 | initial_entry | 2026-04-28 06:06 @ 76987.7 | 2026-04-28 06:44 @ 76588.2 | -460.89 | -1.02 | initial_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
