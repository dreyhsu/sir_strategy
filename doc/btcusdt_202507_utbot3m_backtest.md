# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2025-07

## Data & Setup

- Backtest month: `2025-07` (UTC); warm-up months: 2025-06.
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
| Pine resistance IDs used | 7 |
| Dynamic top versions | 7 |
| Top adjustments | 0 |
| Zones invalidated (full breakout) | 3 |
| Initial-entry signals | 14 |
| Downside-exit initial signals | 4 |
| Re-entry signals | 0 |
| UT Bot SELL total | 519 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 18 |
| Wins / Losses / Breakeven | 4 / 14 / 0 |
| Win rate | 22.2% |
| Gross P&L | 4,214.76 USDT |
| Net P&L after costs | 2,113.87 USDT |
| Total fees | 1,680.72 USDT |
| Net profit factor | 2.11 |
| Average net P&L | 117.44 USDT |
| Maximum net drawdown | -952.69 USDT |

## Exit Reasons

- `breakeven_lock`: 9
- `atr_trailing_stop`: 4
- `initial_stop`: 3
- `breakeven_lock_gap`: 2

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2025-07-02 20:57 @ 109071.9 | 2025-07-02 21:53 @ 109420.1 | -435.65 | -1.03 | initial_stop |
| 2 | initial_entry | 2025-07-02 22:42 @ 109138.2 | 2025-07-03 00:44 @ 109050.9 | -0.00 | 0.32 | breakeven_lock |
| 3 | initial_entry | 2025-07-03 00:57 @ 108860.0 | 2025-07-03 03:35 @ 108773.0 | -0.00 | 0.19 | breakeven_lock |
| 4 | initial_entry | 2025-07-03 04:54 @ 108763.7 | 2025-07-03 05:11 @ 109193.6 | -517.05 | -1.03 | initial_stop |
| 5 | initial_entry_after_downside_exit | 2025-07-17 19:33 @ 119583.1 | 2025-07-17 21:02 @ 119487.5 | -0.00 | 0.14 | breakeven_lock |
| 6 | initial_entry | 2025-07-17 21:51 @ 120307.9 | 2025-07-18 01:11 @ 120211.7 | -0.00 | 0.17 | breakeven_lock |
| 7 | initial_entry | 2025-07-18 02:06 @ 120108.5 | 2025-07-18 02:26 @ 120012.4 | -0.00 | 0.12 | breakeven_lock |
| 8 | initial_entry | 2025-07-18 03:09 @ 119985.7 | 2025-07-18 04:14 @ 119889.8 | -0.00 | 0.12 | breakeven_lock |
| 9 | initial_entry | 2025-07-18 05:45 @ 120255.7 | 2025-07-20 03:35 @ 118147.9 | 2012.45 | 3.37 | atr_trailing_stop |
| 10 | initial_entry_after_downside_exit | 2025-07-20 14:12 @ 118329.1 | 2025-07-20 22:44 @ 117598.3 | 636.37 | 1.19 | atr_trailing_stop |
| 11 | initial_entry | 2025-07-21 10:30 @ 118487.7 | 2025-07-21 10:44 @ 118392.9 | -0.00 | 0.16 | breakeven_lock |
| 12 | initial_entry | 2025-07-21 11:36 @ 118435.3 | 2025-07-21 11:39 @ 118423.4 | -82.93 | 0.02 | breakeven_lock_gap |
| 13 | initial_entry | 2025-07-21 14:09 @ 118528.2 | 2025-07-21 14:15 @ 118634.0 | -200.58 | -0.14 | breakeven_lock_gap |
| 14 | initial_entry | 2025-07-21 15:09 @ 118698.1 | 2025-07-22 01:41 @ 117816.8 | 786.75 | 1.47 | atr_trailing_stop |
| 15 | initial_entry | 2025-07-22 11:12 @ 118793.0 | 2025-07-22 12:38 @ 119372.4 | -674.61 | -1.02 | initial_stop |
| 16 | initial_entry | 2025-07-22 16:27 @ 118948.3 | 2025-07-22 17:35 @ 118853.2 | -0.00 | 0.22 | breakeven_lock |
| 17 | initial_entry_after_downside_exit | 2025-07-30 15:24 @ 118148.9 | 2025-07-30 23:05 @ 117465.5 | 589.11 | 0.78 | atr_trailing_stop |
| 18 | initial_entry_after_downside_exit | 2025-07-31 13:06 @ 118348.9 | 2025-07-31 13:41 @ 118254.2 | -0.00 | 0.19 | breakeven_lock |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
