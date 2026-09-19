# TMF 自適應 60 分 K 壓力反轉空單：Strategy B 規格

## 策略定位

Strategy B 是 TMF 壓力反轉空單策略的風控與成交模型升級版。

- Legacy A：`snr/src/backtest_tmf_adaptive_hourly_resistance_short.py`
- Strategy B：`snr/src/backtest_tmf_adaptive_hourly_resistance_short_ab.py` 中的 `session-risk` 策略
- 方向：僅做空
- 同一時間最多持有一口空單
- 預設商品／到期月份：`TMF / 202609`
- 預設 volume bar：每個交易時段重新累積的 2,000 口 bar

Legacy A 的交易邏輯必須原樣保留，Strategy B 以獨立回測路徑執行，供 A/B test 比較。

預設同時執行 A/B：

```bash
conda run -n tss python snr/src/backtest_tmf_adaptive_hourly_resistance_short_ab.py \
  --start-date 2026-08-05 \
  --end-date 2026-09-15
```

## 資料與交易時段

資料來源為 TAIFEX 逐筆成交資料。程式依成交資料原始列順序保留同一秒內多筆交易的先後關係。

交易時段：

- 日盤：`08:45:00–13:45:00`
- 夜盤：`15:00:00–次日 05:00:00`

每個日盤及夜盤分別建立 volume bar：

1. 每個 session 從 0 開始累積成交量。
2. 累積量達到或超過 2,000 口時完成一根 volume bar。
3. session 結束時，未滿 2,000 口的剩餘量直接丟棄。
4. 未完成 bar、待進場訊號及未成交進場指令不得跨越休市。
5. 已建立的持倉可以跨 session，直到符合出場條件。

因此，Strategy B 不會出現同一根 volume bar 同時包含前一 session 尾盤與下一 session 開盤跳空的情況。

## 60 分 K、壓力區與自適應 Supertrend

60 分 K、Pine-style 壓力區及自適應 Supertrend 沿用 Legacy A 的計算方式：

- 壓力 pivot 使用左右各 20 根完成的 60 分 K 確認。
- 壓力區寬度預設為 `ATR(20) × 1.0`。
- 自適應 Supertrend 使用 `ATR(10)`。
- 基礎 multiplier 為 `3.0`，最小 multiplier 為 `0.8`。
- 價格速度使用最近 2 根 60 分 K，平滑期間為 2。
- 低速門檻為 `0.25`，高速門檻為 `0.8`。

60 分 K 與 Supertrend 可以跨日盤、夜盤連續計算，但任何決策只能讀取當時已完成且時間嚴格早於事件 tick 的小時 K，禁止使用尚未完成的小時 K。

## 進場訊號

Strategy B 沿用 Legacy A 的壓力反轉訊號。完成的 session-reset 2,000 口 volume bar 必須同時符合：

1. 接觸已確認且尚未失效的 60 分 K 壓力區。
2. `high` 是最近 5 根已完成 volume bar 的最高點。
3. `close < open`，形成收黑反轉。
4. 收盤位置位於全幅下方 35%，即：

   ```text
   (close - low) / (high - low) <= 0.35
   ```

訊號判斷只使用目前及更早完成的 volume bar，不要求進場時 hourly Supertrend 已經翻空。

## 進場執行與滑價

訊號 volume bar 完成後：

1. 找到同一 session 中、訊號最後一筆成交之後的下一筆 tick。
2. 該 tick 價格為原始可成交價格。
3. 空單進場套用 2 點不利滑價：

   ```text
   entry_fill_price = next_tick_price - 2
   ```

4. 如果同一 session 已沒有下一筆 tick，取消訊號，不保留至下一 session。
5. 如果最新完成 hourly ATR 尚未初始化，取消進場。
6. 如果滑價後進場價已達到或高於初始停損價，取消進場。

## 初始停損

進場時固定初始停損：

```text
initial_stop = max(signal_bar_high, resistance_top)
               + 0.5 × entry_hourly_atr
```

- `entry_hourly_atr` 是進場前最新完成 60 分 K 的 ATR。
- 初始停損從成交後開始生效。
- 每一筆新 tick 都檢查是否觸及停損，不等待 volume bar 收盤。
- 觸及後以下一筆可成交 tick 加上 2 點不利滑價平倉。
- 若下一筆成交已跳過停損價，使用實際下一筆價格，不假設能成交在停損價。

空單出場滑價：

```text
exit_fill_price = next_tick_price + 2
```

## 壓力失效

持倉期間以完成的 session-reset volume bar 判斷壓力是否失效：

```text
volume_bar_close > entry_resistance_top
```

- `close == resistance_top` 不算失效。
- 失效確認後，於下一筆可成交 tick 平倉並加入 2 點不利滑價。
- 使用進場時對應的壓力區，不因後續建立新壓力區而更換基準。

## Supertrend 確認逾時

Strategy B 允許在 hourly Supertrend 尚未翻空時提前進場，但必須在 12 個鐘錶小時內獲得空頭確認。

```text
confirmation_deadline = entry_time + 12 hours
```

- 進場時最新完成 Supertrend 已是空頭，立即視為確認完成。
- 否則等待後續完成的 hourly Supertrend 轉為空頭。
- 到達期限仍未確認時，於期限後第一筆可成交 tick 平倉。
- 12 小時包含日夜盤之間、休市及週末；期限落在休市時，於下一個可交易 tick 出場。

## 最大持倉時間

不論 Supertrend 狀態，單筆持倉最多保留 120 個鐘錶小時：

```text
maximum_holding_deadline = entry_time + 120 hours
```

期限後於第一筆可成交 tick 平倉。休市時間仍計入 120 小時。

## ATR 獲利追蹤停損

Hourly Supertrend 確認空頭後，啟用 ATR trailing stop：

```text
candidate_trailing_stop = lowest_price_since_entry
                          + 1.5 × latest_completed_hourly_atr

trailing_stop = min(previous_trailing_stop, candidate_trailing_stop)
```

- `lowest_price_since_entry` 使用進場後已發生 tick 的最低價格。
- ATR 使用當時最新完成的 60 分 K ATR。
- trailing stop 只能向下收緊，不可因 ATR 增加而向上放寬。
- 每筆 tick 檢查是否觸及 trailing stop。
- 觸及後於下一筆可成交 tick 平倉並加入 2 點不利滑價。

## 主要出場

主要趨勢出場沿用 Legacy A 的方向：

1. 部位曾經獲得 hourly Supertrend 空頭確認。
2. 後續完成的 hourly Supertrend 從空頭翻為多頭。
3. 在翻多確認後的下一筆可成交 tick 平空。
4. 出場價格加入 2 點不利滑價。

## 同時觸發的出場優先序

同一 tick 或同一決策時間發生多個條件時，依下列順序記錄出場原因：

1. `initial_stop` 或 `atr_trailing_stop`
2. `resistance_invalidated`
3. `supertrend_confirmation_timeout`
4. `maximum_holding_time`
5. `adaptive_hourly_supertrend_bullish_flip`
6. `data_end`

風險控制條件優先於趨勢出場，避免以較佳的理論價格覆蓋實際先發生的停損。

## A/B Test 比較方式

一次回測預設同時執行：

- A：Legacy A 原始策略。
- B：本文件定義的 Strategy B。

Legacy A 的原始交易紀錄與成交價格不得改寫。比較報告另外為 A、B 計算共同的滑價後績效：

- A 的 cost-adjusted P&L：每筆原始 P&L 扣除 4 點。
- B 的 gross P&L：使用下一筆 tick 的原始價格計算。
- B 的 net P&L：使用進出場各 2 點不利滑價後的成交價計算。

比較項目：

- 交易數
- 勝／敗與勝率
- Gross／net P&L
- Profit factor
- 從初始權益 0 開始計算的最大回撤
- 平均及最長持倉時間
- 最佳／最差單筆交易
- 跨 session 交易數
- 各出場原因的次數與損益

## 無前視偏誤要求

- Volume bar 訊號只能在該 bar 最後一筆 tick 完成後使用。
- 下一筆成交必須依原始 tick 列順序取得；同一秒不代表同一筆成交。
- Hourly ATR 與 Supertrend 只能使用事件發生前已完成的小時 K。
- 壓力 pivot 必須等待右側 20 根小時 K 完成後才生效。
- 逐筆停損只能依當時已發生的價格更新，不可使用該 volume bar 未來的 high 或 low。

## 預設參數摘要

| Parameter | Default |
| --- | ---: |
| Volume bar size | 2,000 contracts |
| Tick lookback | 5 bars |
| Bearish close-position maximum | 0.35 |
| Initial-stop ATR multiplier | 0.5 |
| Supertrend confirmation timeout | 12 hours |
| Maximum holding time | 120 hours |
| ATR trailing multiplier | 1.5 |
| Entry slippage | 2 points |
| Exit slippage | 2 points |

本規格不包含手續費、期交稅與買賣價差。這些成本應在正式策略評估時另外加入，且不得只依單一短期間的回測結果調整參數。
