# API 概述

AlphaEdge 提供了豐富的 API 來查詢各種市場資料和開發交易策略。

## 資料 API

資料 API 用於查詢各種市場資料，所有資料 API 都繼承自 `BaseDataAPI`。

### 可用的資料 API

| API | 說明 | 資料來源 |
|-----|------|---------|
| `StockPriceAPI` | 日線價格資料 | SQLite |
| `StockTickAPI` | 逐筆成交資料 | DolphinDB |
| `StockChipAPI` | 三大法人籌碼資料 | SQLite |
| `MonthlyRevenueReportAPI` | 月營收資料 | SQLite |
| `FinancialStatementAPI` | 財報資料 | SQLite |

### 基本使用模式

所有資料 API 都遵循相同的使用模式：

```python
# 1. 建立 API 實例
api = SomeAPI()

# 2. 查詢資料
data = api.get(...)

# 3. 資料以 pandas DataFrame 格式返回
print(data.head())
```

### API 繼承結構

```
BaseDataAPI
├── StockPriceAPI
├── StockTickAPI
├── StockChipAPI
├── MonthlyRevenueReportAPI
└── FinancialStatementAPI
```

## 策略 API

策略 API 用於開發交易策略。

### BaseStockStrategy

`BaseStockStrategy` 是所有股票策略的基礎類別，提供了策略開發所需的框架和介面。

詳細資訊請參考 [BaseStockStrategy 文檔](strategy/base_stock_strategy.md)。

## 資料格式

所有 API 返回的資料都是 `pandas.DataFrame` 格式，方便進行資料分析和處理。

## 錯誤處理

API 在遇到錯誤時會：
- 記錄錯誤日誌（使用 loguru）
- 返回空的 DataFrame（`pd.DataFrame()`）
- 不會拋出異常（部分 API 可能例外）

## 效能考量

- **SQLite API**: 適合查詢歷史資料，效能良好
- **DolphinDB API**: 專為時序資料優化，查詢速度極快
- **資料量**: 建議分批查詢大量資料，避免記憶體問題

## FinMind 資料

AlphaEdge 支援透過 FinMind API 取得以下資料（儲存在 SQLite 資料庫中）：

1. **台股總覽(含權證)** (`taiwan_stock_info_with_warrant`): 包含所有上市、上櫃、興櫃股票及權證的基本資訊
2. **證券商資訊** (`taiwan_securities_trader_info`): 包含所有證券商的代碼、名稱、地址、電話等資訊
3. **券商分點統計** (`taiwan_stock_trading_daily_report_secid_agg`): 每日各券商分點對各股票的買賣統計資料

這些資料可透過 SQL 查詢使用，詳細的更新流程請參考 [券商分點統計更新流程](../../broker_trading_update_flow.md)。

## 相關文檔

- [StockPriceAPI](data/stock_price_api.md)
- [StockTickAPI](data/stock_tick_api.md)
- [StockChipAPI](data/stock_chip_api.md)
- [MonthlyRevenueReportAPI](data/monthly_revenue_report_api.md)
- [FinancialStatementAPI](data/financial_statement_api.md)
- [BaseStockStrategy](strategy/base_stock_strategy.md)
- [券商分點統計更新流程](../../broker_trading_update_flow.md)
