# TMF 202609 Strategy B 回測

## 資料與策略

- 日檔範圍：`2026-08-05` 至 `2026-09-15`；實際資料截止 `2026-09-15 04:59:58`。
- 有效 tick：5,462,818 筆；session-reset 2,000 口 volume bar：7,432 根。
- 進出場各使用 `2` 點不利滑價。
- 初始停損：`max(signal high, resistance top) + hourly ATR × 0.5`。
- Supertrend 確認逾時：`12` 小時；最大持倉：`120` 小時。
- Supertrend 確認翻空後使用 `lowest price + hourly ATR × 1.5` 追蹤停損。

## 結果

| Metric | Gross | Net after slippage |
| --- | ---: | ---: |
| Trades | 13 | 13 |
| Wins / Losses | 6 / 7 | 6 / 7 |
| Win rate | 46.2% | 46.2% |
| P&L | 846.0 points | 794.0 points |
| Profit factor | 2.66 | 2.47 |
| Maximum drawdown | -391.0 points | -415.0 points |
| Average holding | 12.5 hours | 12.5 hours |
| Maximum holding | 59.5 hours | 59.5 hours |

## Exit Reasons

| Exit reason | Trades | Net P&L |
| --- | ---: | ---: |
| atr_trailing_stop | 5 | 1072.0 |
| resistance_invalidated | 6 | -294.0 |
| supertrend_confirmation_timeout | 2 | 16.0 |

結果未包含手續費、期交稅與買賣價差。
