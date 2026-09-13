# 券商分點NO_DATA的metadata語意

## Abstract

- **背景／問題**：爬取券商分點日報時，若 FinMind API 回傳無資料（NO_DATA），metadata **不會**更新，
  下次執行會用同一段日期再請求一次——浪費 API 額度，log 也重複出現 `No data available`。
  根因是 metadata 只記錄「**有資料**到哪一天」（`latest_date`，來自 DB），沒有記錄「**已請求過**到哪一天」，
  兩個概念被混在同一個欄位。
- **目標**：已確認沒有資料的 `(broker_id, stock_id)` 區間不再重複請求；資料延遲上架的情況仍有機會被補回。
- **範圍界線**：只改券商分點（`broker_trading`）的 metadata 讀寫，**不動**其他 FinMind 資料集、
  不改 DB schema、不做爬取並行化或批次寫入（屬 [FinMind爬蟲清洗儲存流程優化.md](FinMind爬蟲清洗儲存流程優化.md) S5／S6）。
- **驗收標準**：對一組已知無資料的組合連跑兩次，第二次不發出 API 請求；metadata 從 DB 重新整理或清理後，
  NO_DATA 的進度仍保留；`pytest -m "not slow"` 全綠。
- **解除條件（何時值得動工）**：確認要省下 FinMind API 額度，或 NO_DATA 的重複請求開始影響日更時間。
  在那之前重複請求的成本可以接受。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | metadata 增加 `last_attempted_date` | `core/pipeline/tw/updaters/finmind/common.py`、`broker_trading_updater.py`、對應測試 | 見步驟章節的四條驗證 | ⬜ | 方案已選定（做法一），見〈附：方案比較〉 |
| S2 | NO_DATA 區間的延遲重試（可選） | 同上 | 手動把 `last_attempted_date` 調到 N 天前，重跑時該區間被重新請求 | ⬜ | 相依 S1；不做也不影響 S1 的效益 |

## S1. metadata 增加 `last_attempted_date` ⬜

- **目的**：把「有資料到哪一天」與「已請求過到哪一天」拆成兩個欄位。
- **做法**：每個 `(broker_id, stock_id)` 除了來自 DB 的 `earliest_date` / `latest_date`，再多一個 `last_attempted_date`：

  | 欄位 | 語意 | 來源 |
  |------|------|------|
  | `latest_date` | DB 裡**有資料**到哪一天 | DB |
  | `last_attempted_date` | 已向 API **請求過**到哪一天（含 NO_DATA 區間） | 請求流程 |

  1. **決定請求區間**：起始日 = `max(latest_date + 1, last_attempted_date + 1)`。
  2. **API 有資料並寫入 DB**：照現有流程從 DB 更新 `earliest_date` / `latest_date`，並把本次請求的 `end_date` 寫入 `last_attempted_date`。
  3. **API 回傳 NO_DATA**：不寫 DB，但**要更新 metadata**——把 `last_attempted_date` 設為本次請求的 `end_date`。
  4. **從 DB 更新 metadata 時**（`refresh_from_database()`）：只覆寫 `earliest_date` / `latest_date`，**必須保留** `last_attempted_date`。
  5. **清理 metadata 時**：某組合在 DB 沒有任何一筆、但 metadata 有 `last_attempted_date` 時**不要刪除**——那代表「曾請求過但無資料」，刪掉下次又會從頭請求。

  第 4、5 條是最容易漏的兩處：漏了會讓 NO_DATA 的進度被靜默覆蓋或清掉，症狀是「改完之後 API 用量沒有下降」，但不會有任何錯誤訊息。
- **產出**：`core/pipeline/tw/updaters/finmind/common.py`（metadata 讀寫）、`core/pipeline/tw/updaters/finmind/broker_trading_updater.py`、新增測試。
- **驗證方式**：
  1. 對一組已知無資料的 `(broker_id, stock_id)` 連跑兩次，第二次不再發出 API 請求。
  2. 先寫入 `last_attempted_date`，再觸發一次「從 DB 更新」，該欄位不變。
  3. DB 無資料但 metadata 有 `last_attempted_date` 的組合，在清理後仍存在。
  4. 既有 metadata 檔（沒有 `last_attempted_date` 欄位）可以直接讀入，行為與現在相同。
- **相依**：無。

## S2. NO_DATA 區間的延遲重試（可選） ⬜

- **目的**：S1 會讓「資料延遲上架」的區間永遠不再被請求；對曾回傳 NO_DATA 的區間在 N 天後再試一次。
- **做法**：新增 `recheck_no_data_after_days`（建議 7／14／30）；若 `(today - last_attempted_date).days >= N`，允許重新請求該區間。
- **產出**：同 S1。
- **驗證方式**：把 `last_attempted_date` 手動調到 N 天前，重跑時該區間被重新請求；未滿 N 天時不請求。
- **相依**：S1。

---

## 附：方案比較

### 做法一：metadata 增加 `last_attempted_date`（採用，即 S1）

**優點**：語意清楚、不會重複打已知無資料的區間、可明顯減少 API 用量。
**注意**：若資料會延遲上架可能漏掉，需搭配 S2 或定期 backfill。

### 做法二：NO_DATA 時把 `latest_date` 推到 end_date（不採用）

不改 metadata 結構，NO_DATA 時直接把 `latest_date` 設成本次請求的 `end_date`。

**優點**：實作最小。
**缺點**：`latest_date` 語意變成「有資料**或**已檢查到這天」；從 DB 更新 metadata 時必須取兩者較大值，
否則會把 NO_DATA 的進度蓋掉——這條合併規則一旦有人忘記，錯誤是靜默的。

### 業界慣例對照

| 做法 | 說明 |
|------|------|
| watermark／cursor 在「無資料」時也前進 | 查詢回傳空時仍把 cursor 往後移，避免對同一區間無限重試 |
| 區分 last_success 與 last_attempted | last_success 來自 DB；last_attempted 含 NO_DATA。下次從 last_attempted + 1 開始 |
| 延遲重試 | 對 NO_DATA 區間設「N 天後再試」或定期 backfill，兼顧省 API 與補漏 |
| **不建議** | 對同一段已知無資料的區間每次跑都重打 API（＝目前行為） |
