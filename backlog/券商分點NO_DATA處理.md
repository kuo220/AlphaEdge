# 券商分點 API 回傳 NO_DATA 的處理

## Abstract

- **背景／問題**：爬取券商分點日報時，若 API 回傳無資料（NO_DATA），目前**不會**更新 metadata，導致下次執行用同一段日期再請求一次，浪費 API 額度並讓 log 重複出現 "No data available"。
- **目標**：定案一套「已請求過的區間不再重複請求」的 metadata 語意，讓 NO_DATA 的進度也能被記錄與續跑。
- **範圍界線**：**本文件目前只做方案紀錄與選型，暫不實作程式碼變更**；不改資料表 schema、不改 crawl/clean/load 流程本身。
- **驗收標準**：三個方案的語意、優缺點與合併規則已寫清楚，並選出建議方案；待決定實作時，S2 之後的步驟才啟動。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 方案盤點與選型（做法一／二／三） | 本文件 | 三方案語意與合併規則寫清楚，並給出建議 | ✅ | 建議做法一（`last_attempted_date`）；驗證方式為人工檢視 |
| S2 | metadata 新增 `last_attempted_date` 欄位與讀寫邏輯 | `core/pipeline/updaters/finmind_updater.py` | NO_DATA 後重跑不再請求同區間 | ⏸ | 暫緩：僅紀錄做法，尚未決定實作時程 |
| S3 | 「從 DB 更新 metadata」時保留 `last_attempted_date` | 同上 | 從 DB 回寫後該欄位未被覆寫 | ⏸ | 相依 S2 |
| S4 | metadata 清理邏輯排除「曾請求過但無資料」的組合 | 同上 | 該類組合不被刪除，下次不會從頭請求 | ⏸ | 相依 S2 |
| S5 | （可選）延遲重試 `recheck_no_data_after_days` | 同上 | 超過 N 天的 NO_DATA 區間會被重試一次 | ⏸ | 相依 S2；用於涵蓋資料延遲上架 |

> **⏸ 暫緩說明（2026-08-01）**
> - 已完成：S1 方案盤點與選型。
> - 暫緩原因：本文件原始定位即為「僅紀錄做法與業界慣例，不做程式碼變更」，尚未決定實作時程。
> - 解除條件：確認要省下 API 額度、或 NO_DATA 重複請求開始影響日更時間時，啟動 S2。

---

## 問題

- 爬取券商分點日報時，若 API 回傳**無資料**（NO_DATA），目前**不會**更新 metadata。
- 下次執行時會用同一段日期再請求一次，造成：
  - 浪費 API 額度
  - log 重複出現 "No data available"

---

## S1. 方案盤點與選型 ✅

- **目的**：在動程式碼前先把 metadata 語意定清楚，避免「已檢查到哪」與「有資料到哪」兩個概念混淆後難以回頭。
- **做法**：盤點三個做法（詳見下方三節），比較語意清晰度、實作成本與被覆寫的風險。
- **產出**：本文件。
- **驗證方式**：人工檢視——三方案的合併規則（尤其「從 DB 更新 metadata」時如何不覆寫）皆已寫明。
- **相依**：無。
- **結論**：
  - **建議實作**：做法一（`last_attempted_date`），語意清楚、易維護。
  - **可選**：做法三（延遲重試），依需求設定 `recheck_no_data_after_days`。
  - 做法二可作為改動最小的替代，但需明確規定 metadata 與 DB 的合併規則。

### 做法一：在 metadata 增加 `last_attempted_date`（推薦）

**概念**

- 每個 `(broker_id, stock_id)` 除了 `earliest_date` / `latest_date`（來自 DB），再多一個 **`last_attempted_date`**（或 `last_checked_date`）。
- **語意**：
  - `latest_date`：DB 裡「有資料」到哪一天。
  - `last_attempted_date`：已向 API「請求過」到哪一天（含 NO_DATA 的區間）。

**邏輯**

1. **決定請求區間時**：起始日 = `max(latest_date + 1, last_attempted_date + 1)`，避免重複請求已知無資料的區間。
2. **API 回傳有資料並寫入 DB 時**：照現有流程從 DB 更新 `earliest_date` / `latest_date`；並可將本次請求的 end_date 寫入 `last_attempted_date`。
3. **API 回傳 NO_DATA 時**：不寫 DB，但**要更新 metadata**——將該組合的 `last_attempted_date` 設為本次請求的 **end_date**。
4. **從 DB 更新 metadata 時**（`_update_broker_trading_metadata_from_database`）：從 DB 寫入的只有 `earliest_date` / `latest_date`，須**保留**既有的 `last_attempted_date`（不覆寫）。
5. **清理 metadata 時**：若某 `(broker_id, stock_id)` 在 DB 沒有任何一筆，但 metadata 裡有 `last_attempted_date`，**不要刪除**該筆 metadata（代表「曾請求過但無資料」），避免下次又從頭請求。

**優缺點**

- **優點**：語意清楚、不會重複打已知無資料的區間、可明顯減少 API 用量。
- **注意**：若資料會「延遲上架」，可能漏掉；可搭配做法三或定期 backfill。

### 做法二：NO_DATA 時把 `latest_date` 推到 end_date

**概念**

- 當 API 回傳 NO_DATA 時，**仍更新 metadata**（不經 DB）：把該組合的 `latest_date` 設成本次請求的 **end_date**；下次起始日 = `latest_date + 1`。

**實作要點**

- 需在 NO_DATA 時單獨寫入 metadata 檔案（或更新 memory 後一併寫回）。
- **從 DB 更新 metadata 時**要與此合併：DB 的 `max(date)` 若小於目前 metadata 的 `latest_date`，則保留較大者，否則會把 NO_DATA 的進度蓋掉。

**優缺點**

- **優點**：不改 metadata 結構，實作較小。
- **缺點**：`latest_date` 語意變成「有資料或已檢查到這天」，需約定好與「從 DB 更新」的合併規則，避免被覆寫。

### 做法三：延遲重試（可選，與做法一／二搭配）

**概念**

- 對「曾回傳 NO_DATA 的區間」在 **N 天後再試一次**，以涵蓋資料延遲上架。
- 在 metadata 記錄 `last_attempted_date`（或 `last_no_data_date`）；若 `(today - last_attempted_date).days >= recheck_no_data_after_days`，則**允許**再請求該區間一次，否則依做法一／二跳過。

**參數建議**

- `recheck_no_data_after_days`：例如 7、14、30，依資料延遲程度調整。

### 業界常見做法摘要

| 做法 | 說明 |
|------|------|
| **Watermark / cursor 在「無資料」時也前進** | 查詢回傳空時仍把 cursor（或等同的 last_attempted）往後移，避免對同一區間無限重試。 |
| **區分 last_success 與 last_attempted** | last_success = 有資料到哪（來自 DB）；last_attempted = 已請求到哪（含 NO_DATA）。下次從 last_attempted + 1 開始。 |
| **延遲重試** | 對 NO_DATA 區間設「N 天後再試一次」或定期 backfill，兼顧省 API 與補漏。 |
| **不建議** | 對同一段已知無資料的區間每次跑都重打 API。 |

---

## S2. metadata 新增 `last_attempted_date` 欄位與讀寫邏輯 ⏸

- **目的**：讓「已請求到哪」成為獨立於 DB 的進度來源。
- **做法**：依做法一的邏輯 1~3 實作：決定請求區間時取 `max(latest_date + 1, last_attempted_date + 1)`；NO_DATA 時把 `last_attempted_date` 設為本次請求的 end_date。
- **產出**：`core/pipeline/updaters/finmind_updater.py`（metadata 讀寫處）。
- **驗證方式**：對一組已知無資料的 `(broker_id, stock_id)` 連跑兩次，第二次不再發出 API 請求。
- **相依**：S1。
- **暫緩原因與解除條件**：見上方進度追蹤表的暫緩說明。

## S3. 「從 DB 更新 metadata」時保留 `last_attempted_date` ⏸

- **目的**：避免從 DB 回寫時把 NO_DATA 的進度蓋掉。
- **做法**：依做法一的邏輯 4，`_update_broker_trading_metadata_from_database` 只覆寫 `earliest_date` / `latest_date`，保留 `last_attempted_date`。
- **產出**：同 S2。
- **驗證方式**：先寫入 `last_attempted_date`，再觸發一次從 DB 更新，該欄位不變。
- **相依**：S2。

## S4. metadata 清理邏輯排除「曾請求過但無資料」的組合 ⏸

- **目的**：避免清理時把「曾請求過但無資料」的紀錄刪掉，導致下次又從頭請求。
- **做法**：依做法一的邏輯 5，清理時若該組合有 `last_attempted_date` 則不刪除。
- **產出**：同 S2。
- **驗證方式**：DB 無資料但 metadata 有 `last_attempted_date` 的組合，在清理後仍存在。
- **相依**：S2。

## S5. （可選）延遲重試 ⏸

- **目的**：涵蓋資料延遲上架的情況，避免永久漏掉。
- **做法**：依做法三，新增 `recheck_no_data_after_days` 參數；超過門檻的 NO_DATA 區間允許重試一次。
- **產出**：同 S2。
- **驗證方式**：把 `last_attempted_date` 手動調到 N 天前，重跑時該區間被重新請求。
- **相依**：S2。

---

## 關聯與狀態

- **優先級**：P2（僅紀錄做法，暫不實作）
- **相關程式**：`core/pipeline/updaters/finmind_updater.py`、broker trading metadata JSON
- **相關 backlog**：[FinMind爬蟲清洗儲存流程優化.md](FinMind爬蟲清洗儲存流程優化.md)（同一條 pipeline 的其他優化）
