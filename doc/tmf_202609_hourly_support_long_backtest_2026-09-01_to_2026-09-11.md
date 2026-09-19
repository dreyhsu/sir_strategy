# TMF 202609：60 分 K 支撐 + Tick 反轉僅做多回測

## 資料與時段

- 日檔：Daily_2026_09_01.zip, Daily_2026_09_02.zip, Daily_2026_09_03.zip, Daily_2026_09_04.zip, Daily_2026_09_07.zip, Daily_2026_09_08.zip, Daily_2026_09_09.zip, Daily_2026_09_10.zip, Daily_2026_09_11.zip
- 商品：`TMF / 202609`；逐筆成交：1,341,435 筆。
- 交易時段：日盤 `08:45–13:45`，夜盤 `15:00–次日 05:00`。不跨時段累積 2,000 口 K 棒，也不隔夜留倉。
- 60 分 K：171 根；2,000 口 volume bar：2,046 根。

## 支撐壓力計算

依照 `pine_script.txt` 的邏輯，以 60 分 K 的 **close** 尋找左右各 20 根 K 的 pivot low/high。pivot 必須等右側 K 線完成後才確認，因此不會在轉折當下提前知道支撐。

- 支撐：pivot low，且確認 K 為正 delta volume；箱體為 `pivot close` 到 `pivot close - ATR(20) × 1`。
- 壓力：pivot high，且確認 K 為負 delta volume；箱體向上使用同一 ATR 寬度。
- Pine 原稿使用 `ATR(200)`；本資料只有 171 根 60 分 K，無法完成 200 根初始化，故本回測使用 `ATR(20)`。
- 已確認 zones：支撐 1 個、壓力 2 個。

## 交易規則

- 僅當一根 2,000 口 volume bar 出現原策略的多方密集反轉，且該 bar 價格範圍接觸一個已確認、未跌破的 60 分 K 支撐箱體，才建立做多訊號。
- 訊號完成後，以**下一根** volume bar open 進場；同一時間最多一口多單。
- 初始停損為訊號 bar low - 2 點。停損、壓力觸及、追蹤停損與空方密集反轉都在 bar 完成後確認，再以下一根 open 出場。
- 最高價達 `+2R` 時，啟用最高價 - `1R` 的追蹤停損。若進場時已有上方已確認壓力，觸及壓力箱體下緣也會出場。

## 結果

| Metric | Value |
| --- | ---: |
| Trades | 0 |
| Wins / Losses | 0 / 0 |
| Win rate | 0.0% |
| Net P&L | 0.0 points |
| Profit factor | n/a |
| Average P&L | 0.0 points |
| Maximum drawdown | 0.0 points |

## Trade Ledger

沒有符合「已確認支撐 + tick 多方反轉」的多單。

## 限制

結果未扣手續費、期交稅、買賣價差與滑價。Pine 的 pivot 需要右側 20 根 60 分 K 才確認，回測也只在確認後的 tick 訊號交易，避免 look-ahead bias。
