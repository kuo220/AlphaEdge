# Broker Trading：API 回傳 NO_DATA 時的處理方案（紀錄）

> 僅紀錄做法與業界慣例，**暫不實作**程式碼變更。

## 問題

- 爬取券商分點日報時，若 API 回傳**無資料**（NO_DATA），目前**不會**更新 metadata。
- 下次執行時會用同一段日期再請求一次，造成：
  - 浪費 API 額度
  - log 重複出現 "No data available"

## 做法一：在 metadata 增加 `last_attempted_date`（推薦）

### 概念

- 每個 `(broker_id, stock_id)` 除了 `earliest_date` / `latest_date`（來自 DB），再多一個 **`last_attempted_date`**（或 `last_checked_date`）。
- **語意**：
  - `latest_date`：DB 裡「有資料」到哪一天。
  - `last_attempted_date`：已向 API「請求過」到哪一天（含 NO_DATA 的區間）。

### 邏輯

1. **決定請求區間時**  
   起始日 = `max(latest_date + 1, last_attempted_date + 1)`，避免重複請求已知無資料的區間。

2. **API 回傳有資料並寫入 DB 時**  
   照現有流程從 DB 更新 `earliest_date` / `latest_date`；並可將本次請求的 end_date 寫入 `last_attempted_date`（與 DB 更新一併或分開皆可）。

3. **API 回傳 NO_DATA 時**  
   不寫 DB，但**要更新 metadata**：將該組合的 `last_attempted_date` 設為本次請求的 **end_date**。

4. **從 DB 更新 metadata 時**（`_update_broker_trading_metadata_from_database`）  
   - 從 DB 寫入的只有 `earliest_date` / `latest_date`。  
   - **保留**既有的 `last_attempted_date`（不覆寫），以維持「已嘗試到哪」的紀錄。

5. **清理 metadata 時**  
   若某 `(broker_id, stock_id)` 在 DB 沒有任何一筆，但 metadata 裡有 `last_attempted_date`，**不要刪除**該筆 metadata（代表「曾請求過但無資料」），避免下次又從頭請求。

### 優缺點

- **優點**：語意清楚、不會重複打已知無資料的區間、可明顯減少 API 用量。
- **注意**：若資料會「延遲上架」，可能漏掉；可搭配「延遲重試」或定期 backfill。

---

## 做法二：NO_DATA 時把 metadata 的 `latest_date` 推到 end_date

### 概念

- 當 API 回傳 NO_DATA 時，**仍更新 metadata**（不經 DB）：把該組合的 `latest_date` 設成本次請求的 **end_date**。
- 下次起始日 = `latest_date + 1`，就不會再請求同一段。

### 實作要點

- 需在 NO_DATA 時單獨寫入 metadata 檔案（或更新 memory 後一併寫回）。
- **從 DB 更新 metadata 時**要與此合併：例如 DB 的 `max(date)` 若小於目前 metadata 的 `latest_date`，則保留較大者（表示「已檢查到」），否則會把 NO_DATA 的進度蓋掉。

### 優缺點

- **優點**：不改 metadata 結構，實作較小。
- **缺點**：`latest_date` 語意變成「有資料或已檢查到這天」，需約定好與「從 DB 更新」的合併規則，避免被覆寫。

---

## 做法三：延遲重試（可選，與做法一/二搭配）

### 概念

- 對「曾回傳 NO_DATA 的區間」在 **N 天後再試一次**，以涵蓋資料延遲上架。
- 實作方式例如：
  - 在 metadata 記錄 `last_attempted_date`（或 `last_no_data_date`）。
  - 若 `(today - last_attempted_date).days >= recheck_no_data_after_days`，則**允許**再請求該區間一次（或只重試該區間），否則依做法一/二跳過。

### 參數建議

- `recheck_no_data_after_days`：例如 7、14、30，依資料延遲程度調整。

---

## 業界常見做法摘要

| 做法 | 說明 |
|------|------|
| **Watermark / cursor 在「無資料」時也前進** | 查詢回傳空時仍把 cursor（或等同的 last_attempted）往後移，避免對同一區間無限重試。 |
| **區分 last_success 與 last_attempted** | last_success = 有資料到哪（來自 DB）；last_attempted = 已請求到哪（含 NO_DATA）。下次從 last_attempted + 1 開始。 |
| **延遲重試** | 對 NO_DATA 區間設「N 天後再試一次」或定期 backfill，兼顧省 API 與補漏。 |
| **不建議** | 對同一段已知無資料的區間每次跑都重打 API。 |

---

## 小結

- **建議實作**：做法一（`last_attempted_date`），語意清楚、易維護。
- **可選**：做法三（延遲重試），依需求設定 `recheck_no_data_after_days`。
- 做法二可作為改動最小的替代，但需明確規定 metadata 與 DB 的合併規則。

以上僅供紀錄，**不做程式碼變更**。
