# Broker Trading Daily Report 更新流程詳解

## 概述

當調用 `update_broker_trading_daily_report(start_date, end_date)` 時（對外公開的批量更新方法），系統會按照以下流程判斷每一筆資料是否需要更新。內部單一組合的更新由私有方法 `_update_broker_trading_daily_report(stock_id, securities_trader_id, start_date, end_date, do_commit)` 執行。

---

## 完整流程圖

```
開始
  ↓
【階段 1】初始化與日期範圍確定
  ↓
【階段 2】獲取股票和券商列表
  ↓
【階段 3】初始化 Metadata
  ↓
【階段 4】對每個 (券商, 股票) 組合進行判斷
  ├─→ 判斷 1: 檢查日期範圍是否已完整存在
  ├─→ 判斷 2: API Quota 耗盡時等待／重試
  ├─→ 判斷 3: 執行實際更新
  └─→ 判斷 4: 定期更新 Metadata
  ↓
【階段 5】完成後更新 Metadata
  ↓
結束
```

---

## 詳細步驟說明

### 【階段 1】初始化與日期範圍確定

#### 步驟 1.1: 日期格式轉換
- **位置**: `update_broker_trading_daily_report()` 第 302-314 行
- **判斷邏輯**:
  - 使用內部函數 `_to_date()` 將 `start_date`、`end_date` 轉為 `datetime.date`
  - 若為字串須為 `YYYY-MM-DD` 格式，否則拋出 `ValueError`

#### 步驟 1.2: 取得股票與券商列表並過濾
- **位置**: 第 316-346 行
- **判斷邏輯**:
  1. 呼叫 `_get_stock_list()` 取得資料庫中所有股票代碼
  2. 呼叫 `_get_securities_trader_list()` 取得所有券商代碼
  3. 使用 `StockUtils.filter_common_stocks()` 過濾出一般股票（排除 ETF、權證等）
  4. 若股票列表或券商列表為空，記錄警告並直接結束
- **說明**: 目前沒有「全局」的實際起始日期檢查；每個 (券商, 股票) 組合的起始日期在階段 4 的迴圈內，依該組合的 metadata 個別決定。

---

### 【階段 2】獲取股票和券商列表

#### 步驟 2.1: 獲取股票列表
- **位置**: `_get_stock_list()` 第 801-817 行
- **判斷邏輯**:
  - 從資料庫 `taiwan_stock_info` 表（`STOCK_INFO_TABLE_NAME`）查詢所有不重複的 `stock_id`
  - **如果沒有股票**: 返回空列表，上層會記錄警告並結束更新

#### 步驟 2.2: 獲取券商列表
- **位置**: `_get_securities_trader_list()` 第 820-837 行
- **判斷邏輯**:
  - 從資料庫 `taiwan_securities_trader_info` 表查詢所有不重複的 `securities_trader_id`
  - **如果沒有券商**: 返回空列表，上層會記錄警告並結束更新

---

### 【階段 3】初始化 Metadata

#### 步驟 3.1: 從資料庫讀取並建立 Metadata
- **位置**: `_update_broker_trading_metadata_from_database()` 第 879 行起（至約 1045 行）
- **判斷邏輯**:
  1. 從資料庫 `taiwan_stock_trading_daily_report_secid_agg` 表查詢每個 (securities_trader_id, stock_id) 組合的日期範圍
  2. 對每個組合:
     - 使用 SQL `MIN(date)` 和 `MAX(date)` 取得日期範圍
     - 計算 `earliest_date` = 最小日期
     - 計算 `latest_date` = 最大日期
     - 更新到 `broker_trading_metadata.json`:
       ```json
       {
         "broker_id": {
           "stock_id": {
             "earliest_date": "2021-01-01",
             "latest_date": "2023-12-31"
           }
         }
       }
       ```
  3. 若 metadata 中已存在該組合，會比較並更新為更早/更晚的日期
  4. 清理 metadata 中資料庫不存在的記錄，並寫入 JSON 與快取

#### 步驟 3.2: Metadata 已就緒
- **說明**: Metadata 已從資料庫讀取並更新完成，可直接用於後續迴圈內的日期範圍檢查

---

### 【階段 4】對每個 (券商, 股票) 組合進行判斷

#### 循環結構
```python
for securities_trader_id in trader_list:  # 外層循環：券商
    for stock_id in stock_list:          # 內層循環：股票
        # 對每個組合進行判斷
```

#### 判斷 1: 檢查日期範圍是否已完整存在 ⭐ **核心判斷**

**位置**: `update_broker_trading_daily_report()` 迴圈內約第 400-484 行

**步驟 1.1: 依 metadata 決定此組合的起始日期**
- **位置**: 約第 401-432 行
- **判斷邏輯**:
  - 從 `_load_broker_trading_metadata()` 取得該組合的 `latest_date`（若存在）
  - 若有 metadata：`update_start_date = latest_date + 1 天`，否則使用傳入的 `start_date_obj`
  - 若 `update_start_date > end_date_obj`：已是最新或範圍無效，跳過此組合（`ALREADY_UP_TO_DATE`）

**步驟 1.2: 取得已存在的日期範圍**
- **方法**: `_get_existing_dates_from_metadata(securities_trader_id, stock_id)`
- **位置**: `_get_existing_dates_from_metadata()` 第 1047-1093 行
- **判斷邏輯**:
  1. 從 metadata 讀取該組合的 `earliest_date`、`latest_date`
  2. 若不存在或缺少日期：返回空集合 `set()`
  3. 使用 `TimeUtils.generate_date_range()` 生成該範圍內所有日期，轉為字串集合
- **結果**: `existing_dates: Set[str]` = 已存在的所有日期

**步驟 1.3: 產生目標日期範圍並計算缺失**
- **位置**: 約第 452-484 行
- **判斷邏輯**:
  - `target_dates = TimeUtils.generate_date_range(update_start_date, end_date_obj)`，再轉為 `target_date_strs`
  - `missing_dates = target_date_strs - existing_dates`
  - 若 `missing_dates` 為空：跳過此組合（`ALREADY_UP_TO_DATE`）；否則進入判斷 2／3（執行更新）
- **結果**: 有缺失日期才繼續呼叫 `_update_broker_trading_daily_report`

---

#### 判斷 2: API Quota 耗盡時的處理

**位置**: `update_broker_trading_daily_report()` 迴圈內約第 486-523 行

目前實作**不**在呼叫 API 前先檢查 quota，而是直接呼叫 `_update_broker_trading_daily_report()`；若 crawler 拋出 `FinMindQuotaExhaustedError`，則在迴圈內處理：

**步驟 2.1: 捕捉 Quota 耗盡**
- **判斷邏輯**:
  1. 在 `try` 中呼叫 `_update_broker_trading_daily_report(...)` 執行單一組合更新
  2. 若拋出 `FinMindQuotaExhaustedError`：進入步驟 2.2；若成功或為其他狀態則更新統計並 `break` 出 `while True`，繼續下一組合

**步驟 2.2: Quota 耗盡後的恢復流程**
- **位置**: 約第 506-523 行
- **判斷邏輯**:
  ```python
  except FinMindQuotaExhaustedError as e:
      # 1. 先將當前進度寫回 metadata（從資料庫更新）
      self._update_broker_trading_metadata_from_database()
      # 2. 等待 quota 重置（QUOTA_CHECK_INTERVAL_MINUTES、QUOTA_MAX_WAIT_MINUTES）
      quota_restored = self._wait_for_quota_reset()
      if not quota_restored:
          quota_exhausted = True
          break  # 結束整個批量更新
      # 3. 已恢復則重試「當前」組合（continue 回到 while True）
  ```
- **方法**: `_wait_for_quota_reset()` 約第 736 行起，每隔 `QUOTA_CHECK_INTERVAL_MINUTES` 查詢 API 剩餘次數或依時間 fallback，最多等待 `QUOTA_MAX_WAIT_MINUTES`
- **結果**:
  - **已恢復**: 重試當前 (券商, 股票) 組合
  - **等待超時**: 設 `quota_exhausted = True` 並結束批量更新

---

#### 判斷 3: 執行實際更新

**位置**: 迴圈內約第 486-537 行（呼叫 `_update_broker_trading_daily_report` 並依 `UpdateStatus` 統計、定期 commit）

**步驟 3.1: 調用單一組合更新方法**
- **方法**: `_update_broker_trading_daily_report(stock_id, securities_trader_id, start_date, end_date, do_commit=False)`
- **位置**: `_update_broker_trading_daily_report()` 第 612-695 行
- **參數**: 批次時 `do_commit=False`，由迴圈依 `BATCH_COMMIT_INTERVAL` 定期 commit

**步驟 3.2: 在單一組合更新方法中的流程**

**子步驟 3.2.1: 執行爬取**
- **位置**: 約第 642-655 行
- **判斷邏輯**:
  - `df = self.crawler.crawl_broker_trading_daily_report(...)`
  - 若 `df is None or df.empty`：返回 `UpdateStatus.NO_DATA`

**子步驟 3.2.2: 執行清理**
- **位置**: 約第 656-663 行
- **判斷邏輯**:
  - `cleaned_df = self.cleaner.clean_broker_trading_daily_report(df)`
  - 若清理後為空：返回 `UpdateStatus.NO_DATA`

**子步驟 3.2.3: 保存資料**
- **位置**: 約第 664-684 行
- **判斷邏輯**:
  - 呼叫 `self.loader.load_broker_trading_daily_report(df=cleaned_df, commit=do_commit)` 將資料寫入 SQLite 資料庫（表 `taiwan_stock_trading_daily_report_secid_agg`）
  - 若 `saved_count == 0`（例如皆為重複）：仍視為成功，返回 `UpdateStatus.SUCCESS`
- **結果**: 成功則返回 `UpdateStatus.SUCCESS`

**步驟 3.3: 處理更新結果與 commit**
- **位置**: 約第 489-537 行
- **判斷邏輯**:
  - 依 `status` 更新 `stats[status.value]`，每 `BATCH_COMMIT_INTERVAL`（50）筆呼叫 `self.loader.conn.commit()`
- **可能的狀態**:
  - `SUCCESS`: 成功寫入資料庫
  - `NO_DATA`: API 返回空或清理後為空
  - `ALREADY_UP_TO_DATE`: 迴圈內已跳過（此方法不會返回此狀態）
  - `ERROR`: 發生錯誤

---

#### 判斷 4: 定期更新 Metadata

**位置**: 輔助函數 `log_progress_and_update_metadata()` 內，約第 374-387 行；每輪迴圈處理完一組合後會呼叫此函數

**判斷邏輯**:
```python
if processed_count % self.BATCH_UPDATE_METADATA_INTERVAL == 0:  # 每 500 個組合
    self._update_broker_trading_metadata_from_database()
```
- **目的**: 避免程式意外中斷時遺失進度
- **頻率**: 每處理 **500** 個組合更新一次（常數 `BATCH_UPDATE_METADATA_INTERVAL = 500`）；進度 log 為每 50 筆（`BATCH_LOG_PROGRESS_INTERVAL`）

---

### 【階段 5】完成後更新 Metadata

**位置**: `update_broker_trading_daily_report()` 約第 541-546 行（迴圈結束後）

**判斷邏輯**:
```python
if self.loader.conn:
    self.loader.conn.commit()
logger.info("Updating broker trading metadata after batch update...")
self._update_broker_trading_metadata_from_database()
```
- **目的**: 將尚未 commit 的寫入一次提交，並確保 metadata 反映資料庫中的最新狀態

---

## 關鍵判斷點總結

### 1. **股票/券商列表與過濾**（階段 1）
- **判斷**: 取得股票與券商列表並過濾一般股票；若任一為空則結束
- **結果**: 確保後續迴圈有可處理的組合

### 2. **單一組合日期範圍檢查**（階段 4，判斷 1）⭐ **最重要**
- **判斷**: `missing_dates = target_date_strs - existing_dates`
- **結果**: 
  - 如果 `missing_dates` 為空 → 跳過此組合
  - 如果 `missing_dates` 不為空 → 繼續更新

### 3. **API Quota 耗盡處理**（階段 4，判斷 2）
- **判斷**: 呼叫 API 時若拋出 `FinMindQuotaExhaustedError`
- **結果**: 
  - 更新 metadata → 呼叫 `_wait_for_quota_reset()` → 恢復則重試當前組合，超時則結束批量更新

### 4. **API 返回資料檢查**（階段 4，判斷 3）
- **判斷**: `df is None or df.empty`
- **結果**: 
  - 如果為空 → 返回 `NO_DATA`
  - 如果有資料 → 繼續處理並保存

---

## Metadata 的作用

### Metadata 結構
```json
{
  "broker_id_1": {
    "stock_id_1": {
      "earliest_date": "2021-01-01",
      "latest_date": "2023-12-31"
    }
  }
}
```

### Metadata 的用途
1. **快速判斷日期範圍**: 不需要讀取整個 CSV 檔案，只需讀取 metadata
2. **生成已存在日期集合**: 基於 `earliest_date` 和 `latest_date` 生成所有日期
3. **避免重複更新**: 如果目標日期範圍完全包含在 metadata 記錄的範圍內，則跳過更新

### Metadata 的更新時機
1. **初始化時**: 從資料庫 `taiwan_stock_trading_daily_report_secid_agg` 查詢並建立/更新 metadata（JSON + 快取）
2. **API Quota 耗盡時**: 在等待重置前先從資料庫更新 metadata，保存當前進度
3. **每 500 個組合**: 定期呼叫 `_update_broker_trading_metadata_from_database()`，避免遺失進度
4. **完成後**: 迴圈結束後再次從資料庫更新 metadata，確保與 DB 一致

---

## 實際範例

### 範例 1: 新組合（首次更新）
```
券商: "1234"
股票: "2330"
目標日期範圍: 2021-06-30 ~ 2021-12-31

判斷流程:
1. 檢查 metadata → 不存在此組合
2. existing_dates = set() (空集合)
3. target_date_strs = {2021-06-30, 2021-07-01, ..., 2021-12-31}
4. missing_dates = target_date_strs - existing_dates = target_date_strs (全部缺失)
5. 繼續更新 → 調用 API → 保存到 CSV
6. 更新 metadata: earliest_date=2021-06-30, latest_date=2021-12-31
```

### 範例 2: 部分日期已存在
```
券商: "1234"
股票: "2330"
目標日期範圍: 2021-06-30 ~ 2021-12-31
Metadata 記錄: earliest_date=2021-06-30, latest_date=2021-09-30

判斷流程:
1. 檢查 metadata → 存在此組合
2. existing_dates = {2021-06-30, ..., 2021-09-30} (生成所有日期)
3. target_date_strs = {2021-06-30, ..., 2021-12-31}
4. missing_dates = {2021-10-01, ..., 2021-12-31} (10月之後的日期缺失)
5. 繼續更新 → 調用 API (查詢 2021-10-01 ~ 2021-12-31) → 保存到 CSV
6. 更新 metadata: earliest_date=2021-06-30, latest_date=2021-12-31 (更新 latest_date)
```

### 範例 3: 所有日期已存在
```
券商: "1234"
股票: "2330"
目標日期範圍: 2021-06-30 ~ 2021-12-31
Metadata 記錄: earliest_date=2021-06-30, latest_date=2021-12-31

判斷流程:
1. 檢查 metadata → 存在此組合
2. existing_dates = {2021-06-30, ..., 2021-12-31} (生成所有日期)
3. target_date_strs = {2021-06-30, ..., 2021-12-31}
4. missing_dates = set() (空集合，所有日期都已存在)
5. 跳過更新 → stats[ALREADY_UP_TO_DATE] += 1
```

---

## 注意事項

1. **Metadata 是唯一判斷依據**: 日期是否已存在依 metadata（由資料庫 `taiwan_stock_trading_daily_report_secid_agg` 彙總而來）判斷，不直接掃描檔案
2. **日期範圍假設**: Metadata 假設日期範圍是連續的（從 earliest_date 到 latest_date 的所有日期都存在）
3. **定期更新 Metadata**: 每 500 個組合會從資料庫重新查詢並寫入 metadata（`_update_broker_trading_metadata_from_database()`），確保與 DB 一致
4. **API Quota**: 配額耗盡時由 crawler 拋出 `FinMindQuotaExhaustedError`，由 updater 捕捉後等待重置或結束批量更新
