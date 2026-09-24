# TMF 202609：5M 壓力區型態 A／B 空單回測

## 資料與設定

- 日期：`2026-08-05` 至 `2026-09-15`；來源檔 30 個、有效 tick 5,462,818 筆、5 分 K 6,780 根、60 分 K 565 根。
- 起始權益：NT$400,000；每點 NT$10；同時最多一口。
- 進出場每邊 2 點不利滑價；未計手續費與期交稅。

## 交易規則

- 型態 A：突破壓力上緣 5 點後，在含突破棒的 3 根內收回箱內，並跌破前 5 根最強紅 K 低點。
- 最強紅 K 模式：`body`；型態 A 停損為突破過程最高價加 5 點。
- 型態 B：進入壓力區後 12 根內，以左右 2 根確認 H1/L1/H2，H2 至少低 5 點，再收破 L1。
- 下一根 5M 第一筆 tick 進場；停利為 2R；5M 收盤站回壓力上緣則下一根開盤退出。

## 帳戶結果

| Metric | Value |
| --- | ---: |
| Pattern A / B signals | 12 / 1 |
| Valid signals / filled entries | 13 / 10 |
| Ignored while occupied | 3 |
| Canceled at session / stop breached | 0 / 0 |
| Contract trades / groups | 10 / 10 |
| Winning / losing trades | 2 / 8 |
| Win rate / profit factor | 20.0% / 0.88 |
| Gross P&L | NT$-380 |
| Net P&L after slippage | NT$-780 |
| Final equity | NT$399,220 |
| Return | -0.19% |
| Minimum tick-level equity | NT$397,290 |
| Maximum tick-level drawdown | NT$5,280 (1.31%) |
| Stop / target / reclaim exits | 2 / 2 / 6 |
| Flat exposure | 979.7 h (98.2%) |
| One-contract exposure | 18.3 h (1.8%) |

## Group Ledger

| Group | Pattern | Entry | Exit | Fill | Net NTD | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | A | 2026-08-11 20:25:01 | 2026-08-11 20:30:06 | 45474.0 | -180 | resistance_reclaimed |
| 2 | A | 2026-08-11 21:35:00 | 2026-08-11 21:41:38 | 45478.0 | -990 | initial_structure_stop |
| 3 | A | 2026-08-11 21:50:06 | 2026-08-11 22:00:04 | 45493.0 | -150 | resistance_reclaimed |
| 4 | A | 2026-08-11 23:25:00 | 2026-08-11 23:30:00 | 45476.0 | -130 | resistance_reclaimed |
| 5 | A | 2026-08-11 23:35:02 | 2026-08-12 01:15:05 | 45426.0 | 1,620 | risk_reward_target |
| 6 | A | 2026-08-28 09:25:00 | 2026-08-28 22:00:20 | 46453.0 | -1,290 | initial_structure_stop |
| 7 | A | 2026-08-28 22:10:00 | 2026-08-29 01:06:12 | 46387.0 | 4,280 | risk_reward_target |
| 8 | A | 2026-09-07 09:15:00 | 2026-09-07 09:40:00 | 47131.0 | -2,740 | resistance_reclaimed |
| 9 | A | 2026-09-07 11:05:00 | 2026-09-07 11:10:00 | 47373.0 | -440 | resistance_reclaimed |
| 10 | A | 2026-09-07 11:45:00 | 2026-09-07 11:55:01 | 47337.0 | -760 | resistance_reclaimed |

## 風險說明

NT$400,000 僅作為權益基準；回測不會因權益或保證金不足自動平倉。
