# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-06

## Data & Setup

- Backtest month: `2026-06` (UTC); warm-up months: 2026-05.
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
| Pine resistance IDs used | 6 |
| Dynamic top versions | 6 |
| Top adjustments | 0 |
| Zones invalidated (full breakout) | 1 |
| Initial-entry signals | 0 |
| Downside-exit initial signals | 1 |
| Re-entry signals | 0 |
| UT Bot SELL total | 400 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 1 |
| Wins / Losses / Breakeven | 0 / 1 / 0 |
| Win rate | 0.0% |
| Gross P&L | -579.82 USDT |
| Net P&L after costs | -644.37 USDT |
| Total fees | 51.64 USDT |
| Net profit factor | 0.00 |
| Average net P&L | -644.37 USDT |
| Maximum net drawdown | -644.37 USDT |

## Exit Reasons

- `initial_stop`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2026-06-22 02:51 @ 64255.5 | 2026-06-22 12:02 @ 64848.2 | -644.37 | -1.01 | initial_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
