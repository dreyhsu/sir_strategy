# BTCUSDT hourly S/R + volume-bar adaptive Supertrend short backtest

- Inputs:
  - `/Users/chihjuihsu/Documents/python_script/snr_strategy/data/btcusdt/BTCUSDT-aggTrades-2026-08.csv`
- Source rows: 35,676,321; completed hourly bars: 744; completed notional-volume bars: 265,223.
- Period: 2026-08-01T00:00:00+00:00 to 2026-08-31T23:59:59.466000+00:00.
- Continuous 24/7 market. Volume bar threshold: US$1,000,000; maximum data gap: 60 seconds.
- Adaptive Supertrend: ATR(10), multiplier 3 to 0.8, speed lookback 2, speed range 0.25–0.8, smoothing 2.
- Hourly Pine S/R: close pivot 20/20, signed-volume filter 2, ATR(200) box width × 1. Generated 1 support and 4 resistance boxes.
- Entry: an armed hourly resistance emits on the first touching bearish volume-Supertrend bar, then requires a bullish state to re-arm. Maximum 3 emitted signals per resistance box; fill on the next raw aggTrade when flat.
- Exit: resistance top + 0.1 × completed hourly ATR(20) structure stop, or completed volume-bar bearish-to-bullish flip filled on the next raw aggTrade. Open trades close at data end.
- Initial equity: US$10,000.00; position: 0.01 BTC.
- Costs: 5 bps taker fee and 2 bps adverse slippage per side. Funding is excluded.

| Resistance box | Signals emitted |
| ---: | ---: |
| 1 | 3 |
| 2 | 3 |
| 3 | 0 |
| 5 | 0 |

| Metric | Value |
| --- | ---: |
| Bearish bars | 130220 |
| Resistance-touch bars | 3161 |
| Entry signals / fills | 6 / 6 |
| Signals ignored while occupied | 0 |
| Entries skipped before stop ATR warm-up | 0 |
| Bullish flip signals / exits | 6 / 6 |
| Structure-stop exits | 0 |
| Data-end exits | 0 |
| Trades | 6 |
| Wins / losses | 0 / 6 |
| Win rate | 0.00% |
| Profit factor | 0.00 |
| Raw-price P&L | US$0.26 |
| Slippage cost | US$1.55 |
| Fees | US$3.89 |
| Net P&L | US$-5.18 |
| Final equity | US$9,994.82 |
| Return | -0.05% |
| Minimum equity | US$9,994.54 |
| Maximum drawdown | US$5.46 |
| Average holding time | 0.00 hours |
| Market exposure | 0.00% |
