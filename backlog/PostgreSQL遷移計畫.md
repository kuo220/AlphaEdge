# PostgreSQL 遷移計畫

## Abstract

- **背景／問題**：專案目前以 `core/database/stock.db`（SQLite3）為主要儲存，且是「直接耦合」——多處 `import sqlite3` 與 `sqlite3.connect(...)`、SQLite 專屬檢查（`sqlite_master`、`PRAGMA table_info`）、Loader／Updater／API 直接持有 `sqlite3.Connection`、測試大量依賴本地 SQLite 檔案。這不是改連線字串就能解決的問題。
- **目標**：導入 SQLAlchemy Engine 作為統一資料庫介面，分階段把讀取、寫入、測試與部署路徑遷移到 PostgreSQL，並保留可回退方案至少一個版本週期。
- **範圍界線**：**先確保功能等價，再做效能優化**；本次**不做** schema 重新設計、不做分區／讀寫分離、不改業務邏輯與欄位語意；高頻 tick 資料的儲存策略不在本次範圍。
- **驗收標準**：主要流程（資料更新、查詢、回測讀取）在 PostgreSQL 可完整執行；核心 smoke ＋ integration 測試在 PostgreSQL 環境通過；文件與部署配置已更新且可重現；SQLite 依賴已降到可移除或已完全移除。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| P0-1 | `docker-compose.yml` 新增 `postgres` service | `docker-compose.yml` | 本機可連線到 PostgreSQL | ⬜ | 含 volume、healthcheck、port |
| P0-2 | 新增環境變數 `DATABASE_URL` / `DB_BACKEND` | `.env.example`、`core/config.py` | `DATABASE_URL` 可由 `.env` 載入 | ⬜ | — |
| P0-3 | 新增 Python 依賴（`sqlalchemy`、`psycopg`） | `pyproject.toml` / `requirements.txt` | 安裝後可建立 engine | ⬜ | `psycopg[binary]` 與 `psycopg2-binary` 二擇一 |
| P1-1 | 建立 DB 抽象層單一入口 | `core/db/connection.py` | 提供 `get_engine()` / `get_connection()` / `db_dialect()` | ⬜ | **關鍵步驟**，後續所有改造的支點 |
| P1-2 | `DB_PATH` 直連改為經由 engine（含 SQLite fallback） | `core/config.py`、各 API | 不改業務邏輯前提下 API 可讀到資料 | ⬜ | 相依 P1-1；優先讀 `DATABASE_URL`，未設定則 fallback SQLite |
| P2-1 | 改造 `sqlite_utils`（去除 `sqlite_master` / `PRAGMA`） | `core/pipeline/utils/sqlite_utils.py` | 改用 Inspector 後行為等價 | ⬜ | 相依 P1-1；高影響優先改 |
| P2-2 | 改造 Loader／Updater | `core/pipeline/loaders/*.py`、`core/pipeline/updaters/*.py` | 核心 update task 可在 PostgreSQL 跑完 | ⬜ | 相依 P2-1 |
| P2-3 | 改造查詢 API | `core/api/*.py` | price/chip/fs/mrr 查詢結果與 SQLite 一致 | ⬜ | 相依 P2-1 |
| P2-4 | 改造 tasks 腳本 | `tasks/delete_price_data.py` 等 | 可在 PostgreSQL 正常執行 | ⬜ | 相依 P2-1 |
| P3-1 | 選定資料遷移方案（pgloader 或 Python ETL） | 本文件（決策紀錄） | 決策與理由寫入本文件 | ⬜ | 相依 P2-*；中文欄位名稱需特別驗證 |
| P3-2 | 執行一次性資料遷移與完整性比對 | 遷移腳本／指令紀錄 | 每張表 row count 比對、主鍵完整性、抽樣 20 筆查詢一致 | ⬜ | 相依 P3-1 |
| P4-1 | 測試 fixture 改為 PostgreSQL 測試資料庫 | `tests/conftest.py` | 不再直接 patch 檔案型 DB 路徑 | ⬜ | 相依 P2-* |
| P4-2 | 補齊核心路徑測試覆蓋 | `tests/` | `update_db` 各 target、FinMind loader/updater、API 查詢、去重與主鍵衝突 | ⬜ | 相依 P4-1 |
| P5-1 | 灰度：開發環境全面改 PostgreSQL，保留 SQLite fallback | — | 觀察期內無資料不一致 | ⬜ | 相依 P4-2 |
| P5-2 | 移除 SQLite 專屬程式碼與舊路徑 | 全專案 | 全域搜尋無 `import sqlite3` 殘留 | ⬜ | 相依 P5-1；至少保留一個版本週期後再執行 |
| P5-3 | 更新 README 與部署文件 | `README.md`、`README_zh.md`、部署文件 | 團隊可依文件重現部署 | ⬜ | 相依 P5-2 |

---

## 遷移原則

- 將目前以 `core/database/stock.db` 為主的 SQLite 存取，改為 PostgreSQL。
- 先確保「功能等價」再做「效能優化」。
- 採用分階段遷移：先讀取、再寫入、最後清理舊路徑。
- 保留可回退方案（至少一個版本週期）。

## 技術路線

建議導入 SQLAlchemy Engine 作為統一資料庫介面，原因：

- 可以同時支援 SQLite 與 PostgreSQL（有利於過渡期）。
- 與 pandas `read_sql_query` / `to_sql` 搭配成熟。
- 可避免不同 DB driver 在 placeholder 與 transaction 行為差異造成的大量 if/else。

連線字串範例：

- 開發環境：`postgresql+psycopg://postgres:postgres@localhost:5432/alphaedge`
- Docker 內部：`postgresql+psycopg://postgres:postgres@postgres:5432/alphaedge`

---

## Phase 0：準備環境（低風險）

### P0-1. `docker-compose.yml` 新增 `postgres` service ⬜

- **目的**：提供本機與 CI 一致的 PostgreSQL 環境。
- **做法**：新增 `postgres` service，設定 volume（資料持久化）、healthcheck、port mapping。
- **產出**：`docker-compose.yml`。
- **驗證方式**：`docker compose up` 後本機可成功連線到 PostgreSQL。
- **相依**：無。

### P0-2. 新增環境變數 ⬜

- **目的**：讓連線設定可由環境決定，不再寫死路徑。
- **做法**：新增 `DATABASE_URL`（主來源）與 `DB_BACKEND`（可選，用於開關 `sqlite` / `postgres`）。
- **產出**：`.env.example`、`core/config.py`。
- **驗證方式**：`DATABASE_URL` 可由 `.env` 載入並被讀取到。
- **相依**：無。

### P0-3. 新增 Python 依賴 ⬜

- **目的**：具備建立 SQLAlchemy engine 的能力。
- **做法**：新增 `sqlalchemy` 與 `psycopg[binary]`（或 `psycopg2-binary`，二擇一）。
- **產出**：`pyproject.toml` / `requirements.txt`。
- **驗證方式**：安裝後可用 `DATABASE_URL` 建立 engine 並執行 `SELECT 1`。
- **相依**：無。

---

## Phase 1：建立 DB 抽象層（關鍵）

### P1-1. 建立單一入口 `core/db/connection.py` ⬜

- **目的**：所有 DB 存取收斂到單一入口，後續改造才不會散落各處。
- **做法**：提供三個函式——`get_engine()`、`get_connection()`（必要時）、`db_dialect()`（判斷 sqlite/postgresql）。
- **產出**：`core/db/connection.py`。
- **驗證方式**：兩種 backend 下 `get_engine()` 皆可用，`db_dialect()` 回傳正確。
- **相依**：P0-1~P0-3。

### P1-2. `DB_PATH` 直連改為經由 engine ⬜

- **目的**：在不改業務邏輯的前提下切換底層連線來源。
- **做法**：優先讀 `DATABASE_URL`；若未設定則 fallback 到 SQLite（過渡期）。
- **產出**：`core/config.py` 及各處直連點。
- **驗證方式**：不改業務邏輯前提下，API 可透過 engine 讀到資料，結果與改動前一致。
- **相依**：P1-1。

---

## Phase 2：替換 SQLite 專屬語法

### P2-1. 改造 `sqlite_utils` ⬜

- **目的**：這是 SQLite 專屬語法最集中的地方，也是後續所有檔案改造的支點。
- **做法**：
  - `sqlite_master` → 改為 SQLAlchemy Inspector 或 `information_schema` 查詢。
  - `PRAGMA table_info(...)` → 改為 Inspector 欄位檢查。
  - 型別註記 `sqlite3.Connection` → 改為 SQLAlchemy Connection/Engine 或 Protocol。
- **產出**：`core/pipeline/utils/sqlite_utils.py`。
- **驗證方式**：不再依賴 `sqlite_master` 與 `PRAGMA`；既有呼叫端在 SQLite 下行為等價。
- **相依**：P1-1。

### P2-2. 改造 Loader／Updater ⬜

- **目的**：讓寫入路徑脫離 `sqlite3.Connection`。
- **做法**：改用 engine／connection 抽象；placeholder 與 transaction 行為交由 SQLAlchemy 處理。
- **產出**：`core/pipeline/loaders/*.py`、`core/pipeline/updaters/*.py`。
- **驗證方式**：核心 update task 可在 PostgreSQL 正常跑完，且中斷後 resume 行為不變。
- **相依**：P2-1。

### P2-3. 改造查詢 API ⬜

- **目的**：讓讀取路徑脫離 SQLite 專屬型別。
- **做法**：同 P2-2；`pd.read_sql_query` 改吃 engine。
- **產出**：`core/api/*.py`。
- **驗證方式**：price / chip / fs / mrr 查詢在兩種 backend 下結果一致。
- **相依**：P2-1。

### P2-4. 改造 tasks 腳本 ⬜

- **目的**：補齊最後的直連殘留。
- **做法**：同上。
- **產出**：`tasks/delete_price_data.py` 等。
- **驗證方式**：可在 PostgreSQL 正常執行。
- **相依**：P2-1。

---

## Phase 3：資料遷移（一次性）

### P3-1. 選定遷移方案 ⬜

- **目的**：兩個方案的風險與可控程度不同，須先定案。
- **做法**：二選一——
  - **方案 A：pgloader（推薦先嘗試）**。優點是快速、表結構與資料可一次搬運；缺點是轉型規則需驗證，**中文欄位名稱需特別檢查**。

    ```bash
    pgloader sqlite:///absolute/path/to/core/database/stock.db postgresql://postgres:postgres@localhost:5432/alphaedge
    ```

  - **方案 B：Python ETL（可控）**。流程為：SQLite 逐表 `read_sql_query` → 欄位型別修正（日期、整數、浮點）→ 寫入 PostgreSQL（`to_sql` 或 COPY）→ 建立索引與 constraints。
- **產出**：本文件補上決策段落。
- **驗證方式**：先以小表試跑，確認中文欄位名稱與型別無誤後再定案。
- **相依**：P2-1~P2-4。

### P3-2. 執行遷移與完整性比對 ⬜

- **目的**：確保資料一筆不漏、型別無誤。
- **做法**：依 P3-1 選定的方案執行，並建立索引與 constraints。
- **產出**：遷移腳本或指令紀錄。
- **驗證方式**：至少三項——① 每張表 row count 比對；② 主鍵／唯一鍵完整性；③ 抽樣 20 筆關鍵查詢結果一致。
- **相依**：P3-1。

---

## Phase 4：測試與驗證

### P4-1. 測試 fixture 改為 PostgreSQL 測試資料庫 ⬜

- **目的**：現有測試高度依賴 sqlite tempfile，不改造就無法驗證 PostgreSQL 路徑。
- **做法**：將 `sqlite3.connect(temp_db_path)` 改為 PostgreSQL 測試資料庫（docker container ＋ fixture），減少對檔案型 DB 路徑的直接 patch，DB 建立／清理自動化。
- **產出**：`tests/conftest.py`。
- **驗證方式**：既有測試在新 fixture 下可執行。
- **相依**：P2-1~P2-4。

### P4-2. 補齊核心路徑測試覆蓋 ⬜

- **目的**：確保功能等價。
- **做法**：至少覆蓋——`tasks.update_db` 各 target 路徑、FinMind 相關 loader/updater、API 查詢（price/chip/fs/mrr）、重複資料去重與主鍵衝突行為。
- **產出**：`tests/`。
- **驗證方式**：核心 smoke ＋ integration 測試在 PostgreSQL 環境全數通過。
- **相依**：P4-1。

---

## Phase 5：切換與收斂

### P5-1. 灰度切換 ⬜

- **目的**：先在低風險環境驗證，保留回退能力。
- **做法**：開發環境全面改 PostgreSQL，保留 SQLite fallback。
- **產出**：環境設定變更。
- **驗證方式**：觀察期內日更與回測流程無資料不一致。
- **相依**：P4-2。

### P5-2. 移除 SQLite 專屬程式碼 ⬜

- **目的**：收斂維護成本，避免兩套路徑長期並存。
- **做法**：移除 SQLite 專屬程式碼與舊文件；**至少保留一個版本週期的觀察期後再執行**。
- **產出**：全專案。
- **驗證方式**：全域搜尋無 `import sqlite3` 殘留；測試全數通過。
- **相依**：P5-1。

### P5-3. 更新文件與部署配置 ⬜

- **目的**：讓團隊可重現部署。
- **做法**：更新 `README.md` / `README_zh.md` / 部署文件。
- **產出**：上述文件。
- **驗證方式**：依文件從零建置一次可成功。
- **相依**：P5-2。

---

## 風險與對策

| 風險 | 說明 | 對策 |
|------|------|------|
| 型別風險 | SQLite 寬鬆型別 → PostgreSQL 嚴格型別 | 先做欄位型別盤點，遷移前先清洗 |
| 衝突策略風險 | 目前去重策略多在 pandas 層 | 補上 DB 層 unique/PK，必要時改為 upsert（`ON CONFLICT`） |
| 效能風險 | 大表寫入速度變慢 | 批次寫入、COPY、索引延後建立、分批 commit |
| 測試風險 | 現有測試高度依賴 sqlite tempfile | 建立 PostgreSQL 測試 fixture，DB 建立／清理自動化 |

---

## 關聯與狀態

- **優先級**：P3（影響面廣，建議在其他重構收斂後再動）
- **相關程式**：`core/pipeline/utils/sqlite_utils.py`、`core/pipeline/loaders/*`、`core/pipeline/updaters/*`、`core/api/*`、`core/config.py`、`tasks/*`、`tests/`
- **相關 backlog**：[FinMind爬蟲清洗儲存流程優化.md](FinMind爬蟲清洗儲存流程優化.md)（S2、S6 的批次寫入與查詢優化會被本計畫的抽象層影響，建議先後不要交錯）
