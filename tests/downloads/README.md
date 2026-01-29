# 測試資料目錄

此目錄存放所有測試過程中產生的資料，包括 CSV 檔案、資料庫和 metadata。

**所有測試共用同一個目錄結構和資料庫**，完全按照實際的 `tasks/update_db.py` 結構組織。

## 目錄結構

```
tests/
├── database/
│   └── test.db                              # 測試資料庫（所有測試共用）
│
└── downloads/
    ├── finmind/
    │   └── broker_trading/
    │       └── {broker_id}/
    │           └── {stock_id}.csv           # CSV 檔案
    │
    └── meta/
        └── broker_trading/
            └── broker_trading_metadata.json  # Metadata JSON
```

## 資料類型說明

### CSV 檔案
- **位置**: `tests/downloads/finmind/broker_trading/{broker_id}/{stock_id}.csv`
- **格式**: UTF-8 with BOM
- **欄位**: 
  - `securities_trader`: 券商名稱
  - `securities_trader_id`: 券商代碼
  - `stock_id`: 股票代碼
  - `date`: 日期 (YYYY-MM-DD)
  - `buy_volume`: 買進總股數
  - `sell_volume`: 賣出總股數
  - `buy_price`: 買進均價
  - `sell_price`: 賣出均價

### 資料庫
- **位置**: `tests/database/test.db`
- **表格**: `taiwan_stock_trading_daily_report_secid_agg`
- **說明**: 所有測試共用同一個資料庫，每次測試前會清空重新開始

### Metadata JSON
- **位置**: `tests/downloads/meta/broker_trading/broker_trading_metadata.json`
- **格式**: JSON
- **結構**:
  ```json
  {
    "broker_id": {
      "stock_id": {
        "earliest_date": "2021-06-30",
        "latest_date": "2026-01-27"
      }
    }
  }
  ```

## 注意事項

- 所有測試資料都會保留，不會自動刪除
- **所有測試共用同一個目錄結構和資料庫**
- 每次測試運行前會清空資料庫，確保乾淨的測試環境
- CSV 檔案按照 `broker_id/stock_id` 的結構分類存放
- 目錄結構已簡化，移除多餘的 `pipeline/downloads` 層級
- 可以手動檢查這些檔案來驗證測試結果
