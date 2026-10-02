# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2025-03

## Data & Setup

- Backtest month: `2025-03` (UTC); warm-up months: 2025-02.
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
| Pine resistance IDs used | 3 |
| Dynamic top versions | 3 |
| Top adjustments | 0 |
| Zones invalidated (full breakout) | 2 |
| Initial-entry signals | 5 |
| Downside-exit initial signals | 2 |
| Re-entry signals | 0 |
| UT Bot SELL total | 445 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 7 |
| Wins / Losses / Breakeven | 2 / 5 / 0 |
| Win rate | 28.6% |
| Gross P&L | 2,771.37 USDT |
| Net P&L after costs | 2,181.86 USDT |
| Total fees | 471.61 USDT |
| Net profit factor | 40345476220146.42 |
| Average net P&L | 311.69 USDT |
| Maximum net drawdown | -0.00 USDT |

## Exit Reasons

- `breakeven_lock`: 5
- `atr_trailing_stop`: 2

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2025-03-02 01:33 @ 85979.0 | 2025-03-02 15:26 @ 85910.2 | -0.00 | 0.10 | breakeven_lock |
| 2 | initial_entry_after_downside_exit | 2025-03-13 12:33 @ 82887.8 | 2025-03-14 07:44 @ 82120.8 | 701.04 | 0.50 | atr_trailing_stop |
| 3 | initial_entry | 2025-03-14 15:54 @ 84610.6 | 2025-03-14 16:50 @ 84543.0 | -0.00 | 0.09 | breakeven_lock |
| 4 | initial_entry | 2025-03-14 17:27 @ 84259.1 | 2025-03-14 20:38 @ 84191.7 | -0.00 | 0.07 | breakeven_lock |
| 5 | initial_entry | 2025-03-14 23:06 @ 84277.9 | 2025-03-15 00:32 @ 84210.5 | -0.00 | 0.13 | breakeven_lock |
| 6 | initial_entry | 2025-03-17 19:57 @ 84366.1 | 2025-03-19 00:17 @ 82818.4 | 1480.82 | 2.26 | atr_trailing_stop |
| 7 | initial_entry | 2025-03-19 16:15 @ 84458.6 | 2025-03-19 18:02 @ 84391.0 | -0.00 | 0.10 | breakeven_lock |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
