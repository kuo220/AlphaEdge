# Broker Trading Daily Report 更新流程詳解

## 概述

當調用 `update_broker_trading_daily_report_batch(start_date, end_date)` 時，系統會按照以下流程判斷每一筆資料是否需要更新。

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
  ├─→ 判斷 2: 檢查 API Quota
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
- **位置**: `update_broker_trading_daily_report_batch()` 第 405-418 行
- **判斷邏輯**:
  - 如果 `start_date` 是字串，轉換為 `datetime.date`
  - 如果 `end_date` 是字串，轉換為 `datetime.date`

#### 步驟 1.2: 確定實際起始日期
- **位置**: `get_actual_update_start_date()` 第 803-839 行
- **判斷邏輯**:
  1. 查詢資料庫 `taiwan_stock_trading_daily_report_secid_agg` 表的最新日期
  2. **如果資料庫有資料**:
     - 取得最新日期 `latest_date`
     - 實際起始日期 = `latest_date + 1天`
  3. **如果資料庫沒有資料**:
     - 使用提供的 `start_date` 作為實際起始日期
- **結果**: 得到 `actual_start_date`

#### 步驟 1.3: 檢查是否需要更新（全局檢查）
- **位置**: `update_broker_trading_daily_report_batch()` 第 429-434 行
- **判斷邏輯**:
  ```
  if actual_start_date > end_date_obj:
      # 資料庫已是最新，不需要更新
      return  # 直接結束，不進行任何更新
  ```
- **結果**: 如果實際起始日期已超過結束日期，整個更新流程結束

---

### 【階段 2】獲取股票和券商列表

#### 步驟 2.1: 獲取股票列表
- **位置**: `_get_stock_list()` 第 841-858 行
- **判斷邏輯**:
  - 從資料庫 `taiwan_stock_info_with_warrant` 表查詢所有不重複的 `stock_id`
  - **如果沒有股票**: 記錄警告並結束更新

#### 步驟 2.2: 獲取券商列表
- **位置**: `_get_securities_trader_list()` 第 860-879 行
- **判斷邏輯**:
  - 從資料庫 `taiwan_securities_trader_info` 表查詢所有不重複的 `securities_trader_id`
  - **如果沒有券商**: 記錄警告並結束更新

---

### 【階段 3】初始化 Metadata

#### 步驟 3.1: 從資料庫讀取並建立 Metadata
- **位置**: `_update_broker_trading_metadata_from_database()` 第 993-1142 行
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
  3. 如果 metadata 中已存在該組合:
     - 比較並更新 `earliest_date`（取更早的日期）
     - 比較並更新 `latest_date`（取更晚的日期）
  4. 清理 metadata 中資料庫不存在的記錄

#### 步驟 3.2: Metadata 已就緒
- **說明**: Metadata 已從資料庫讀取並更新完成，可以直接用於後續的日期範圍檢查

---

### 【階段 4】對每個 (券商, 股票) 組合進行判斷

#### 循環結構
```python
for securities_trader_id in trader_list:  # 外層循環：券商
    for stock_id in stock_list:          # 內層循環：股票
        # 對每個組合進行判斷
```

#### 判斷 1: 檢查日期範圍是否已完整存在 ⭐ **核心判斷**

**位置**: `update_broker_trading_daily_report_batch()` 第 488-508 行

**步驟 1.1: 取得已存在的日期範圍**
- **方法**: `_get_existing_dates_from_metadata(securities_trader_id, stock_id)`
- **位置**: `_get_existing_dates_from_metadata()` 第 1197-1246 行
- **判斷邏輯**:
  1. 從 `broker_trading_metadata.json` 讀取該組合的日期範圍
  2. **如果 metadata 中不存在該組合**:
     - 返回空集合 `set()`
  3. **如果 metadata 中存在該組合**:
     - 取得 `earliest_date` 和 `latest_date`
     - 使用 `TimeUtils.generate_date_range()` 生成該範圍內的所有日期
     - 返回所有日期的字串集合
- **結果**: `existing_dates: Set[str]` = 已存在的所有日期

**步驟 1.2: 產生目標日期範圍**
- **位置**: `update_broker_trading_daily_report_batch()` 第 494-500 行
- **判斷邏輯**:
  - 使用 `TimeUtils.generate_date_range(actual_start_date, end_date_obj)` 生成目標日期範圍
  - 轉換為字串集合: `target_date_strs: Set[str]`
- **結果**: `target_date_strs` = 需要更新的所有日期

**步驟 1.3: 計算缺失的日期**
- **位置**: `update_broker_trading_daily_report_batch()` 第 502-508 行
- **判斷邏輯**:
  ```python
  missing_dates = target_date_strs - existing_dates
  
  if not missing_dates:  # 如果沒有缺失的日期
      # 所有日期都已存在，跳過此組合
      stats[UpdateStatus.ALREADY_UP_TO_DATE.value] += 1
      continue  # 跳過，不進行更新
  ```
- **結果**: 
  - **如果 `missing_dates` 為空**: 跳過此組合，不進行更新
  - **如果 `missing_dates` 不為空**: 繼續進行後續判斷

---

#### 判斷 2: 檢查 API Quota

**位置**: `update_broker_trading_daily_report_batch()` 第 510-540 行

**步驟 2.1: 檢查 Quota 是否足夠**
- **方法**: `_check_and_update_api_quota()`
- **位置**: `_check_and_update_api_quota()` 第 661-701 行
- **判斷邏輯**:
  1. 檢查是否超過重置時間（每小時重置）
  2. 計算剩餘 quota: `remaining_quota = api_quota_limit - api_call_count`
  3. **如果 `remaining_quota <= 50`**:
     - 記錄警告
     - 返回 `False`（quota 不足）
  4. **如果 quota 足夠**:
     - `api_call_count += 1`
     - 返回 `True`（可以繼續）

**步驟 2.2: 處理 Quota 耗盡的情況**
- **位置**: `update_broker_trading_daily_report_batch()` 第 511-540 行
- **判斷邏輯**:
  ```python
  if not self._check_and_update_api_quota():
      # 1. 更新 metadata（保存當前進度）
      self._update_broker_trading_metadata_from_database()
      
      # 2. 等待 quota 重置
      quota_restored = self._wait_for_quota_reset(
          check_interval_minutes=10,
          max_wait_minutes=120
      )
      
      if not quota_restored:
          # 等待超時，結束更新
          quota_exhausted = True
          break
      else:
          # Quota 已恢復，繼續處理當前組合
          continue
  ```
- **結果**:
  - **如果 quota 足夠**: 繼續執行更新
  - **如果 quota 耗盡且等待超時**: 結束整個更新流程
  - **如果 quota 耗盡但已恢復**: 繼續處理當前組合

---

#### 判斷 3: 執行實際更新

**位置**: `update_broker_trading_daily_report_batch()` 第 551-590 行

**步驟 3.1: 調用單一組合更新方法**
- **方法**: `update_broker_trading_daily_report()`
- **位置**: `update_broker_trading_daily_report()` 第 228-382 行
- **參數**: 
  - `skip_processed_check=True`（因為 batch 方法已經檢查過了）

**步驟 3.2: 在單一組合更新方法中的判斷**

**子步驟 3.2.1: 檢查是否跳過處理檢查**
- **位置**: `update_broker_trading_daily_report()` 第 258-296 行
- **判斷邏輯**:
  ```python
  if not skip_processed_check and stock_id and securities_trader_id:
      if start_date_obj == end_date_obj:  # 單個日期
          # 從 metadata 檢查日期是否在範圍內
          if self._check_date_exists_in_metadata(...):
              return UpdateStatus.ALREADY_UP_TO_DATE
  ```
- **注意**: 在 batch 模式下，`skip_processed_check=True`，所以此檢查會被跳過

**子步驟 3.2.2: 再次確認實際起始日期**
- **位置**: `update_broker_trading_daily_report()` 第 298-317 行
- **判斷邏輯**:
  ```python
  actual_start_date = self.get_actual_update_start_date(default_date=start_date)
  
  if actual_start_date > end_date:
      return UpdateStatus.ALREADY_UP_TO_DATE
  ```
- **結果**: 如果實際起始日期已超過結束日期，返回 `ALREADY_UP_TO_DATE`

**子步驟 3.2.3: 執行爬取**
- **位置**: `update_broker_trading_daily_report()` 第 321-341 行
- **判斷邏輯**:
  ```python
  df = self.crawler.crawl_broker_trading_daily_report(...)
  
  if df is None or df.empty:
      return UpdateStatus.NO_DATA  # API 返回空結果
  ```
- **結果**:
  - **如果 API 返回空資料**: 返回 `NO_DATA`
  - **如果有資料**: 繼續處理

**子步驟 3.2.4: 執行清理**
- **位置**: `update_broker_trading_daily_report()` 第 343-349 行
- **判斷邏輯**:
  ```python
  cleaned_df = self.cleaner.clean_broker_trading_daily_report(df)
  
  if cleaned_df is None or cleaned_df.empty:
      return UpdateStatus.NO_DATA  # 清理後為空
  ```
- **結果**:
  - **如果清理後為空**: 返回 `NO_DATA`
  - **如果有資料**: 繼續處理

**子步驟 3.2.5: 保存資料**
- **位置**: `update_broker_trading_daily_report()` 第 351-375 行
- **判斷邏輯**:
  - 目前資料庫存儲被禁用（註解掉）
  - 資料會保存到 CSV 檔案: `finmind/downloads/broker_trading/{broker_id}/{stock_id}.csv`
- **結果**: 返回 `UpdateStatus.SUCCESS`

**步驟 3.3: 處理更新結果**
- **位置**: `update_broker_trading_daily_report_batch()` 第 562-575 行
- **判斷邏輯**:
  ```python
  status = self.update_broker_trading_daily_report(...)
  
  # 統計狀態
  if status.value in stats:
      stats[status.value] += 1
  ```
- **可能的狀態**:
  - `SUCCESS`: 成功更新
  - `NO_DATA`: API 返回空結果或清理後為空
  - `ALREADY_UP_TO_DATE`: 已是最新（理論上不會出現，因為前面已檢查）
  - `ERROR`: 發生錯誤

---

#### 判斷 4: 定期更新 Metadata

**位置**: `update_broker_trading_daily_report_batch()` 第 577-582 行

**判斷邏輯**:
```python
if combination_count % update_metadata_interval == 0:  # 每 100 個組合
    # 從資料庫讀取並更新 metadata
    self._update_broker_trading_metadata_from_database()
```
- **目的**: 避免程式意外中斷時遺失進度
- **頻率**: 每處理 100 個組合後更新一次

---

### 【階段 5】完成後更新 Metadata

**位置**: `update_broker_trading_daily_report_batch()` 第 595-597 行

**判斷邏輯**:
```python
# 無論是否完成，都更新 metadata
self._update_broker_trading_metadata_from_database()
```
- **目的**: 確保 metadata 反映資料庫中的最新數據狀態

---

## 關鍵判斷點總結

### 1. **全局日期範圍檢查**（階段 1）
- **判斷**: `actual_start_date > end_date_obj`
- **結果**: 如果為真，整個更新流程結束

### 2. **單一組合日期範圍檢查**（階段 4，判斷 1）⭐ **最重要**
- **判斷**: `missing_dates = target_date_strs - existing_dates`
- **結果**: 
  - 如果 `missing_dates` 為空 → 跳過此組合
  - 如果 `missing_dates` 不為空 → 繼續更新

### 3. **API Quota 檢查**（階段 4，判斷 2）
- **判斷**: `remaining_quota <= 50`
- **結果**: 
  - 如果 quota 不足 → 等待或結束
  - 如果 quota 足夠 → 繼續更新

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
1. **初始化時**: 掃描所有 CSV 檔案並建立 metadata
2. **API Quota 耗盡前**: 保存當前進度
3. **每 100 個組合**: 定期更新，避免遺失進度
4. **完成後**: 最終更新，確保 metadata 最新

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

1. **Metadata 是唯一判斷依據**: 系統不會直接讀取 CSV 檔案來判斷，而是依賴 metadata
2. **日期範圍假設**: Metadata 假設日期範圍是連續的（從 earliest_date 到 latest_date 的所有日期都存在）
3. **定期更新 Metadata**: 每 100 個組合後會重新掃描 CSV 並更新 metadata，確保準確性
4. **API Quota 管理**: 系統會自動檢查和管理 API quota，避免超過限制
