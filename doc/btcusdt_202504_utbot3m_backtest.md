# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2025-04

## Data & Setup

- Backtest month: `2025-04` (UTC); warm-up months: 2025-03.
- Hourly bars in span: 1,462; simulated 3m bars (target month): 14,399.
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
| Pine resistance IDs used | 10 |
| Dynamic top versions | 10 |
| Top adjustments | 0 |
| Zones invalidated (full breakout) | 4 |
| Initial-entry signals | 17 |
| Downside-exit initial signals | 4 |
| Re-entry signals | 0 |
| UT Bot SELL total | 440 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 21 |
| Wins / Losses / Breakeven | 2 / 19 / 0 |
| Win rate | 9.5% |
| Gross P&L | -2,490.31 USDT |
| Net P&L after costs | -4,399.45 USDT |
| Total fees | 1,527.31 USDT |
| Net profit factor | 0.04 |
| Average net P&L | -209.50 USDT |
| Maximum net drawdown | -4,463.78 USDT |

## Exit Reasons

- `breakeven_lock`: 10
- `initial_stop`: 7
- `breakeven_lock_gap`: 3
- `atr_trailing_stop`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2025-04-01 10:39 @ 84170.2 | 2025-04-01 11:11 @ 84102.9 | 0.00 | 0.12 | breakeven_lock |
| 2 | initial_entry | 2025-04-01 16:27 @ 84861.0 | 2025-04-01 21:38 @ 85392.5 | -599.61 | -1.02 | initial_stop |
| 3 | initial_entry | 2025-04-01 23:00 @ 85056.5 | 2025-04-01 23:32 @ 85372.7 | -384.41 | -1.03 | initial_stop |
| 4 | initial_entry | 2025-04-02 02:09 @ 84927.5 | 2025-04-02 09:05 @ 84859.6 | -0.00 | 0.16 | breakeven_lock |
| 5 | initial_entry | 2025-04-02 09:27 @ 84941.5 | 2025-04-02 12:41 @ 84873.6 | -0.00 | 0.17 | breakeven_lock |
| 6 | initial_entry_after_downside_exit | 2025-04-02 14:00 @ 85175.1 | 2025-04-02 15:08 @ 86091.8 | -985.24 | -1.01 | initial_stop |
| 7 | initial_entry_after_downside_exit | 2025-04-09 19:00 @ 81749.8 | 2025-04-09 19:02 @ 81886.7 | -202.33 | -1.06 | initial_stop |
| 8 | initial_entry_after_downside_exit | 2025-04-11 14:03 @ 82463.7 | 2025-04-11 17:41 @ 83731.9 | -1334.68 | -1.01 | initial_stop |
| 9 | initial_entry_after_downside_exit | 2025-04-28 08:09 @ 94560.4 | 2025-04-28 10:38 @ 94997.1 | -512.48 | -1.02 | initial_stop |
| 10 | initial_entry | 2025-04-28 11:48 @ 95218.2 | 2025-04-28 12:47 @ 95586.9 | -445.05 | -1.03 | initial_stop |
| 11 | initial_entry | 2025-04-28 13:03 @ 95239.0 | 2025-04-28 23:11 @ 94969.6 | 193.25 | 0.78 | atr_trailing_stop |
| 12 | initial_entry | 2025-04-28 23:51 @ 94928.1 | 2025-04-29 00:20 @ 94852.2 | -0.00 | 0.16 | breakeven_lock |
| 13 | initial_entry | 2025-04-29 00:51 @ 94916.1 | 2025-04-29 01:20 @ 94840.2 | -0.00 | 0.14 | breakeven_lock |
| 14 | initial_entry | 2025-04-29 01:57 @ 94894.5 | 2025-04-29 02:02 @ 94818.6 | -0.00 | 0.10 | breakeven_lock |
| 15 | initial_entry | 2025-04-29 08:27 @ 94877.5 | 2025-04-29 08:33 @ 94842.4 | -40.76 | 0.08 | breakeven_lock_gap |
| 16 | initial_entry | 2025-04-29 11:39 @ 95021.5 | 2025-04-29 12:41 @ 94945.5 | -0.00 | 0.16 | breakeven_lock |
| 17 | initial_entry | 2025-04-29 15:18 @ 94840.5 | 2025-04-29 15:21 @ 94787.3 | -22.61 | 0.08 | breakeven_lock_gap |
| 18 | initial_entry | 2025-04-29 16:57 @ 94885.5 | 2025-04-29 17:05 @ 94809.6 | -0.00 | 0.11 | breakeven_lock |
| 19 | initial_entry | 2025-04-29 20:06 @ 95132.6 | 2025-04-30 03:56 @ 95056.5 | -0.00 | 0.16 | breakeven_lock |
| 20 | initial_entry | 2025-04-30 05:48 @ 94850.8 | 2025-04-30 06:09 @ 94840.5 | -65.55 | 0.02 | breakeven_lock_gap |
| 21 | initial_entry | 2025-04-30 11:48 @ 94997.3 | 2025-04-30 12:26 @ 94921.3 | -0.00 | 0.19 | breakeven_lock |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
