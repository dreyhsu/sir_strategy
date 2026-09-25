# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-08

## Data & Setup

- Backtest month: `2026-08` (UTC); warm-up months: none.
- Hourly bars in span: 743; simulated 3m bars (target month): 14,879.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Pine resistance: close pivot `20/20`, volume filter `2`, ATR(200) × `1`.
- Entry: 3m UT Bot(a=2, ATR=10) SELL with close inside the zone; short on next 3m open.
- Initial stop: zone top + `0.5 × hourly ATR(20)`.
- Re-entry only after an initial stop; break above top then a UT Bot SELL back inside the zone within `15` min.
- Adjust Supertrend dynamic multiplier `4.5–1.5`; short-confirmed + 1R reached enables `3 × ATR(20)` trailing.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Pine resistance IDs used | 4 |
| Dynamic top versions | 4 |
| Top adjustments | 0 |
| Initial-entry signals | 3 |
| Downside-exit initial signals | 1 |
| Re-entry signals | 0 |
| UT Bot SELL total | 474 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 4 |
| Wins / Losses / Breakeven | 0 / 4 / 0 |
| Win rate | 0.0% |
| Gross P&L | -965.07 USDT |
| Net P&L after costs | -1,222.71 USDT |
| Total fees | 206.11 USDT |
| Net profit factor | 0.00 |
| Average net P&L | -305.68 USDT |
| Maximum net drawdown | -1,222.71 USDT |

## Exit Reasons

- `initial_stop`: 4

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2026-08-17 17:30 @ 64163.4 | 2026-08-17 18:23 @ 64532.9 | -421.00 | -1.02 | initial_stop |
| 2 | initial_entry | 2026-08-17 19:03 @ 64307.6 | 2026-08-17 23:32 @ 64542.7 | -286.66 | -1.03 | initial_stop |
| 3 | initial_entry | 2026-08-18 06:51 @ 64281.2 | 2026-08-18 14:23 @ 64535.9 | -306.23 | -1.03 | initial_stop |
| 4 | initial_entry | 2026-08-19 01:45 @ 64380.8 | 2026-08-19 12:35 @ 64538.0 | -208.83 | -1.04 | initial_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
