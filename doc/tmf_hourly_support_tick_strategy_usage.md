# TMF 60 分 K 支撐 + Tick 反轉策略：使用說明

## 目的

這個策略先由 TAIFEX 的 TMF 逐筆成交資料建立 60 分 K，依照 `pine_script.txt` 的支撐壓力邏輯找出已確認的支撐箱體，再用 2,000 口 volume bar 的密集成交反轉作為精準進場確認。

目前程式是**僅做多**版本，且同一時間最多持有一口多單。空方交易尚未加入。

## 使用的程式

`snr/src/backtest_tmf_hourly_support_long.py`

## 執行環境

使用專案指定的 Conda 環境 `tss`：

```bash
conda run -n tss python snr/src/backtest_tmf_hourly_support_long.py \
  --start-date 2026-09-01 \
  --end-date 2026-09-11
```

## 輸入資料

1. 從 TAIFEX 下載每日逐筆成交 ZIP 檔。
2. 將檔案放在 `~/Downloads`。檔名必須是 `Daily_YYYY_MM_DD.zip`，例如 `Daily_2026_09_01.zip`。
3. 程式預設篩選：
   - 商品：`TMF`
   - 到期月份：`202609`
4. 起訖日期代表要讀取的日檔日期。週末與休市日沒有檔案時會自然略過。

若日檔放在其他資料夾，使用 `--input-dir`：

```bash
conda run -n tss python snr/src/backtest_tmf_hourly_support_long.py \
  --input-dir /path/to/daily-files \
  --start-date 2026-09-01 \
  --end-date 2026-09-11
```

若交易其他契約，覆寫商品與到期月份：

```bash
conda run -n tss python snr/src/backtest_tmf_hourly_support_long.py \
  --start-date 2026-09-01 \
  --end-date 2026-09-11 \
  --product TMF \
  --contract-month 202610
```

## 交易時段

- 日盤：`08:45:00–13:45:00`
- 夜盤：`15:00:00–次日 05:00:00`

日盤與夜盤各自重新開始 2,000 口 volume bar；不跨休市累積未完成 K 棒、不保留待進場訊號，也不留倉到下一個時段。

## 60 分 K 支撐壓力

每個交易時段從開盤時間開始切成 60 分鐘 K：日盤從 `08:45` 開始，夜盤從 `15:00` 開始。

支撐與壓力沿用 Pine 指標的核心方式：

- 使用 60 分 K 的 `close` 尋找 pivot。
- `--pivot-lookback 20` 代表 pivot 左右各要有 20 根 60 分 K 確認。
- pivot low 配合正 delta volume 建立支撐箱體。
- pivot high 配合負 delta volume 建立壓力箱體。
- 箱體寬度為 `ATR × --box-width`。

原始 Pine 指標使用 `ATR(200)`。少於 200 根 60 分 K 時，請使用較短的 ATR；本回測預設 `ATR(20)`。這是資料量不足時的實務替代，並非 Pine 原始參數的完全複製。

## Tick 進場規則

只有下列條件同時成立才建立多方訊號：

1. 2,000 口 volume bar 的成交速度大於等於前 50 根已完成 bar 的第 75 百分位。
2. 該 bar low 為最近 5 根的最低 low。
3. 該 bar 收紅，且 close 位於全幅上半部。
4. 該 bar 的價格範圍接觸一個已確認、尚未跌破的 60 分 K 支撐箱體。

訊號 K 棒完成後，以下一根 2,000 口 volume bar 的 open 進場做多。支撐 pivot 必須等右側 20 根 60 分 K 完成後才有效，因此不會提前使用尚未確認的轉折點。

## 出場規則

- 初始停損：訊號 volume bar 的 `low - 2` 點。
- 最高價達到 `+2R` 後，啟用追蹤停損：進場後最高價 `- 1R`。
- 進場時若上方已有已確認壓力，價格觸及該壓力箱體下緣時出場。
- 出現空方密集成交反轉時出場。
- 時段最後一根完成 volume bar 的 close 強制平倉。

停損、壓力觸及、追蹤停損與空方反轉都是在 volume bar 完成後確認，並於下一根 bar open 執行；時段結束則用最後一根完成 bar 的 close。這是為了避免使用 K 棒內尚未完成時不可得的資訊。

## 可調整參數

```bash
conda run -n tss python snr/src/backtest_tmf_hourly_support_long.py \
  --start-date 2026-09-01 \
  --end-date 2026-09-11 \
  --volume-bar-size 2000 \
  --density-window 50 \
  --density-quantile 0.75 \
  --tick-lookback-bars 5 \
  --pivot-lookback 20 \
  --volume-filter-length 2 \
  --atr-length 20 \
  --box-width 1.0
```

不要只依單一期間最佳化這些參數；應以更多月份與不同市場狀態重跑，再將手續費、期交稅、買賣價差與滑價納入評估。

## 輸出檔案

預設輸出在 `snr/txf_tick/`：

- `TMF_202609_hourly_bars_2026-09-01_to_2026-09-11.csv`：60 分 K 資料。
- `TMF_202609_hourly_support_long_trades_2026-09-01_to_2026-09-11.csv`：交易明細。無交易時仍會保留欄位標題。
- `TMF_202609_hourly_support_long_backtest_2026-09-01_to_2026-09-11.html`：互動式圖表，包含 60 分 K、支撐壓力箱、tick 反轉、進出場與權益曲線。

報告輸出在 `snr/doc/`：

- `tmf_202609_hourly_support_long_backtest_2026-09-01_to_2026-09-11.md`

可使用 `--report-output`、`--chart-output`、`--trades-output` 與 `--hourly-output` 指定不同路徑，避免覆蓋先前回測。

## 僅做空壓力反轉回測

`snr/src/backtest_tmf_hourly_resistance_short.py` 是對稱的僅做空版本。它讀取前一個腳本輸出的 60 分 K 與 2,000 口 volume bar，因此先完成一次 60 分 K 資料建立後再執行：

```bash
conda run -n tss python snr/src/backtest_tmf_hourly_resistance_short.py
```

空單條件為：已確認、未突破的 60 分 K 壓力箱內，2,000 口 volume bar 為最近 5 根的高點、收黑、且 close 位於全幅下方 35%。這個版本不要求成交速度超過密集成交門檻，目的在捕捉壓力區的正常回落。訊號完成後以下一根 volume bar open 放空。

停損與獲利了結由**連續 60 分 K**的 Supertrend 管理，而不是 volume bar：已完成的 60 分 K Supertrend 從空頭翻為多頭後，下一根 volume bar open 平倉；交易時段結束仍強制平倉。volume bar 只會讀取較早、已完成的 60 分 K 狀態，因此不會使用正在形成的小時 K。

目前 Supertrend 只作為出場條件，不作為進場過濾。因此若空單進場時 60 分 K Supertrend 已是多頭，只有在它先轉空、再轉多時才會出現翻轉出場；否則會持有到時段結束。若要避免逆勢空單，需另外啟用「僅 Supertrend 空頭才放空」的進場過濾。

若使用不同檔案名稱，指定輸入：

```bash
conda run -n tss python snr/src/backtest_tmf_hourly_resistance_short.py \
  --hourly-source snr/txf_tick/your_hourly_bars.csv \
  --volume-bars-source snr/txf_tick/your_volume_bars.csv \
  --close-position-max 0.35 \
  --hourly-supertrend-atr-length 10 \
  --hourly-supertrend-multiplier 3.0
```

預設會輸出交易明細、互動圖與 Markdown 報告，檔名以 `hourly_resistance_short` 開頭。

## 自適應 60 分 K Supertrend 跨時段空單回測

`snr/src/backtest_tmf_adaptive_hourly_resistance_short.py` 是可跨日持倉的版本。它預設讀取 `snr/data` 的 TAIFEX CSV／ZIP 日檔，重新建立連續的 2,000 口 volume bar；不在日盤或夜盤結束時平倉。

```bash
conda run -n tss python snr/src/backtest_tmf_adaptive_hourly_resistance_short.py \
  --start-date 2026-09-01 \
  --end-date 2026-09-11
```

進場仍是壓力區的 tick volume-bar 空方反轉。出場則使用連續 60 分 K 自適應 Supertrend：價格速度越高，ATR 倍數越小，Supertrend 線會更貼近價格。預設值為：

- 基礎寬度：`ATR(10) × 3.0`
- 最小寬度：`ATR × 0.8`
- 速度：最近 2 根 60 分 K 的 ATR 正規化移動，並以 2 根平滑。
- 速度小於 `0.25` 使用 `3.0` 倍；大於 `0.8` 使用 `0.8` 倍；中間線性收緊。

完成的 60 分 K Supertrend 從空頭翻成多頭後，下一根 2,000 口 volume bar open 出場。這是趨勢追蹤出場，沒有固定點數停損或獲利目標；若回測結束前沒有翻轉，程式以最後一根完成 volume bar close 結算。

```bash
conda run -n tss python snr/src/backtest_tmf_adaptive_hourly_resistance_short.py \
  --start-date 2026-09-01 \
  --end-date 2026-09-11 \
  --base-multiplier 3.0 \
  --min-multiplier 0.8 \
  --speed-lookback 2 \
  --low-speed 0.25 \
  --high-speed 0.8 \
  --smoothing-span 2
```

## 自適應空單 Strategy B 與 A/B Test

Legacy A 明確指定為：

```text
snr/src/backtest_tmf_adaptive_hourly_resistance_short.py
```

Strategy B 與 A/B runner 為：

```text
snr/src/backtest_tmf_adaptive_hourly_resistance_short_ab.py
```

預設執行 Legacy A 與 Strategy B，並使用相同資料產生獨立交易明細及統一比較報告：

```bash
conda run -n tss python snr/src/backtest_tmf_adaptive_hourly_resistance_short_ab.py \
  --start-date 2026-08-05 \
  --end-date 2026-09-15
```

Strategy B 的主要差異：

- 每個日／夜盤重新累積 2,000 口 volume bar，不跨休市保留未完成量或待進場訊號。
- 訊號完成後使用同一 session 的下一筆 tick 成交，進出場各加入 2 點不利滑價。
- 初始停損為 `max(訊號 high, 壓力區 top) + 0.5 × hourly ATR`，逐筆成交觸發。
- 完成的 volume bar 收在進場壓力區上緣以上時，判定壓力失效。
- 進場後 12 個鐘錶小時內 Supertrend 未確認空頭則退出。
- 最大持倉時間為 120 個鐘錶小時，休市與週末仍計時。
- Supertrend 確認空頭後，以最低價加 `1.5 × 最新完成 hourly ATR` 追蹤；停損只能向下收緊。
- 主要出場仍為完成的 hourly Supertrend 從空頭翻多。

可用 `--strategy-variant legacy` 或 `--strategy-variant session-risk` 單獨執行其中一組。完整規則與成交優先序請見 `snr/doc/tmf_adaptive_hourly_resistance_short_strategy_b.md`。
