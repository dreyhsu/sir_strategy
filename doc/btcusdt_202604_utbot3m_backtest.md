# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-04

## Data & Setup

- Backtest month: `2026-04` (UTC); warm-up months: 2026-03.
- Hourly bars in span: 1,462; simulated 3m bars (target month): 14,399.
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
| Dynamic top versions | 5 |
| Top adjustments | 1 |
| Initial-entry signals | 17 |
| Downside-exit initial signals | 1 |
| Re-entry signals | 1 |
| UT Bot SELL total | 402 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 19 |
| Wins / Losses / Breakeven | 3 / 16 / 0 |
| Win rate | 15.8% |
| Gross P&L | -6,306.74 USDT |
| Net P&L after costs | -7,719.56 USDT |
| Total fees | 1,130.25 USDT |
| Net profit factor | 0.11 |
| Average net P&L | -406.29 USDT |
| Maximum net drawdown | -7,728.33 USDT |

## Exit Reasons

- `initial_stop`: 15
- `atr_trailing_stop`: 3
- `data_end`: 1

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2026-04-07 23:42 @ 72062.8 | 2026-04-08 13:08 @ 72523.1 | -518.19 | -1.02 | initial_stop |
| 2 | initial_entry | 2026-04-08 13:33 @ 72074.2 | 2026-04-09 15:32 @ 71756.0 | 260.68 | 0.77 | atr_trailing_stop |
| 3 | initial_entry | 2026-04-09 16:39 @ 71797.5 | 2026-04-09 17:05 @ 72506.6 | -766.82 | -1.01 | initial_stop |
| 4 | initial_entry | 2026-04-09 18:03 @ 72025.2 | 2026-04-09 21:08 @ 72510.0 | -542.58 | -1.02 | initial_stop |
| 5 | initial_entry | 2026-04-09 21:12 @ 72178.4 | 2026-04-09 22:17 @ 72512.2 | -391.67 | -1.02 | initial_stop |
| 6 | initial_entry | 2026-04-10 02:48 @ 72032.5 | 2026-04-10 14:05 @ 72529.2 | -554.52 | -1.01 | initial_stop |
| 7 | initial_entry | 2026-04-12 01:36 @ 72204.4 | 2026-04-13 13:50 @ 71461.5 | 685.46 | 3.44 | atr_trailing_stop |
| 8 | initial_entry | 2026-04-13 15:09 @ 71910.9 | 2026-04-13 17:32 @ 72447.7 | -594.49 | -1.01 | initial_stop |
| 9 | initial_entry | 2026-04-13 17:51 @ 72148.7 | 2026-04-13 19:17 @ 72467.0 | -376.17 | -1.02 | initial_stop |
| 10 | initial_entry_after_downside_exit | 2026-04-16 20:21 @ 75100.7 | 2026-04-17 09:29 @ 76216.8 | -1176.66 | -1.01 | initial_stop |
| 11 | reentry_after_initial_stop | 2026-04-17 09:33 @ 75690.0 | 2026-04-17 13:02 @ 76384.2 | -755.00 | -1.01 | initial_stop |
| 12 | initial_entry | 2026-04-20 19:24 @ 76124.4 | 2026-04-21 08:47 @ 76699.2 | -635.96 | -1.01 | initial_stop |
| 13 | initial_entry | 2026-04-21 09:03 @ 76366.2 | 2026-04-21 10:50 @ 76673.5 | -368.55 | -1.03 | initial_stop |
| 14 | initial_entry | 2026-04-21 11:12 @ 76356.1 | 2026-04-21 11:26 @ 76674.6 | -379.78 | -1.02 | initial_stop |
| 15 | initial_entry | 2026-04-21 11:57 @ 76369.7 | 2026-04-22 02:11 @ 76674.6 | -366.18 | -1.03 | initial_stop |
| 16 | initial_entry | 2026-04-28 13:09 @ 76144.0 | 2026-04-29 01:50 @ 76626.5 | -543.59 | -1.02 | initial_stop |
| 17 | initial_entry | 2026-04-29 02:33 @ 76388.1 | 2026-04-29 03:17 @ 76607.4 | -280.51 | -1.04 | initial_stop |
| 18 | initial_entry | 2026-04-30 02:00 @ 76186.3 | 2026-04-30 13:41 @ 76549.0 | -423.81 | -0.78 | atr_trailing_stop |
| 19 | initial_entry | 2026-04-30 14:00 @ 76362.8 | 2026-04-30 23:56 @ 76292.9 | 8.77 | 0.25 | data_end |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
