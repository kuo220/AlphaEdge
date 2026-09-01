# 券商分點 NO_DATA 的 metadata 語意（選型紀錄）

> **狀態：已選型，尚未實作。** 本文件是決策紀錄，不是待辦——它從一開始的定位就是
> 「只紀錄做法與業界慣例，不做程式碼變更」，故不放在 `backlog/`。
> 要動工時依〈實作規格〉開一份新的 backlog 即可。
>
> 選型日期：2026-08-01｜移入 `docs/`：2026-08-16

---

## 問題

爬取券商分點日報時，若 FinMind API 回傳無資料（NO_DATA），目前**不會**更新 metadata。
下次執行會用同一段日期再請求一次，造成：

- 浪費 API 額度
- log 重複出現 `No data available`

根因是 metadata 只記錄「**有資料**到哪一天」（`latest_date`，來自 DB），
沒有記錄「**已請求過**到哪一天」。兩個概念被混在同一個欄位。

---

## 決策

**採做法一（`last_attempted_date`）**，語意清楚、易維護。
做法三（延遲重試）可選配。做法二可作為改動最小的替代，但需明確規定合併規則。

### 何時該動工（解除條件）

以下任一成立時才值得實作——在那之前重複請求的成本可以接受：

- 確認要省下 FinMind API 額度
- NO_DATA 的重複請求開始影響日更時間

---

## 三個方案

### 做法一：metadata 增加 `last_attempted_date`（採用）

每個 `(broker_id, stock_id)` 除了來自 DB 的 `earliest_date` / `latest_date`，
再多一個 `last_attempted_date`：

| 欄位 | 語意 | 來源 |
|------|------|------|
| `latest_date` | DB 裡**有資料**到哪一天 | DB |
| `last_attempted_date` | 已向 API **請求過**到哪一天（含 NO_DATA 區間） | 請求流程 |

**優點**：語意清楚、不會重複打已知無資料的區間、可明顯減少 API 用量。
**注意**：若資料會延遲上架可能漏掉，需搭配做法三或定期 backfill。

### 做法二：NO_DATA 時把 `latest_date` 推到 end_date

不改 metadata 結構，NO_DATA 時直接把 `latest_date` 設成本次請求的 `end_date`。

**優點**：實作最小。
**缺點**：`latest_date` 語意變成「有資料**或**已檢查到這天」；
從 DB 更新 metadata 時必須取兩者較大值，否則會把 NO_DATA 的進度蓋掉——
這條合併規則一旦有人忘記，錯誤是靜默的。

### 做法三：延遲重試（可選，搭配一或二）

對曾回傳 NO_DATA 的區間在 N 天後再試一次，涵蓋資料延遲上架。
以 `recheck_no_data_after_days`（建議 7／14／30）控制；
若 `(today - last_attempted_date).days >= N` 則允許重新請求該區間。

### 業界慣例對照

| 做法 | 說明 |
|------|------|
| watermark／cursor 在「無資料」時也前進 | 查詢回傳空時仍把 cursor 往後移，避免對同一區間無限重試 |
| 區分 last_success 與 last_attempted | last_success 來自 DB；last_attempted 含 NO_DATA。下次從 last_attempted + 1 開始 |
| 延遲重試 | 對 NO_DATA 區間設「N 天後再試」或定期 backfill，兼顧省 API 與補漏 |
| **不建議** | 對同一段已知無資料的區間每次跑都重打 API（＝目前行為） |

---

## 實作規格

動工時照這五條做，全部集中在 `core/pipeline/tw/updaters/finmind_updater.py` 的 metadata 讀寫處。

1. **決定請求區間**：起始日 = `max(latest_date + 1, last_attempted_date + 1)`。
2. **API 有資料並寫入 DB**：照現有流程從 DB 更新 `earliest_date` / `latest_date`，
   並把本次請求的 `end_date` 寫入 `last_attempted_date`。
3. **API 回傳 NO_DATA**：不寫 DB，但**要更新 metadata**——
   把 `last_attempted_date` 設為本次請求的 `end_date`。
4. **從 DB 更新 metadata 時**（`_update_broker_trading_metadata_from_database`）：
   只覆寫 `earliest_date` / `latest_date`，**必須保留** `last_attempted_date`。
5. **清理 metadata 時**：某組合在 DB 沒有任何一筆、但 metadata 有 `last_attempted_date` 時
   **不要刪除**——那代表「曾請求過但無資料」，刪掉下次又會從頭請求。

第 4、5 條是最容易漏的兩處：漏了會讓 NO_DATA 的進度被靜默覆蓋或清掉，
症狀是「改完之後 API 用量沒有下降」，但不會有任何錯誤訊息。

**可選**：新增 `recheck_no_data_after_days` 參數實作做法三。

### 驗證方式

- 對一組已知無資料的 `(broker_id, stock_id)` 連跑兩次，第二次不再發出 API 請求。
- 先寫入 `last_attempted_date`，再觸發一次「從 DB 更新」，該欄位不變。
- DB 無資料但 metadata 有 `last_attempted_date` 的組合，在清理後仍存在。
- （做法三）把 `last_attempted_date` 手動調到 N 天前，重跑時該區間被重新請求。

---

## 相關

- `core/pipeline/tw/updaters/finmind_updater.py`、broker trading metadata JSON
- [FinMind 爬蟲清洗儲存流程優化](../../backlog/FinMind爬蟲清洗儲存流程優化.md)——同一條 pipeline 的其他優化，其範圍界線刻意排除本文件的主題
