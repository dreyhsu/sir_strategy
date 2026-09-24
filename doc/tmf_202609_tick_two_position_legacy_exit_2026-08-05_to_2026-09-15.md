# TMF 202609：Tick 兩口空單＋Legacy Supertrend 出場回測

## 資料與設定

- 日期：`2026-08-05` 至 `2026-09-15`；來源檔 30 個、有效 tick 5,462,818 筆、60 分 K 565 根。
- 起始權益：NT$400,000；TMF 每點 NT$10；最多同時 2 口。
- 進出場每邊使用 2 點不利滑價；未計手續費與期交稅；不模擬追繳或強制平倉。
- 2,000 口量 K 每個日／夜盤重新累積，時段尾端不足量直接丟棄。

## 交易規則

- 60 分鐘 K 建立支撐／壓力箱；2,000 口量 K 判定訊號，訊號完成後同交易時段下一筆 tick 放空。
- 壓力反轉需先形成收黑 rejection K，再由後續量 K 跌破 rejection 低點；支撐跌破需收盤有效跌破箱底。
- 只在 60 分鐘 Supertrend 為空頭時進場；首口確認後，同箱體回測失敗且至少達 0.5R 才允許第二口。
- 使用箱體失效位置加 0.25 ATR 初始停損，並在達到確認獲利後使用 1 ATR 移動停損。
- 首口以 1R 目標出場；另設 12 小時確認逾時與 24 小時最大持倉時間。
- 60 分狀態只在其完成時間嚴格早於當前 tick 時使用，保留同秒成交的原始列順序。

## 帳戶結果

| Metric | Value |
| --- | ---: |
| Valid signals / filled entries | 108 / 7 |
| Ignored at two-contract capacity | 3 |
| Contract trades / position groups | 7 / 6 |
| Winning / losing contracts | 2 / 5 |
| Winning / losing groups | 2 / 4 |
| Contract / group win rate | 28.6% / 33.3% |
| Group profit factor | 0.35 |
| Gross P&L | NT$-3,470 |
| Net P&L after slippage | NT$-3,750 |
| Final equity | NT$396,250 |
| Return | -0.94% |
| Minimum tick-level equity | NT$394,650 |
| Maximum tick-level drawdown | NT$7,420 (1.85%) |
| Peak open contracts | 1 |
| Flat exposure | 987.7 h (99.0%) |
| One-contract exposure | 10.1 h (1.0%) |
| Two-contract exposure | 0.2 h (0.0%) |

## Group Ledger

| Group | Lots | First entry | Exit | Average fill | Net NTD | Exit reason |
|---:|---:|---|---|---:|---:|---|
| 1 | 1 | 2026-08-18 22:55:00 | 2026-08-19 03:27:20 | 44626.0 | -630 | initial_structure_stop |
| 2 | 1 | 2026-08-27 17:04:31 | 2026-08-27 22:13:41 | 46314.0 | 1,120 | initial_structure_stop |
| 3 | 1 | 2026-09-01 09:02:48 | 2026-09-01 09:08:43 | 46296.0 | -2,880 | initial_structure_stop |
| 4 | 1 | 2026-09-01 09:11:34 | 2026-09-01 09:15:01 | 46618.0 | -1,050 | initial_structure_stop |
| 5 | 2 | 2026-09-01 09:26:33 | 2026-09-01 09:37:10 | 46787.0 | -1,240 | initial_structure_stop |
| 6 | 1 | 2026-09-10 20:16:55 | 2026-09-10 20:32:21 | 46398.0 | 930 | one_r_target |

## 風險說明

NT$400,000 僅作為權益基準；回測不會因權益或保證金不足自動平倉。
