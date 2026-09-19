# TMF 202609 自適應壓力反轉空單 A/B Test

## 資料與假設

- 日檔範圍：`2026-08-05` 至 `2026-09-15`；實際資料截止 `2026-09-15 04:59:58`。
- 有效 tick：5,462,818 筆。
- Legacy A：`backtest_tmf_adaptive_hourly_resistance_short.py` 原始交易邏輯。
- Strategy B：session-reset 2,000 口 volume bar、逐筆成交、ATR 風控與鐘錶時間限制。
- A/B cost-adjusted / net 統一使用進出場每邊 `2` 點不利滑價。

## 績效比較

| Variant | Trades | Wins / Losses | Win rate | Net P&L | Profit factor | Max drawdown | Avg hold | Max hold |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Legacy A gross | 7 | 5 / 2 | 71.4% | 1259.0 | 1.91 | -1093.0 | 58.0 h | 143.2 h |
| Legacy A cost-adjusted | 7 | 5 / 2 | 71.4% | 1231.0 | 1.88 | -1109.0 | 58.0 h | 143.2 h |
| Strategy B gross | 13 | 6 / 7 | 46.2% | 846.0 | 2.66 | -391.0 | 12.5 h | 59.5 h |
| Strategy B net | 13 | 6 / 7 | 46.2% | 794.0 | 2.47 | -415.0 | 12.5 h | 59.5 h |

## Strategy B 出場原因

| Exit reason | Trades | Net P&L |
| --- | ---: | ---: |
| atr_trailing_stop | 5 | 1072.0 |
| resistance_invalidated | 6 | -294.0 |
| supertrend_confirmation_timeout | 2 | 16.0 |


## Strategy B 參數

- Initial stop：`max(signal high, resistance top) + ATR × 0.5`
- Supertrend confirmation timeout：`12` 小時
- Maximum holding：`120` 小時
- ATR trailing：確認翻空後使用 `lowest price + ATR × 1.5`，只可向下收緊

結果未包含手續費、期交稅與買賣價差。最大回撤從初始權益 0 開始計算。
