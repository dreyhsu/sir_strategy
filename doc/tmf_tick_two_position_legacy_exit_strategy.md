# TMF Tick 兩口空單策略規格

> 狀態：本文件描述下一版策略規格。結構停損尚未加入 Python 回測，因此不可將現有回測績效視為本規格的結果。

## 1. 策略目的與基本設定

這套策略以 60 分 K 的支撐／壓力箱為大方向，再用每盤重新累積的 2,000 口量 K 提早確認壓力反轉，避免等到 60 分紅菱形收定後才放空。

- 商品：TMF；每點 NT$10。
- 起始權益：NT$400,000；最多同時持有兩口空單。
- 日盤與夜盤分開建立 2,000 口量 K；盤末不足 2,000 口的殘量丟棄。
- 訊號完成後，以同一 session 的下一筆來源排序 tick 進場。
- 空單進場價扣 2 點、出場價加 2 點，代表每邊 2 點不利滑價。
- 不模擬手續費、交易稅、追繳或強制平倉。

## 2. 原版 Pine Script 指標

原始碼為 [`pine_script.txt`](pine_script.txt)，指標名稱是 `Support and Resistance (High Volume Boxes) [ChartPrime]`。以下先描述原版 Pine；第 3 節的 tick 加速進場是另外增加的交易邏輯。

### 2.1 Delta Volume

每根 K 棒的成交量依 K 棒方向加上正負號：

```text
close > open  → Vol = +volume
close < open  → Vol = -volume
close = open  → 沿用上一根 K 棒的成交量方向
```

接著使用最近 `vol_len = 2` 根的極值：

```text
vol_hi = highest(Vol / 2.5, 2)
vol_lo = lowest (Vol / 2.5, 2)
```

白話解釋：上漲 K 的量視為買方量，下跌 K 的量視為賣方量；十字 K 不自行改變方向。這不是逐筆判斷主動買賣，而是用整根 K 棒漲跌近似成交量方向。

### 2.2 Pivot 與箱體

原版以 `close` 尋找左右各 20 根的 pivot：

```text
pivotHigh = pivothigh(close, 20, 20)
pivotLow  = pivotlow (close, 20, 20)
width     = ATR(200) × box_width
```

- Pivot 必須等右側 20 根 K 棒完成後才確認；不能在 pivot 當下預先知道。
- 支撐箱在 `pivotLow` 下方：

  ```text
  support_top    = pivotLow
  support_bottom = pivotLow - width
  ```

- 壓力箱在 `pivotHigh` 上方：

  ```text
  resistance_bottom = pivotHigh
  resistance_top    = pivotHigh + width
  ```

- 只有 `pivotLow` 同時配合正向高量才建立支撐；`pivotHigh` 配合負向高量才建立壓力。
- 舊箱體仍留在圖上，但突破、守住與菱形公式使用變數中最新的支撐／壓力價位。

白話解釋：壓力不是一條精確價格，而是從 pivot close 往上延伸一個 ATR 寬度的區域；支撐則從 pivot close 往下延伸。

> 原版 Pine 的箱寬是 `ATR(200)`。目前 Python legacy 回測依先前設定使用 `ATR(20)` 建箱，兩者不可混稱；日後若要逐點對照 TradingView，必須把 Python 箱寬改回 ATR(200)。

### 2.3 Break 公式

原始公式如下：

```text
Break Res = crossover(low, resistance_top)
Break Sup = crossunder(high, support_bottom)
```

簡單解釋：

- `Break Res`：K 棒最低價由箱頂下方穿到箱頂上方，代表整根 K 棒已站上壓力箱。
- `Break Sup`：K 棒最高價由箱底上方穿到箱底下方，代表整根 K 棒已跌到支撐箱下方。
- 因為使用 `crossover/crossunder`，條件同時比較前一根與目前 K 棒，不是價格單純碰到邊界就算突破。
- 第一次突破顯示 `Break Res` 或 `Break Sup` 標籤，並把箱體改為虛線及角色轉換顏色。

### 2.4 四種菱形

| 圖形 | Pine 條件 | 原始名稱 | 白話意思 |
| --- | --- | --- | --- |
| 紅菱形 | `crossunder(high, resistance_bottom)` | Resistance Holds | 測試壓力後，整根 K 棒重新回到壓力箱下方，壓力守住。 |
| 綠菱形 | `crossover(low, support_top)` | Support Holds | 測試支撐後，整根 K 棒重新回到支撐箱上方，支撐守住。 |
| 綠菱形 | `Break Res and res_is_sup[1]` | Resistance as Support Holds | 壓力已突破並轉為支撐後，再次站回原壓力箱上方。 |
| 紅菱形 | `Break Sup and sup_is_res[1]` | Support as Resistance Holds | 支撐已跌破並轉為壓力後，再次跌回原支撐箱下方。 |

角色狀態：

```text
Break Res      → res_is_sup = true
Resistance Holds → res_is_sup = false

Break Sup      → sup_is_res = true
Support Holds  → sup_is_res = false
```

圖上的菱形使用 `offset = -1`，所以視覺上被畫到前一根 K 棒；實際條件是在目前 K 棒收定時才確認。回測必須使用確認時間，不能使用向前移動後的圖示時間。

## 3. Tick 加速空單進場

原版 60 分紅菱形要等整根 K 棒收定。本策略只用已完成資料，透過 2,000 口量 K 提早判斷同一個壓力測試。

共同條件：

```text
量 K 接觸已啟動的壓力箱
close < open
close_position = (close - low) / (high - low) ≤ 35%
```

分層狀態依序為：

1. `Early`：完整 60 分 K 已確認碰到有效壓力後，第一根符合共同條件的量 K。
2. `Balanced`：後續完整 60 分 K 形成更高的壓力測試高點後，第一根 lower-high 且符合共同條件的量 K。
3. `Conservative`：Balanced 之後，第一根符合共同條件且收盤跌破壓力箱下緣的量 K。

`Conservative` 是向下跌破壓力箱下緣的確認，不是 Supertrend 翻空，也不是原 Pine 的 `Break Res`。最多兩口時，Early 與 Balanced 若均已成交，Conservative 仍記錄為有效訊號，但因滿倉而不再加碼。

Sep 9 範例：

| 層級 | 訊號時間 | 訊號重點 | 部位處理 |
| --- | --- | --- | --- |
| Early | 09:51:12 | 碰壓後第一根合格反轉量 K | 建立第 1 口空單 |
| Balanced | 10:49:45 | 47,590 高點後的 lower-high 反轉 | 建立第 2 口空單 |
| Conservative | 10:55:28 | 收盤回到 47,500 壓力下緣以下 | 已滿兩口，忽略加碼 |

## 4. 壓力失效與結構停損

每口成交時，以該口對應的壓力箱與進場前最新完成的 60 分 `ATR(20)` 固定停損：

```text
lot_stop = entry_resistance_top
           + 0.10 × latest_completed_hourly_ATR(20)

group_stop = min(all_open_lot_stops)
```

- `lot_stop` 進場後固定，不因後續 ATR 或新壓力箱改變。
- 兩口共同管理；任何一口的結構停損失效，就平掉整組，因此採用距離價格最近的 `group_stop`。
- 第一筆價格 `>= group_stop` 的 tick 代表壓力壓不住，兩口在該 tick 一起停損。
- 空單停損成交價為該 tick 實際價格加 2 點；若跳空越過停損，不假設能成交在原停損價。
- 停損 tick 不接受新進場；必須等後續新的完整 60 分碰壓確認，才可啟動下一組 Early 流程。

這個 `0.10 × ATR(20)` 是交易策略的停損緩衝，不是原版 Pine 的箱體寬度 `ATR(200) × box_width`。

## 5. 其他出場與優先順序

未觸發結構停損時，兩口沿用共同趨勢出場：

1. 持倉後，已完成的 adaptive hourly Supertrend 曾呈空頭。
2. 後續完成的 hourly Supertrend 從空頭翻為多頭。
3. 在翻多後第一筆可用 tick 同時平掉全部空單，出場價加 2 點不利滑價。

同一 tick 有多個事件時：

```text
1. resistance_structure_stop
2. adaptive_hourly_supertrend_bullish_flip
3. data_end
```

停損優先於趨勢出場與任何新進場訊號。資料結束仍有部位時，以最後一筆 tick 加 2 點出場滑價結算。

## 6. 實作狀態

- Early／Balanced／Conservative 與兩口共同 Supertrend 出場已有舊版回測結果。
- 本文件新增的 `resistance_structure_stop` 尚未加入回測程式、交易 CSV、圖表或績效報告。
- 現有報告中的 NT$423,090 最終權益屬於「沒有結構停損」版本，不能用來評估本文件的新停損規格。
- 實作停損後必須重新執行單元測試及 2026-08-05～2026-09-15 全資料回測，再更新績效數字。
