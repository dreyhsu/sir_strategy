# TMF 一小時壓力區＋三分 K UT Bot 純空策略回測

## 資料與設定

- 期間：`2021-01-01` 至 `2023-12-31`；來源 1 檔、有效 tick 829,932 筆。
- 一小時 K：13,851 根；有成交的三分 K：276,840 根。
- 商品／合約：`TXF / TXF2021-2023`；每邊滑價 `2` 點。
- Pine 壓力區：close pivot `20/20`、volume filter `2`、ATR(200) × `1`。
- 首次進場：3m UT Bot(a=2, ATR=10) 出現 SELL 且該 3m close 位於壓力區內；下一根 3m open 放空。
- 初始停損：min(進場上蓋, 最近 20 根擺盪高) 加 `0.5 × 一小時 ATR(20)`——錨定拒絕高點，不只是箱頂。
- 跌破區進場：close 需在區底下方 `1.5 × 一小時 ATR(20)` 以內（不追過低放空）。
- 只有 initial stop 啟動再進場；突破原上蓋後，必須在 `15` 分鐘內再次出現 UT Bot SELL 且 close 回到原壓力區。
- 回區訊號後於下一根 3m open 再進場；成交後才把上蓋向突破最高價移動 `50%`，並用新上蓋計算該筆停損。
- 保本鎖利：一旦價格跌破區底或達到 1R，停損收斂到扣除來回滑價後的保本價（`breakeven_lock`），獲利單不再翻成淨虧。
- 壓力區失效（不再放空）：3m close 收在上蓋上方超過 `1.5 × 一小時 ATR(20)`——完整突破、角色反轉為支撐。
- 趨勢濾網：當一小時 SMA(100) 在 `24h` 內上升超過 `0.5%` 時不開新空單（強多頭時觀望）。
- 靠近帶：高點來到區底下方 `0.25 × 一小時 ATR(20)` 內即視為觸及壓力（捕捉壓力下方的拒絕）。
- Adjust Supertrend：ATR 正規化價格速度動態 multiplier `4.5–1.5`；空頭確認且曾達 1R 後啟用 `3 × ATR(20)` trailing。

## 訊號與結構

| 項目 | 數量 |
| --- | ---: |
| Pine resistance IDs used | 117 |
| Dynamic top versions | 124 |
| Top adjustments | 7 |
| Zones invalidated (full breakout) | 51 |
| Initial-entry signals | 85 |
| Downside-exit initial signals | 50 |
| Re-entry signals | 7 |
| UT Bot SELL total | 7357 |

## 績效

| 指標 | 結果 |
| --- | ---: |
| Trades | 141 |
| Wins / Losses / Breakeven | 10 / 69 / 62 |
| Win rate | 7.1% |
| Gross P&L | -2097.4 points |
| Net P&L after slippage | -2661.4 points |
| Net P&L, 1 TMF contract | NT$-26,614 |
| Net profit factor | 0.21 |
| Average net P&L | -18.9 points |
| Maximum net drawdown | -2673.4 points |

## 出場原因

- `breakeven_lock`：59
- `initial_stop`：53
- `breakeven_lock_gap`：14
- `atr_trailing_stop`：8
- `initial_stop_gap`：4
- `adjust_supertrend_bullish_flip`：3

## 交易明細

| # | Entry type | Entry | Exit | Net | Net R | Exit reason |
|---:|---|---|---|---:|---:|---|
| 1 | initial_entry_after_downside_exit | 2021-02-25 09:07 @ 16365.0 | 2021-02-25 09:46 @ 16353.0 | 12.0 | 0.18 | adjust_supertrend_bullish_flip |
| 2 | initial_entry_after_downside_exit | 2021-03-11 21:28 @ 16216.0 | 2021-03-11 23:36 @ 16216.0 | 0.0 | 0.00 | breakeven_lock |
| 3 | initial_entry | 2021-03-12 01:04 @ 16247.0 | 2021-03-12 02:00 @ 16247.0 | 0.0 | 0.00 | breakeven_lock |
| 4 | initial_entry | 2021-03-12 02:28 @ 16241.0 | 2021-03-12 08:48 @ 16287.3 | -46.3 | -1.05 | initial_stop |
| 5 | initial_entry | 2021-03-18 09:16 @ 16274.0 | 2021-03-18 09:21 @ 16274.0 | 0.0 | 0.00 | breakeven_lock |
| 6 | initial_entry | 2021-03-26 11:55 @ 16235.0 | 2021-03-26 12:24 @ 16287.6 | -52.6 | -1.04 | initial_stop |
| 7 | initial_entry | 2021-03-26 20:07 @ 16282.0 | 2021-03-26 22:03 @ 16312.9 | -30.9 | -1.07 | initial_stop |
| 8 | initial_entry_after_downside_exit | 2021-04-08 09:55 @ 16767.0 | 2021-04-08 10:39 @ 16845.5 | -78.5 | -1.03 | initial_stop |
| 9 | initial_entry_after_downside_exit | 2021-04-29 03:13 @ 17560.0 | 2021-04-29 08:51 @ 17608.8 | -48.8 | -1.04 | initial_stop |
| 10 | initial_entry | 2021-04-29 09:13 @ 17599.0 | 2021-04-29 09:15 @ 17626.6 | -27.6 | -1.08 | initial_stop |
| 11 | initial_entry_after_downside_exit | 2021-06-07 17:10 @ 17158.0 | 2021-06-08 02:21 @ 17158.0 | 0.0 | 0.00 | breakeven_lock |
| 12 | initial_entry_after_downside_exit | 2021-06-11 09:25 @ 17222.0 | 2021-06-11 09:54 @ 17292.2 | -70.2 | -1.03 | initial_stop |
| 13 | initial_entry_after_downside_exit | 2021-06-24 22:55 @ 17414.0 | 2021-06-25 09:00 @ 17449.8 | -35.8 | -1.06 | initial_stop |
| 14 | reentry_after_initial_stop | 2021-06-25 09:22 @ 17461.0 | 2021-06-25 09:39 @ 17516.6 | -55.6 | -1.04 | initial_stop |
| 15 | initial_entry | 2021-06-25 17:22 @ 17429.0 | 2021-06-26 00:39 @ 17429.0 | 0.0 | 0.00 | breakeven_lock |
| 16 | initial_entry | 2021-06-26 01:13 @ 17420.0 | 2021-06-26 03:03 @ 17459.7 | -39.7 | -1.05 | initial_stop |
| 17 | initial_entry_after_downside_exit | 2021-06-28 13:13 @ 17513.0 | 2021-06-28 21:06 @ 17565.2 | -52.2 | -1.04 | initial_stop |
| 18 | initial_entry_after_downside_exit | 2021-07-03 00:10 @ 17727.0 | 2021-07-05 08:48 @ 17763.7 | -36.7 | -1.06 | initial_stop |
| 19 | initial_entry | 2021-07-15 13:34 @ 18019.0 | 2021-07-16 11:42 @ 17904.3 | 114.7 | 4.25 | atr_trailing_stop |
| 20 | initial_entry | 2021-08-02 16:13 @ 17455.0 | 2021-08-02 21:18 @ 17455.0 | 0.0 | 0.00 | breakeven_lock |
| 21 | initial_entry | 2021-08-02 21:43 @ 17442.0 | 2021-08-03 08:48 @ 17442.0 | 0.0 | 0.00 | breakeven_lock |
| 22 | initial_entry | 2021-08-03 09:37 @ 17412.0 | 2021-08-03 13:30 @ 17488.8 | -76.8 | -1.03 | initial_stop |
| 23 | initial_entry | 2021-08-03 21:34 @ 17443.0 | 2021-08-03 22:27 @ 17443.0 | 0.0 | 0.00 | breakeven_lock |
| 24 | initial_entry | 2021-08-03 23:19 @ 17425.0 | 2021-08-03 23:57 @ 17474.1 | -49.1 | -1.04 | initial_stop |
| 25 | initial_entry_after_downside_exit | 2021-09-04 04:04 @ 17466.0 | 2021-09-06 09:03 @ 17508.6 | -42.6 | -1.05 | initial_stop |
| 26 | reentry_after_initial_stop | 2021-09-06 10:43 @ 17523.0 | 2021-09-06 10:48 @ 17523.0 | 0.0 | 0.00 | breakeven_lock |
| 27 | initial_entry | 2021-09-06 12:22 @ 17561.0 | 2021-09-06 22:03 @ 17561.0 | 0.0 | 0.00 | breakeven_lock |
| 28 | initial_entry | 2021-09-06 23:19 @ 17552.0 | 2021-09-07 10:51 @ 17457.8 | 94.2 | 2.67 | atr_trailing_stop |
| 29 | initial_entry_after_downside_exit | 2021-09-14 09:01 @ 17504.0 | 2021-09-15 12:57 @ 17409.3 | 94.7 | 1.13 | atr_trailing_stop |
| 30 | initial_entry_after_downside_exit | 2021-10-15 11:10 @ 16745.0 | 2021-10-15 15:12 @ 16818.8 | -73.8 | -1.03 | initial_stop |
| 31 | initial_entry | 2021-10-18 08:49 @ 16811.0 | 2021-10-18 09:24 @ 16811.0 | 0.0 | 0.00 | breakeven_lock |
| 32 | initial_entry | 2021-10-19 03:13 @ 16797.0 | 2021-10-19 03:16 @ 16798.0 | -1.0 | -0.03 | breakeven_lock_gap |
| 33 | initial_entry | 2021-10-19 09:16 @ 16805.0 | 2021-10-19 09:21 @ 16805.0 | 0.0 | 0.00 | breakeven_lock |
| 34 | initial_entry_after_downside_exit | 2021-10-25 17:22 @ 16925.0 | 2021-10-25 22:18 @ 16925.0 | 0.0 | 0.00 | breakeven_lock |
| 35 | initial_entry | 2021-10-27 03:22 @ 16981.0 | 2021-10-27 04:51 @ 16981.0 | 0.0 | 0.00 | breakeven_lock |
| 36 | initial_entry | 2021-11-04 04:07 @ 17208.0 | 2021-11-04 08:46 @ 17271.0 | -63.0 | -1.69 | initial_stop_gap |
| 37 | reentry_after_initial_stop | 2021-11-04 09:04 @ 17210.0 | 2021-11-04 09:42 @ 17210.0 | 0.0 | 0.00 | breakeven_lock |
| 38 | initial_entry | 2021-11-05 15:22 @ 17253.0 | 2021-11-05 16:18 @ 17282.7 | -29.7 | -1.07 | initial_stop |
| 39 | initial_entry_after_downside_exit | 2021-11-13 03:34 @ 17584.0 | 2021-11-15 08:48 @ 17623.7 | -39.7 | -1.05 | initial_stop |
| 40 | initial_entry | 2021-11-15 10:22 @ 17663.0 | 2021-11-15 11:09 @ 17663.0 | 0.0 | 0.00 | breakeven_lock |
| 41 | initial_entry | 2021-11-16 00:46 @ 17649.0 | 2021-11-16 09:03 @ 17689.4 | -40.4 | -1.05 | initial_stop |
| 42 | initial_entry_after_downside_exit | 2021-12-02 00:58 @ 17679.0 | 2021-12-02 09:42 @ 17665.2 | 13.8 | 0.28 | atr_trailing_stop |
| 43 | initial_entry | 2021-12-02 15:31 @ 17721.0 | 2021-12-02 22:39 @ 17721.0 | 0.0 | 0.00 | breakeven_lock |
| 44 | initial_entry | 2021-12-02 23:19 @ 17711.0 | 2021-12-02 23:25 @ 17717.0 | -6.0 | -0.11 | breakeven_lock_gap |
| 45 | initial_entry | 2021-12-03 00:34 @ 17708.0 | 2021-12-03 00:37 @ 17709.0 | -1.0 | -0.02 | breakeven_lock_gap |
| 46 | initial_entry | 2021-12-03 02:10 @ 17732.0 | 2021-12-03 02:54 @ 17732.0 | 0.0 | 0.00 | breakeven_lock |
| 47 | initial_entry | 2021-12-03 03:55 @ 17723.0 | 2021-12-03 04:33 @ 17765.4 | -42.4 | -1.05 | initial_stop |
| 48 | initial_entry | 2021-12-03 12:31 @ 17710.0 | 2021-12-03 15:51 @ 17710.0 | 0.0 | 0.00 | breakeven_lock |
| 49 | initial_entry | 2021-12-03 20:58 @ 17697.0 | 2021-12-03 21:22 @ 17699.0 | -2.0 | -0.05 | breakeven_lock_gap |
| 50 | initial_entry_after_downside_exit | 2021-12-06 12:16 @ 17701.0 | 2021-12-07 02:03 @ 17701.0 | 0.0 | 0.00 | breakeven_lock |
| 51 | initial_entry_after_downside_exit | 2021-12-22 03:40 @ 17834.0 | 2021-12-22 13:30 @ 17834.0 | 0.0 | 0.00 | breakeven_lock |
| 52 | initial_entry | 2021-12-22 20:40 @ 17839.0 | 2021-12-22 22:48 @ 17866.3 | -27.3 | -1.08 | initial_stop |
| 53 | initial_entry_after_downside_exit | 2022-01-11 18:22 @ 18263.0 | 2022-01-12 00:15 @ 18320.1 | -57.1 | -1.04 | initial_stop |
| 54 | initial_entry | 2022-01-12 01:28 @ 18325.0 | 2022-01-12 03:42 @ 18369.5 | -44.5 | -1.05 | initial_stop |
| 55 | initial_entry_after_downside_exit | 2022-02-08 00:19 @ 17921.0 | 2022-02-08 08:48 @ 17985.7 | -64.7 | -1.03 | initial_stop |
| 56 | initial_entry | 2022-02-08 09:34 @ 17976.0 | 2022-02-08 09:42 @ 18043.9 | -67.9 | -1.03 | initial_stop |
| 57 | initial_entry | 2022-02-08 10:37 @ 18001.0 | 2022-02-08 23:48 @ 18001.0 | 0.0 | 0.00 | breakeven_lock |
| 58 | initial_entry_after_downside_exit | 2022-03-18 02:19 @ 17441.0 | 2022-03-18 22:15 @ 17441.0 | 0.0 | 0.00 | breakeven_lock |
| 59 | initial_entry | 2022-03-21 09:28 @ 17513.0 | 2022-03-21 09:48 @ 17513.0 | 0.0 | 0.00 | breakeven_lock |
| 60 | initial_entry | 2022-03-21 10:55 @ 17523.0 | 2022-03-21 15:03 @ 17523.0 | 0.0 | 0.00 | breakeven_lock |
| 61 | initial_entry | 2022-03-21 18:28 @ 17531.0 | 2022-03-21 23:24 @ 17531.0 | 0.0 | 0.00 | breakeven_lock |
| 62 | initial_entry | 2022-03-22 00:19 @ 17510.0 | 2022-03-22 02:24 @ 17510.0 | 0.0 | 0.00 | breakeven_lock |
| 63 | initial_entry | 2022-03-22 02:58 @ 17500.0 | 2022-03-22 03:03 @ 17500.0 | 0.0 | 0.00 | breakeven_lock |
| 64 | initial_entry | 2022-03-22 04:58 @ 17531.0 | 2022-03-22 09:36 @ 17531.0 | 0.0 | 0.00 | breakeven_lock |
| 65 | initial_entry | 2022-03-22 13:07 @ 17499.0 | 2022-03-22 15:18 @ 17550.6 | -51.6 | -1.04 | initial_stop |
| 66 | initial_entry_after_downside_exit | 2022-03-30 10:07 @ 17702.0 | 2022-03-31 08:46 @ 17749.0 | -47.0 | -0.71 | breakeven_lock_gap |
| 67 | initial_entry_after_downside_exit | 2022-04-14 03:55 @ 17325.0 | 2022-04-14 15:06 @ 17325.0 | 0.0 | 0.00 | breakeven_lock |
| 68 | initial_entry | 2022-05-27 10:58 @ 16191.0 | 2022-05-27 15:03 @ 16264.4 | -73.4 | -1.03 | initial_stop |
| 69 | initial_entry_after_downside_exit | 2022-06-27 11:16 @ 15360.0 | 2022-06-28 15:15 @ 15271.7 | 88.3 | 1.22 | atr_trailing_stop |
| 70 | initial_entry_after_downside_exit | 2022-08-05 15:19 @ 14993.0 | 2022-08-05 22:15 @ 14993.0 | 0.0 | 0.00 | breakeven_lock |
| 71 | initial_entry | 2022-08-09 12:43 @ 15026.0 | 2022-08-09 13:15 @ 15026.0 | 0.0 | 0.00 | breakeven_lock |
| 72 | initial_entry | 2022-08-09 17:31 @ 15017.0 | 2022-08-10 11:48 @ 14946.4 | 70.6 | 1.85 | atr_trailing_stop |
| 73 | initial_entry | 2022-08-11 02:52 @ 15066.0 | 2022-08-11 08:46 @ 15117.0 | -51.0 | -1.42 | initial_stop_gap |
| 74 | initial_entry | 2022-09-20 15:43 @ 14559.0 | 2022-09-22 02:36 @ 14437.1 | 121.9 | 2.13 | atr_trailing_stop |
| 75 | initial_entry_after_downside_exit | 2022-10-31 12:04 @ 12957.0 | 2022-11-01 08:46 @ 12962.0 | -5.0 | -0.08 | breakeven_lock_gap |
| 76 | initial_entry | 2022-11-01 15:28 @ 13019.0 | 2022-11-01 16:06 @ 13049.7 | -30.7 | -1.07 | initial_stop |
| 77 | initial_entry_after_downside_exit | 2022-11-02 12:04 @ 13067.0 | 2022-11-03 02:03 @ 13067.0 | 0.0 | 0.00 | breakeven_lock |
| 78 | initial_entry_after_downside_exit | 2022-11-04 19:04 @ 13055.0 | 2022-11-04 20:34 @ 13056.0 | -1.0 | -0.02 | breakeven_lock_gap |
| 79 | initial_entry | 2022-11-04 21:40 @ 13089.0 | 2022-11-04 21:43 @ 13098.0 | -9.0 | -0.15 | breakeven_lock_gap |
| 80 | initial_entry | 2022-11-04 23:31 @ 13122.0 | 2022-11-05 00:21 @ 13122.0 | 0.0 | 0.00 | breakeven_lock |
| 81 | initial_entry | 2022-11-05 00:43 @ 13084.0 | 2022-11-05 02:57 @ 13151.3 | -67.3 | -1.03 | initial_stop |
| 82 | initial_entry_after_downside_exit | 2022-11-22 22:16 @ 14529.0 | 2022-11-22 23:18 @ 14571.3 | -42.3 | -1.05 | initial_stop |
| 83 | reentry_after_initial_stop | 2022-11-23 09:04 @ 14605.0 | 2022-11-23 10:48 @ 14605.0 | 0.0 | 0.00 | breakeven_lock |
| 84 | initial_entry | 2022-11-23 11:16 @ 14600.0 | 2022-11-23 22:39 @ 14645.1 | -45.1 | -1.05 | initial_stop |
| 85 | initial_entry_after_downside_exit | 2022-11-30 13:34 @ 14801.0 | 2022-12-01 02:33 @ 14801.0 | 0.0 | 0.00 | breakeven_lock |
| 86 | initial_entry | 2023-01-03 13:07 @ 14217.0 | 2023-01-03 15:15 @ 14217.0 | 0.0 | 0.00 | breakeven_lock |
| 87 | initial_entry | 2023-01-03 21:10 @ 14242.0 | 2023-01-03 22:36 @ 14284.2 | -42.2 | -1.05 | initial_stop |
| 88 | initial_entry | 2023-01-04 11:34 @ 14216.0 | 2023-01-04 11:37 @ 14217.0 | -1.0 | -0.02 | breakeven_lock_gap |
| 89 | initial_entry | 2023-01-04 13:28 @ 14215.0 | 2023-01-04 13:34 @ 14216.0 | -1.0 | -0.02 | breakeven_lock_gap |
| 90 | initial_entry | 2023-01-04 16:43 @ 14249.0 | 2023-01-04 22:30 @ 14285.5 | -36.5 | -1.06 | initial_stop |
| 91 | initial_entry | 2023-01-05 09:37 @ 14327.0 | 2023-01-05 19:57 @ 14327.0 | 0.0 | 0.00 | breakeven_lock |
| 92 | initial_entry | 2023-01-05 20:04 @ 14310.0 | 2023-01-05 20:57 @ 14310.0 | 0.0 | 0.00 | breakeven_lock |
| 93 | initial_entry_after_downside_exit | 2023-01-06 09:49 @ 14307.0 | 2023-01-06 11:12 @ 14370.1 | -63.1 | -1.03 | initial_stop |
| 94 | initial_entry | 2023-01-06 12:43 @ 14374.0 | 2023-01-06 21:33 @ 14374.0 | 0.0 | 0.00 | breakeven_lock |
| 95 | initial_entry_after_downside_exit | 2023-01-17 23:34 @ 15004.0 | 2023-01-30 08:46 @ 15560.0 | -556.0 | -11.05 | initial_stop_gap |
| 96 | initial_entry_after_downside_exit | 2023-02-09 15:16 @ 15590.0 | 2023-02-09 16:07 @ 15629.0 | -39.0 | -1.06 | initial_stop_gap |
| 97 | initial_entry_after_downside_exit | 2023-02-14 21:04 @ 15692.0 | 2023-02-14 21:33 @ 15723.6 | -31.6 | -1.07 | initial_stop |
| 98 | initial_entry_after_downside_exit | 2023-02-23 11:07 @ 15629.0 | 2023-02-23 13:00 @ 15629.0 | 0.0 | 0.00 | breakeven_lock |
| 99 | initial_entry | 2023-02-23 13:25 @ 15611.0 | 2023-02-23 16:39 @ 15611.0 | 0.0 | 0.00 | breakeven_lock |
| 100 | initial_entry | 2023-02-23 18:37 @ 15587.0 | 2023-02-23 20:03 @ 15619.8 | -32.8 | -1.06 | initial_stop |
| 101 | reentry_after_initial_stop | 2023-02-23 21:34 @ 15607.0 | 2023-02-23 22:30 @ 15649.2 | -42.2 | -1.05 | initial_stop |
| 102 | initial_entry_after_downside_exit | 2023-03-06 09:01 @ 15738.0 | 2023-03-06 09:42 @ 15738.0 | 0.0 | 0.00 | breakeven_lock |
| 103 | initial_entry_after_downside_exit | 2023-03-21 11:04 @ 15466.0 | 2023-03-21 21:42 @ 15541.9 | -75.9 | -1.03 | initial_stop |
| 104 | reentry_after_initial_stop | 2023-03-21 22:07 @ 15545.0 | 2023-03-22 01:30 @ 15545.0 | 0.0 | 0.00 | breakeven_lock |
| 105 | initial_entry | 2023-03-22 01:52 @ 15537.0 | 2023-03-22 03:42 @ 15572.4 | -35.4 | -1.06 | initial_stop |
| 106 | initial_entry_after_downside_exit | 2023-03-31 10:01 @ 15926.0 | 2023-03-31 22:03 @ 15906.5 | 19.5 | 0.36 | atr_trailing_stop |
| 107 | initial_entry | 2023-04-12 21:07 @ 15973.0 | 2023-04-12 22:12 @ 15973.0 | 0.0 | 0.00 | breakeven_lock |
| 108 | initial_entry | 2023-04-14 12:49 @ 15970.0 | 2023-04-14 22:00 @ 15970.0 | 0.0 | 0.00 | breakeven_lock |
| 109 | initial_entry_after_downside_exit | 2023-04-17 16:25 @ 15958.0 | 2023-04-18 03:10 @ 15958.0 | 0.0 | 0.00 | breakeven_lock_gap |
| 110 | initial_entry_after_downside_exit | 2023-05-02 09:46 @ 15632.0 | 2023-05-03 09:46 @ 15573.0 | 59.0 | 1.09 | adjust_supertrend_bullish_flip |
| 111 | initial_entry | 2023-05-05 09:37 @ 15647.0 | 2023-05-05 09:43 @ 15647.0 | 0.0 | 0.00 | breakeven_lock_gap |
| 112 | initial_entry | 2023-05-05 20:22 @ 15652.0 | 2023-05-05 20:36 @ 15652.0 | 0.0 | 0.00 | breakeven_lock |
| 113 | initial_entry_after_downside_exit | 2023-05-17 09:40 @ 15757.0 | 2023-05-17 10:18 @ 15802.0 | -45.0 | -1.05 | initial_stop |
| 114 | initial_entry_after_downside_exit | 2023-05-25 09:19 @ 16145.0 | 2023-05-25 10:30 @ 16198.7 | -53.7 | -1.04 | initial_stop |
| 115 | initial_entry | 2023-06-02 23:40 @ 16743.0 | 2023-06-03 01:27 @ 16767.8 | -24.8 | -1.09 | initial_stop |
| 116 | initial_entry | 2023-06-05 12:04 @ 16739.0 | 2023-06-06 09:15 @ 16739.0 | 0.0 | 0.00 | breakeven_lock |
| 117 | initial_entry_after_downside_exit | 2023-06-06 11:04 @ 16738.0 | 2023-06-07 00:01 @ 16803.0 | -65.0 | -1.00 | adjust_supertrend_bullish_flip |
| 118 | initial_entry | 2023-06-07 03:16 @ 16788.0 | 2023-06-07 09:27 @ 16817.0 | -29.0 | -1.07 | initial_stop |
| 119 | initial_entry_after_downside_exit | 2023-07-27 09:55 @ 17192.0 | 2023-07-27 16:24 @ 17279.1 | -87.1 | -1.02 | initial_stop |
| 120 | initial_entry | 2023-07-28 11:46 @ 17264.0 | 2023-07-28 11:54 @ 17264.0 | 0.0 | 0.00 | breakeven_lock |
| 121 | initial_entry_after_downside_exit | 2023-08-23 11:28 @ 16512.0 | 2023-08-23 15:12 @ 16577.4 | -65.4 | -1.03 | initial_stop |
| 122 | initial_entry | 2023-08-23 15:40 @ 16550.0 | 2023-08-23 20:00 @ 16550.0 | 0.0 | 0.00 | breakeven_lock |
| 123 | initial_entry | 2023-08-23 20:28 @ 16532.0 | 2023-08-23 20:31 @ 16533.0 | -1.0 | -0.02 | breakeven_lock_gap |
| 124 | initial_entry_after_downside_exit | 2023-08-30 09:07 @ 16741.0 | 2023-08-30 12:33 @ 16741.0 | 0.0 | 0.00 | breakeven_lock |
| 125 | initial_entry | 2023-09-04 16:34 @ 16779.0 | 2023-09-04 21:33 @ 16779.0 | 0.0 | 0.00 | breakeven_lock |
| 126 | initial_entry | 2023-09-04 21:52 @ 16767.0 | 2023-09-05 13:18 @ 16767.0 | 0.0 | 0.00 | breakeven_lock |
| 127 | initial_entry | 2023-09-06 03:07 @ 16764.0 | 2023-09-06 03:21 @ 16764.0 | 0.0 | 0.00 | breakeven_lock |
| 128 | initial_entry | 2023-10-07 00:40 @ 16622.0 | 2023-10-07 01:21 @ 16659.5 | -37.5 | -1.06 | initial_stop |
| 129 | initial_entry_after_downside_exit | 2023-11-02 21:19 @ 16467.0 | 2023-11-02 22:54 @ 16467.0 | 0.0 | 0.00 | breakeven_lock |
| 130 | initial_entry | 2023-11-03 04:16 @ 16499.0 | 2023-11-03 09:45 @ 16499.0 | 0.0 | 0.00 | breakeven_lock |
| 131 | initial_entry | 2023-11-03 10:25 @ 16478.0 | 2023-11-03 11:12 @ 16536.4 | -58.4 | -1.04 | initial_stop |
| 132 | initial_entry | 2023-11-03 11:43 @ 16505.0 | 2023-11-03 12:54 @ 16505.0 | 0.0 | 0.00 | breakeven_lock |
| 133 | initial_entry | 2023-11-03 15:58 @ 16499.0 | 2023-11-03 20:48 @ 16537.1 | -38.1 | -1.06 | initial_stop |
| 134 | initial_entry_after_downside_exit | 2023-11-20 23:25 @ 17232.0 | 2023-11-21 02:03 @ 17275.9 | -43.9 | -1.05 | initial_stop |
| 135 | initial_entry_after_downside_exit | 2023-12-08 03:58 @ 17392.0 | 2023-12-08 08:51 @ 17426.4 | -34.4 | -1.06 | initial_stop |
| 136 | reentry_after_initial_stop | 2023-12-08 09:22 @ 17430.0 | 2023-12-08 09:30 @ 17430.0 | 0.0 | 0.00 | breakeven_lock |
| 137 | initial_entry | 2023-12-11 08:52 @ 17427.0 | 2023-12-11 15:03 @ 17427.0 | 0.0 | 0.00 | breakeven_lock |
| 138 | initial_entry | 2023-12-11 16:16 @ 17415.0 | 2023-12-11 16:58 @ 17415.0 | 0.0 | 0.00 | breakeven_lock_gap |
| 139 | initial_entry | 2023-12-11 20:40 @ 17412.0 | 2023-12-11 22:39 @ 17438.5 | -26.5 | -1.08 | initial_stop |
| 140 | initial_entry | 2023-12-12 00:37 @ 17451.0 | 2023-12-12 01:30 @ 17476.3 | -25.3 | -1.09 | initial_stop |
| 141 | initial_entry_after_downside_exit | 2023-12-26 12:46 @ 17719.0 | 2023-12-26 22:42 @ 17750.0 | -31.0 | -1.07 | initial_stop |

## 限制

- 3m OHLC 無法還原分鐘內 high/low 先後；既有停損優先，新 trailing stop 僅從下一根 3m 生效。
- 只使用事件當下已完成的資料；pivot 的歷史回畫及 Pine `offset=-1` 不用於交易。
- 淨損益包含每邊固定滑價，但未扣手續費、期交稅、買賣價差與排隊成交影響。
- UT Bot 狀態機從資料最早段開始遞推，靠近資料起點的訊號受 warm-up 影響。
