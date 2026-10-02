# TMF：一小時 Pine 支撐區＋三分 K UT Bot 進出場純多策略

## 1. 策略定位

本策略只做多。支撐區以一小時 K 建立，Pine 原始邏輯不動；進場、停損、trailing 與再進場全部改用三分 K，訊號來源改為 UT Bot Alert（Key Value = 2, ATR Period = 10, source = close, 不使用 Heikin-Ashi）。策略中不再讀取一分 K。

- 商品：TMF。
- 交易方向：只做多。
- 支撐結構週期：一小時 K。
- 訊號 / 成交 / 停損 / 出場週期：三分 K。
- 同一時間最多持有一口多單。
- 訊號只能使用已完成的 K 棒。
- `Adjust Supertrend` 與其他 Adaptive Supertrend 腳本相同，以一小時 ATR 正規化價格速度動態調整 multiplier。

## 2. 一小時 K 的建立方式

一小時 K 依交易時段錨定：

- 日盤自 `08:45` 開始切分：`08:45–09:44:59`、`09:45–10:44:59`，依此類推。
- 夜盤自 `15:00` 開始切分：`15:00–15:59:59`、`16:00–16:59:59`，依此類推。
- 不把休市前後的成交混在同一根 K 棒。
- 一小時 K 尚未完成前，不得用其 high、low、close、volume、ATR 或 Supertrend 做決策。

## 3. Pine 原版方向成交量與支撐區建立

沿用 [`pine_script.txt`](pine_script.txt)：

```text
close > open  → Vol = +volume
close < open  → Vol = -volume
close = open  → 沿用上一根方向

vol_hi = highest(Vol / 2.5, 2)
vol_lo = lowest (Vol / 2.5, 2)

pivotLow = pivotlow(close, 20, 20)

若 pivotLow 已確認 且 目前確認 K 的 Vol > vol_hi → 建立支撐區

box_atr        = ATR(200)（Wilder RMA）
support_top    = pivotLow 的收盤價
support_bottom = pivotLow 的收盤價 − box_atr × 1.0
```

- 支撐區只能在 pivot 發生 20 小時後、右側 K 全部完成才生效。
- 三分 K 只能讀取在該三分 K 收盤時間之前已確認的支撐區。
- 最新支撐區建立後，進場判斷改用最新支撐區；既有持倉的停損仍固定使用其進場時綁定的支撐區。

## 4. UT Bot 訊號模組

在每根**已完成**的三分 K 上維護 UT Bot 狀態：

```text
sensitivity a  = 2.0
atr_period     = 10
src            = 該三分 K close
nLoss          = a × ATR(atr_period) on 3m

以 prev_stop = 上一根 3m 的 xATRTrailingStop，prev_src = 上一根 3m close：

if src > prev_stop and prev_src > prev_stop:
    stop = max(prev_stop, src - nLoss)
elif src < prev_stop and prev_src < prev_stop:
    stop = min(prev_stop, src + nLoss)
elif src > prev_stop:
    stop = src - nLoss
else:
    stop = src + nLoss

ut_buy_signal  = (prev_src < prev_stop) and (src > prev_stop)
ut_sell_signal = (prev_src > prev_stop) and (src < prev_stop)
```

- 只使用已完成的 3m K close。
- 訊號時間標記在「產生 BUY 的那根三分 K 收盤時間」。
- ATR(10) 資料尚未累積足夠時不出訊號。
- UT Bot state 從資料最早段開始 warm-up，不能在測試起點才初始化。

## 5. 首次多單進場

### 5.1 進場條件

```text
無持倉 且 非 reentry_armed
且 存在有效的最新支撐區 zone
且 當根已完成 3m K 出現 ut_buy_signal
且 該 3m K close ∈ [zone.support_bottom, zone.support_top]
```

**取消**：SMA(9) 濾網、`previous_close > support_top` 進區條件、任何一分 K 條件。

### 5.2 成交時間

```text
signal_time  = BUY 3m K 的收盤時間
entry_time   = 下一根三分 K 開盤時間
entry_price  = 下一根三分 K open + 多單滑價
```

若 BUY 3m K 是同一 session 的最後一根，訊號取消，不保留到下一 session。

### 5.3 支撐區向上脫離後的補進場

若支撐區自確認以來**從未觸發過任何 initial_entry**（包含 in-zone 與本節的補進場），一旦價格向上脫離區間，下一次 UT Bot BUY 仍視為首次進場：

```text
zone_had_initial_entry   = False   # 該支撐區從未成交過首次進場
zone_price_touched       = False   # 支撐區是否曾被價格觸及
zone_upside_exit_seen    = False   # 是否已出現向上脫離

每根已完成 3m K（zone 有效期間，尚未有 initial_entry）:
  若 low <= support_top → zone_price_touched = True
  若 zone_price_touched 且 close > support_top → zone_upside_exit_seen = True
```

- **必須先真的觸及支撐區**（3m low 達到或穿入 `support_top`）才可能標記「向上脫離」。
- 若支撐區確認時價格早已在區上，且從未回落觸及區間，本規則永遠不會啟用。

進場條件（entry_type = `initial_entry_after_upside_exit`）：

```text
無持倉 且 非 reentry_armed
且 zone_had_initial_entry == False
且 zone_upside_exit_seen == True
且 該 3m K 出現 ut_buy_signal
```

- close 位置不限制在區內，可以在區外任意位置成立。
- 停損仍使用該支撐區的 `support_bottom`（原下蓋），因此 close 越高、`initial_risk` 越大。
- 一旦以此規則成交（或任何 initial_entry 成交），`zone_had_initial_entry = True`，本規則在該支撐區之後不再啟用。
- 若新支撐區覆蓋，`zone_had_initial_entry` 與 `zone_upside_exit_seen` 都在切區時重設為 False。
- 出場、trailing、再進場邏輯不變；停損後的 `reentry_armed` 一樣要求跌破原下蓋 + close 回原區。

## 6. 初始結構停損

```text
risk_atr     = 進場前最新完成的一小時 ATR(20)
initial_stop = entry_support_bottom − 0.5 × risk_atr
```

- `entry_support_bottom` 是該筆進場所使用的支撐區下緣。
- 3m K open 已低於 stop → 按 open 跳空停損。
- 否則 3m K low 觸及 stop → 按 stop 出場。
- 同一 3m K 內同時觸多事件，`initial_stop / atr_trailing_stop` 優先。
- 停損固定，不因後續 ATR 或下蓋改變。

## 7. 停損後再進場

### 7.1 啟動條件

只有 `initial_stop` 出場才啟動 `reentry_armed`；`atr_trailing_stop`、`adjust_hourly_supertrend_bearish_flip`、`data_end` 均不啟動。停損當根不重複進場，最早由停損後**下一根完成的三分 K** 判斷。

### 7.2 跌破觀察窗（3m 版）

```text
- reentry_timeout_minutes = 15
- 跌破啟動：完成的 3m K low < current_support_bottom
- 期間持續更新 downside_breakout_valley = min(prev_valley, 3m_low)
- 期限：downside_breakout_start_time + 15 minutes
```

### 7.3 再進場條件

```text
reentry_armed == true
且 downside_breakout_armed == true
且 current_3m_start_time <= downside_breakout_start_time + 15 minutes
且 該 3m K 出現 ut_buy_signal
且 該 3m K close ∈ [pre_adjustment_support_bottom, zone.support_top]
```

- 條件成立時只先建立待成交訊號；下蓋維持原值。
- 於下一根三分 K open 成交後才依 8 節將下蓋朝跌破最低價移動 50%。
- 下蓋更新後才鎖定該筆再進場停損：

```text
reentry_stop = updated_support_bottom
               − 0.5 × 進場前最新完成一小時 ATR(20)
```

- 再進場的 `initial_risk` 依更新後下蓋重新計算。
- 若窗內未觸發 UT Bot BUY 或未同時 close 回原區，再進場資格逾時失效，下蓋維持不變。
- **再進場不受一小時 SMA 方向限制**，UT Bot 本身即為方向濾網。
- 同一支撐區再進場次數預設無上限；每次都必須先發生新的 `initial_stop`，並在該次跌破後 15 分鐘內產生 UT Bot BUY 且 close 回原區。

## 8. 動態下蓋（沿用原策略 4.5）

支撐區初次建立時完全沿用 Pine。價格跌破下蓋只啟動 15 分鐘觀察窗，不立即下調下蓋。二次多單於下一根三分 K open 成交後才計算：

```text
breakout_distance   = current_support_bottom - downside_breakout_valley
new_support_bottom  = current_support_bottom - 0.5 × breakout_distance
current_support_bottom := min(old_bottom, new_bottom)
zone_version += 1
downside_breakout_armed = false
downside_breakout_valley = na
```

- 下蓋只能下移，`support_top` 不變。
- 首次多單的 `initial_stop` 固定，不因下蓋降低而放寬。
- 若跌破期間出現新的 Pine 支撐區，切換至新支撐區並清除舊區跌破追蹤狀態。

## 9. Adjust Supertrend 與 ATR 追蹤停損

Adjust Supertrend 與其他腳本完全一致（ATR 正規化價格速度、multiplier 3.0 → 0.8、speed 0.25–0.8、EMA span 2、lookback 2）。多頭確認與 trailing 條件如下：

- 進場前最新完成的一小時 Adjust Supertrend 已為多頭 → 立即視為多頭確認；否則等待後續完成的一小時 Supertrend 翻多。
- 1R 判定：`highest_3m_high_since_entry - entry_price >= initial_risk`。
- ATR trailing 啟用條件（同時滿足）：Adjust Supertrend 多頭確認 + 曾達 1R。
- Trailing 公式：

```text
candidate_trailing_stop = highest_3m_high_since_entry
                          - 1.5 × latest_completed_hourly_ATR(20)

trailing_stop = max(prev_trailing_stop, candidate_trailing_stop)
active_stop   = max(initial_stop, trailing_stop)
```

- 1R 首次達成的當根 3m K 內，`trailing_stop` 最早從下一根 3m 生效。
- Trailing 只能向上收緊，不能因 ATR 增加放寬。
- `atr_trailing_stop` 屬正常獲利管理出場，不啟動再進場。

## 10. Adjust Supertrend 多翻空出場

- 已獲得多頭確認的持倉，若後續完成的一小時 Adjust Supertrend 多翻空，在下一根三分 K open 平多。
- 屬正常趨勢出場，不啟動再進場。之後若要重新進場，必須重新符合 5.1 的首次進場條件。

## 11. 事件優先順序

同一根三分 K 內：

```text
1. initial_stop / atr_trailing_stop
2. adjust_hourly_supertrend_bearish_flip
3. data_end
4. 新進場訊號
```

- 已持倉時忽略新進場訊號，不加碼。
- 停損 K 不允許同根再進場，最早由下一根完成 3m K 重新判斷。
- 資料結束仍有持倉時以最後一根 3m close 結算，標記 `data_end`。

## 12. 無前視偏誤要求

- 一小時 pivot 必須等右側 20 根完成後才建立支撐區。
- 一小時 SMA/ATR/Supertrend 只讀已完成一小時 K。
- 三分 K 必須完成後才可讀 close 與 UT Bot 狀態；交易在下一根三分 K open 執行。
- UT Bot `xATRTrailingStop` 只用已完成 3m K 遞推，不假設未完成 K 的 close。
- 追蹤最高價只用進場後已發生的 3m high，不用未來 K 的 high。

## 13. 預設參數摘要

| 類別 | 參數 | 預設值 |
| --- | --- | ---: |
| 支撐區 | Pivot left / right | 20 / 20 |
| 支撐區 | Delta-volume length | 2 |
| 支撐區 | Box ATR length | 200 |
| 支撐區 | Box width | 1.0 ATR |
| 動態下蓋 | Breakout trigger | Completed 3m low below current bottom |
| 動態下蓋 | Return trigger | UT Bot BUY + 3m close 回原區 |
| 動態下蓋 | Bottom-adjust ratio | 0.5 of breakout distance |
| 動態下蓋 | Direction | Down only |
| 訊號 | Timeframe | 3 minutes |
| UT Bot | Key value (a) | 2.0 |
| UT Bot | ATR period | 10 |
| UT Bot | Source | 3m close (非 Heikin-Ashi) |
| 進場 | Fill | Next 3m open |
| 首次進場 | Trigger | UT Bot BUY 且 close ∈ 支撐區 |
| 首次進場（補） | Trigger | 支撐區從未進場 + 已向上脫離 + UT Bot BUY |
| 首次進場 | SMA / Supertrend filter | 不套用 |
| 再進場 | 觀察窗 | 15 minutes |
| 再進場 | Trigger | UT Bot BUY + close ∈ 原區 |
| 再進場 | Same-zone retry cap | Unlimited |
| 初始停損 | Risk ATR length | 20 (hourly) |
| 初始停損 | Buffer | 0.5 × hourly ATR(20) below bottom |
| 追蹤停損 | Activation | 多頭確認 + 曾達 1R |
| 追蹤停損 | ATR multiplier | 3.0 × hourly ATR(20) |
| Adjust Supertrend | ATR length | 10 (hourly) |
| Adjust Supertrend | Base / minimum multiplier | 4.5 / 1.5 |
| Adjust Supertrend | Speed lookback | 2 |
| Adjust Supertrend | Speed smoothing | 2 |
| Adjust Supertrend | Low / high speed threshold | 0.25 / 0.8 |
| 部位 | Max simultaneous | 1 long |

## 14. 回測輸出要求

至少輸出：

- 支撐區 ID、pivot 時間、確認時間、上下緣。
- 每次跌破的開始時間、跌破最低價、回區時間、調整前後下蓋、`zone_version`。
- 每根 3m K 的 `ut_atr_10`、`ut_trailing_stop`、`ut_direction`；BUY / SELL 訊號時間點。
- `initial_entry` / `reentry_after_stop` 分類。
- 進場時間、進場價、進場前最新 ATR。
- 初始停損、trailing stop 每次更新值。
- 每筆交易的 `initial_risk`、首次達 1R 時間與價格。
- Adjust Supertrend 多頭確認時間與多翻空時間。
- 出場時間、價格、原因。
- Gross / net 損益、MFE / MAE、持倉時間。
- 每個支撐區的進場次數、停損次數、再進場次數。
- 交易數、勝率、profit factor、累積損益、最大回撤。

正式評估必須加入手續費、交易稅、買賣價差與滑價，並分開呈現 gross 與 net。此文件為策略規格，不代表已完成回測或策略具正期望值。
