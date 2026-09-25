# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-05

## Data & Setup

- Backtest month: `2026-05` (UTC); warm-up months: 2026-04.
- Hourly bars in span: 1,462; simulated 3m bars (target month): 14,879.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Pine resistance: close pivot `20/20`, volume filter `2`, ATR(200) × `1`.
- Entry: 3m UT Bot(a=2, ATR=10) SELL with close inside the zone; short on next 3m open.
- Initial stop: zone top + `0.5 × hourly ATR(20)`.
- Re-entry only after an initial stop; break above top then a UT Bot SELL back inside the zone within `15` min.
- Adjust Supertrend dynamic multiplier `4.5–1.5`; short-confirmed + 1R reached enables `3 × ATR(20)` trailing.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Pine resistance IDs used | 6 |
| Dynamic top versions | 8 |
| Top adjustments | 2 |
| Initial-entry signals | 6 |
| Downside-exit initial signals | 1 |
| Re-entry signals | 2 |
| UT Bot SELL total | 449 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 9 |
| Wins / Losses / Breakeven | 1 / 8 / 0 |
| Win rate | 11.1% |
| Gross P&L | 521.37 USDT |
| Net P&L after costs | -185.37 USDT |
| Total fees | 565.39 USDT |
| Net profit factor | 0.95 |
| Average net P&L | -20.60 USDT |
| Maximum net drawdown | -3,849.61 USDT |

## Exit Reasons

- `initial_stop`: 8
- `atr_trailing_stop`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2026-05-01 00:57 @ 76379.0 | 2026-05-01 01:50 @ 76613.3 | -295.51 | -1.03 | initial_stop |
| 2 | initial_entry | 2026-05-02 21:42 @ 78766.3 | 2026-05-03 20:38 @ 79237.7 | -534.60 | -1.02 | initial_stop |
| 3 | reentry_after_initial_stop | 2026-05-03 20:51 @ 78859.2 | 2026-05-03 22:14 @ 79310.9 | -514.96 | -1.02 | initial_stop |
| 4 | reentry_after_initial_stop | 2026-05-03 22:24 @ 78951.1 | 2026-05-04 01:56 @ 79446.1 | -558.34 | -1.02 | initial_stop |
| 5 | initial_entry | 2026-05-04 13:51 @ 78779.3 | 2026-05-04 14:38 @ 79539.2 | -823.18 | -1.01 | initial_stop |
| 6 | initial_entry | 2026-05-08 03:03 @ 79267.5 | 2026-05-08 03:17 @ 79524.6 | -320.65 | -1.03 | initial_stop |
| 7 | initial_entry | 2026-05-13 22:33 @ 79200.8 | 2026-05-14 00:14 @ 79513.0 | -375.75 | -1.03 | initial_stop |
| 8 | initial_entry | 2026-05-14 03:09 @ 79143.4 | 2026-05-14 05:23 @ 79506.5 | -426.62 | -1.02 | initial_stop |
| 9 | initial_entry_after_downside_exit | 2026-05-26 14:33 @ 77584.2 | 2026-05-28 21:41 @ 73859.4 | 3664.24 | 5.66 | atr_trailing_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
