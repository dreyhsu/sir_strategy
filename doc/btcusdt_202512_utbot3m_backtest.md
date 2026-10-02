# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2025-12

## Data & Setup

- Backtest month: `2025-12` (UTC); warm-up months: 2025-11.
- Hourly bars in span: 1,462; simulated 3m bars (target month): 14,879.
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
| Pine resistance IDs used | 4 |
| Dynamic top versions | 4 |
| Top adjustments | 0 |
| Zones invalidated (full breakout) | 2 |
| Initial-entry signals | 5 |
| Downside-exit initial signals | 2 |
| Re-entry signals | 0 |
| UT Bot SELL total | 468 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 7 |
| Wins / Losses / Breakeven | 1 / 6 / 0 |
| Win rate | 14.3% |
| Gross P&L | 1,726.58 USDT |
| Net P&L after costs | 1,081.78 USDT |
| Total fees | 515.84 USDT |
| Net profit factor | 2.34 |
| Average net P&L | 154.54 USDT |
| Maximum net drawdown | -806.33 USDT |

## Exit Reasons

- `breakeven_lock`: 4
- `initial_stop`: 1
- `breakeven_lock_gap`: 1
- `atr_trailing_stop`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2025-12-02 19:54 @ 91886.1 | 2025-12-02 22:14 @ 91812.6 | -0.00 | 0.09 | breakeven_lock |
| 2 | initial_entry | 2025-12-03 10:36 @ 92990.8 | 2025-12-03 14:41 @ 92916.4 | -0.00 | 0.16 | breakeven_lock |
| 3 | initial_entry | 2025-12-03 14:54 @ 92510.6 | 2025-12-03 15:02 @ 92436.7 | -0.00 | 0.08 | breakeven_lock |
| 4 | initial_entry | 2025-12-03 18:21 @ 92989.0 | 2025-12-03 19:50 @ 92914.6 | -0.00 | 0.16 | breakeven_lock |
| 5 | initial_entry | 2025-12-03 20:06 @ 92811.9 | 2025-12-03 21:47 @ 93476.0 | -738.55 | -1.01 | initial_stop |
| 6 | initial_entry | 2025-12-05 03:24 @ 92378.8 | 2025-12-05 03:27 @ 92372.6 | -67.78 | 0.01 | breakeven_lock_gap |
| 7 | initial_entry_after_downside_exit | 2025-12-29 05:33 @ 90028.2 | 2025-12-29 14:38 @ 88068.8 | 1888.11 | 3.75 | atr_trailing_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
