# BTCUSDT aggTrades two-position legacy short backtest

- Inputs:
  - `/Users/chihjuihsu/Documents/python_script/snr_strategy/data/btcusdt/BTCUSDT-aggTrades-2026-08.csv`
- Source rows: 35,676,321; completed hourly bars: 744; completed notional-volume bars: 265,223.
- Period: 2026-08-01T00:00:00+00:00 to 2026-08-31T23:59:59.466000+00:00.
- Continuous 24/7 market. Volume bar threshold: US$1,000,000; max permitted data gap: 60 seconds.
- Initial equity: US$10,000.00; each layer: 0.01 BTC; max layers: 2.
- Costs: 5 bps taker fee per side and 2 bps adverse slippage per side. Funding is excluded.
- Pine resistance boxes use ATR(200); each lot stop is resistance top + 0.10 × completed ATR(20).

| Metric | Value |
| --- | ---: |
| Signals / filled entries | 153 / 11 |
| Ignored at capacity | 142 |
| Structure-stop exits | 6 |
| Entries skipped before stop ATR warms up | 0 |
| Contract trades / groups | 11 / 6 |
| Net P&L | US$-23.37 |
| Final equity | US$9,976.63 |
| Return | -0.23% |
| Minimum equity | US$9,976.63 |
| Maximum drawdown | US$27.33 |
| Peak positions | 2 |
