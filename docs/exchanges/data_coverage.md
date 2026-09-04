# Data Coverage — AlphaEdge 資料覆蓋範圍

本文件描述目前 `AlphaEdge` 程式碼中**實際可用**的資料來源與對應模組。

## 總覽

| 類別           | 來源                    | 主要模組                      | 儲存位置                     | 起始日期                                                                                                  | 備註                                   |
| ------------ | --------------------- | ------------------------- | ------------------------ | ----------------------------------------------------------------------------------------------------- | ------------------------------------ |
| 股票日線         | 台股資料來源（由 pipeline 更新） | `StockPriceAPI`           | SQLite `price`           | 2013-01-01                                                                                            | 回測常用；對應 `DEFAULT_PRICE_START_DATE`   |
| 三大法人籌碼       | 台股資料來源（由 pipeline 更新） | `StockChipAPI`            | SQLite `chip`            | 2013-01-01                                                                                            | 回測/選股可用；對應 `DEFAULT_CHIP_START_DATE` |
| 除權除息          | **上市**：證交所 `TWT49U`；**上櫃**：櫃買中心 `bulletin/exDailyQ` | `StockDividendAPI`        | SQLite `dividend`        | 2013-01-01（`DEFAULT_DIVIDEND_START_DATE`）                                                             | 股價還原係數、現金股利、開盤競價基準       |
| 融資融券餘額       | **上市**：證交所 `MI_MARGN`；**上櫃**：櫃買中心 `margin/balance` | `StockMarginAPI`          | SQLite `margin`          | 2013-01-01（`DEFAULT_MARGIN_START_DATE`）                                                              | 券源檢核（`check_borrowable`）、券資比；歷史回補已於 2026-08-16 完成（574 萬列、3,330 個交易日） |
| 月營收          | 台股資料來源（由 pipeline 更新） | `MonthlyRevenueReportAPI` | SQLite `monthly_revenue` | 2013-01（`DEFAULT_START_YEAR` 起、1 月）                                                                   | 基本面可用                                |
| 財報           | 台股資料來源（由 pipeline 更新） | `FinancialStatementAPI`   | SQLite 各財報表              | 2013 年第 1 季（`DEFAULT_START_YEAR`）；**`equity_change` 例外，目前僅 2020Q1**                                    | 基本面可用；權益變動表的資料形狀與限制見 [權益變動表](../pipeline/equity-change.md) |
| FinMind 參考資料 | FinMind API           | `FinMindAPI`              | SQLite FinMind 相關表       | 券商分點：`2021-06-30`（`FINMIND_BROKER_TRADING_START_DATE`）；台股總覽／證券商為 API 快照，更新流程未帶歷史起日                    | 股票、券商、分點                             |
| 台期貨日線       | TAIFEX 每日行情頁（POST） | `FuturesPriceAPI`（`core/api/tw/futures_price_api.py`） | SQLite `tw_futures.db` `futures_price_daily` | 2015-01-01（`DEFAULT_FUTURES_START_DATE`）                                                              | 日盤／夜盤分列存（`session` 欄位）；指數期貨 7 檔（`FUTURES_TARGET_PRODUCTS`：TX／MTX／TMF／TE／ZEF／TF／ZFF，**歷史回補已於 2026-09-04 完成並驗收**，逐檔涵蓋見〈已知限制〉）＋ 股票期貨（`--target futures_stock_price`，預設流動性前 20 檔） |
| 台期貨連續合約   | 由 `futures_price_daily` 衍生（不連網路） | `FuturesPriceAPI`（`get_continuous*`） | SQLite `tw_futures.db` `futures_continuous` | 同上                                                                                                    | 3 種調整方式 × 3 種換月規則；每次 `--target futures_continuous` 整段重建 |
| 台期貨保證金     | TAIFEX 公告附件（CSV） | `FuturesMarginAPI`          | SQLite `tw_futures.db` `futures_margin_history`（指數類每口金額）、`stock_futures_margin_rate_history`（股票類比例） | 2020-03（更早為掃描影像，見 [台期貨保證金ETL](../../backlog/台期貨保證金ETL.md) S6） | 變動序列，達門檻才有新列 |
| 台期貨籌碼       | TAIFEX 三大法人／大額交易人／選擇權 PCR | `FuturesChipAPI`            | SQLite `tw_futures.db` `futures_institutional_chip`、`futures_large_trader`、`futures_put_call_ratio` | 歷史回補進行中（2026-09-02）                                                                          | `get_available()` 只回傳查詢日之前已公布者（避免前視） |
| 股票期貨標的池     | TAIFEX 標的證券一覽表（GET） | 尚無 API                    | SQLite `tw_futures.db` `futures_stock_universe` | 2026-08-29（首份快照）                                                                                   | **快照序列**：來源無掛牌／下市日欄位，兩者由差分推得；商品清單取用一律走 `FuturesStockUniverseUpdater.get_active_products()` |
| Tick 逐筆      | Shioaji + DolphinDB   | `StockTickAPI`            | DolphinDB `tickDB`       | 預設更新起日 `2024-05-10`（`TICK_UPDATE_START_DATE`）；Shioaji 可查區間約自 **2020-03-02**（見 `tasks/update_db` 模組註解） | 需 DDB 環境                             |

## API 與資料表對照

| API 類別                    | 檔案                                       | 後端        | 關鍵資料表/資料庫                                                                                            | 起始日期                                                                              |
| ------------------------- | ---------------------------------------- | --------- | ---------------------------------------------------------------------------------------------------- | --------------------------------------------------------------------------------- |
| `StockPriceAPI`           | `core/api/tw/stock_price_api.py`         | SQLite    | `price`                                                                                              | 2013-01-01                                                                        |
| `StockChipAPI`            | `core/api/tw/stock_chip_api.py`          | SQLite    | `chip`                                                                                               | 2013-01-01                                                                        |
| `StockDividendAPI`        | `core/api/tw/stock_dividend_api.py`      | SQLite    | `dividend`                                                                                           | 2013-01-01                                                                        |
| `StockMarginAPI`          | `core/api/tw/stock_margin_api.py`        | SQLite    | `margin`                                                                                             | 2013-01-01                                                                        |
| `MonthlyRevenueReportAPI` | `core/api/tw/monthly_revenue_report_api.py` | SQLite    | `monthly_revenue`                                                                                    | 2013-01                                                                           |
| `FinancialStatementAPI`   | `core/api/tw/financial_statement_api.py` | SQLite    | `balance_sheet`、`comprehensive_income`、`cash_flow`、`equity_change`                                  | 2013 Q1；`equity_change` 目前僅 2020Q1                                               |
| `FinMindAPI`              | `core/api/tw/finmind_api.py`             | SQLite    | `taiwan_stock_info`、`taiwan_stock_info_with_warrant`、`taiwan_securities_trader_info`、`taiwan_stock_trading_daily_report_secid_agg` | `finmind`／`broker_trading`：`2021-06-30`；`stock_info`／`broker_info` 等為快照，無程式內建歷史起日 |
| `StockTickAPI`            | `core/api/tw/stock_tick_api.py`          | DolphinDB | `tickDB` / `tick`                                                                                    | 預設更新 `2024-05-10`；Shioaji 約 **2020-03-02** 起                                      |
| `FuturesPriceAPI`         | `core/api/tw/futures_price_api.py`       | SQLite    | `futures_price_daily`、`futures_continuous`（`tw_futures.db`）                                         | 2015-01-01                                                                        |
| `FuturesMarginAPI`        | `core/api/tw/futures_margin_api.py`      | SQLite    | `futures_margin_history`、`stock_futures_margin_rate_history`                                          | 2020-03                                                                           |
| `FuturesChipAPI`          | `core/api/tw/futures_chip_api.py`        | SQLite    | `futures_institutional_chip`、`futures_large_trader`、`futures_put_call_ratio`                        | 回補中                                                                            |
| `FuturesStockUniverseAPI` | `core/api/tw/futures_stock_universe_api.py` | SQLite | `futures_stock_universe`                                                                             | 2026-08-29（首份快照）                                                              |

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
| `margin`                  | 2013-01-01（`DEFAULT_MARGIN_START_DATE`）                    |
| `fs`                      | 2013 年第 1 季；`equity_change` 為逐檔查詢，歷史回補進行中（目前僅 2020Q1）        |
| `mrr`                     | 2013 年 1 月                                                   |
| `tick`                    | 2024-05-10（`TICK_UPDATE_START_DATE`）；Shioaji 可查約自 2020-03-02 |
| `finmind`                 | `broker_trading` 區間自 2021-06-30；其餘子項見下                       |
| `stock_info`              | 快照更新，無日期區間                                                   |
| `stock_info_with_warrant` | 快照更新，無日期區間                                                   |
| `broker_info`             | 快照更新，無日期區間                                                   |
| `broker_trading`          | 2021-06-30                                                   |
| `futures_price`           | 2015-01-01（`DEFAULT_FUTURES_START_DATE`）；寫入 `tw_futures.db` |
| `futures_stock_universe`  | 快照更新，無日期區間；同一天重跑不產生第二份快照              |
| `futures_stock_price`     | 2015-01-01；商品清單取自標的池、預設流動性前 20 檔（`STOCK_FUTURES_TOP_N`） |
| `futures_continuous`      | 無區間；由 `futures_price_daily` 整段重建                          |
| `futures_margin`          | 快照更新（現行一覽表），沒調整時不新增列                             |
| `futures_chip`            | 各表最新日 +1（盤後公布，盤中跑到「無資料」屬正常）                  |
| `futures_tick`            | 2015-01-01；需 `[tick]` 相依與 Shioaji 金鑰，DolphinDB 寫入路徑未實測 |

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
- **`equity_change`（權益變動表）與其他三張財報表不同**：目前僅涵蓋 2020Q1，其餘 55 個年季待回補；
  且爬取清單取自 `taiwan_stock_info` 現況，**不含已下市公司與興櫃**（倖存者偏誤來源）。
  資料形狀為長表、單位仟元，詳見[權益變動表](../pipeline/equity-change.md)。
- `tick` 依賴 DolphinDB 環境與對應連線參數，未設定時無法使用 tick 相關流程。
- 上表「起始日期」與 `tasks.update_db` 的 `get_update_time_config` 一致者，皆定義於 `core/config/settings.py`（`DEFAULT_PRICE_START_DATE`、`DEFAULT_CHIP_START_DATE`、`DEFAULT_START_YEAR`、`TICK_UPDATE_START_DATE`、`FINMIND_BROKER_TRADING_START_DATE` 等）。
- 實際本地 SQLite／DolphinDB 內容可能與預設起日不同，以庫內最早一筆為準。

### 指數期貨日行情的實際涵蓋（2026-09-04 驗收）

七檔指數期貨的歷史回補已完成。**日盤自上市日起零缺漏**，以 TX＋MTX 的交易日聯集
為基準日曆逐日比對：

| 商品 | 涵蓋區間 | 交易日數 | 對基準日曆的缺漏 | 夜盤起始 |
|------|----------|---------:|:----------------:|----------|
| TX | 2015-01-05 ~ | 2,843 | —（基準本身） | 2017-05-16 |
| MTX | 2015-01-05 ~ | 2,843 | —（基準本身） | 2017-05-16 |
| TE | 2015-01-05 ~ | 2,843 | 0 | 2018-11-20 |
| TF | 2015-01-05 ~ | 2,844 | 0 | **2025-06-24** |
| ZEF | 2021-06-28 ~ | 1,263 | 0 | 2021-06-29（上市次日） |
| ZFF | 2021-12-06 ~ | 1,151 | 0 | **2025-06-24** |
| TMF | 2024-07-29 ~ | 512 | 0 | 2024-07-30（上市次日） |

間隔超過 5 天的斷點共 28 個（TF 14、ZEF 6、ZFF 6、TMF 2），**全部**在基準日曆上
同樣沒有交易日——都是農曆年、清明等連假，無不明缺口。

**內容品質**（2026-09-04 逐檔查核，五檔皆通過）：

- **沒有任何一天是「有日期但沒資料」**：零「整天所有契約都無收盤價」、零「整天成交量全為 0」。
- **`收盤價 IS NULL` 恆等於「該契約當天零成交」**（不一致 0 列）。無成交的契約
  **不寫 0 元**而是 NULL——0 元會被下游當成真實價格，這是 2026-09-03 的無成交價修復
  所建立的口徑。冷門遠月契約占比高（TE 65%、TF 61%），屬正常。
- **價格無解析錯誤**：近月收盤的逐日變動超過 ±10% 者共 9 筆，全部落在真實的漲跌停日
  ——2020-03-19（COVID）、2024-08-05（全球股災）、2025-04-07（關稅衝擊）與 04-10 反彈。
  略微超過 10% 是因為漲跌停以**前一日結算價**為基準，而這裡比的是收盤對收盤。
- **`expiry` 格式零異常**（`YYYYMM` 或 `YYYYMMWn`）。

**兩種 `結算價 IS NULL` 都是來源特性，不是缺漏**：

1. **夜盤全部為 NULL**——結算價由日盤決定，盤後交易時段沒有這個欄位。
2. **日盤每月剛好一筆**，落在**該月契約的最後交易日**（TE／TF 各 140 筆對應 140 個月，
   ZEF 62、ZFF 57、TMF 25，全部一對一）。到期契約當天的最後結算價由**特別結算價**
   另行公布，每日行情頁給「-」。日期會隨連假順延——例如 2015-02-24 不是第三個星期三，
   而是農曆年順延後的最後交易日。
   **回測端已處理**：`TwFuturesSettlementModel.get_quote_mark_price()` 取價順序為
   「結算價 → 收盤價」，到期日自動退回收盤價。

**夜盤的涵蓋率遠低於日盤，而且是來源如此，不是漏抓**：

- 各商品被納入盤後交易的時間不同，**TF 與 ZFF 同為 2025-06-24**，在那之前來源
  就沒有這兩檔的夜盤資料。crawler 對每個日期都會打日盤、夜盤兩次
  （`futures_price_crawler.py` 的 `for session in FuturesSession.data_sessions()`），
  空結果只記 `no data` 而**不落檔**，所以「沒有檔案」等於「來源沒有資料」。
- **要用夜盤資料的策略必須先確認該商品的夜盤起始日**，否則會把「制度上還沒有夜盤」
  誤讀成「當天沒有夜盤成交」。
- 夜盤era 內另有零星缺日（占比 0.2%）：TX／MTX 各缺 5 天
  （2017-06-05、2017-10-02、2018-04-02、2018-07-11、2018-12-24），
  TE 缺 3 天（2018-12-24、2024-06-18、2024-07-03）。日盤當天都有資料，
  故不影響日線策略；未逐一向交易所查證是臨時暫停還是來源缺漏。

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

