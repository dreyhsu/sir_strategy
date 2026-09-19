# TMF 202609：自適應 60 分 K Supertrend 壓力反轉空單回測

## 資料與持倉

- 商品 / 到期月份：`TMF / 202609`
- 日檔範圍：`2026-08-05` 至 `2026-09-15`；有效 tick：5,462,818 筆。
- 實際成交資料截止：`2026-09-15 04:59:58`。
- 2,000 口 volume bar：7,459 根，跨日盤、夜盤與休市時段連續累積。
- 不強制在 `13:45` 或 `05:00` 平倉；未結束部位只在資料結尾以最後一根完成 volume bar close 結算。

## 進場

- 60 分 K 依 Pine pivot 與 delta volume 建立壓力箱；已確認壓力：7 個。
- 2,000 口 volume bar 必須接觸已確認、未失效壓力，為最近 5 根高點、收黑，且 close 位於全幅下方 35%。
- 訊號完成後，下一根 volume bar open 放空；同一時間最多一口。

## 自適應 60 分 K Supertrend 出場

- 基礎寬度：`ATR(10) × 3`；最小寬度：`ATR × 0.8`。
- 價格速度使用最近 2 根 60 分 K 的 ATR 正規化移動，並以 2 根平滑。
- 速度低於 0.25 時使用較寬的基礎倍數；速度高於 0.8 時收緊至最小倍數，中間線性調整。
- 已完成的 60 分 K Supertrend 從空頭翻多後，下一根 volume bar open 平空。volume bar 只讀取較早完成的小時 K 狀態，沒有 look-ahead。

## 結果

| Metric | Value |
| --- | ---: |
| Resistance + bearish volume-bar signals | 54 |
| Trades | 7 |
| Wins / Losses | 5 / 2 |
| Win rate | 71.4% |
| Net P&L | 1259.0 points |
| Profit factor | 1.91 |
| Maximum drawdown | -342.0 points |
| Cross-session trades | 6 |

## Look-Ahead Bias 稽核

- 壓力 pivot 必須等右側 20 根 60 分 K 完成才建立，訊號時間早於壓力確認時間時不會交易。
- volume-bar 反轉只使用目前與更早的 5 根 volume bar；同一秒多筆官方成交保留原始列順序。
- 自適應 ATR 倍數與 Supertrend 只在 60 分 K 收盤後計算。volume bar 以嚴格早於自身時間的小時 K 狀態判斷，不能使用同時或未完成的小時 K。
- Supertrend 翻轉被觀察到後，仍在下一根 volume bar open 才執行平倉。
- 官方 tick 時間只有秒級；前一根 volume bar 結束與下一根開始可以顯示同一秒，但程式保留官方 CSV 的列順序，實際仍是下一筆成交開始的新 bar，不是用同一根 bar 的未來價格成交。

## Trade Ledger

| # | Signal | Entry | Exit | Entry Px | Exit Px | P&L | Exit Reason | Cross Session |
|---:|---|---|---|---:|---:|---:|---|---|
| 1 | 2026-08-11 13:34:11 | 2026-08-11 13:34:19 | 2026-08-17 12:47:33 | 45196 | 46238 | -1042.0 | adaptive_hourly_supertrend_bullish_flip | True |
| 2 | 2026-08-27 09:39:19 | 2026-08-27 09:39:19 | 2026-08-28 00:03:40 | 46394 | 46365 | 29.0 | adaptive_hourly_supertrend_bullish_flip | True |
| 3 | 2026-08-28 00:08:16 | 2026-08-28 00:08:18 | 2026-08-31 15:00:01 | 46369 | 46107 | 262.0 | adaptive_hourly_supertrend_bullish_flip | True |
| 4 | 2026-09-01 09:06:30 | 2026-09-01 09:06:30 | 2026-09-01 09:45:51 | 46545 | 46887 | -342.0 | adaptive_hourly_supertrend_bullish_flip | False |
| 5 | 2026-09-01 10:05:50 | 2026-09-01 10:05:50 | 2026-09-02 20:02:11 | 46826 | 46030 | 796.0 | adaptive_hourly_supertrend_bullish_flip | True |
| 6 | 2026-09-05 00:23:01 | 2026-09-05 00:23:01 | 2026-09-08 18:02:18 | 47191 | 46842 | 349.0 | adaptive_hourly_supertrend_bullish_flip | True |
| 7 | 2026-09-09 09:33:49 | 2026-09-09 09:33:49 | 2026-09-10 23:01:27 | 47482 | 46275 | 1207.0 | adaptive_hourly_supertrend_bullish_flip | True |

結果未包含手續費、期交稅、價差與滑價。
