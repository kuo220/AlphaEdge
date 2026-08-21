# FinMind 爬蟲／清洗／儲存流程優化

## Abstract

- **背景／問題**：FinMind 券商分點資料的 crawl → clean → load 流程存在重複 I/O（每個組合至少讀 2 次 metadata）、全表掃描的「已存在」查詢、每筆組合一次 commit、以及嚴格序列執行等瓶頸，資料表越大越慢。
- **目標**：在**不改動「中斷後重新爬取時能跳過已爬過的資料」語意**的前提下，降低磁碟 I/O、縮小查詢範圍、減少 commit 次數並導入並行爬取。
- **範圍界線**：**不改** resume 判斷依據（仍為 metadata ＋ DB）、不改資料表 schema 語意、不處理 NO_DATA 的 metadata 更新（屬 [券商分點 NO_DATA 的 metadata 語意](../docs/pipeline/broker-trading-no-data.md)，已選型未實作）。
- **驗收標準**：七項優化全部落地或明確標記暫緩，且每項變更後「中斷 → 重跑」皆不會重複爬取已存在的 `(broker_id, stock_id, date)`。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | Metadata 快取（減少重複讀取） | `core/pipeline/updaters/finmind_updater.py` | 中斷後重跑仍跳過已爬組合 | ✅ | 完成於本文件建立進度表之前，未留下當時的驗證紀錄 |
| S2 | Loader「已存在」查詢改為只查該組合 | `core/pipeline/loaders/finmind_loader.py` | 同上；插入結果與全表查詢版本一致 | ✅ | 同上 |
| S3 | Cleaner 可選不寫 CSV | `core/pipeline/cleaners/finmind_cleaner.py` | `write_csv=False` 時 DB 內容與 `True` 時相同 | ⬜ | — |
| S4 | 減少 DB commit 次數（批次 commit） | `core/pipeline/loaders/finmind_loader.py` | 中斷後最多損失最後一個未 commit batch，重跑可補齊 | ✅ | 完成於本文件建立進度表之前，未留下當時的驗證紀錄 |
| S5 | 並行爬取（遵守 API quota） | `core/pipeline/updaters/finmind_updater.py` | quota 未被超用；結果與序列版本一致 | ⬜ | 相依 S1 的 cache；需與 `_check_and_update_api_quota()` 整合 |
| S6 | 批次寫入 DB（進階） | `core/pipeline/loaders/finmind_loader.py` | 同 S2 的一致性檢查 | ⬜ | 相依 S5 |
| S7 | 其他小優化（日誌降頻、移除多餘查詢） | `core/pipeline/updaters/finmind_updater.py` | 人工檢視 log 量下降 | ✅ | 完成於本文件建立進度表之前，未留下當時的驗證紀錄 |
| S8 | 拆分 `finmind_updater.py`／`finmind_loader.py` | `core/pipeline/updaters/finmind/*.py`、`core/pipeline/loaders/finmind/*.py` | `tests/test_finmind_*.py` 五檔全數通過；行為零改變 | ⬜ | 1097 ＋ 859 行，全專案最大單體；**建議在 S5／S6 之前做**，否則並行邏輯會塞進更大的檔案 |

---

## S1. Metadata 快取（減少重複讀取）✅

- **目的**：消除每個組合至少 2 次的 metadata 磁碟讀取。
- **做法**：**現狀**是每個 `(broker_id, stock_id)` 都會呼叫 `_load_broker_trading_metadata()`（updater 迴圈內），且 `_get_existing_dates_from_metadata()` 內部又再讀一次同一份 JSON。改為在雙層迴圈外讀一次 metadata 放進 instance 變數（例如 `_metadata_cache`），迴圈內只讀 cache；僅在「定期更新 metadata」（例如每 100 筆呼叫 `_update_broker_trading_metadata_from_database`）或寫入後要反映進度時，才更新 cache 或重讀檔案。
- **產出**：`core/pipeline/updaters/finmind_updater.py`。
- **驗證方式**：不影響「用 metadata 跳過已爬」的邏輯，只減少 I/O；中斷後重跑仍跳過已爬組合。
- **相依**：無。

## S2. Loader「已存在」查詢改為只查該組合 ✅

- **目的**：避免每次插入前掃描整張表，表越大越慢、記憶體越多。
- **做法**：**現狀**是 `finmind_loader.py` 的 `_load_broker_trading_daily_report_from_dataframe` 每次插入前執行 `SELECT DISTINCT stock_id, date, securities_trader_id FROM table`。改為：
  - 從 df 取唯一的 `(stock_id, securities_trader_id)`；
  - SQL 改為 `WHERE stock_id = ? AND securities_trader_id = ?`（單一組合），多組用 `OR (stock_id = ? AND securities_trader_id = ?)`；
  - 必要時為表加 index：`(stock_id, securities_trader_id, date)` 或至少前兩欄。
- **產出**：`core/pipeline/loaders/finmind_loader.py`。
- **驗證方式**：跳過邏輯不變（仍只插入不重複的 key），不影響中斷後 resume。
- **相依**：無。

## S3. Cleaner 可選不寫 CSV ⬜

- **目的**：流程為 crawl → clean（會寫 `broker_trading/{broker_id}/{stock_id}.csv`）→ 用同一個 DataFrame 直接入 DB；中斷後「跳過已爬」依賴 metadata ＋ DB，不依賴這些 CSV，因此在直接入 DB 的路徑上可省去寫檔。
- **做法**：在 cleaner 加參數（例如 `write_csv: bool = True`），由 updater 呼叫且確定會立刻從 DataFrame 入 DB 時傳 `write_csv=False`，只做欄位檢查與去重、不寫 CSV。
- **產出**：`core/pipeline/cleaners/finmind_cleaner.py`、`core/pipeline/updaters/finmind_updater.py`。
- **驗證方式**：同一批資料在 `write_csv=True` / `False` 兩種模式下，DB 內容逐筆相同；resume 行為不變（仍看 DB ＋ metadata）。
- **相依**：無。

## S4. 減少 DB commit 次數（批次 commit）✅

- **目的**：Loader 原本每插入一個 `(broker_id, stock_id)` 就 `conn.commit()` 一次，commit 開銷過高。
- **做法**：改為每 N 個組合或每 N 秒 commit 一次。
- **產出**：`core/pipeline/loaders/finmind_loader.py`。
- **驗證方式**：若中斷，最多損失最後一個未 commit 的 batch，已 commit 的仍會被 metadata ＋「已存在」查詢跳過，重跑可補齊。
- **相依**：無。

## S5. 並行爬取（在遵守 API quota 下）⬜

- **目的**：**現狀**是嚴格順序，一個組合跑完 crawl → clean → load 才處理下一個，網路延遲無法重疊。
- **做法**：用 `ThreadPoolExecutor` 或 `asyncio` 並行處理多個組合；用 semaphore 控制同時進行的 API 請求數，並與現有 `_check_and_update_api_quota()` 整合。每個 worker 仍先查 metadata（或從 cache 讀）→ 需更新才打 API → clean → 結果放入 queue，再由單一線程或批次寫入 DB。
- **產出**：`core/pipeline/updaters/finmind_updater.py`。
- **驗證方式**：API quota 未被超用；同一組輸入的 DB 結果與序列版本逐筆相同；跳過已爬邏輯不受影響。
- **相依**：S1（worker 需從 cache 讀 metadata）。

## S6. 批次寫入 DB（進階）⬜

- **目的**：把並行爬取的結果合併後一次寫入，減少查詢與 commit 次數。
- **做法**：並行 crawl 多個組合後，多個 DataFrame 先 clean 再合併，累積到一定筆數再呼叫一次 loader；loader 對這批只做一次「已存在」查詢（針對這批出現的 `(stock_id, securities_trader_id)` 用 `WHERE ... IN (...)`），過濾後一次或分批 INSERT，再 commit 一次。
- **產出**：`core/pipeline/loaders/finmind_loader.py`。
- **驗證方式**：同 S2 的一致性檢查；不影響 resume，仍可跳過已存在資料。
- **相依**：S5。

## S7. 其他小優化 ✅

- **目的**：降低非必要的 log 與查詢 I/O。
- **做法**：
  - **日誌**：每個組合都 `logger.info("Processing: trader_id=...")` 改為 `logger.debug` 或每 N 個 log 一次。
  - **成功後查詢**：`_update_broker_trading_daily_report` 成功後呼叫 `SQLiteUtils.get_table_latest_value` 只為 log；改用當次 DataFrame 的 `date` 最大值來 log，或移除／降頻。
- **產出**：`core/pipeline/updaters/finmind_updater.py`。
- **驗證方式**：人工檢視 log 量下降，且不影響任何寫入行為。
- **相依**：無。

## S8. 拆分 `finmind_updater.py`／`finmind_loader.py` ⬜

- **目的**：`core/pipeline/updaters/finmind_updater.py`（**1097 行**）與 `core/pipeline/loaders/finmind_loader.py`（**859 行**）是全專案最大的兩個檔案，遠超其他 updater／loader（次大者 574 行）。單一 `FinMindUpdater` 同時處理券商分點、月營收、財報等多種 FinMind 資料集的 metadata 管理、quota 控制、resume 判斷與寫入協調，已明顯超出單一職責。
  **順序上這步該排在 S5／S6 之前**：並行爬取與批次寫入會再往這兩個檔案加相當份量的程式碼，先拆再加比較省事。
- **做法**：**行為零改變的純搬移**，先按資料集切分，不要按技術層次切：
  1. `core/pipeline/updaters/finmind/` 下依資料集拆檔（券商分點、月營收、財報…），共用的 metadata cache 與 quota 控制抽成 `finmind/common.py`。
  2. `core/pipeline/loaders/finmind/` 同樣處理。
  3. 保留 `FinMindUpdater` / `FinMindLoader` 作為門面（facade），對外介面與 `tasks/update_db.py` 的呼叫方式完全不變。
  - **不做**：不改 resume 語意、不改 metadata 格式、不改 SQL、不改任何欄位處理。
- **產出**：`core/pipeline/updaters/finmind/*.py`、`core/pipeline/loaders/finmind/*.py`。
- **驗證方式**：
  1. `tests/test_finmind_updater.py`、`test_finmind_loader_broker_trading.py`、`test_finmind_pipeline.py`、`test_finmind_api.py`、`test_broker_trading_updater.py` 五檔全數通過。
  2. 拆分前後對同一段日期跑一次增量更新，DB 內容逐筆相同。
  3. 「中斷 → 重跑」仍不重複爬取已存在的 `(broker_id, stock_id, date)`（本文件的共通驗收標準）。
- **相依**：無（但建議排在 S5 之前）。

---

## 關聯與狀態

- **優先級**：P2
- **相關程式**：`core/pipeline/crawlers/finmind_crawler.py`、`core/pipeline/cleaners/finmind_cleaner.py`、`core/pipeline/loaders/finmind_loader.py`、`core/pipeline/updaters/finmind_updater.py`
- **相關文件**：[券商分點 NO_DATA 的 metadata 語意](../docs/pipeline/broker-trading-no-data.md)（選型紀錄；若動工，NO_DATA 的 metadata 處理可與本文件一併減少 API 用量）
