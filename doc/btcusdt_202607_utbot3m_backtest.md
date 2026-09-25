# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-07

## Data & Setup

- Backtest month: `2026-07` (UTC); warm-up months: 2026-06.
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
| Pine resistance IDs used | 7 |
| Dynamic top versions | 8 |
| Top adjustments | 1 |
| Initial-entry signals | 14 |
| Downside-exit initial signals | 3 |
| Re-entry signals | 1 |
| UT Bot SELL total | 443 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 18 |
| Wins / Losses / Breakeven | 4 / 14 / 0 |
| Win rate | 22.2% |
| Gross P&L | 662.79 USDT |
| Net P&L after costs | -485.04 USDT |
| Total fees | 918.27 USDT |
| Net profit factor | 0.90 |
| Average net P&L | -26.95 USDT |
| Maximum net drawdown | -2,024.91 USDT |

## Exit Reasons

- `initial_stop`: 13
- `atr_trailing_stop`: 4
- `adjust_supertrend_bullish_flip`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2026-07-01 15:51 @ 60051.8 | 2026-07-01 22:23 @ 61149.1 | -1145.79 | -1.01 | initial_stop |
| 2 | reentry_after_initial_stop | 2026-07-01 22:27 @ 60832.7 | 2026-07-02 09:53 @ 61361.3 | -577.43 | -1.01 | initial_stop |
| 3 | initial_entry | 2026-07-06 01:27 @ 63597.3 | 2026-07-06 01:32 @ 63848.1 | -301.69 | -1.03 | initial_stop |
| 4 | initial_entry | 2026-07-06 01:51 @ 63563.2 | 2026-07-06 14:26 @ 62356.1 | 1156.77 | 4.34 | atr_trailing_stop |
| 5 | initial_entry | 2026-07-06 17:54 @ 63596.1 | 2026-07-06 21:08 @ 63911.3 | -366.13 | -1.02 | initial_stop |
| 6 | initial_entry | 2026-07-07 12:33 @ 63573.6 | 2026-07-07 15:38 @ 63886.8 | -364.11 | -1.02 | initial_stop |
| 7 | initial_entry | 2026-07-07 20:33 @ 63621.2 | 2026-07-09 06:02 @ 62680.1 | 890.62 | 3.28 | atr_trailing_stop |
| 8 | initial_entry_after_downside_exit | 2026-07-11 15:00 @ 64314.6 | 2026-07-14 05:08 @ 62804.7 | 1459.02 | 2.32 | atr_trailing_stop |
| 9 | initial_entry_after_downside_exit | 2026-07-14 17:06 @ 64632.9 | 2026-07-14 21:41 @ 64771.2 | -190.04 | -1.05 | initial_stop |
| 10 | initial_entry | 2026-07-16 01:18 @ 64473.7 | 2026-07-16 01:50 @ 64747.9 | -325.98 | -1.02 | initial_stop |
| 11 | initial_entry | 2026-07-16 14:57 @ 64451.3 | 2026-07-16 15:26 @ 64748.8 | -349.24 | -1.02 | initial_stop |
| 12 | initial_entry | 2026-07-16 16:03 @ 64555.0 | 2026-07-17 14:11 @ 63482.2 | 1021.66 | 5.41 | atr_trailing_stop |
| 13 | initial_entry | 2026-07-18 19:30 @ 64440.7 | 2026-07-18 20:23 @ 64684.5 | -295.52 | -1.03 | initial_stop |
| 14 | initial_entry | 2026-07-19 11:27 @ 64505.7 | 2026-07-19 17:11 @ 64670.8 | -216.71 | -1.04 | initial_stop |
| 15 | initial_entry | 2026-07-19 17:57 @ 64529.3 | 2026-07-19 22:17 @ 64670.6 | -192.91 | -1.05 | initial_stop |
| 16 | initial_entry | 2026-07-20 01:54 @ 64530.2 | 2026-07-20 02:02 @ 64694.9 | -216.33 | -1.04 | initial_stop |
| 17 | initial_entry | 2026-07-25 20:00 @ 64353.3 | 2026-07-26 01:00 @ 64489.1 | -187.42 | -0.44 | adjust_supertrend_bullish_flip |
| 18 | initial_entry | 2026-07-26 01:42 @ 64426.7 | 2026-07-26 14:05 @ 64658.9 | -283.83 | -1.03 | initial_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
