# BTCUSDT 1h-trend + 15m MACD trend-line breakout (LONG) — 2025-04

## Data & Setup

- Backtest month: `2025-04` (UTC); warm-up months: 2025-03.
- Hourly bars in span: 1,462; simulated 15m bars (target month): 2,879.
- Costs: slippage `1` bps/side, taker fee `0.0400%`, size `1` BTC.
- Trend filter: last closed 1h close > MA(20) and the last `7` 15m closes all above that 1h MA.
- Pullback: 15m MACD(12,26,9) DIF below zero; golden cross below zero arms the setup.
- Trend line through H1 and the most recent confirmed swing high (k=2) below H1; valid when slope/ATR(14) ≤ `-0.03`, H1 distance `6`–`40` bars, and no prior close has breached it.
- Entry: 15m close > line + `0.15 × ATR(15m)`; long filled on the next 15m open.
- Disarm after `20` bars without a breakout; sub-zero death cross returns to pullback; 1h filter failure resets.
- Exit mode: `fixed_2r`. Initial stop = nearer of pullback low / `1.5 × ATR(15m)` below entry (= 1R); fixed target `2R`; 1h close below MA exits; time stop `24` bars without 1R.
- Pullback-depth filter: off.

## Signals & Structure

| Item | Count |
| --- | ---: |
| Trend lines drawn | 2 |
| Entry signals | 0 |
| DIF sub-zero crosses | 48 |
| Sub-zero golden crosses | 73 |

### Trend-line outcomes

- `unresolved`: 2

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 0 |
| Wins / Losses / Breakeven | 0 / 0 / 0 |
| Win rate | 0.0% |
| Gross P&L | 0.00 USDT |
| Net P&L after costs | 0.00 USDT |
| Total fees | 0.00 USDT |
| Net profit factor | n/a |
| Average net P&L | 0.00 USDT |
| Maximum net drawdown | 0.00 USDT |

## Exit Reasons

- no trades

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| - | - | - | - | - | - | No trade |

## Notes

- 15m OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, swing pivots are consumed only after their k-bar confirmation, and each 15m bar sees only the previously closed 1h bar.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
