# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-03

## Data & Setup

- Backtest month: `2026-03` (UTC); warm-up months: 2026-02.
- Hourly bars in span: 1,414; simulated 3m bars (target month): 14,879.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Pine resistance: close pivot `20/20`, volume filter `2`, ATR(200) × `1`.
- Entry: 3m UT Bot(a=2, ATR=10) SELL with close inside the zone; short on next 3m open.
- Initial stop: min(zone top, recent 20-bar swing high) + `0.5 × hourly ATR(20)` — anchored to the rejection high, not just the box top.
- Downside-exit entries only when the close is within `1.5 × hourly ATR(20)` below the zone bottom (no shorting far under the zone).
- Re-entry only after an initial stop; break above top then a UT Bot SELL back inside the zone within `15` min.
- Profit lock: once price trades below the zone bottom OR the trade reaches 1R, the stop ratchets to break-even net of round-trip fees (`breakeven_lock`), so a profitable short can't turn into a net loss.
- Resistance retired (no more shorts) once a 3m close clears the zone top by more than `1.5 × hourly ATR(20)` — a full breakout, role reversal to support.
- Trend filter: no new shorts while the hourly SMA(100) is rising faster than `0.5%` over `24h` (stand aside in strong uptrends).
- Approach band: price counts as reaching the zone when the high comes within `0.25 × hourly ATR(20)` of the bottom (captures rejections just under resistance).
- Adjust Supertrend dynamic multiplier `4.5–1.5`; short-confirmed + 1R reached enables `3 × ATR(20)` trailing.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Pine resistance IDs used | 6 |
| Dynamic top versions | 6 |
| Top adjustments | 0 |
| Zones invalidated (full breakout) | 3 |
| Initial-entry signals | 11 |
| Downside-exit initial signals | 1 |
| Re-entry signals | 0 |
| UT Bot SELL total | 395 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 12 |
| Wins / Losses / Breakeven | 4 / 8 / 0 |
| Win rate | 33.3% |
| Gross P&L | 5,941.96 USDT |
| Net P&L after costs | 5,091.21 USDT |
| Total fees | 680.60 USDT |
| Net profit factor | 5.60 |
| Average net P&L | 424.27 USDT |
| Maximum net drawdown | -1,103.76 USDT |

## Exit Reasons

- `breakeven_lock`: 6
- `atr_trailing_stop`: 3
- `initial_stop`: 2
- `breakeven_lock_gap`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2026-03-21 14:48 @ 70816.0 | 2026-03-22 03:29 @ 69390.2 | 1369.75 | 3.19 | atr_trailing_stop |
| 2 | initial_entry | 2026-03-23 14:51 @ 71116.9 | 2026-03-23 15:24 @ 71063.5 | -3.49 | 0.07 | breakeven_lock_gap |
| 3 | initial_entry | 2026-03-24 10:30 @ 71070.9 | 2026-03-24 11:08 @ 71014.1 | -0.00 | 0.10 | breakeven_lock |
| 4 | initial_entry | 2026-03-24 11:54 @ 70996.9 | 2026-03-24 23:23 @ 70670.1 | 270.16 | 0.55 | atr_trailing_stop |
| 5 | initial_entry | 2026-03-25 05:27 @ 71067.9 | 2026-03-25 06:08 @ 71011.1 | 0.00 | 0.11 | breakeven_lock |
| 6 | initial_entry | 2026-03-25 06:57 @ 71052.9 | 2026-03-25 07:02 @ 70996.1 | -0.00 | 0.13 | breakeven_lock |
| 7 | initial_entry | 2026-03-25 07:45 @ 71015.9 | 2026-03-25 07:50 @ 70959.1 | -0.00 | 0.12 | breakeven_lock |
| 8 | initial_entry | 2026-03-25 09:48 @ 71081.5 | 2026-03-25 11:17 @ 71636.4 | -611.95 | -1.01 | initial_stop |
| 9 | initial_entry | 2026-03-25 12:18 @ 71409.6 | 2026-03-25 12:56 @ 71844.1 | -491.81 | -1.02 | initial_stop |
| 10 | initial_entry | 2026-03-25 14:00 @ 71539.4 | 2026-03-25 14:17 @ 71482.2 | -0.00 | 0.19 | breakeven_lock |
| 11 | initial_entry | 2026-03-25 16:51 @ 71231.9 | 2026-03-25 17:29 @ 71174.9 | -0.00 | 0.09 | breakeven_lock |
| 12 | initial_entry | 2026-03-25 23:18 @ 71234.8 | 2026-03-28 13:32 @ 66621.1 | 4558.56 | 7.51 | atr_trailing_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
