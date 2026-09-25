# BTCUSDT Hourly-Resistance + 3m UT Bot Short — 2026-03

## Data & Setup

- Backtest month: `2026-03` (UTC); warm-up months: 2026-02.
- Hourly bars in span: 1,414; simulated 3m bars (target month): 14,879.
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
| Dynamic top versions | 6 |
| Top adjustments | 0 |
| Initial-entry signals | 20 |
| Downside-exit initial signals | 1 |
| Re-entry signals | 0 |
| UT Bot SELL total | 395 |

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 21 |
| Wins / Losses / Breakeven | 6 / 15 / 0 |
| Win rate | 28.6% |
| Gross P&L | 4,460.60 USDT |
| Net P&L after costs | 2,971.52 USDT |
| Total fees | 1,191.26 USDT |
| Net profit factor | 1.36 |
| Average net P&L | 141.50 USDT |
| Maximum net drawdown | -5,648.60 USDT |

## Exit Reasons

- `initial_stop`: 13
- `atr_trailing_stop`: 8

## Trade Detail

| # | Entry type | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry | 2026-03-03 05:36 @ 68171.2 | 2026-03-03 16:08 @ 68294.8 | -178.21 | -0.30 | atr_trailing_stop |
| 2 | initial_entry | 2026-03-03 17:12 @ 67720.4 | 2026-03-03 18:32 @ 68644.1 | -978.23 | -1.01 | initial_stop |
| 3 | initial_entry | 2026-03-04 00:36 @ 67930.3 | 2026-03-04 01:38 @ 68610.9 | -735.24 | -1.01 | initial_stop |
| 4 | initial_entry | 2026-03-04 03:30 @ 67941.1 | 2026-03-04 06:44 @ 68602.9 | -716.43 | -1.01 | initial_stop |
| 5 | initial_entry | 2026-03-06 19:00 @ 68137.1 | 2026-03-08 09:14 @ 67736.2 | 346.52 | 0.94 | atr_trailing_stop |
| 6 | initial_entry | 2026-03-08 10:39 @ 67916.4 | 2026-03-09 03:08 @ 66946.6 | 915.87 | 1.91 | atr_trailing_stop |
| 7 | initial_entry | 2026-03-09 06:06 @ 67643.9 | 2026-03-09 13:11 @ 68520.9 | -931.45 | -1.01 | initial_stop |
| 8 | initial_entry | 2026-03-13 02:33 @ 71338.2 | 2026-03-13 08:35 @ 71701.6 | -420.66 | -1.02 | initial_stop |
| 9 | initial_entry | 2026-03-13 21:27 @ 71246.9 | 2026-03-15 02:05 @ 71348.7 | -158.85 | -0.22 | atr_trailing_stop |
| 10 | initial_entry | 2026-03-16 06:06 @ 73880.9 | 2026-03-16 13:35 @ 74249.8 | -428.13 | -1.02 | initial_stop |
| 11 | initial_entry | 2026-03-16 13:54 @ 73955.6 | 2026-03-16 14:02 @ 74252.1 | -355.78 | -1.03 | initial_stop |
| 12 | initial_entry | 2026-03-16 14:30 @ 73573.7 | 2026-03-16 18:11 @ 74256.7 | -742.07 | -1.01 | initial_stop |
| 13 | initial_entry | 2026-03-16 19:57 @ 73870.8 | 2026-03-16 21:05 @ 74283.4 | -471.87 | -1.02 | initial_stop |
| 14 | initial_entry | 2026-03-17 06:45 @ 73961.1 | 2026-03-17 07:14 @ 74308.6 | -406.78 | -1.02 | initial_stop |
| 15 | initial_entry | 2026-03-17 09:54 @ 73960.6 | 2026-03-17 14:47 @ 74288.6 | -387.29 | -1.02 | initial_stop |
| 16 | initial_entry | 2026-03-18 10:36 @ 73960.8 | 2026-03-19 19:26 @ 70564.2 | 3338.79 | 12.88 | atr_trailing_stop |
| 17 | initial_entry_after_downside_exit | 2026-03-21 14:48 @ 70816.0 | 2026-03-22 03:29 @ 69390.2 | 1369.75 | 1.51 | atr_trailing_stop |
| 18 | initial_entry | 2026-03-23 14:51 @ 71116.9 | 2026-03-24 23:23 @ 70670.1 | 390.10 | 0.55 | atr_trailing_stop |
| 19 | initial_entry | 2026-03-25 05:27 @ 71067.9 | 2026-03-25 11:29 @ 71860.5 | -849.82 | -1.01 | initial_stop |
| 20 | initial_entry | 2026-03-25 12:18 @ 71409.6 | 2026-03-25 12:56 @ 71844.1 | -491.81 | -1.02 | initial_stop |
| 21 | initial_entry | 2026-03-25 14:00 @ 71539.4 | 2026-03-28 13:32 @ 66621.1 | 4863.11 | 16.09 | atr_trailing_stop |

## Notes

- 3m OHLC cannot resolve intra-bar high/low ordering; existing stop takes priority, new trailing stop applies from the next 3m bar.
- Only data available at event time is used; pivot repainting and Pine `offset=-1` are not used for trading.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
