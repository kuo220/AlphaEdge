# FinMind 爬蟲／清洗／儲存流程優化

## Abstract

- **背景／問題**：FinMind 券商分點資料的 crawl → clean → load 流程存在重複 I/O（每個組合至少讀 2 次 metadata）、全表掃描的「已存在」查詢、每筆組合一次 commit、以及嚴格序列執行等瓶頸，資料表越大越慢。
- **目標**：在**不改動「中斷後重新爬取時能跳過已爬過的資料」語意**的前提下，降低磁碟 I/O、縮小查詢範圍、減少 commit 次數並導入並行爬取。
- **範圍界線**：**不改** resume 判斷依據（仍為 metadata ＋ DB）、不改資料表 schema 語意、不處理 NO_DATA 的 metadata 更新（屬 [券商分點 NO_DATA 的 metadata 語意](../docs/pipeline/broker-trading-no-data.md)，已選型未實作）。
- **驗收標準**：全部步驟落地或明確標記暫緩，且每項變更後「中斷 → 重跑」皆不會重複爬取已存在的 `(broker_id, stock_id, date)`。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | Metadata 快取（減少重複讀取） | `core/pipeline/tw/updaters/finmind_updater.py` | 中斷後重跑仍跳過已爬組合 | ✅ | 完成於本文件建立進度表之前，未留下當時的驗證紀錄 |
| S2 | Loader「已存在」查詢改為只查該組合 | `core/pipeline/tw/loaders/finmind_loader.py` | 同上；插入結果與全表查詢版本一致 | ✅ | 同上 |
| S3 | Cleaner 可選不寫 CSV | `core/pipeline/tw/cleaners/finmind_cleaner.py` | `write_csv=False` 時 DB 內容與 `True` 時相同 | ⬜ | — |
| S4 | 減少 DB commit 次數（批次 commit） | `core/pipeline/tw/loaders/finmind_loader.py` | 中斷後最多損失最後一個未 commit batch，重跑可補齊 | ✅ | 完成於本文件建立進度表之前，未留下當時的驗證紀錄 |
| S5 | 並行爬取（遵守 API quota） | `core/pipeline/tw/updaters/finmind/broker_trading_updater.py` | quota 未被超用；結果與序列版本一致 | ⬜ | 相依 S1 的 cache；需與 `_check_and_update_api_quota()` 整合 |
| S6 | 批次寫入 DB（進階） | `core/pipeline/tw/loaders/finmind/broker_trading_loader.py` | 同 S2 的一致性檢查 | ⬜ | 相依 S5 |
| S7 | 其他小優化（日誌降頻、移除多餘查詢） | `core/pipeline/tw/updaters/finmind_updater.py` | 人工檢視 log 量下降 | ✅ | 完成於本文件建立進度表之前，未留下當時的驗證紀錄 |
| S8 | 拆分 `finmind_updater.py`／`finmind_loader.py` | `core/pipeline/tw/updaters/finmind/*.py`、`core/pipeline/tw/loaders/finmind/*.py` | 新增 `tests/test_finmind_broker_trading_batch.py` 4 條護欄；拆分前後行為逐項比對 | ✅ | **2026-09-01 完成**：最大單檔由 1097 降為 483 行。**原定的「五檔測試全數通過」不是有效驗收**，理由見完成紀錄 |
| S9 | 合併 `loaders/finmind/` 三個重複的 `load_*` | `core/pipeline/tw/loaders/finmind/*.py` | 既有測試全綠；三張表的入庫列數與訊息不變 | ⬜ | S8 刻意沒做（超出「純搬移」）；三支約 85% 重複 |

---

## S1. Metadata 快取（減少重複讀取）✅

- **目的**：消除每個組合至少 2 次的 metadata 磁碟讀取。
- **做法**：**現狀**是每個 `(broker_id, stock_id)` 都會呼叫 `_load_broker_trading_metadata()`（updater 迴圈內），且 `_get_existing_dates_from_metadata()` 內部又再讀一次同一份 JSON。改為在雙層迴圈外讀一次 metadata 放進 instance 變數（例如 `_metadata_cache`），迴圈內只讀 cache；僅在「定期更新 metadata」（例如每 100 筆呼叫 `_update_broker_trading_metadata_from_database`）或寫入後要反映進度時，才更新 cache 或重讀檔案。
- **產出**：`core/pipeline/tw/updaters/finmind_updater.py`。
- **驗證方式**：不影響「用 metadata 跳過已爬」的邏輯，只減少 I/O；中斷後重跑仍跳過已爬組合。
- **相依**：無。

## S2. Loader「已存在」查詢改為只查該組合 ✅

- **目的**：避免每次插入前掃描整張表，表越大越慢、記憶體越多。
- **做法**：**現狀**是 `finmind_loader.py` 的 `_load_broker_trading_daily_report_from_dataframe` 每次插入前執行 `SELECT DISTINCT stock_id, date, securities_trader_id FROM table`。改為：
  - 從 df 取唯一的 `(stock_id, securities_trader_id)`；
  - SQL 改為 `WHERE stock_id = ? AND securities_trader_id = ?`（單一組合），多組用 `OR (stock_id = ? AND securities_trader_id = ?)`；
  - 必要時為表加 index：`(stock_id, securities_trader_id, date)` 或至少前兩欄。
- **產出**：`core/pipeline/tw/loaders/finmind_loader.py`。
- **驗證方式**：跳過邏輯不變（仍只插入不重複的 key），不影響中斷後 resume。
- **相依**：無。

## S3. Cleaner 可選不寫 CSV ⬜

- **目的**：流程為 crawl → clean（會寫 `broker_trading/{broker_id}/{stock_id}.csv`）→ 用同一個 DataFrame 直接入 DB；中斷後「跳過已爬」依賴 metadata ＋ DB，不依賴這些 CSV，因此在直接入 DB 的路徑上可省去寫檔。
- **做法**：在 cleaner 加參數（例如 `write_csv: bool = True`），由 updater 呼叫且確定會立刻從 DataFrame 入 DB 時傳 `write_csv=False`，只做欄位檢查與去重、不寫 CSV。
- **產出**：`core/pipeline/tw/cleaners/finmind_cleaner.py`、`core/pipeline/tw/updaters/finmind_updater.py`。
- **驗證方式**：同一批資料在 `write_csv=True` / `False` 兩種模式下，DB 內容逐筆相同；resume 行為不變（仍看 DB ＋ metadata）。
- **相依**：無。

## S4. 減少 DB commit 次數（批次 commit）✅

- **目的**：Loader 原本每插入一個 `(broker_id, stock_id)` 就 `conn.commit()` 一次，commit 開銷過高。
- **做法**：改為每 N 個組合或每 N 秒 commit 一次。
- **產出**：`core/pipeline/tw/loaders/finmind_loader.py`。
- **驗證方式**：若中斷，最多損失最後一個未 commit 的 batch，已 commit 的仍會被 metadata ＋「已存在」查詢跳過，重跑可補齊。
- **相依**：無。

## S5. 並行爬取（在遵守 API quota 下）⬜

- **目的**：**現狀**是嚴格順序，一個組合跑完 crawl → clean → load 才處理下一個，網路延遲無法重疊。
- **做法**：用 `ThreadPoolExecutor` 或 `asyncio` 並行處理多個組合；用 semaphore 控制同時進行的 API 請求數，並與現有 `_check_and_update_api_quota()` 整合。每個 worker 仍先查 metadata（或從 cache 讀）→ 需更新才打 API → clean → 結果放入 queue，再由單一線程或批次寫入 DB。
- **產出**：`core/pipeline/tw/updaters/finmind_updater.py`。
- **驗證方式**：API quota 未被超用；同一組輸入的 DB 結果與序列版本逐筆相同；跳過已爬邏輯不受影響。
- **相依**：S1（worker 需從 cache 讀 metadata）。

## S6. 批次寫入 DB（進階）⬜

- **目的**：把並行爬取的結果合併後一次寫入，減少查詢與 commit 次數。
- **做法**：並行 crawl 多個組合後，多個 DataFrame 先 clean 再合併，累積到一定筆數再呼叫一次 loader；loader 對這批只做一次「已存在」查詢（針對這批出現的 `(stock_id, securities_trader_id)` 用 `WHERE ... IN (...)`），過濾後一次或分批 INSERT，再 commit 一次。
- **產出**：`core/pipeline/tw/loaders/finmind_loader.py`。
- **驗證方式**：同 S2 的一致性檢查；不影響 resume，仍可跳過已存在資料。
- **相依**：S5。

## S7. 其他小優化 ✅

- **目的**：降低非必要的 log 與查詢 I/O。
- **做法**：
  - **日誌**：每個組合都 `logger.info("Processing: trader_id=...")` 改為 `logger.debug` 或每 N 個 log 一次。
  - **成功後查詢**：`_update_broker_trading_daily_report` 成功後呼叫 `SQLiteUtils.get_table_latest_value` 只為 log；改用當次 DataFrame 的 `date` 最大值來 log，或移除／降頻。
- **產出**：`core/pipeline/tw/updaters/finmind_updater.py`。
- **驗證方式**：人工檢視 log 量下降，且不影響任何寫入行為。
- **相依**：無。

## S8. 拆分 `finmind_updater.py`／`finmind_loader.py` ✅

- **目的**：`core/pipeline/tw/updaters/finmind_updater.py`（**1097 行**）與 `core/pipeline/tw/loaders/finmind_loader.py`（**859 行**）是全專案最大的兩個檔案，遠超其他 updater／loader（次大者 574 行）。單一 `FinMindUpdater` 同時處理券商分點、月營收、財報等多種 FinMind 資料集的 metadata 管理、quota 控制、resume 判斷與寫入協調，已明顯超出單一職責。
  **順序上這步該排在 S5／S6 之前**：並行爬取與批次寫入會再往這兩個檔案加相當份量的程式碼，先拆再加比較省事。
- **做法**：**行為零改變的純搬移**，先按資料集切分，不要按技術層次切：
  1. `core/pipeline/tw/updaters/finmind/` 下依資料集拆檔（券商分點、月營收、財報…），共用的 metadata cache 與 quota 控制抽成 `finmind/common.py`。
  2. `core/pipeline/tw/loaders/finmind/` 同樣處理。
  3. 保留 `FinMindUpdater` / `FinMindLoader` 作為門面（facade），對外介面與 `tasks/update_db.py` 的呼叫方式完全不變。
  - **不做**：不改 resume 語意、不改 metadata 格式、不改 SQL、不改任何欄位處理。
- **產出**：`core/pipeline/tw/updaters/finmind/*.py`、`core/pipeline/tw/loaders/finmind/*.py`。
- **驗證方式**：
  1. `tests/test_finmind_updater.py`、`test_finmind_loader_broker_trading.py`、`test_finmind_pipeline.py`、`test_finmind_api.py`、`test_broker_trading_updater.py` 五檔全數通過。
  2. 拆分前後對同一段日期跑一次增量更新，DB 內容逐筆相同。
  3. 「中斷 → 重跑」仍不重複爬取已存在的 `(broker_id, stock_id, date)`（本文件的共通驗收標準）。
- **相依**：無（但建議排在 S5 之前）。

> **✅ 完成紀錄（2026-09-01）**
>
> **⚠️ 原定的驗收方式無效，已換掉**：`tests/test_broker_trading_updater.py` 把整段
> 測試包在 `try/except` 裡、失敗時 `return False`，pytest 只會發一個
> `PytestReturnNotNoneWarning` 並判定 **passed**——那一檔永遠不會紅。實際檢查還發現
> 它呼叫的 `update_broker_trading_daily_report(stock_id=..., securities_trader_id=...)`
> 與現行簽名不符、也用到不存在的 `_check_and_update_api_quota`，全被 except 吞掉。
> 拿它當「行為零改變」的證據等於沒有證據。
>
> **改用的驗收**（三道，皆為真的會失敗的檢查）：
> 1. **新增 `tests/test_finmind_broker_trading_batch.py`（4 條，完全離線）**：逐組合送出請求、
>    資料入庫、metadata 記錄日期範圍、**重跑不重複爬取**、區間往後延伸只爬新日期。
>    **先在拆分前的程式碼上跑過一次**（4 passed），拆完再跑一次，結果相同。
> 2. **搬移過的每個方法與 `HEAD` 版本逐行比對**（把 `self.X` 正規化成新的接收者後 diff）：
>    批量迴圈、單組合更新、quota 兩支、清單查詢兩支、metadata 三支——**差異全部是
>    docstring、註解與 ruff 換行，沒有任何一行可執行程式碼不同**。
> 3. **公開介面比對**：`FinMindUpdater`／`FinMindLoader` 的 public 方法**一個沒少**；
>    移走的 14 個全是 `_` 開頭的私有方法。`api_quota_limit` 由 instance 屬性改為
>    property（存取寫法不變，狀態改放在 `FinMindContext`）。
>
> **拆出來的結構**
>
> | 檔案 | 行數 | 內容 |
> |------|-----:|------|
> | `updaters/finmind_updater.py`（門面） | 223 | 對外介面、`update()` 分派、`update_all()` |
> | `updaters/finmind/common.py` | 483 | `FinMindContext`（ETL 三件組 ＋ 連線 ＋ **quota**）、`BrokerTradingMetadataStore` |
> | `updaters/finmind/broker_trading_updater.py` | 417 | 券商分點批量迴圈 ＋ 單組合更新 |
> | `updaters/finmind/stock_info_updater.py` | 86 | 台股總覽（含／不含權證） |
> | `updaters/finmind/broker_info_updater.py` | 49 | 證券商資訊 |
> | `loaders/finmind_loader.py`（門面） | 172 | 連線、建表協調、四個 `load_*` 的轉呼叫 |
> | `loaders/finmind/broker_trading_loader.py` | 343 | DataFrame 直入 ＋ CSV 目錄批次 |
> | `loaders/finmind/stock_info_loader.py` | 179 | 台股總覽兩張表的 CSV 入庫 |
> | `loaders/finmind/schema.py` | 138 | 四張表的建表與索引 |
> | `loaders/finmind/broker_info_loader.py` | 96 | 證券商資訊的 CSV 入庫 |
>
> **兩個實作決定**
> 1. **updater 用 context 物件、loader 用模組層級函式**。loader 的 `connect()`／
>    `disconnect()` 會換掉 `self.conn`，子模組若把連線存成自己的屬性，斷線重連後
>    會拿著已關閉的連線；改成吃 `conn` 參數的純函式就沒有這個狀態問題。
>    updater 沒有這個模式，且四個資料集要共享 quota 狀態，故用 `FinMindContext`。
> 2. **quota 放 `common.py`**：四個資料集打同一把 FinMind token，quota 是共享資源。
>
> **刻意沒做**（本步驟只搬不改）：`loaders/finmind/` 的三個 `load_*`（台股總覽、
> 含權證、證券商）有約 85% 重複——同一套「讀 CSV → 查已存在主鍵 → 去重 → 指定欄位序
> → append」，只有表名、CSV 檔名與去重鍵不同。合併成一支參數化函式是明顯的下一步，
> 但那已超出「行為零改變的純搬移」，**另立步驟再做**。

---

## S9. 合併 `loaders/finmind/` 三個重複的 `load_*` ⬜

- **目的**：`load_stock_info()`、`load_stock_info_with_warrant()`、`load_broker_info()`
  是同一套流程的三份複本（讀 CSV → 查 DB 已存在主鍵 → 檔內去重 → 過濾新資料 →
  指定欄位順序 → `to_sql(append)` → 統計 log），約 85% 逐字相同，只有**四個東西**不同：
  資料表名、CSV 檔名、去重主鍵欄、欄位順序。改一處要記得改三處，是典型的漂移來源。
- **做法**：抽成一支參數化函式（例如 `load_reference_table(conn, spec)`，`spec` 帶上述四項），
  三個既有函式改為薄封裝以保留各自的 log 措辭。**log 文字必須逐字保留**——那是回補時
  唯一的進度依據。
- **產出**：`core/pipeline/tw/loaders/finmind/stock_info_loader.py`、`broker_info_loader.py`。
- **驗證方式**：`tests/test_finmind_pipeline.py` 與 `tests/test_finmind_broker_trading_batch.py`
  全綠；以同一份 CSV 跑三張表的入庫，列數與 log 訊息與合併前相同。
- **相依**：S8（✅）。

---

## 關聯與狀態

- **優先級**：P2
- **相關程式**：`core/pipeline/tw/crawlers/finmind_crawler.py`、`core/pipeline/tw/cleaners/finmind_cleaner.py`、`core/pipeline/tw/loaders/finmind_loader.py`、`core/pipeline/tw/updaters/finmind_updater.py`
- **相關文件**：[券商分點 NO_DATA 的 metadata 語意](../docs/pipeline/broker-trading-no-data.md)（選型紀錄；若動工，NO_DATA 的 metadata 處理可與本文件一併減少 API 用量）
