# BTCUSDT 1h-trend + 15m MACD trend-line breakout (LONG) — 2025-02

## Data & Setup

- Backtest month: `2025-02` (UTC); warm-up months: 2025-01.
- Hourly bars in span: 1,414; simulated 15m bars (target month): 2,687.
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
| Entry signals | 1 |
| DIF sub-zero crosses | 48 |
| Sub-zero golden crosses | 72 |

### Trend-line outcomes

- `unresolved`: 1
- `entered`: 1

## Performance

| Metric | Result |
| --- | ---: |
| Trades | 1 |
| Wins / Losses / Breakeven | 0 / 1 / 0 |
| Win rate | 0.0% |
| Gross P&L | -261.40 USDT |
| Net P&L after costs | -358.79 USDT |
| Total fees | 77.91 USDT |
| Net profit factor | 0.00 |
| Average net P&L | -358.79 USDT |
| Maximum net drawdown | -358.79 USDT |

## Exit Reasons

- `hourly_ma_break`: 1

## Trade Detail

| # | Entry | Exit | Net USDT | Net R | Exit reason |
|---:|---|---|---:|---:|---|
| 1 | 2025-02-10 19:00 @ 97529.8 | 2025-02-10 23:14 @ 97248.9 | -358.79 | -0.56 | hourly_ma_break |

## Notes

- 15m OHLC cannot resolve intra-bar high/low ordering; the stop is given priority over the target.
- Only data available at event time is used: signals read closed bars, fills are next-bar open, swing pivots are consumed only after their k-bar confirmation, and each 15m bar sees only the previously closed 1h bar.
- Net P&L includes per-side slippage and taker fee; funding, spread, and queue effects are not modelled.
- Indicators are warmed with the preceding month(s); trades are counted only inside the target month.
