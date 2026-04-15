# Data Coverage — AlphaEdge 資料覆蓋範圍

本文件描述目前 `AlphaEdge` 程式碼中**實際可用**的資料來源與對應模組。

## 總覽

| 類別 | 來源 | 主要模組 | 儲存位置 | 備註 |
| --- | --- | --- | --- | --- |
| 股票日線 | 台股資料來源（由 pipeline 更新） | `StockPriceAPI` | SQLite `price` | 回測常用 |
| 三大法人籌碼 | 台股資料來源（由 pipeline 更新） | `StockChipAPI` | SQLite `chip` | 回測/選股可用 |
| 月營收 | 台股資料來源（由 pipeline 更新） | `MonthlyRevenueReportAPI` | SQLite `monthly_revenue` | 基本面可用 |
| 財報 | 台股資料來源（由 pipeline 更新） | `FinancialStatementAPI` | SQLite 各財報表 | 基本面可用 |
| FinMind 參考資料 | FinMind API | `FinMindAPI` | SQLite FinMind 相關表 | 股票、券商、分點 |
| Tick 逐筆 | Shioaji + DolphinDB | `StockTickAPI` | DolphinDB `tickDB` | 需 DDB 環境 |

## API 與資料表對照

| API 類別 | 檔案 | 後端 | 關鍵資料表/資料庫 |
| --- | --- | --- | --- |
| `StockPriceAPI` | `trader/api/stock_price_api.py` | SQLite | `price` |
| `StockChipAPI` | `trader/api/stock_chip_api.py` | SQLite | `chip` |
| `MonthlyRevenueReportAPI` | `trader/api/monthly_revenue_report_api.py` | SQLite | `monthly_revenue` |
| `FinancialStatementAPI` | `trader/api/financial_statement_api.py` | SQLite | 財報相關表 |
| `FinMindAPI` | `trader/api/finmind_api.py` | SQLite | `taiwan_stock_info*`, `taiwan_securities_trader_info`, `taiwan_stock_trading_daily_report_secid_agg` |
| `StockTickAPI` | `trader/api/stock_tick_api.py` | DolphinDB | `tickDB` / `tick` |

## 更新入口

資料更新統一入口：

```bash
python -m tasks.update_db --target <targets...>
```

支援重點 target：

- `price`
- `chip`
- `fs`
- `mrr`
- `tick`
- `finmind`
- `stock_info`
- `stock_info_with_warrant`
- `broker_info`
- `broker_trading`

## 已知限制

- 專案目前無內建加密貨幣 / prediction market collectors（如 Kalshi、Polymarket 實作）。
- `tick` 依賴 DolphinDB 環境與對應連線參數，未設定時無法使用 tick 相關流程。
- 文件中的資料範圍以 `trader/config.py` 預設日期與實際本地資料庫內容為準。
