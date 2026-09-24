# Pine Script 支撐與壓力指標詳解

本文說明 [`pine_script.txt`](./pine_script.txt) 的運作方式。這份程式是 ChartPrime 的 Pine Script v5 指標：

```text
Support and Resistance (High Volume Boxes) [ChartPrime]
```

它會在 TradingView 圖表上尋找帶有特定成交量方向的樞紐高低點，畫出支撐／壓力區塊，並標示價格何時突破或重新守住區域。

> 重要：程式使用 `indicator()`，不是 `strategy()`。它只負責計算與繪圖，不會自動下單、設定停損或產生 TradingView 策略回測績效。

## 一、整體流程

每根 K 棒更新時，指標依序執行：

1. 依 K 棒漲跌把整根成交量標成正值或負值。
2. 使用收盤價尋找已確認的樞紐低點與樞紐高點。
3. 樞紐成立且目前 K 棒的方向成交量通過過濾條件時，建立支撐或壓力區塊。
4. 用 200 期 ATR 決定區塊的垂直厚度。
5. 將目前最新的支撐與壓力區塊向右延伸。
6. 判斷價格是否完全穿越區塊，或重新回到區塊另一側。
7. 依狀態改變區塊顏色、線型，並繪製菱形或突破標籤。

簡化後的概念如下：

```text
K 棒資料
   │
   ├─ 判斷漲／跌 K → 方向成交量 Vol
   │
   ├─ close 的樞紐低點 + 正成交量條件 → 支撐區
   │
   └─ close 的樞紐高點 + 負成交量條件 → 壓力區
                                      │
                                      └─ 價格跨越區域邊界
                                           ├─ 突破
                                           └─ 守住／回到原側
```

## 二、指標宣告

```pine
indicator(
    "Support and Resistance (High Volume Boxes) [ChartPrime]",
    shorttitle = "SR Breaks and Retests [ChartPrime]",
    overlay = true,
    max_boxes_count = 50
)
```

- `overlay=true`：把結果直接疊加在價格圖上。
- `max_boxes_count=50`：圖表最多保留 50 個由此指標建立的 box。超過平台可保留的數量時，較舊物件會被清除。
- 腳本沒有 `alertcondition()`、`strategy.entry()` 或 `strategy.exit()`，所以沒有內建警報條件與交易執行。

## 三、使用者參數

| 參數 | 預設值 | 功能 | 實際影響 |
| --- | ---: | --- | --- |
| `lookbackPeriod` | 20 | 樞紐左右側的確認長度 | 數值越大，轉折越重要但確認越慢 |
| `vol_len` | 2 | 方向成交量門檻的回看長度 | 數值越大，會拿更多近期 K 棒計算門檻 |
| `box_withd` | 1.0 | 區塊厚度的 ATR 倍數 | `0` 會使區塊退化成單一價位；越大區域越厚 |

原始變數名 `box_withd` 少了字母 `i`，但不影響執行。

### `lookbackPeriod` 的確認延遲

程式呼叫：

```pine
ta.pivothigh(close, lookbackPeriod, lookbackPeriod)
ta.pivotlow(close, lookbackPeriod, lookbackPeriod)
```

以預設值 20 為例，一個候選低點必須同時符合：

- 左側 20 根 K 棒的比較條件；
- 右側接下來 20 根 K 棒的比較條件。

因此，樞紐發生後至少要再等 20 根 K 棒才會確認。指標確認後把區塊左端畫回 `bar_index - 20`，也就是樞紐實際所在的位置。歷史圖看起來像是區塊早已存在，但即時交易中，在右側 20 根 K 棒走完前無法知道該樞紐成立。

此外，樞紐計算使用的是 `close`，不是 `high` 或 `low`：

- 「樞紐高點」代表局部最高的收盤價；
- 「樞紐低點」代表局部最低的收盤價；
- K 棒上下影線極值不直接用來選擇樞紐。

## 四、方向成交量 `upAndDownVolume()`

函式先根據 K 棒方向設定 `isBuyVolume`：

```pine
close > open  → isBuyVolume = true
close < open  → isBuyVolume = false
```

再把整根 K 棒的 `volume` 加上正負號：

```text
上漲 K 棒：Vol = +volume
下跌 K 棒：Vol = -volume
```

這不是逐筆成交資料算出的真正買賣量差，也不是 bid/ask delta。它只是用 K 棒收盤價相對開盤價的方向，將整根成交量分類。

### 十字 K 的處理

當 `close == open` 時，`switch` 兩個條件都不成立。由於 `isBuyVolume` 是 `var` 變數，它會沿用上一根非十字 K 的方向；若資料一開始就是十字 K，初始值為 `true`。因此十字 K 的成交量可能被歸為正量或負量，取決於先前狀態。

## 五、成交量過濾條件

程式計算：

```pine
vol_hi = ta.highest(Vol / 2.5, vol_len)
vol_lo = ta.lowest(Vol / 2.5, vol_len)
```

然後使用：

```text
建立支撐：Vol > vol_hi
建立壓力：Vol < vol_lo
```

若把公式展開，它比較的是目前方向成交量 `Vol`，以及最近 `vol_len` 根方向成交量除以 2.5 後的最高／最低值。計算視窗包含目前 K 棒。

這裡有兩個值得注意的地方：

1. `vol_len` 的 tooltip 說數值越高越能過濾低量區塊，但實際結果同時受正負成交量混合及 `/ 2.5` 影響，並不是單純的「成交量必須創近期新高」。
2. 負數除以 2.5 會更靠近零。例如 `Vol=-1000` 時，`Vol/2.5=-400`；判斷 `-1000 < -400` 會成立。因此多空兩側的條件應依原公式回測，不宜把它直接理解成對稱的高成交量百分位篩選。

### 成交量使用的時間點

樞紐是 `lookbackPeriod` 根之前發生的，但 `Vol` 是「樞紐獲得確認的目前 K 棒」之成交量。也就是說：

- 區塊價位來自過去的樞紐 K 棒；
- 成交量篩選與 box 內顯示的 `Vol:` 數字來自確認 K 棒；
- 它顯示的不是樞紐 K 棒本身的成交量。

## 六、支撐與壓力區塊如何建立

### 區塊厚度

```pine
atr   = ta.atr(200)
withd = atr * box_withd
```

區塊厚度會隨波動度調整：

```text
區塊厚度 = 200 期 ATR × box_withd
```

ATR 取的是樞紐確認當下的值，建立後該區塊厚度不會隨後續 ATR 繼續改變。

### 支撐區

建立條件：

```pine
not na(pivotLow) and Vol > vol_hi
```

價格範圍：

```text
上界 = supportLevel = pivotLow
下界 = supportLevel_1 = pivotLow - withd
```

視覺樣式：

- 綠色實線邊框；
- 綠色漸層背景；
- box 文字顯示確認 K 棒的方向成交量。

### 壓力區

建立條件：

```pine
not na(pivotHigh) and Vol < vol_lo
```

價格範圍：

```text
下界 = resistanceLevel = pivotHigh
上界 = resistanceLevel_1 = pivotHigh + withd
```

視覺樣式：

- 紅色實線邊框；
- 紅色漸層背景；
- box 文字顯示確認 K 棒的方向成交量。

### 水平位置與延伸

新 box 的左端是樞紐 K 棒，初始右端是確認 K 棒：

```text
左端 = bar_index - lookbackPeriod
右端 = bar_index
```

之後每根 K 棒會把「最新一個支撐 box」與「最新一個壓力 box」的右端更新為 `bar_index + 1`。當新的同類 box 出現後，變數 `sup` 或 `res` 會改為指向新 box；舊 box 仍保留在圖上，但不再延伸或改色。

## 七、突破與守住的精確定義

程式使用 `ta.crossover()` 與 `ta.crossunder()`。這不只是「目前在某價位上方／下方」，而是要求目前與前一根 K 棒的相對位置發生跨越。

| 事件變數 | 程式條件 | 直觀意義 |
| --- | --- | --- |
| `brekout_res` | `ta.crossover(low, resistanceLevel_1)` | K 棒最低價向上穿越壓力區上界，整根 K 棒已位於區域上方 |
| `res_holds` | `ta.crossunder(high, resistanceLevel)` | K 棒最高價向下穿越壓力區下界，整根 K 棒已位於區域下方 |
| `sup_holds` | `ta.crossover(low, supportLevel)` | K 棒最低價向上穿越支撐區上界，整根 K 棒已位於區域上方 |
| `brekout_sup` | `ta.crossunder(high, supportLevel_1)` | K 棒最高價向下穿越支撐區下界，整根 K 棒已位於區域下方 |

拼字 `brekout` 雖不是標準英文 `breakout`，但所有引用一致，所以不影響程式。

這些條件使用 `low` 或 `high`，門檻比只要求 `close` 穿越更嚴格。例如 `brekout_res` 不是收盤價站上壓力上界，而是最低價也必須跨到上界之上。

### 新區塊切換造成的影響

`supportLevel` 與 `resistanceLevel` 是階梯狀序列：新樞紐成立時，價位會突然換成新值。`ta.crossover()`／`ta.crossunder()` 同時比較前一根與目前值，因此某些訊號可能受到「門檻本身改變」影響，而不完全是價格實際穿越同一條固定水平線。實務上應特別檢查新 box 出現當根的訊號。

## 八、區塊顏色與線型變化

### 支撐跌破

當 `brekout_sup` 成立：

- 支撐 box 變成淡紅色；
- 邊框變紅；
- 邊框改成虛線。

表示原支撐已被跌破，視覺上暗示它可能轉為壓力。

### 支撐重新守住

當 `sup_holds` 成立：

- box 恢復原本綠色背景；
- 邊框恢復綠色實線。

### 壓力突破

當 `brekout_res` 成立：

- 壓力 box 變成淡綠色；
- 邊框變綠；
- 邊框改成虛線。

表示原壓力已被向上突破，視覺上暗示它可能轉為支撐。

### 壓力重新壓住價格

當 `res_holds` 成立：

- box 恢復原本紅色背景；
- 邊框恢復紅色實線。

## 九、狀態變數

程式用兩個持久化布林值記錄最近狀態：

```text
res_is_sup：原壓力是否處於「已向上突破」狀態
sup_is_res：原支撐是否處於「已向下跌破」狀態
```

更新規則如下：

```text
brekout_res 成立 → res_is_sup = true
res_holds 成立   → res_is_sup = false

brekout_sup 成立 → sup_is_res = true
sup_holds 成立   → sup_is_res = false
```

`var` 讓狀態跨 K 棒保存；`[1]` 則表示讀取上一根 K 棒的狀態。

要注意，這兩個狀態是整個指標各一個，並非每個歷史 box 各自保存一份狀態。當新的支撐或壓力 box 產生時，狀態不會在程式中明確重設，解讀久遠舊區塊時要格外小心。

## 十、圖表符號與標籤

### 菱形符號

| 圖形 | 條件 | 顏色與位置 |
| --- | --- | --- |
| `Resistance Holds` | `res_holds` | 紅色菱形，K 棒上方 |
| `Support Holds` | `sup_holds` | 綠色菱形，K 棒下方 |
| `Resistance as Support Holds` | `brekout_res and res_is_sup[1]` | 綠色菱形，K 棒下方 |
| `Support as Resistance Holds` | `brekout_sup and sup_is_res[1]` | 紅色菱形，K 棒上方 |

所有 `plotchar()` 都設定 `offset=-1`，因此符號會畫在條件真正成立 K 棒的前一根。這只是繪圖位移，不代表訊號能提前一根被知道；即時判斷仍要等目前 K 棒條件成立。

後兩個名稱雖寫著「as Support/Resistance Holds」，但實際程式沒有另外檢查價格回測區塊後反彈／回落。它檢查的是：上一根已處於突破狀態，且目前再次出現同方向的突破條件。因此名稱與一般交易者所稱的「突破後回測守住」不完全相同。

### 首次突破標籤

支撐首次跌破時：

```text
Break Sup
```

壓力首次突破時：

```text
Break Res
```

標籤條件使用上一根狀態：

```pine
brekout_sup and not sup_is_res[1]
brekout_res and not res_is_sup[1]
```

標籤座標也刻意放在前一根：

```text
x = bar_index[1]
y = supportLevel[1] 或 resistanceLevel[1]
```

所以標籤位置不是訊號確認的目前 K 棒。除此之外，狀態初始值是 `na`；若尚未先被其他事件初始化，`not na` 仍為 `na`，最早期的第一次突破可能不會產生標籤。

## 十一、逐根 K 棒範例

假設使用預設參數，20 根之前有一個收盤價樞紐低點 100，目前 200 期 ATR 為 4，`box_withd=1`：

```text
支撐上界 = 100
支撐下界 = 100 - 4 × 1 = 96
```

若目前確認 K 棒的 `Vol > vol_hi`，指標會從 20 根之前開始畫出 96～100 的綠色區塊。

後續若 `high` 從前一根仍高於或等於 96，變成目前低於 96，則：

```text
ta.crossunder(high, 96) = true
brekout_sup = true
```

此時 box 轉成紅色虛線，代表支撐跌破。由於條件使用 `high`，目前整根 K 棒連最高價都已低於 96。

反之，若之後 `low` 向上穿越 100，`sup_holds` 成立，box 恢復綠色實線。

## 十二、重繪、回看偏誤與即時使用注意事項

### 1. 樞紐需要未來 K 棒確認

`ta.pivothigh()` 與 `ta.pivotlow()` 天生需要右側 K 棒資料。區塊左端回畫到樞紐位置，因此只看完成的歷史圖時，容易誤以為當時已經知道該支撐或壓力。實際可用時間是 `lookbackPeriod` 根之後。

### 2. 未收盤 K 棒內可能變動

指標沒有用 `barstate.isconfirmed` 限制計算。即時 K 棒尚未收盤時，`high`、`low`、`close` 與 `volume` 都可能持續變化，所以成交量資格、穿越事件及圖形可能在棒內出現或消失。若拿來發送警報，通常應考慮設定為 K 棒收盤確認。

### 3. 圖形向前位移不等於提前訊號

樞紐 box 回畫到過去，菱形也使用 `offset=-1`。這些都是視覺配置，不表示歷史位置當下已有可交易訊號。

### 4. 只管理最新同類區塊

舊 box 會留在圖上，但程式只延伸與改色目前 `sup`／`res` 指向的最新 box。因此畫面上的舊區域不會繼續依價格行為更新狀態。

### 5. 不是完整交易系統

程式沒有定義：

- 多空進場價格；
- 倉位大小；
- 停損與停利；
- 手續費與滑價；
- 同時持倉規則；
- 回測績效。

若要把圖示當成交易訊號，必須另外明確定義進出場與風控，不能直接把歷史 box 或標記視為可成交績效。

## 十三、參數調整的直觀效果

### 增加 `lookbackPeriod`

- 樞紐通常更少、層級更大；
- 確認時間更晚；
- 回畫距離更長。

### 增加 `vol_len`

- 成交量門檻參考更多近期 K 棒；
- 但效果不一定單調，因為視窗混合正負值且公式先除以 2.5；
- 應針對商品與週期實測訊號數量。

### 增加 `box_withd`

- 支撐／壓力區域變厚；
- 價格要讓整根 K 棒穿過外側邊界才觸發突破，訊號通常會更晚、更嚴格；
- 高波動期間因 ATR 上升，區域還會進一步加厚。

## 十四、核心邏輯摘要

可將原始程式濃縮成以下偽程式碼：

```text
每根 K 棒：
    若收盤 > 開盤：Vol = +成交量
    若收盤 < 開盤：Vol = -成交量
    若收盤 = 開盤：沿用先前方向

    尋找 lookbackPeriod 根之前、使用 close 計算的已確認樞紐
    區塊厚度 = ATR(200) × box_withd

    若樞紐低點成立且 Vol > 近期 Vol/2.5 最高值：
        建立 [pivotLow - 厚度, pivotLow] 支撐區

    若樞紐高點成立且 Vol < 近期 Vol/2.5 最低值：
        建立 [pivotHigh, pivotHigh + 厚度] 壓力區

    若 low 向上穿越壓力上界：
        壓力視為向上突破，box 變綠色虛線

    若 high 向下穿越支撐下界：
        支撐視為向下跌破，box 變紅色虛線

    若 high 向下穿越壓力下界：
        壓力視為守住，box 恢復紅色實線

    若 low 向上穿越支撐上界：
        支撐視為守住，box 恢復綠色實線
```

總結來說，這個指標的特色是以「收盤價樞紐 + K 棒方向成交量 + ATR 區域」建立動態支撐壓力。解讀時最重要的三點是：樞紐有右側確認延遲、成交量來自確認 K 棒而非樞紐 K 棒，以及歷史圖形存在回畫與 `offset=-1` 的視覺位移。
