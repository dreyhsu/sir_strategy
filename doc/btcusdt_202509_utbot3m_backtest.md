# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2025-09

## Data & Setup

- Backtest month: `2025-09` (UTC); warm-up months: 2025-08.
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
| Pine resistance IDs used | 7 |
| Dynamic top versions | 9 |
| Top adjustments | 2 |
| Zones invalidated (full breakout) | 4 |
| Initial-entry signals | 12 |
| Downside-exit initial signals | 2 |
| Re-entry signals | 2 |
| UT Bot SELL total | 512 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 16 |
| Wins / Losses / Breakeven | 2 / 14 / 0 |
| Win rate | 12.5% |
| Gross P&L | 205.50 USDT |
| Net P&L after costs | -1,603.98 USDT |
| Total fees | 1,447.58 USDT |
| Net profit factor | 0.40 |
| Average net P&L | -100.25 USDT |
| Maximum net drawdown | -1,603.98 USDT |

## Exit Reasons

- `breakeven_lock`: 7
- `initial_stop`: 4
- `breakeven_lock_gap`: 2
- `atr_trailing_stop`: 2
- `adjust_supertrend_bullish_flip`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2025-09-01 09:54 @ 109570.9 | 2025-09-01 13:26 @ 109483.3 | -0.00 | 0.16 | breakeven_lock |
| 2 | initial_entry | 2025-09-05 08:18 @ 112611.0 | 2025-09-05 10:08 @ 112521.0 | -0.00 | 0.18 | breakeven_lock |
| 3 | initial_entry | 2025-09-08 15:48 @ 112498.7 | 2025-09-08 16:26 @ 112408.8 | -0.00 | 0.17 | breakeven_lock |
| 4 | initial_entry | 2025-09-08 16:39 @ 112288.8 | 2025-09-08 16:48 @ 112255.6 | -56.67 | 0.06 | breakeven_lock_gap |
| 5 | initial_entry | 2025-09-08 17:42 @ 112250.5 | 2025-09-09 05:59 @ 112160.7 | -0.00 | 0.20 | breakeven_lock |
| 6 | initial_entry | 2025-09-09 06:21 @ 112444.6 | 2025-09-09 06:47 @ 113016.1 | -661.68 | -1.02 | initial_stop |
| 7 | initial_entry | 2025-09-09 10:48 @ 112658.7 | 2025-09-10 07:29 @ 112042.8 | 526.03 | 1.64 | atr_trailing_stop |
| 8 | initial_entry | 2025-09-10 08:36 @ 112507.0 | 2025-09-10 12:14 @ 112417.1 | -0.00 | 0.16 | breakeven_lock |
| 9 | initial_entry_after_downside_exit | 2025-09-16 17:39 @ 116410.9 | 2025-09-17 02:53 @ 117068.1 | -750.68 | -1.02 | initial_stop |
| 10 | reentry_after_initial_stop | 2025-09-17 02:57 @ 116638.9 | 2025-09-17 05:08 @ 116545.7 | -0.00 | 0.16 | breakeven_lock |
| 11 | initial_entry | 2025-09-17 09:09 @ 116624.8 | 2025-09-17 20:08 @ 116003.0 | 528.82 | 1.04 | atr_trailing_stop |
| 12 | initial_entry | 2025-09-17 23:21 @ 116566.4 | 2025-09-17 23:30 @ 116515.7 | -42.44 | 0.08 | breakeven_lock_gap |
| 13 | initial_entry | 2025-09-18 02:03 @ 116544.6 | 2025-09-18 02:26 @ 116451.4 | -0.00 | 0.16 | breakeven_lock |
| 14 | initial_entry_after_downside_exit | 2025-09-28 15:12 @ 109654.4 | 2025-09-28 16:02 @ 110011.3 | -444.72 | -1.03 | initial_stop |
| 15 | reentry_after_initial_stop | 2025-09-28 16:18 @ 110005.5 | 2025-09-28 17:00 @ 110183.5 | -266.09 | -0.39 | adjust_supertrend_bullish_flip |
| 16 | initial_entry | 2025-09-28 17:24 @ 110121.8 | 2025-09-28 20:23 @ 110470.1 | -436.54 | -1.03 | initial_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
