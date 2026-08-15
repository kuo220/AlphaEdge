# Data Coverage — AlphaEdge 資料覆蓋範圍

本文件描述目前 `AlphaEdge` 程式碼中**實際可用**的資料來源與對應模組。

## 總覽

| 類別           | 來源                    | 主要模組                      | 儲存位置                     | 起始日期                                                                                                  | 備註                                   |
| ------------ | --------------------- | ------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 股票日線         | 台股資料來源（由 pipeline 更新） | `StockPriceAPI`           | SQLite `price`           | 2013-01-01                                                                                            | 回測常用；對應 `DEFAULT_PRICE_START_DATE`   |
| 三大法人籌碼       | 台股資料來源（由 pipeline 更新） | `StockChipAPI`            | SQLite `chip`            | 2013-01-01                                                                                            | 回測/選股可用；對應 `DEFAULT_CHIP_START_DATE` |
| 除權除息          | **上市**：證交所 `TWT49U`；**上櫃**：櫃買中心 `bulletin/exDailyQ` | `StockDividendAPI`        | SQLite `dividend`        | 2013-01-01（`DEFAULT_DIVIDEND_START_DATE`）                                                             | 股價還原係數、現金股利、開盤競價基準       |
| 月營收          | 台股資料來源（由 pipeline 更新） | `MonthlyRevenueReportAPI` | SQLite `monthly_revenue` | 2013-01（`DEFAULT_START_YEAR` 起、1 月）                                                                   | 基本面可用                                |
| 財報           | 台股資料來源（由 pipeline 更新） | `FinancialStatementAPI`   | SQLite 各財報表              | 2013 年第 1 季（`DEFAULT_START_YEAR`）                                                                     | 基本面可用                                |
| FinMind 參考資料 | FinMind API           | `FinMindAPI`              | SQLite FinMind 相關表       | 券商分點：`2021-06-30`（`FINMIND_BROKER_TRADING_START_DATE`）；台股總覽／證券商為 API 快照，更新流程未帶歷史起日                    | 股票、券商、分點                             |
| Tick 逐筆      | Shioaji + DolphinDB   | `StockTickAPI`            | DolphinDB `tickDB`       | 預設更新起日 `2024-05-10`（`TICK_UPDATE_START_DATE`）；Shioaji 可查區間約自 **2020-03-02**（見 `tasks/update_db` 模組註解） | 需 DDB 環境                             |

## API 與資料表對照

| API 類別                    | 檔案                                       | 後端        | 關鍵資料表/資料庫                                                                                            | 起始日期                                                                              |
| ------------------------- | ---------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `StockPriceAPI`           | `core/api/stock_price_api.py`            | SQLite    | `price`                                                                                              | 2013-01-01                                                                        |
| `StockChipAPI`            | `core/api/stock_chip_api.py`             | SQLite    | `chip`                                                                                               | 2013-01-01                                                                        |
| `StockDividendAPI`        | `core/api/stock_dividend_api.py`         | SQLite    | `dividend`                                                                                           | 2013-01-01                                                                        |
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
| `dividend`                | 2013-01-01                                                   |
| `fs`                      | 2013 年第 1 季                                                  |
| `mrr`                     | 2013 年 1 月                                                   |
| `tick`                    | 2024-05-10（`TICK_UPDATE_START_DATE`）；Shioaji 可查約自 2020-03-02 |
| `finmind`                 | `broker_trading` 區間自 2021-06-30；其餘子項見下                       |
| `stock_info`              | 快照更新，無日期區間                                                   |
| `stock_info_with_warrant` | 快照更新，無日期區間                                                   |
| `broker_info`             | 快照更新，無日期區間                                                   |
| `broker_trading`          | 2021-06-30                                                   |

## 股價還原（除權息調整）

回測的**訊號計算預設使用還原價**（後復權），成交與成本一律使用原始價。

### 用途界線（取錯會直接算錯錢）

| 用途 | 該用哪個 | 取值方式 |
|------|----------|----------|
| 策略訊號（漲跌幅、均線、動能） | **還原價** | `StockQuote.signal_close`、`BaseStockStrategy.get_signal_close_map()`、`StockPriceAPI.get_adjusted_close_*()` |
| 成交價、手續費、證交稅 | **原始價** | `StockQuote.close`、`StockPriceAPI.get_close_map()` |
| 漲跌停與價格檔位判定 | **原始價** | 同上；除權息日的基準改用 `dividend` 表的**開盤競價基準** |

**「今日價走 quote、昨日價走 API」是兩條不同的路徑**，只還原一邊會比完全不還原更糟且不會報錯。
策略請一律以 `get_signal_close_map()` 取昨日價，它會依引擎的還原模式自動配對。

### 還原方式

- **後復權**：以最早日為基準，歷史價格不變、除權息之後的價格往上還原。
  係數 = Π（除權息前收盤價 / 除權息參考價），取所有「除權息日 ≤ 查詢日」。
- **查詢時即時還原**，不在 `price` 表落地還原欄位——避免出現「還原價與原始價不同步」
  且不會報錯的資料腐化。
- **不用前復權**：前復權會讓同一個歷史日期的價格隨每次新除權息而改變，回歸 baseline 會自動失效。

### 開關

`build_backtester(strategy, adjusted_price=True)`，預設啟用。設為 `False` 可還原成
2026-08-15 之前的行為（訊號直接使用原始價）。

## 已知限制

- 專案目前無內建加密貨幣 / prediction market collectors（如 Kalshi、Polymarket 實作）。
- `tick` 依賴 DolphinDB 環境與對應連線參數，未設定時無法使用 tick 相關流程。
- 上表「起始日期」與 `tasks.update_db` 的 `get_update_time_config` 一致者，皆定義於 `core/config.py`（`DEFAULT_PRICE_START_DATE`、`DEFAULT_CHIP_START_DATE`、`DEFAULT_START_YEAR`、`TICK_UPDATE_START_DATE`、`FINMIND_BROKER_TRADING_START_DATE` 等）。
- 實際本地 SQLite／DolphinDB 內容可能與預設起日不同，以庫內最早一筆為準。

### 股價還原的已知限制

- **`tick` 不做還原**：tick 為當日盤中資料，跨日還原無意義。日內策略若需跨日比較，須自行處理。
- **只處理除權除息**，**不涵蓋**下列同樣會造成價格不連續的公司行動：
  **減資**、**合併**、**股票代號變更**、**下市**。這些的資料源與處理方式都不同。
- **上市的現金股利在「權息並存」時為 `NULL`**：證交所 `TWT49U` 只提供「權值+息值」合計，
  其「減除股利參考價」欄在權息並存時語意不一致，無法可靠拆分（2024 年上市 1,184 筆中
  85 筆為 `NULL`）。**上櫃不受影響**——櫃買中心直接提供 `現金股利` 與 `每仟股無償配股`。
  需要現金股利的用途（如放空的股利補償）須另接股利政策資料源。
  **還原係數不受此限制影響**，它只用到前收盤價與參考價。
- **查無資料與「無除權息」不可區分**：`get_cumulative_factor()` 兩種情況都回傳 `1.0`。
  若某段期間的 `dividend` 資料未更新，該期間會安靜地使用未還原價格。更新資料後
  請確認 `dividend` 表的日期涵蓋整個回測區間。

