# FinMind 爬蟲／清洗／儲存流程優化計畫

在不改動「中斷後重新爬取時能跳過已爬過的資料」的前提下，可採用的優化方式如下。

---

## 1. Metadata 快取（減少重複讀取）

**現狀**：每個 `(broker_id, stock_id)` 都會呼叫 `_load_broker_trading_metadata()`（updater 迴圈內），且 `_get_existing_dates_from_metadata()` 內部又再讀一次同一份 JSON，等於每個組合至少讀 2 次磁碟。

**作法**：在雙層迴圈外讀一次 metadata 放進 instance 變數（例如 `_metadata_cache`），迴圈內只讀 cache；僅在「定期更新 metadata」（例如每 100 筆呼叫 `_update_broker_trading_metadata_from_database`）或寫入後要反映進度時，才更新 cache 或重讀檔案。

**影響**：不影響「用 metadata 跳過已爬」的邏輯，只減少 I/O。

**狀態**：未實作

---

## 2. Loader「已存在」改為只查該組合（縮小查詢範圍）

**現狀**：`finmind_loader.py` 的 `_load_broker_trading_daily_report_from_dataframe` 每次插入前都執行「查詢整張表」的 SQL（`SELECT DISTINCT stock_id, date, securities_trader_id FROM table`），表越大越慢、記憶體越多。

**作法**：這次要插入的 df 來自單一或少量 `(stock_id, securities_trader_id)`，只需查「這些組合」在表裡已有哪些 date。改為：

- 從 df 取唯一的 `(stock_id, securities_trader_id)`；
- SQL 改為：`WHERE stock_id = ? AND securities_trader_id = ?`（單一組合）或對多組用 `OR (stock_id = ? AND securities_trader_id = ?)`；
- 若有需要，可為表加 index：`(stock_id, securities_trader_id, date)` 或至少前兩欄。

**影響**：跳過邏輯不變（仍只插入不重複的 key），不影響中斷後 resume。

**狀態**：已實作

---

## 3. Cleaner 可選不寫 CSV（僅在「直接入 DB」時）

**現狀**：流程為 crawl → clean（會寫 `broker_trading/{broker_id}/{stock_id}.csv`）→ 用同一個 DataFrame 直接入 DB。中斷後「跳過已爬」是依賴 metadata + DB，不依賴這些 CSV。

**作法**：在 cleaner 加參數（例如 `write_csv: bool = True`），由 updater 呼叫且確定會立刻從 DataFrame 入 DB 時傳 `write_csv=False`，只做欄位檢查與去重、不寫 CSV。

**影響**：不影響 resume（resume 仍看 DB + metadata）。

**狀態**：未實作

---

## 4. 減少 DB commit 次數（批次 commit）

**現狀**：Loader 每插入一個 `(broker_id, stock_id)` 就 `conn.commit()` 一次。

**作法**：改為每 N 個組合或每 N 秒 commit 一次；若中斷，最多少最後一個未 commit 的 batch，已 commit 的仍會被 metadata + 「已存在」查詢跳過。

**影響**：不影響「中斷後跳過已爬」。

**狀態**：未實作

---

## 5. 並行爬取（在遵守 API quota 下）

**現狀**：嚴格順序，一個組合跑完 crawl → clean → load 才處理下一個，網路延遲無法重疊。

**作法**：用 `ThreadPoolExecutor` 或 `asyncio` 並行處理多個組合；用 semaphore 控制同時進行的 API 請求數，並與現有 `_check_and_update_api_quota()` 整合。每個 worker 仍可先查 metadata（或從 cache 讀）→ 需更新才打 API → clean → 結果放入 queue，再由單一線程或批次寫入 DB。

**影響**：不影響「跳過已爬」邏輯。

**狀態**：未實作

---

## 6. 批次寫入 DB（進階）

**作法**：並行 crawl 多個組合後，多個 DataFrame 先 clean 再合併（或分別 clean 再合併），累積到一定筆數再呼叫一次 loader；loader 對這批只做一次「已存在」查詢（可針對這批出現的 `(stock_id, securities_trader_id)` 用 `WHERE ... IN (...)`），過濾後一次或分批 INSERT，再 commit 一次。

**影響**：不影響 resume，仍可跳過已存在資料。

**狀態**：未實作

---

## 7. 其他小優化

- **日誌**：每個組合都 `logger.info("Processing: trader_id=...")` 可改為 `logger.debug` 或每 N 個 log 一次，減少 I/O。
- **成功後查詢**：`_crawl_and_save_broker_trading_daily_report` 成功後呼叫 `SQLiteUtils.get_table_latest_value` 只為 log；可改為用當次 DataFrame 的 `date` 最大值來 log，或移除／降頻。

**狀態**：未實作
