# TMF 202609：Tick 兩口空單＋Legacy Supertrend 出場回測

## 資料與設定

- 日期：`2026-08-05` 至 `2026-09-15`；來源檔 30 個、有效 tick 5,462,818 筆、60 分 K 565 根。
- 起始權益：NT$400,000；TMF 每點 NT$10；最多同時 2 口。
- 進出場每邊使用 2 點不利滑價；未計手續費與期交稅；不模擬追繳或強制平倉。
- 2,000 口量 K 每個日／夜盤重新累積，時段尾端不足量直接丟棄。

## 交易規則

- 完整小時 K 確認碰到有效壓力後啟動分層進場；量 K 必須接觸該壓力、收黑，且收盤位置不高於 35%。
- `Early` 是確認後第一個合格反轉；之後完整小時 K 若形成更高測試點，第一個 lower-high 合格反轉為 `Balanced`；再往後首次收回壓力下緣為 `Conservative`。
- 訊號後同一交易時段的下一筆 tick 放空一口；持有一口時，下個有效訊號再加一口，滿兩口後忽略其他訊號。
- 兩口視為同一組。自適應 60 分 Supertrend 曾呈空頭後翻多，於第一筆可用 tick 同時平倉。
- 不設初始停損、移動停利、保本、壓力失效、確認逾時或最大持倉時間；資料結束時以最後 tick 平倉。
- 60 分狀態只在其完成時間嚴格早於當前 tick 時使用，保留同秒成交的原始列順序。

## 帳戶結果

| Metric | Value |
| --- | ---: |
| Valid signals / filled entries | 19 / 10 |
| Ignored at two-contract capacity | 9 |
| Contract trades / position groups | 10 / 5 |
| Winning / losing contracts | 8 / 2 |
| Winning / losing groups | 4 / 1 |
| Contract / group win rate | 80.0% / 80.0% |
| Group profit factor | 2.47 |
| Gross P&L | NT$23,490 |
| Net P&L after slippage | NT$23,090 |
| Final equity | NT$423,090 |
| Return | 5.77% |
| Minimum tick-level equity | NT$374,840 |
| Maximum tick-level drawdown | NT$29,340 (7.26%) |
| Peak open contracts | 2 |
| Flat exposure | 634.8 h (63.6%) |
| One-contract exposure | 63.6 h (6.4%) |
| Two-contract exposure | 299.6 h (30.0%) |

## Group Ledger

| Group | Lots | First entry | Exit | Average fill | Net NTD | Exit reason |
|---:|---:|---|---|---:|---:|---|
| 1 | 2 | 2026-08-11 20:25:54 | 2026-08-17 12:45:01 | 45453.0 | -15,660 | adaptive_hourly_supertrend_bullish_flip |
| 2 | 2 | 2026-08-27 09:57:38 | 2026-08-28 00:00:00 | 46384.5 | 550 | adaptive_hourly_supertrend_bullish_flip |
| 3 | 2 | 2026-08-28 00:18:20 | 2026-08-31 15:00:00 | 46405.0 | 6,000 | adaptive_hourly_supertrend_bullish_flip |
| 4 | 2 | 2026-09-05 01:01:05 | 2026-09-08 18:00:00 | 47286.5 | 8,370 | adaptive_hourly_supertrend_bullish_flip |
| 5 | 2 | 2026-09-09 09:51:12 | 2026-09-10 23:00:00 | 47514.5 | 23,830 | adaptive_hourly_supertrend_bullish_flip |

## 風險說明

本版本依選定的 Legacy 行為，不會在獲利時移動停損，也沒有虧損上限。NT$400,000 僅作為權益基準；回測不會因權益或保證金不足自動平倉。
