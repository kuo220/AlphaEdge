# ETL 入庫約定

> 本文件描述 `core/pipeline/` **入庫階段**的現行約定：分批時機、冪等性、失敗語意與結束碼。
> 實作於 2026-08-16 完成；規劃文件已依
> [`manage-backlog` skill §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理) 移出 `backlog/`。
>
> **各項設計的理由寫在程式碼的 docstring**（`BaseDataLoader.insert_dataframe()` /
> `finish_load()` / `select_csv_files()`、`DataLoadError`、`tasks.update_db.target_guard()`）。
> 本文件只放**跨檔案的全貌**與新增 updater 時的檢查表，不重複那些說明。

---

## 一、四層流程與入庫時機

pipeline 為 crawler → cleaner → loader → updater 四層：crawler 回傳 DataFrame、
cleaner 落地成 `downloads/<source>/{market}_{YYYYMMDD}.csv`、loader 把 CSV 寫進資料庫、
updater 負責串起流程與決定要處理哪些日期。

**入庫時機是這一層最關鍵的設計選擇。** 「整段日期全部爬完才一次 `add_to_db()`」
會讓中斷成本等於全部重來——2026-08-15 的 margin 回補實際發生過：已爬 3,790 個
CSV，程序中斷後資料庫仍是 0 列。

高風險的三個來源（price／chip／margin）因此改為**每 100 天入庫一次**
（`LOAD_BATCH_SIZE`），中斷最多只損失最後一批。

---

## 二、各 updater 現況對照（2026-08-16）

新增 updater 時對照本表，確認四個欄位都有著落。

| Updater | 入庫時機 | Resume 依據 | 重載防護 | 失敗可見度 |
|---------|----------|-------------|----------|-----------|
| `StockPriceUpdater` | **每 100 天** | DB 最新 `date` +1 | 先查既有鍵再過濾 | `logger.error` |
| `StockChipUpdater` | **每 100 天** | 同上 | `INSERT OR IGNORE` | `DataLoadError` |
| `StockMarginUpdater` | **每 100 天** | 同上 | `INSERT OR IGNORE` | `DataLoadError` |
| `StockDividendUpdater` | 全部跑完 | 同上 | `INSERT OR REPLACE` | `DataLoadError` |
| `MonthlyRevenueReportUpdater` | 全部跑完 | DB 最大年月 +1 | 先查既有鍵再過濾 | `DataLoadError` |
| `FinancialStatementUpdater` | 每種報表一次 | 各表最大年季 +1 | `INSERT OR IGNORE` | `DataLoadError` |
| `FinMindUpdater`（broker_trading） | 逐組合、每 50 組 commit | metadata ＋ DB | 先查既有鍵再過濾 | — |
| `StockTickUpdater` | 全部跑完 | 固定起日 ＋ `tick_metadata.json` | **無**（`keepDuplicates=ALL`） | — |

**未分批的四個並非疏漏**：dividend／mrr／fs 的量級是十餘年 × 數十個年月或年季，
單次執行以分鐘計，中斷重跑的成本可接受。tick 走 DolphinDB，語意與 SQLite 組不同。

**`StockTickUpdater` 是目前唯一沒有重載防護的**：DolphinDB 建表時
`keepDuplicates=ALL` 是 tick 語意的刻意選擇（同一時間戳可以有多筆成交），
代價是同一批 CSV 重複 load 會產生重複 tick，需由入庫流程自行把關。

---

## 三、三個必須守住的性質

### 3.1 冪等：重跑不得產生重複列，也不得被誤判為失敗

loader **每次都掃整個 `downloads/` 目錄**，已入庫的檔案必然會再被送一次。
三種結果要分清楚，否則「重跑」會被當成「出錯」：

| 結果 | 判定 | 處置 |
|------|------|------|
| 整檔 0 列寫入、全部跳過 | 重跑，正常 | 計入「已存在跳過」，不出聲 |
| 部分寫入、部分跳過 | 同鍵不同值，資料可能有衝突 | `logger.warning` 列出檔名 |
| 拋出例外 | 欄位不符、檔案損毀 | 計入失敗，最終讓行程非零結束 |

分批入庫讓「重載已入庫檔案」從偶發變成**每批都會發生**，所以分批與冪等必須成對——
只做分批不做冪等，每批都會撞鍵。

### 3.2 失敗必須浮出來

單檔失敗**不中止整批**（其餘檔案仍該入庫），但整批跑完後若有任何失敗，
`finish_load()` 會拋出 `DataLoadError`，最終讓 `tasks/update_db.py` 以**結束碼 1** 結束
且不印 `✅`。

同時，單一 target 失敗**不中斷其餘 target**（`target_guard()`）——一次
`--target no_tick` 會跑十來個 updater、耗時數小時，若其中一個失敗就中止整批，
等於拿可用性換可見度。

### 3.3 交易日判定不可用「非週末」近似

台股有**補行交易日**（補班的週六照常開市），2013 起就有 11 天。
以 `date.weekday()` 判斷會整天漏掉這些日子。
正確做法是以 `price` 表實際有資料的日期為準（見 `StockMarginUpdater.get_candidate_dates()`）。

---

## 四、四次事故與其教訓

這一節記錄**實際發生過**的問題。它們的價值不在歷史，而在於後續實作者若不知道會重蹈覆轍。

### 4.1 回補中斷 → 資料歸零

margin 回補已爬 3,790 個 CSV 後中斷，DB 仍為 0 列——因為入庫在最後一步。
**教訓**：長時間回補必須分批入庫。已於 `LOAD_BATCH_SIZE` 處理。

### 4.2 入庫失敗被降級成 warning，行程仍回報成功

6,632 個 CSV 中有 2 個入庫失敗，只留下 warning，行程照樣印
`✅ Database Update Completed` 且結束碼 0。缺的 **1,553 列**是事後逐日比對列數才發現的。
**教訓**：`except` 之後不吭聲，比不 catch 更危險。已由 `DataLoadError` ＋ 結束碼處理。

延伸問題：`to_sql(append)` 是整批送出，**一列撞鍵就整檔失敗**。上述 2 個檔案中，
`tpex_20170907.csv` 的 625 列裡只有 1 列撞鍵，卻導致 625 列全部沒進資料庫。
改用 `INSERT OR IGNORE` 之後，撞鍵那列跳過、其餘 624 列照常入庫。

### 4.3 「修好可見度」反而讓日常更新每天失敗

把入庫失敗改成硬失敗之後，日常更新**每次都會以結束碼 1 結束**——loader 每次掃
全目錄，已入庫的 6,632 個檔案全部撞鍵，被當成 6,632 次失敗。
**教訓**：提高失敗可見度之前，得先讓「正常的重複」不算失敗。兩者必須同時做。

### 4.4 沒有市場欄位的主鍵擋不住跨市場代號衝突

`price` 表把上市與上櫃合併存放卻沒有市場欄位。2017-01-17 之前上櫃 ETF 使用 4 碼代號，
與上市股票的代號空間相撞：`6201` 同時是 亞弘電（上市）與 元大富櫃50（上櫃 ETF），
共 992 天；`6202` 89 天。因為 `price` 的主鍵含證券名稱，兩者能並存而不撞鍵、
也沒有任何錯誤訊息。

`margin` 的主鍵是 `(date, stock_id)`，同一情況會直接撞鍵——這正是 4.2 那 2 個檔案失敗的原因。

**教訓**：主鍵若無法唯一識別商品，衝突不是「會不會發生」而是「什麼時候發現」。
資料已修正（`dev/scripts/fix_price_etf_stock_id.py`），並在
`StockQuoteAdapter.warn_duplicate_symbols()` 加了防護，讓同一 bar 內的重複代號不再靜默。

---

## 相關文件

- [指令教學](../commands/command-usage.md)——`update_db` 的完整 target 對照與範例
- [券商分點 NO_DATA 的 metadata 語意](broker-trading-no-data.md)——選型紀錄，尚未實作
- [程式碼品質工具鏈與基線](../dev/code-quality.md)——§二〈例外處理現況〉記錄了全專案 85 條盲捕，4.2 是其中的第一個收斂案例
- [資料覆蓋範圍](../exchanges/data_coverage.md)——各資料來源的時間涵蓋與已知限制
