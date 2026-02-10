# Broker Trading 索引與 SQLite 鎖競爭修正

券商分點批次更新時，在 `log_progress_and_update_metadata()` 印出進度後可能卡住。原因：(1) metadata 用的 `GROUP BY securities_trader_id, stock_id` 查詢缺合適索引；(2) `self.loader.conn` 未 commit 的寫入與 `self.conn` 的 SELECT 造成 SQLite 鎖競爭。

---

## 1. 索引：在 _create_broker_trading_daily_report_table 內處理，create_missing_tables 照舊（解耦）

**檔案:** `trader/pipeline/loaders/finmind_loader.py`

**做法（解耦）：**

- **`_create_broker_trading_daily_report_table()`** 負責「表 + 索引」：
  - 維持現有 `CREATE TABLE IF NOT EXISTS ...` 與 `self.conn.commit()`。
  - 在該方法內、commit 之後，再執行 `CREATE INDEX IF NOT EXISTS idx_broker_trading_secid_stock_date ON {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} (securities_trader_id, stock_id, date);`（必要時再 commit）。不需額外「判斷要不要創建索引」—`IF NOT EXISTS` 已具備 idempotent，有則略過、無則建立。
- **`create_missing_tables()`** 照舊的呼叫方式，只做一處調整：對 broker trading 表**改為每次都呼叫** `_create_broker_trading_daily_report_table()`，而不是僅在「表不存在」時才呼叫。如此一來：
  - 新 DB：表與索引在第一次呼叫時一併建立。
  - 舊 DB（表在、索引不在）：每次跑 `create_missing_tables()` 都會呼叫該方法，方法內 `CREATE INDEX IF NOT EXISTS` 會補建索引；之後再跑為 no-op。
  - 不在 `create_missing_tables()` 裡加任何 inline 的 CREATE INDEX，索引邏輯只存在於 `_create_broker_trading_daily_report_table()`，職責單一、較解耦。

**效果:** 索引要不要建、怎麼建都封裝在「建表」方法內；上層只負責「確保 broker trading 表（含索引）存在」時呼叫同一方法即可。

**狀態:** 已實作

---

## 3. 避免 metadata 更新時的 SQLite 鎖競爭（卡住）

**檔案:** `trader/pipeline/updaters/finmind_updater.py`

- 在 `log_progress_and_update_metadata()` 內，**在**呼叫 `self._update_broker_trading_metadata_from_database()` **之前**：
  - 當 `processed_count % self.BATCH_UPDATE_METADATA_INTERVAL == 0` 時，若 `self.loader.conn` 存在則先執行 `self.loader.conn.commit()`，再呼叫 `_update_broker_trading_metadata_from_database()`。
- 讓 `self.conn` 的 SELECT 不會被 `self.loader.conn` 的未提交寫入擋住。

**狀態:** 已實作

### 3.1 評估：commit 頻率與爬蟲速度

- **是否要降低 commit 頻率？**
  - 目前每 50 筆 commit 一次（`BATCH_COMMIT_INTERVAL`）。降低頻率（例如改為 100 或 200）可減少磁碟 I/O，理論上能加快寫入；代價是程式中斷時，最後未 commit 的那段會遺失（例如 100 筆而非 50 筆）。若可接受，可適度調高 `BATCH_COMMIT_INTERVAL`。
  - 不論頻率為何，**在執行 metadata 更新前一定要先 commit**，否則仍會鎖競爭卡住；此項不可省略。

- **其他可加快爬蟲的方式：**
  - **本 backlog 的索引（項目 1）**：讓 `_update_broker_trading_metadata_from_database()` 的 `GROUP BY` 查詢變快，每 500 筆那次的停頓會明顯縮短。
  - **提高 metadata 更新間隔**：將 `BATCH_UPDATE_METADATA_INTERVAL` 從 500 調大（例如 1000～2000），可減少「整表 GROUP BY」的次數，整體爬蟲會更快，但中斷時 metadata 落後筆數較多（resume 仍正確，只是進度檔較不即時）。
  - **先做鎖競爭修正（項目 3）與索引**，再視實測結果決定是否調整 `BATCH_COMMIT_INTERVAL` 或 `BATCH_UPDATE_METADATA_INTERVAL`，較穩妥。

---

## 驗證建議

- 新環境：建立表後檢查該表是否有 `idx_broker_trading_secid_stock_date`（例如 `PRAGMA index_list(...)` 或 DB 工具）。
- 舊環境：不刪 DB，跑一次 `python -m tasks.update_db --target broker_trading`，再檢查索引是否存在。
- 卡住：跑較多筆（例如超過 500 筆）觀察是否還會在 Progress log 後卡住。
