# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-08

## Data & Setup

- Backtest month: `2026-08` (UTC); warm-up months: 2026-07.
- Hourly bars in span: 1,486; simulated 3m bars (target month): 14,879.
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
| Zones invalidated (full breakout) | 2 |
| Initial-entry signals | 6 |
| Downside-exit initial signals | 4 |
| Re-entry signals | 0 |
| UT Bot SELL total | 474 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 10 |
| Wins / Losses / Breakeven | 1 / 9 / 0 |
| Win rate | 10.0% |
| Gross P&L | -129.29 USDT |
| Net P&L after costs | -790.23 USDT |
| Total fees | 528.75 USDT |
| Net profit factor | 0.29 |
| Average net P&L | -79.02 USDT |
| Maximum net drawdown | -1,113.61 USDT |

## Exit Reasons

- `breakeven_lock`: 5
- `initial_stop`: 4
- `data_end`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2026-08-05 20:57 @ 64802.3 | 2026-08-06 05:05 @ 64750.5 | -0.00 | 0.14 | breakeven_lock |
| 2 | initial_entry_after_downside_exit | 2026-08-07 10:27 @ 64781.5 | 2026-08-07 11:23 @ 65064.4 | -334.83 | -1.02 | initial_stop |
| 3 | initial_entry | 2026-08-08 16:15 @ 65046.2 | 2026-08-09 13:05 @ 64994.2 | -0.00 | 0.44 | breakeven_lock |
| 4 | initial_entry | 2026-08-09 14:24 @ 65138.2 | 2026-08-09 14:59 @ 65254.9 | -168.84 | -1.06 | initial_stop |
| 5 | initial_entry | 2026-08-09 17:03 @ 65184.6 | 2026-08-09 20:35 @ 65132.5 | -0.00 | 0.82 | breakeven_lock |
| 6 | initial_entry_after_downside_exit | 2026-08-17 16:12 @ 64050.6 | 2026-08-17 17:23 @ 64306.6 | -307.30 | -1.03 | initial_stop |
| 7 | initial_entry | 2026-08-17 19:03 @ 64307.6 | 2026-08-17 23:59 @ 64558.7 | -302.63 | -1.03 | initial_stop |
| 8 | initial_entry | 2026-08-18 06:51 @ 64281.2 | 2026-08-18 08:32 @ 64229.8 | -0.00 | 0.21 | breakeven_lock |
| 9 | initial_entry | 2026-08-18 12:03 @ 64299.9 | 2026-08-18 13:50 @ 64248.5 | -0.00 | 0.28 | breakeven_lock |
| 10 | initial_entry_after_downside_exit | 2026-08-31 19:42 @ 78913.7 | 2026-08-31 23:56 @ 78527.4 | 323.38 | 0.69 | data_end |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
