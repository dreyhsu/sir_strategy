# TMF 0923：一小時 Pine 壓力區＋一分 K 收盤進場純空策略

## 1. 策略定位

本策略只做空，以一小時 K 建立壓力區，再用一分 K 加速進場。壓力區的初始建立方式與 [`pine_script.txt`](pine_script.txt) 完全相同；交易邏輯與突破回落後的動態上蓋調整則是本策略另外加入，不使用原 Pine 紅菱形作為必要進場條件。

- 商品：TMF。
- 交易方向：只做空。
- 壓力結構週期：一小時 K。
- 進場判斷週期：一分 K。
- 首次進場趨勢條件：已完成的一小時 SMA(9) 必須向上。
- 同一時間最多持有一口空單。
- 訊號只能使用已完成的 K 棒。
- 本文中的 `Adjust Supertrend` 與專案其他 Adaptive Supertrend 腳本相同，依一小時 ATR 正規化價格速度動態調整有效 ATR 距離，不使用價格加速度。

## 2. 一小時 K 的建立方式

TMF 一小時 K 依交易時段錨定：

- 日盤從 `08:45` 開始切分：`08:45–09:44:59`、`09:45–10:44:59`，依此類推。
- 夜盤從 `15:00` 開始切分：`15:00–15:59:59`、`16:00–16:59:59`，依此類推。
- 不把休市前後的成交混在同一根 K 棒。
- 一小時 K 尚未完成前，不得用其 high、low、close、volume、ATR 或 Supertrend 做決策。

## 3. Pine 原版方向成交量

每根完成的一小時 K 依開收盤方向將整根成交量加上正負號：

```text
close > open  → Vol = +volume
close < open  → Vol = -volume
close = open  → 沿用上一根 K 棒的方向
```

這不是逐筆成交的 bid/ask delta，而是依一小時 K 漲跌方向分類的 signed volume。

成交量門檻完全沿用 Pine 原稿：

```text
vol_hi = highest(Vol / 2.5, 2)
vol_lo = lowest (Vol / 2.5, 2)
```

本策略只使用壓力區，因此實際建壓條件使用：

```text
Vol < vol_lo
```

門檻視窗包含目前這根一小時 K。

## 4. 一小時壓力區建立規則

### 4.1 Pivot High

壓力 pivot 使用完成的一小時 K 收盤價：

```text
pivotHigh = pivothigh(close, 20, 20)
```

候選收盤價必須是左右各 20 根一小時 K 的局部高點。由於必須等待右側 20 根 K 棒完成，壓力區只能在 pivot 發生 20 小時 K 之後確認。

### 4.2 建立條件

完成的一小時 K 同時符合下列條件才建立壓力區：

```text
pivotHigh 已確認
且
目前確認 K 的 Vol < vol_lo
```

壓力價格來自 20 根之前的 pivot close，但成交量條件和 box 顯示的成交量來自「目前確認 K」，不是 pivot K 本身。

### 4.3 壓力區寬度

完全沿用原 Pine：

```text
box_atr   = ATR(200)，使用 Pine/Wilder RMA
box_width = box_atr × 1.0

resistance_bottom = pivotHigh
resistance_top    = pivotHigh + box_width
```

因此，壓力區從 pivot 收盤價向上延伸一個一小時 `ATR(200)`。

> `ATR(200)` 是建立壓力箱的 ATR。後面的交易停損另用 `ATR(20)`；兩者用途不同，不得混為同一參數。

### 4.4 壓力區生效時間

- 壓力區從右側 20 根 K 棒完成、pivot 正式確認後才可用於交易。
- 圖表可以把 box 左端畫回 pivot K，但回測與即時策略不得從過去的 pivot 時間開始使用它。
- 一分 K 只能讀取在該一分 K 收盤之前已確認的壓力區。
- 最新壓力區建立後，進場判斷改用最新壓力區；既有持倉的停損仍固定使用其進場時綁定的壓力區。

### 4.5 二次進場成交後：動態提高壓力上蓋

壓力區初次建立時完全沿用 Pine。價格突破上蓋本身只會啟動最長 10 分鐘的觀察窗，**不會立即調高上蓋**。只有符合第 7 節條件、二次空單確實在下一根一分 K open 成交後，才把上蓋向該次突破最高價方向上移。

每個壓力區另外保存：

```text
current_resistance_top
upside_breakout_armed
upside_breakout_peak
upside_breakout_start_time
reentry_timeout_minutes = 10
top_adjust_ratio = 0.5
```

#### 突破啟動

持有空單或已因該筆空單的 `initial_stop` 等待再進場時，完成的一分 K high 高於目前壓力上蓋即啟動觀察窗：

```text
current_1m_high > current_resistance_top
→ upside_breakout_armed = true
→ upside_breakout_start_time = current_1m_start_time
→ reentry_deadline = upside_breakout_start_time + 10 minutes
```

突破期間持續記錄已發生的最高價：

```text
upside_breakout_peak = max(
    previous_upside_breakout_peak,
    current_1m_high
)
```

只使用已完成的一分 K high，不使用尚未完成 K 棒的未來高點。

#### 10 分鐘內回到原壓力區

突破啟動後，以突破前的 `current_resistance_top` 作為回區判斷基準。只有 `initial_stop` 已成交，而且後續完成的一分 K close 在 10 分鐘期限內回到原區域，才產生二次進場訊號：

```text
upside_breakout_armed == true
and reentry_armed == true
and current_1m_start_time <= reentry_deadline
and resistance_bottom <= current_1m_close
and current_1m_close <= current_resistance_top
```

突破當根若同時收回區內，但當時首次空單尚未停損，不能預先保留為二次進場訊號。停損當根也不重複進場；必須由停損後的下一根完成一分 K 重新確認。

若超過 10 分鐘仍未收回原壓力區，該次再進場資格失效，上蓋維持不變。期限以第一次突破該上蓋的一分 K `minute_start` 起算，後續再創高只更新 `upside_breakout_peak`，不重設 10 分鐘倒數。

#### 二次進場成交後才調高

符合限時回區條件時，先記錄二次進場訊號，但訊號 K 收盤時仍保留舊上蓋。下一根一分 K open 成交二次空單後，才計算並套用：

```text
breakout_distance =
    upside_breakout_peak - current_resistance_top

new_resistance_top =
    current_resistance_top
    + top_adjust_ratio × breakout_distance
```

預設 `top_adjust_ratio = 0.5`，代表上蓋向本次突破最高價移動一半距離。例如：

```text
原上蓋          = 48,800
本次突破最高價  = 49,000
突破距離        = 200
調整比例        = 0.5
新上蓋          = 48,900
```

二次進場成交後更新：

```text
current_resistance_top = max(
    old_resistance_top,
    new_resistance_top
)

upside_breakout_armed = false
upside_breakout_peak = na
```

上蓋只能上移、不能下移；`resistance_bottom` 維持原 pivot close 不變。若下一根一分 K 無法成交、跨 session 而取消訊號，或風險條件無效，上蓋也不得調整。

#### 對持倉與後續交易的影響

- 動態上蓋是同一壓力區的新版上緣，壓力區 ID 不變，但在二次進場成交時 `zone_version` 加 1。
- 首次空單的 `initial_stop` 固定，不因後續上蓋提高而回頭放寬。
- 二次進場以舊上蓋完成回區判斷；成交後立即套用新上蓋，並以新上蓋計算該筆初始停損。
- 上蓋提高會直接放寬二次進場及之後交易的結構停損。若 ATR 不變，上蓋提高多少點，停損價就同步提高多少點：

  ```text
  top_shift = updated_resistance_top - old_resistance_top

  old_future_stop = old_resistance_top + 0.5 × ATR(20)
  new_future_stop = updated_resistance_top + 0.5 × ATR(20)

  new_future_stop - old_future_stop = top_shift
  ```

- 若進場價相近，停損距離與每口風險也會增加。不得沿用調整前的 stop 或 `1R`。
- 該筆二次進場的停損使用成交後才生效的新上蓋：

  ```text
  reentry_stop = updated_resistance_top
                 + 0.5 × latest_completed_hourly_ATR(20)
  ```

- 若突破期間出現新的 Pine 壓力區，切換至新壓力區並清除舊區的突破追蹤狀態。
- 只有二次進場成交才更新上蓋；單純突破、回區或逾時都不改動上蓋。

## 5. 首次空單進場

### 5.1 一分 K 收盤進入壓力區

空手且尚未進入「停損後等待回區」狀態時，價格必須由壓力區下方向上進入最新有效壓力區。使用完成的一分 K close 定義：

```text
previous_1m_close < resistance_bottom
and resistance_bottom <= current_1m_close <= resistance_top
```

因此，價格原本已在壓力區內、由壓力區上方往下進入，或壓力區剛確認時價格已經位於區內，都不構成首次進場。首次進場只捕捉價格由下往上測試壓力區。

### 5.2 一小時 SMA(9) 必須向上

首次進場必須同時確認一小時 SMA(9) 方向向上：

```text
hourly_sma9 = SMA(hourly_close, 9)

latest_completed_hourly_sma9
    > previous_completed_hourly_sma9
```

也就是最新完成的一小時 SMA(9) 高於前一根已完成的一小時 SMA(9)。本策略不以幾何角度或螢幕上的視覺斜率計算，而以相鄰兩個 SMA 數值上升作為「角度向上」的精確定義。

首次空單訊號完整條件為：

```text
目前沒有持倉
and 目前不是停損後的 reentry_armed 狀態
and 最新完成 hourly SMA(9) > 前一個完成 hourly SMA(9)
and previous_1m_close < resistance_bottom
and resistance_bottom <= current_1m_close <= resistance_top
```

- 只能使用一分 K 訊號時間以前已完成的一小時 K。
- 正在形成中的一小時 close 與 SMA(9) 不得使用。
- SMA(9) 尚未累積足夠資料時，不產生首次進場訊號。
- SMA(9) 相等或下降時，即使一分 K close 位於壓力區內，也不首次放空。
- 這是一個刻意在一小時短期均線仍向上時，於壓力區嘗試逆勢放空的條件。

不要求：

- 一分 K 必須收黑；
- 一分 K 必須形成反轉型態；
- 一分 K 成交量必須放大；
- 一小時紅菱形成立；
- 一小時 Adjust Supertrend 已經翻空。

### 5.3 成交時間

訊號一分 K 完成後，於下一根一分 K 的 open 放空：

```text
signal_time = 一分 K 收盤時間
entry_time  = 下一根一分 K 開盤時間
entry_price = 下一根一分 K open，加上回測設定的空單進場滑價
```

不得使用訊號一分 K 的 close 假設成交，也不得在一分 K 尚未完成時提前進場。

若訊號出現在 session 最後一根一分 K，且同一 session 沒有下一根可成交 K 棒，訊號取消，不保留到下一個 session。

## 6. 初始結構停損

每次空單成交時，固定初始停損：

```text
risk_atr = 進場前最新完成的一小時 ATR(20)

initial_stop = entry_resistance_top
               + 0.5 × risk_atr
```

- `entry_resistance_top` 是該筆進場所使用的壓力區上緣。
- `risk_atr` 只能使用進場前已完成的一小時 K。
- 初始停損成交後固定，不因後續 ATR 擴大、縮小或新壓力區產生而改變。
- 一分 K 回測若 open 已高於停損，按該 open 模擬跳空停損；否則一分 K high 觸及停損時按停損價模擬出場。
- 若一分 K OHLC 同時碰到停損和其他出場價，因無法知道分鐘內順序，停損優先。

這裡的 `0.5 × ATR(20)` 是壓力區上方的交易風險緩衝，不是壓力箱的 `ATR(200) × 1.0` 寬度。

## 7. 停損後再進場

### 7.1 再進場啟動狀態

空單只有因 `initial_stop` 出場後，該筆壓力區才進入「等待回到區內」狀態。

下列出場不啟動 `reentry_armed`：

- `atr_trailing_stop`；
- `adjust_hourly_supertrend_bullish_flip`；
- `data_end`。

停損當根不立即反手，也不在同一根一分 K 重新放空。

### 7.2 從壓力區上方回到區內

由於 initial stop 本身位於 `resistance_top + 0.5 × ATR(20)`，initial stop 事件已證明價格到達壓力區上方。只有 initial stop 成交後才設定：

```text
reentry_armed = true
```

從停損後下一根完成的一分 K 開始，必須在「第一次突破上蓋後 10 分鐘內」收回原壓力區，才觸發再進場：

```text
reentry_armed == true
and upside_breakout_armed == true
and current_1m_start_time <= upside_breakout_start_time + 10 minutes
and resistance_bottom <= current_1m_close <= pre_adjustment_resistance_top
```

條件成立時，只先建立待成交訊號；上蓋仍保持原值。於下一根一分 K open 二次放空成交後，才依第 4.5 節提高壓力上蓋，並清除 `reentry_armed`。

若收回區內的 close 晚於 10 分鐘期限，該次二次進場資格取消：不進場、不提高上蓋。後續一分 K 再創新高不會延長原倒數。

停損後的再進場**不受一小時 SMA(9) 方向限制**。無論最新完成的 SMA(9) 正在上升、持平或下降，只要 `reentry_armed` 已啟動，而且在突破後 10 分鐘內收回原壓力區，就可以在下一根一分 K open 再次放空。

停損當根即使 close 已回到壓力區內，也不在同一根重新進場；最早從停損後下一根完成的一分 K 判斷。

### 7.3 再進場停損

每次再進場都視為一筆新交易。成交順序為：先以一分 K open 建立空單，再把上蓋調高，接著用更新後上蓋鎖定初始停損：

```text
reentry_stop = 同一壓力區更新後的 resistance_top
               + 0.5 × 再進場前最新完成的一小時 ATR(20)
```

再進場的新 `initial_risk` 必須依更新後上蓋重新計算：

```text
reentry_initial_risk = reentry_stop - reentry_price
```

後續的 `1R` 啟動門檻也使用這個新風險值，不能沿用上一筆交易的 `1R`。

- 同時仍只允許一口空單。
- 預設不限制同一壓力區的再進場次數；每次都必須先發生 `initial_stop`，並在該次突破上蓋後 10 分鐘內由後續一分 K close 收回原區內。
- 回測報告必須分開記錄 `initial_entry` 與 `reentry_after_stop`。
- 若等待期間出現新的壓力區，後續訊號改以最新壓力區判斷，原壓力區的等待狀態取消。

## 8. Adjust Supertrend：價格速度動態 ATR

本策略的 Adjust Supertrend 與專案其他 Adaptive Supertrend 腳本一致，直接使用 ATR 正規化後的價格速度調整 ATR multiplier，不再計算價格加速度。價格移動越快，有效 ATR 距離越小，Supertrend 越貼近價格；價格移動越慢，有效 ATR 距離越寬，降低盤整時頻繁翻轉。

### 8.1 預設參數

| 參數 | 預設值 |
| --- | ---: |
| Supertrend ATR length | 10 |
| Base multiplier | 3.0 |
| Minimum multiplier | 0.8 |
| Speed lookback | 2 |
| Speed smoothing span | 2 |
| Low-speed threshold | 0.25 |
| High-speed threshold | 0.8 |

`0.25–0.8` 沿用其他 Adaptive Supertrend 腳本的速度門檻。

### 8.2 ATR 正規化價格速度

只使用已完成的一小時 K：

```text
raw_atr_t = ATR(10)_t

raw_price_speed_t =
    abs(close_t - close_(t-2))
    / (raw_atr_t × 2)

price_speed_t =
    EMA(raw_price_speed, span=2)
```

- 使用絕對價格變化，因此只衡量移動快慢，不區分上漲或下跌方向。
- 除以 ATR 與回看根數，使不同波動環境的速度可比較。
- 使用 EMA 平滑後的 `price_speed` 調整 multiplier。

### 8.3 動態調整有效 ATR 距離

先將平滑後的價格速度正規化至 `0–1`：

```text
speed_score = clip(
    (price_speed - 0.25) / (0.8 - 0.25),
    0,
    1
)
```

再動態調整 ATR multiplier：

```text
adjust_multiplier =
    3.0 - (3.0 - 0.8) × speed_score

adjusted_atr_distance = raw_atr_t × adjust_multiplier
```

因此：

```text
價格速度 <= 0.25 → adjusted ATR distance = ATR(10) × 3.0
價格速度 >= 0.8  → adjusted ATR distance = ATR(10) × 0.8
中間區間       → multiplier 從 3.0 線性縮小到 0.8
```

嚴格來說，Wilder ATR(10) 本身仍依真實波幅計算；動態變化的是 Supertrend 使用的「有效 ATR 距離」`ATR × adjust_multiplier`。

### 8.4 Adjust Supertrend 線

```text
midpoint    = (high + low) / 2
basic_upper = midpoint + adjusted_atr_distance
basic_lower = midpoint - adjusted_atr_distance
```

後續 upper/lower band 延續與方向翻轉規則沿用標準 Supertrend。Adjust Supertrend、價格速度及 multiplier 都只能在一小時 K 完成後更新。

## 9. Adjust Supertrend 與 ATR 追蹤停損

本策略不設定固定點數停利。獲利至少達到 `1R` 且 Adjust Supertrend 已確認空頭後，才啟用 ATR trailing stop；主要趨勢出場由 Adjust Supertrend 空翻多完成。

其中：

```text
initial_risk = initial_stop - entry_price
unrealized_profit = entry_price - current_price

1R reached ⇔ unrealized_profit >= initial_risk
```

每筆交易的 `initial_risk` 在進場時固定，後續不因 ATR 或 trailing stop 改變。

### 9.1 空頭確認

進場後：

- 如果進場前最新完成的一小時 Adjust Supertrend 已是空頭，立即視為空頭確認。
- 否則等待後續完成的一小時 Adjust Supertrend 轉為空頭。
- 空頭確認前，初始結構停損仍持續有效。

### 9.2 ATR 追蹤停損

ATR 追蹤停損必須同時符合：

```text
Adjust Supertrend 已確認空頭
and 進場後已實現過至少 1R 的未實現獲利
```

`1R` 以進場後已發生的一分 K low 判斷：

```text
entry_price - lowest_price_since_entry >= initial_risk
```

兩項條件都成立後，啟用：

```text
candidate_trailing_stop = lowest_price_since_entry
                          + 1.5 × latest_completed_hourly_ATR(20)

trailing_stop = min(previous_trailing_stop,
                    candidate_trailing_stop)

active_stop = min(initial_stop,
                  trailing_stop)
```

- `lowest_price_since_entry` 是進場後截至當時已發生的一分 K low 最低值。
- ATR 只使用當時最新完成的一小時 `ATR(20)`。
- 若某根一分 K 首次使獲利達到 `1R`，只能在該一分 K 完成後計算 trailing stop；新 trailing stop 從下一根一分 K 開始生效，不假設能在同一根 K 內先看到 low、再用較早的 high 出場。
- 追蹤停損只能向下收緊，不能因 ATR 增加而向上放寬。
- 一分 K open 跳過 active stop 時，以實際 open 出場；否則 high 觸及 active stop 時，以 stop 價出場。
- 一旦達到過 `1R`，即使價格之後反彈，`1R reached` 狀態仍保持為 true。
- `atr_trailing_stop` 屬於正常獲利管理出場，不啟動第 7 節的再進場流程。

### 9.3 Adjust Supertrend 空翻多出場

主要趨勢出場條件：

1. 該筆持倉已經獲得 Adjust Supertrend 空頭確認。
2. 後續完成的一小時 Adjust Supertrend 從空頭翻為多頭。
3. 翻多確認後，在下一根一分 K open 平空。

不得在造成翻轉的一小時 K 尚未完成前出場，也不能把 Supertrend 翻轉回填到前一根 K 棒。

Adjust Supertrend 空翻多屬正常趨勢出場，不視為停損，也不啟動同一壓力區的再進場狀態。之後若要再次進場，必須重新符合一般的首次進場規則，包括價格由下往上進入壓力區以及一小時 SMA(9) 向上。

## 10. 狀態流程

```text
等待 Pine 壓力區確認
        │
        ▼
空手／監控一分 K close
        │
        ├─ hourly SMA(9) 向上
        │  ＋價格由下往上進入壓力區
        │       └─ 下一根一分 K open 放空
        │
        ▼
	持有一口空單
	        │
	        ├─ 價格突破原上蓋
	        │       └─ 啟動 10 分鐘倒數並記錄突破最高價
	        │
	        ├─ initial stop
	        │       └─ 10 分鐘內 close 收回原壓力區
	        │               └─ 不看 SMA(9)，下一根一分 K open 二次進場
	        │                       └─ 成交後才把上蓋朝突破最高價上調 50%
        │
        ├─ Adjust Supertrend 空頭確認＋獲利曾達 1R
        │       └─ 啟用 1.5 ATR trailing stop
        │               └─ 出場後不啟動再進場
        │
        └─ Adjust Supertrend 空翻多
                └─ 下一根一分 K open 正常平倉，不啟動再進場
```

## 11. 出場與事件優先順序

同一根一分 K 或同一決策時間發生多個事件時：

```text
1. initial_stop / atr_trailing_stop
2. adjust_hourly_supertrend_bullish_flip
3. data_end
4. 新進場訊號
```

- 已持倉時忽略新的進場訊號，不加碼。
- 停損 K 不允許同根再進場，最早從下一根完成的一分 K 重新判斷。
- 資料結束仍有持倉時，以最後一根一分 K close 結算，並標記 `data_end`。

## 12. 無前視偏誤要求

- 一小時 pivot high 必須等右側 20 根一小時 K 完成後才建立壓力區。
- 壓力區的歷史回畫位置不能當成實際生效時間。
- 一分 K 必須完成後才能讀取 close；交易在下一根一分 K open 執行。
- 一分 K 只能讀取時間早於其決策時間的已完成一小時 SMA(9)、ATR、價格速度與 Adjust Supertrend。
- 不可用正在形成的一小時 K 高低價、ATR 或 Supertrend。
- 追蹤最低價只可使用進場後已完成或已發生的價格，不可使用後續一分 K 的未來 low。
- 原 Pine 菱形的 `offset=-1` 只屬繪圖位移，本策略完全不使用位移後時間做交易。

## 13. 預設參數摘要

| 類別 | 參數 | 預設值 |
| --- | --- | ---: |
| 壓力區 | Pivot left/right | 20 / 20 |
| 壓力區 | Delta-volume length | 2 |
| 壓力區 | Box ATR length | 200 |
| 壓力區 | Box width | 1.0 ATR |
| 動態上蓋 | Breakout trigger | Completed 1m high above current top |
| 動態上蓋 | Return trigger | Completed 1m close back inside pre-adjustment zone |
| 動態上蓋 | Top-adjust ratio | 0.5 of breakout distance |
| 動態上蓋 | Direction | Up only |
| 動態上蓋 | Future-stop effect | Stop rises point-for-point with adjusted top |
| 進場 | Signal timeframe | 1 minute |
| 首次進場 | SMA filter | Completed hourly SMA(9) rising |
| 首次進場 | Entry trigger | SMA(9) rising + 1m close enters resistance from below |
| 進場 | Fill | Next 1m open |
| 初始停損 | Risk ATR length | 20 |
| 初始停損 | Buffer | 0.5 ATR above resistance top |
| 追蹤停損 | Activation | Bearish Supertrend confirmed + profit reached 1R |
| 追蹤停損 | ATR multiplier | 1.5 |
| Adjust Supertrend | ATR length | 10 |
| Adjust Supertrend | Base / minimum multiplier | 3.0 / 0.8 |
| Adjust Supertrend | Speed lookback | 2 |
| Adjust Supertrend | Speed smoothing | 2 |
| Adjust Supertrend | Low / high speed threshold | 0.25 / 0.8 |
| 部位 | Maximum simultaneous position | 1 short |
| 再進場 | SMA(9) filter | Not applied |
| 再進場 | Armed by | Initial stop only |
| 再進場 | Same-zone retry limit | Unlimited by default |

## 14. 回測輸出要求

實作回測時至少輸出：

- 壓力區 ID、pivot 時間、確認時間、下緣與上緣。
- 每次向上突破的開始時間、突破最高價、回區時間、調整前後上蓋、調整距離與 `zone_version`。
- 訊號一分 K 時間與 close。
- 首次進場訊號當下最新兩個已完成的一小時 SMA(9) 數值及方向。
- `initial_entry` 或 `reentry_after_stop`。
- 進場時間、進場價與進場前最新 ATR。
- 初始停損、每次 ATR trailing stop 更新值。
- 每筆交易的 `initial_risk`、首次達到 1R 的時間與價格。
- 每根完成一小時 K 的 raw price speed、smoothed price speed、adjust multiplier 與 adjusted ATR distance。
- Adjust Supertrend 空頭確認時間與空翻多時間。
- 出場時間、出場價、出場原因。
- 毛損益、成本後淨損益、MFE、MAE、持倉時間。
- 每個壓力區的進場次數、停損次數與再進場次數。
- 交易數、勝率、profit factor、累積損益與最大回撤。

正式評估必須加入手續費、交易稅、買賣價差與滑價，並分開呈現 gross 與 net 結果。此文件是策略規格，不代表已完成回測或策略具有正期望值。
