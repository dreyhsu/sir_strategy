# BTCUSDT aggTrades two-position legacy short backtest

- Input: `/Users/chihjuihsu/Documents/python_script/TXF_analysis/snr/data/btcusdt/BTCUSDT-aggTrades-2026-08.csv`
- Source rows: 35,676,321; completed hourly bars: 744; completed notional-volume bars: 265,223.
- Period: 2026-08-01T00:00:00+00:00 to 2026-08-31T23:59:59.466000+00:00.
- Continuous 24/7 market. Volume bar threshold: US$1,000,000; max permitted data gap: 60 seconds.
- Initial equity: US$10,000.00; each layer: 0.01 BTC; max layers: 2.
- Costs: 5 bps taker fee per side and 2 bps adverse slippage per side. Funding is excluded.
- Pine resistance boxes use ATR(200); each lot stop is resistance top + 0.10 × completed ATR(20).

| Metric | Value |
| --- | ---: |
| Signals / filled entries | 3 / 3 |
| Ignored at capacity | 0 |
| Structure-stop exits | 3 |
| Entries skipped before stop ATR warms up | 0 |
| Contract trades / groups | 3 / 3 |
| Net P&L | US$-6.38 |
| Final equity | US$9,993.62 |
| Return | -0.06% |
| Minimum equity | US$9,993.62 |
| Maximum drawdown | US$6.75 |
| Peak positions | 1 |
