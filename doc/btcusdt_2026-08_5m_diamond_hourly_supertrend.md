# BTCUSDT 5 分鐘 Pine 菱形＋1 小時 Adaptive Supertrend 空單回測

- 輸入：
  - `/Users/chihjuihsu/Documents/python_script/snr_strategy/data/btcusdt/BTCUSDT-aggTrades-2026-08.csv`
- 資料範圍：2026-08-01T00:00:00+00:00 至 2026-08-31T23:59:59.466000+00:00；raw aggTrades 35,676,321 筆。
- 已完成 K 棒：5 分鐘 8,927 根、1 小時 744 根；支撐箱 1 個、壓力箱 4 個。
- 箱體：close pivot 20/20、signed-volume filter 2、ATR(200) × 1。
- 進場：5 分鐘已完成 K 的兩種紅菱形；訊號後下一筆 raw aggTrade 做空，同時最多一個 0.01 BTC 部位。
- 出場：持倉後先觀察到小時 Supertrend 空頭，再於空翻多後下一筆成交退出；raw price 結構停損優先。停損為 anchor + 0.1 × 小時 ATR(20)。
- 小時 Adaptive Supertrend：ATR(10)、乘數 3–0.8、speed lookback 2、threshold 0.25–0.8、smoothing 2。
- 成本：單邊手續費 5 bps、單邊不利滑價 2 bps，不計 funding；初始資金 US$10,000.00。

## 確認時間與 TradingView 顯示

Pine 原碼的 `offset=-1` 只把菱形視覺上往前移一根，並不代表當時已可交易。本回測把菱形標在真正完成確認的 5 分鐘 K，並只在之後的 raw trade 成交，沒有未完成 K 或 intrabar 偷看。

5 分鐘紅菱形共 13 個；直接用 1 小時 OHLC 計算的紅菱形共 3 個。對每個 5 分鐘訊號，以其所在小時 K 的真正收盤作等待時間基準，共比較 13 個；5 分鐘確認平均提早 28.08 分鐘，中位數 25.00 分鐘。這是確認延遲比較；由於 5 分鐘與 1 小時 OHLC 的 crossing 路徑不同，不表示每個訊號在 1 小時資料上也一定會出現。

| 訊號／績效 | 數值 |
| --- | ---: |
| Resistance Holds 紅菱形 | 13 |
| Support-as-Resistance 紅菱形 | 0 |
| Support Holds 綠菱形 | 1 |
| Resistance-as-Support 綠菱形 | 4 |
| 紅菱形 / 成交 | 13 / 4 |
| 持倉中或同 tick 忽略 | 9 |
| ATR 尚未完成而略過 | 0 |
| Supertrend 空翻多出場 | 1 |
| 結構停損出場 | 3 |
| 資料結束出場 | 0 |
| 交易 / 勝 / 負 | 4 / 0 / 4 |
| 勝率 | 0.00% |
| Profit factor | 0.00 |
| Raw-price P&L | US$-18.44 |
| 滑價成本 | US$1.08 |
| 手續費 | US$2.71 |
| 淨損益 | US$-22.23 |
| 最終權益 | US$9,977.77 |
| 報酬率 | -0.22% |
| 最大回撤 | US$23.10 |
| 平均持倉 | 10.65 小時 |
| 市場曝險 | 5.73% |
