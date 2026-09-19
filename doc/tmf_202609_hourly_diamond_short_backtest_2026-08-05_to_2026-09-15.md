# TMF 202609：60 分 K 紅綠菱形純放空回測

## 資料與設定

- 日期：`2026-08-05` 至 `2026-09-15`；來源檔 30 個，有效 tick 5,462,818 筆，60 分 K 565 根。
- 日盤從 `08:45`、夜盤從 `15:00` 起算 60 分 K；指標與部位允許跨盤延續。
- Pine 參數：close pivot `20/20`、delta-volume length `2`、ATR `200`、箱體寬度 `1 ATR`。
- 結構停損：觸發箱體上緣加 `0.1 ATR`；每筆完整交易成本 `0` 點。

## 交易規則

- `Resistance Holds` 或 `Support as Resistance Holds` 紅菱形於 60 分 K 收盤確認，下一根開盤放空。
- 開盤已越過停損則取消進場；持倉後跳空越過停損按開盤價出場，盤中 high 觸價則按停損價出場。
- `Support Holds` 或 `Resistance as Support Holds` 綠菱形收盤確認後，下一根開盤平空；停損優先於綠菱形。
- 同時最多一口、不加碼、不設停利或時間停損；資料結尾仍持倉則按最後收盤結算。
- 訊號使用實際確認 K，不採用原圖 `offset=-1` 的顯示位置。

## 結果

| Metric | Value |
| --- | ---: |
| Red diamond signals | 10 |
| Green diamond signals | 2 |
| Trades | 6 |
| Wins / Losses / Breakeven | 1 / 5 / 0 |
| Win rate | 16.7% |
| Gross P&L | -1239.6 points |
| Net P&L | -1239.6 points |
| Net profit factor | 0.33 |
| Average net P&L | -206.6 points |
| Maximum net drawdown | -1673.6 points |
| Cross-session trades | 6 |

## Trade Ledger

| # | Signal | Entry | Exit | Type | Gross | Net | Exit reason |
|---:|---|---|---|---|---:|---:|---|
| 1 | 2026-08-27 13:44:59 | 2026-08-27 15:00:00 @ 46130 | 2026-08-28 22:59:59 @ 46586 | resistance_holds | -455.9 | -455.9 | intrabar_stop |
| 2 | 2026-08-29 00:59:59 | 2026-08-29 01:00:00 @ 46042 | 2026-09-01 09:44:59 @ 46585 | resistance_holds | -543.3 | -543.3 | intrabar_stop |
| 3 | 2026-09-02 10:44:59 | 2026-09-02 10:45:00 @ 46320 | 2026-09-04 13:44:59 @ 46721 | resistance_holds | -401.4 | -401.4 | intrabar_stop |
| 4 | 2026-09-05 02:59:48 | 2026-09-05 03:00:00 @ 47159 | 2026-09-07 09:44:59 @ 47432 | resistance_holds | -273.0 | -273.0 | intrabar_stop |
| 5 | 2026-09-08 11:44:59 | 2026-09-08 11:45:00 @ 47274 | 2026-09-10 11:45:00 @ 46675 | resistance_holds | 599.0 | 599.0 | green_diamond |
| 6 | 2026-09-14 09:44:59 | 2026-09-14 09:45:00 @ 45401 | 2026-09-15 04:59:58 @ 45566 | support_as_resistance_holds | -165.0 | -165.0 | data_end |

## 回測限制

- 盤中停損只有 60 分 OHLC，無法得知該小時內的精確觸價秒數；成交價依上述停損規則模擬。
- MFE/MAE 使用持倉涵蓋之完整 60 分 K 高低點；停損 K 因盤中先後順序不可知，保守地只計入已知停損成交價。
- 淨損益只扣指定的固定每筆點數成本，未換算契約乘數或逐項估算手續費、稅與滑價。
