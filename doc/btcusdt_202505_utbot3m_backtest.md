# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2025-05

## Data & Setup

- Backtest month: `2025-05` (UTC); warm-up months: 2025-04.
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
| Pine resistance IDs used | 6 |
| Dynamic top versions | 6 |
| Top adjustments | 0 |
| Zones invalidated (full breakout) | 3 |
| Initial-entry signals | 2 |
| Downside-exit initial signals | 3 |
| Re-entry signals | 0 |
| UT Bot SELL total | 466 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 5 |
| Wins / Losses / Breakeven | 0 / 5 / 0 |
| Win rate | 0.0% |
| Gross P&L | -1,097.05 USDT |
| Net P&L after costs | -1,595.43 USDT |
| Total fees | 398.71 USDT |
| Net profit factor | 0.00 |
| Average net P&L | -319.09 USDT |
| Maximum net drawdown | -1,595.43 USDT |

## Exit Reasons

- `initial_stop`: 2
- `breakeven_lock`: 1
- `breakeven_lock_gap`: 1
- `adjust_supertrend_bullish_flip`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2025-05-01 02:54 @ 94728.5 | 2025-05-01 09:20 @ 95218.3 | -565.70 | -1.02 | initial_stop |
| 2 | initial_entry_after_downside_exit | 2025-05-07 01:57 @ 97177.9 | 2025-05-07 12:17 @ 97100.2 | -0.00 | 0.10 | breakeven_lock |
| 3 | initial_entry | 2025-05-08 01:12 @ 97732.7 | 2025-05-08 01:18 @ 97735.8 | -81.23 | -0.00 | breakeven_lock_gap |
| 4 | initial_entry_after_downside_exit | 2025-05-13 16:45 @ 103889.8 | 2025-05-13 18:00 @ 104225.9 | -419.36 | -0.42 | adjust_supertrend_bullish_flip |
| 5 | initial_entry | 2025-05-18 13:51 @ 104254.0 | 2025-05-18 13:59 @ 104699.5 | -529.14 | -1.02 | initial_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
