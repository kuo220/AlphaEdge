# Data Coverage — AlphaEdge 資料覆蓋範圍

本文件描述目前 `AlphaEdge` 程式碼中**實際可用**的資料來源與對應模組。

## 總覽

| 類別           | 來源                    | 主要模組                      | 儲存位置                     | 起始日期                                                                                                  | 備註                                   |
| ------------ | --------------------- | ------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 股票日線         | 台股資料來源（由 pipeline 更新） | `StockPriceAPI`           | SQLite `price`           | 2013-01-01                                                                                            | 回測常用；對應 `DEFAULT_PRICE_START_DATE`   |
| 三大法人籌碼       | 台股資料來源（由 pipeline 更新） | `StockChipAPI`            | SQLite `chip`            | 2013-01-01                                                                                            | 回測/選股可用；對應 `DEFAULT_CHIP_START_DATE` |
| 月營收          | 台股資料來源（由 pipeline 更新） | `MonthlyRevenueReportAPI` | SQLite `monthly_revenue` | 2013-01（`DEFAULT_START_YEAR` 起、1 月）                                                                   | 基本面可用                                |
| 財報           | 台股資料來源（由 pipeline 更新） | `FinancialStatementAPI`   | SQLite 各財報表              | 2013 年第 1 季（`DEFAULT_START_YEAR`）                                                                     | 基本面可用                                |
| FinMind 參考資料 | FinMind API           | `FinMindAPI`              | SQLite FinMind 相關表       | 券商分點：`2021-06-30`（`FINMIND_BROKER_TRADING_START_DATE`）；台股總覽／證券商為 API 快照，更新流程未帶歷史起日                    | 股票、券商、分點                             |
| Tick 逐筆      | Shioaji + DolphinDB   | `StockTickAPI`            | DolphinDB `tickDB`       | 預設更新起日 `2024-05-10`（`TICK_UPDATE_START_DATE`）；Shioaji 可查區間約自 **2020-03-02**（見 `tasks/update_db` 模組註解） | 需 DDB 環境                             |

## API 與資料表對照

| API 類別                    | 檔案                                       | 後端        | 關鍵資料表/資料庫                                                                                            | 起始日期                                                                              |
| ------------------------- | ---------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `StockPriceAPI`           | `core/api/stock_price_api.py`            | SQLite    | `price`                                                                                              | 2013-01-01                                                                        |
| `StockChipAPI`            | `core/api/stock_chip_api.py`             | SQLite    | `chip`                                                                                               | 2013-01-01                                                                        |
| `MonthlyRevenueReportAPI` | `core/api/monthly_revenue_report_api.py` | SQLite    | `monthly_revenue`                                                                                    | 2013-01                                                                           |
| `FinancialStatementAPI`   | `core/api/financial_statement_api.py`    | SQLite    | 財報相關表                                                                                                | 2013 Q1                                                                           |
| `FinMindAPI`              | `core/api/finmind_api.py`                | SQLite    | `taiwan_stock_info`、`taiwan_stock_info_with_warrant`、`taiwan_securities_trader_info`、`taiwan_stock_trading_daily_report_secid_agg` | `finmind`／`broker_trading`：`2021-06-30`；`stock_info`／`broker_info` 等為快照，無程式內建歷史起日 |
| `StockTickAPI`            | `core/api/stock_tick_api.py`             | DolphinDB | `tickDB` / `tick`                                                                                    | 預設更新 `2024-05-10`；Shioaji 約 **2020-03-02** 起                                      |

## 更新入口

資料更新統一入口：

```bash
python -m tasks.update_db --target <targets...>
```

支援重點 target 與預設起始（與 `get_update_time_config`／各 updater 行為一致）：

| `--target`                | 預設起始日期                                                       |
| ------------------------- | ------------------------------------------------------------ |
| `price`                   | 2013-01-01                                                   |
| `chip`                    | 2013-01-01                                                   |
| `fs`                      | 2013 年第 1 季                                                  |
| `mrr`                     | 2013 年 1 月                                                   |
| `tick`                    | 2024-05-10（`TICK_UPDATE_START_DATE`）；Shioaji 可查約自 2020-03-02 |
| `finmind`                 | `broker_trading` 區間自 2021-06-30；其餘子項見下                       |
| `stock_info`              | 快照更新，無日期區間                                                   |
| `stock_info_with_warrant` | 快照更新，無日期區間                                                   |
| `broker_info`             | 快照更新，無日期區間                                                   |
| `broker_trading`          | 2021-06-30                                                   |

## 已知限制

- 專案目前無內建加密貨幣 / prediction market collectors（如 Kalshi、Polymarket 實作）。
- `tick` 依賴 DolphinDB 環境與對應連線參數，未設定時無法使用 tick 相關流程。
- 上表「起始日期」與 `tasks.update_db` 的 `get_update_time_config` 一致者，皆定義於 `core/config.py`（`DEFAULT_PRICE_START_DATE`、`DEFAULT_CHIP_START_DATE`、`DEFAULT_START_YEAR`、`TICK_UPDATE_START_DATE`、`FINMIND_BROKER_TRADING_START_DATE` 等）。
- 實際本地 SQLite／DolphinDB 內容可能與預設起日不同，以庫內最早一筆為準。

