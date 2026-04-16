# AlphaEdge SQLite -> PostgreSQL 遷移計畫

本文件提供 `AlphaEdge` 專案由 SQLite3 遷移到 PostgreSQL 的實作指引，目標是降低中斷風險，並能分階段上線。

## 1. 遷移目標與原則

- 將目前以 `trader/database/data.db` 為主的 SQLite 存取，改為 PostgreSQL。
- 先確保「功能等價」再做「效能優化」。
- 採用分階段遷移：先讀取、再寫入、最後清理舊路徑。
- 保留可回退方案（至少一個版本週期）。

## 2. 目前專案現況（為何不是只改連線字串）

目前專案中 SQLite 使用是「直接耦合」：

- 多處使用 `import sqlite3` 與 `sqlite3.connect(...)`。
- 有 SQLite 專屬檢查邏輯（例如 `sqlite_master`、`PRAGMA table_info`）。
- 多個 Loader / Updater / API 都直接持有 `sqlite3.Connection`。
- 測試大量使用本地 SQLite 檔案（含 `temp_db_path` patch）。

因此，這次遷移屬於中等偏高工作量，需要一個穩定的抽象層與分批改造。

## 3. 建議技術路線

建議導入 SQLAlchemy Engine 作為統一資料庫介面，原因：

- 可以同時支援 SQLite 與 PostgreSQL（有利於過渡期）。
- 與 pandas `read_sql_query` / `to_sql` 搭配成熟。
- 可避免不同 DB driver 在 placeholder 與 transaction 行為差異造成的大量 if/else。

建議連線字串範例：

- 開發環境：`postgresql+psycopg://postgres:postgres@localhost:5432/alphaedge`
- Docker 內部：`postgresql+psycopg://postgres:postgres@postgres:5432/alphaedge`

## 4. 分階段實作計畫

## Phase 0：準備環境（低風險）

1. 在 `docker-compose.yml` 新增 `postgres` service（volume、healthcheck、port）。
2. 新增環境變數：
   - `DATABASE_URL`（主來源）
   - `DB_BACKEND`（可選，用於開關 `sqlite/postgres`）
3. 新增 Python 依賴：
   - `sqlalchemy`
   - `psycopg[binary]`（或 `psycopg2-binary`，二擇一）

交付檢查：

- 本機可成功連線到 PostgreSQL。
- `DATABASE_URL` 可由 `.env` 載入。

## Phase 1：建立 DB 抽象層（關鍵）

建立單一入口（例如 `trader/db/connection.py`）：

- 提供 `get_engine()`。
- 提供 `get_connection()`（必要時）。
- 提供 `db_dialect()`（判斷 sqlite/postgresql）。

將現有 `DB_PATH` 直連邏輯轉為：

- 優先讀 `DATABASE_URL`。
- 若未設定則 fallback 到 SQLite（過渡期）。

交付檢查：

- 不改業務邏輯前提下，API 可透過 engine 讀到資料。

## Phase 2：替換 SQLite 專屬語法

需要處理的 SQLite 專屬點：

- `sqlite_master` -> 改為 SQLAlchemy Inspector 或 `information_schema` 查詢。
- `PRAGMA table_info(...)` -> 改為 Inspector 欄位檢查。
- 型別註記 `sqlite3.Connection` -> 改為 SQLAlchemy Connection/Engine 或 Protocol。

建議優先改檔（高影響）：

- `trader/pipeline/utils/sqlite_utils.py`
- `trader/pipeline/loaders/*.py`
- `trader/pipeline/updaters/*.py`
- `trader/api/*.py`
- `tasks/delete_price_data.py`

交付檢查：

- 不再依賴 `sqlite_master` 與 `PRAGMA`。
- 核心 update task 可在 PostgreSQL 正常跑完。

## Phase 3：資料遷移（一次性）

### 方案 A：pgloader（推薦先嘗試）

優點：快速、表結構與資料可一次搬運。  
缺點：轉型規則需驗證，中文欄位名稱需特別檢查。

範例：

```bash
pgloader sqlite:///absolute/path/to/trader/database/data.db postgresql://postgres:postgres@localhost:5432/alphaedge
```

### 方案 B：Python ETL（可控）

流程：

1. SQLite 逐表 `read_sql_query`
2. 欄位型別修正（日期、整數、浮點）
3. 寫入 PostgreSQL（`to_sql` 或 COPY）
4. 建立索引與 constraints

交付檢查（至少）：

- 每張表 row count 比對
- 主鍵/唯一鍵完整性
- 抽樣 20 筆關鍵查詢結果一致

## Phase 4：測試與驗證

需要調整測試策略：

- 將 `sqlite3.connect(temp_db_path)` 改為 PostgreSQL 測試資料庫（可用 docker container + fixture）。
- 減少對檔案型 DB 路徑的直接 patch。

至少要覆蓋：

- `tasks.update_db` 各 target 路徑
- `FinMind` 相關 loader/updater
- API 查詢（price/chip/fs/mrr）
- 重複資料去重與主鍵衝突行為

## Phase 5：切換與收斂

1. 先灰度：開發環境全面改 PostgreSQL，保留 SQLite fallback。
2. 觀察一段時間後，移除 SQLite 專屬程式碼與舊文件。
3. 更新 `README.md` / `README_zh.md` / 部署文件。

## 5. 風險與對策

- 型別風險：SQLite 寬鬆型別 -> PostgreSQL 嚴格型別  
  對策：先做欄位型別盤點，遷移前先清洗。

- 衝突策略風險：目前去重策略多在 pandas 層  
  對策：補上 DB 層 unique/PK，必要時改為 upsert（`ON CONFLICT`）。

- 效能風險：大表寫入速度變慢  
  對策：批次寫入、COPY、索引延後建立、分批 commit。

- 測試風險：現有測試高度依賴 sqlite tempfile  
  對策：建立 PostgreSQL 測試 fixture，將 DB 建立/清理自動化。

## 6. 建議時程（可調）

- Day 1-2：Phase 0-1（環境 + 抽象層）
- Day 3-4：Phase 2（核心 loader/updater/api 改造）
- Day 5：Phase 3（資料遷移演練）
- Day 6：Phase 4（整合測試與回歸）
- Day 7：Phase 5（文件與正式切換）

## 7. Definition of Done

符合以下條件才算遷移完成：

- 專案主要流程在 PostgreSQL 可完整執行（更新資料、查詢、回測流程相關讀取）。
- 測試可在 PostgreSQL 環境通過（至少核心 smoke + integration）。
- 文件與部署配置已更新，團隊可重現部署。
- SQLite 依賴已降到可移除或已完全移除。

---

若要落地實作，建議先從「建立 DB 抽象層 + 改寫 `sqlite_utils`」開始，這會是後續所有檔案改造的支點。
