# ETL 失敗語意與缺口回補

## Abstract

- **背景／問題**：[全專案架構與邏輯健檢（2026-09）](../docs/dev/health-check-2026-09.md) 於 2026-09-02 在 `core/pipeline/` 抓到 4 條 A 級——台股 5 支 crawler 把連線失敗記成「休市」（F-030）、`stock_price_loader` 入庫失敗只記 log 不拋 `DataLoadError`（F-043）、FinMind 三條入庫路徑失敗算成 skipped（F-045）、台股 updater 續跑只從 `MAX(date)+1` 起算，缺口永不回補（F-050）。四條串起來的後果是：**資料缺一天不會有任何錯誤，回測把那天當休市靜默跳過**（F-028）。另有 19 條 B 級同屬「失敗語意」與「續跑」主題。
- **目標**：每一層對「沒資料」「被擋」「入庫失敗」三種結果有不同的回傳值與結束碼；缺口能被偵測並回補；每批結束有一行統計。
- **範圍界線**：不改資料表 schema、不改 API 介面、不做 PostgreSQL 遷移；tick（DolphinDB）路徑只補失敗回報，不實測寫入。
- **驗收標準**：`pytest -m "not slow"` 全綠且新增測試涵蓋每一條 A 級；`./scripts/run_regression.sh` 雙線逐筆相同；以「刪掉 `price` 表任一天」的實驗確認 `--target price` 會回補該日；`python -m tasks.update_db`（預設）在無 Shioaji 金鑰的機器結束碼為 0。

> **前置條件**：期貨行情回補（`backfill_price.py`，2026-09-02 20:16 起跑）結束前**不動 `core/utils/log_manager.py`**（S6 的日誌隔離部分順延）；其餘步驟改的是台股 crawler／loader／updater，與回補程序無共用檔案，可先動工，但跑 `--target price` 實測要等回補結束以免搶 DB 鎖。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | `RequestUtils` 回傳語意收斂（HTTP 狀態、None vs 空表） | `core/pipeline/shared/request_utils.py`、`core/pipeline/utils/exceptions.py`、`core/pipeline/tw/crawlers/stock_info_crawler.py` | 新增測試：4xx／5xx／逾時／被擋四種結果各自可辨識 | ✅ | F-030 ①②、F-031、F-032；2026-09-03 完成，`tests/test_request_utils.py` 12 條全綠 |
| S2 | 台股 5 支 crawler 的「休市 vs 失敗」分流 | `core/pipeline/shared/base_crawler.py`、`base_updater.py`、五支 crawler、四支 updater | `tests/test_crawl_result_semantics.py` 16 條：連線失敗回 `FAILED`、`unreachable` +1 而非 `no_data` | ✅ | F-030 ③④；2026-09-03 完成 |
| S3 | loader 失敗一律拋 `DataLoadError` | `core/pipeline/tw/loaders/stock_price_loader.py`、`loaders/finmind/*.py`、`futures_{margin,continuous,chip}_loader.py`、`stock_tick_loader.py`、`core/pipeline/utils/sqlite_utils.py` | `tests/test_loader_failure_reporting.py` 擴充：每個 loader 注入一個壞檔即 `DataLoadError`，結束碼 1 | ⬜ | F-043、F-045、F-046、F-056、`etl-ingestion.md` §二 三列期貨 loader 為 `logger.error` |
| S4 | updater 缺口偵測與回補、統計行 | `core/pipeline/tw/updaters/stock_*_updater.py`、`futures_chip_updater.py`、`financial_statement_updater.py`、`monthly_revenue_report_updater.py`、`finmind/broker_trading_updater.py` | 刪掉 `price` 表中間一天後 `--target price` 會補回；每批結束印 `N requested / N no data / N unreachable` | ⬜ | F-050、F-052、F-053、F-054、F-051、F-002（B008） |
| S5 | cleaner 邊界：無成交日的 OHLC、TPEX 欄位數檢查、dividend 去重順序 | `stock_price_cleaner.py`、`stock_chip_cleaner.py`、`stock_dividend_loader.py` | 新增測試：`--` 不再變成 0；欄位數不符即拋錯；三來源去重以來源優先序而非檔名字典序 | ⬜ | F-037、F-038、F-047 |
| S6 | 入口與日誌：`no_tick` 排除 `futures_tick`、`delete_price_data` 加 dry-run、loguru sink 隔離與 api 桶保留 | `tasks/update_db.py`、`tasks/delete_price_data.py`、`core/utils/log_manager.py`、`core/api/tw/*.py`、`tests/conftest.py` | `python -m tasks.update_db` 無金鑰結束碼 0；`delete_price_data --dry-run` 不寫入；pytest 不再寫 `logs/`；`logs/api/` 檔案 sink 預設 WARNING | ⬜ | F-078、F-079、F-001、F-097、F-015、F-017、F-044；**`log_manager.py` 部分等期貨回補結束** |

## 步驟詳述

### S1. `RequestUtils` 回傳語意收斂 ✅

- **目的**：`requests_get/post()` 重試耗盡回 `None` 且從不檢查 HTTP 狀態碼，呼叫端無法區分「被擋」「逾時」「站方回空表」（F-030 ①②、F-031、F-032）。
- **做法**：回傳值改為明確型別（例如 `Optional[requests.Response]` ＋ `raise_for_status()`，或自訂 `FetchResult(status, body, error)`）；`find_best_session()` 10 次失敗改為拋出 `IPBlockedError`；`stock_info_crawler` 對 `response.text` 先檢查狀態碼。
- **產出**：`core/pipeline/shared/request_utils.py`、`core/pipeline/utils/exceptions.py`（新增例外）。
- **驗證方式**：`tests/test_request_utils.py` 擴充四種結果；既有 crawler 測試不變。
- **相依**：無。

> **✅ 完成紀錄（2026-09-03）**
> - 新增 `FetchStatus`（`OK`／`HTTP_ERROR`／`UNREACHABLE`／`BLOCKED`）與 `FetchResult`，
>   以 `RequestUtils.fetch()` 為新入口；4xx 直接回 `HTTP_ERROR` 不重試，
>   429／5xx 列入 `RETRYABLE_STATUS_CODES` 重試後才降為 `UNREACHABLE`。
> - `find_best_session()` 10 次失敗改拋 `IPBlockedError`（新增於 `exceptions.py`）。
>   回 `None` 的舊行為會讓呼叫端接著撞 `AttributeError`，或把「被擋」當成「休市」。
> - `requests_get()`／`requests_post()` 保留 `Optional[Response]` 舊介面（改為 `fetch()` 的薄包裝、
>   只在 HTTP 2xx 回 Response），故期貨等尚未改寫的呼叫端行為不變。
> - `stock_info_crawler` 新增 `fetch_html()`：非 2xx 一律拋 `PipelineError`，
>   不再把錯誤頁交給 `pd.read_html()` 解析成一張看起來正常、實際全錯的表。

### S2. 台股 5 支 crawler 的「休市 vs 失敗」分流 ✅

- **目的**：`crawl_*()` 拿到 `None` 就 log「is a Holiday!」並回空表，連線失敗與休市在 updater 眼裡完全相同（F-030 ③④）。
- **做法**：休市只以「HTTP 200 ＋ 站方明確的『查無資料』訊息」判定；其餘一律回傳失敗（拋例外或回 `CrawlResult.failed`），由 updater 決定重試或計入 unreachable。五支 crawler 共用同一個判斷函式，放 `core/pipeline/shared/base_crawler.py`。
- **產出**：五支 crawler、`base_crawler.py`。
- **驗證方式**：以 monkeypatch 模擬連線失敗，斷言 updater 的 `unreachable` 計數 +1 而非 `skipped`。
- **相依**：S1。

> **✅ 完成紀錄（2026-09-03）**
> - `base_crawler.py` 新增 `CrawlStatus`（`OK`／`NO_DATA`／`FAILED`）、`CrawlResult`，
>   以及五支 crawler 共用的 `looks_like_no_data()`／`judge_fetch()`／`parse_html_table()`。
> - **休市只認「HTTP 200 ＋ 站方明確訊息且回應短於 4 KB」**。長度也是判準：
>   被擋時站方回的是一整頁 HTML，裡頭夾帶「很抱歉」不稀奇，只靠關鍵字會把被擋誤判成休市。
> - **HTTP 200 但解析不出表格改判 `FAILED`**（舊版印 `is a Holiday!`）：站方真的沒資料時
>   會回明確訊息，解析不出來代表版面改了，讓改版靜靜變成「這一年都休市」是原本的坑。
> - 月營收一個年月要打四次請求（TWSE／TPEX × 國內／外國），改為
>   **任一次失敗即整個年月 `FAILED`**——拿到一半的表會產出「少了外國發行人」的月營收，
>   數字看起來正常、實際短少數百檔。原本四支近乎重複的實作合併為
>   `crawl_exchange_monthly_revenue()`。
> - `base_updater.py` 新增 `UpdateStats`：`record()` 對同一天的多個來源做「任一失敗即
>   不算確定沒資料」的判斷，`report()` 印統計行且有 unreachable 時提升為 warning。
>   五支 updater（price／chip／margin／dividend／mrr）都已接上。
> - TPEX 除權息的「區間不符」由 `None` 改判 `FAILED`：那是**取錯資料**（拿到近三日
>   而非整年），不是沒有資料，記成 `NO_DATA` 會讓這一年再也不補。

### S3. loader 失敗一律拋 `DataLoadError` ⬜

- **目的**：`etl-ingestion.md` §3.2「失敗必須浮出來」在 `stock_price_loader`、FinMind 三路徑、三支期貨 loader、tick loader 都沒落實（F-043、F-045、F-046、F-056）。
- **做法**：全部改走 `BaseDataLoader.insert_dataframe()` ＋ `finish_load()`；`sqlite_utils.get_table_*_value()` 不再吞 `sqlite3.Error`。
- **產出**：上表所列 loader、`sqlite_utils.py`。
- **驗證方式**：`tests/test_loader_failure_reporting.py` 對每個 loader 各一條「壞檔 → `DataLoadError`」；`update_db` 結束碼 1。
- **相依**：無（可與 S1／S2 平行）。

### S4. updater 缺口偵測與回補、統計行 ⬜

- **目的**：續跑起點一律 `MAX(date)+1`（F-050），中間缺的日子永遠不會再被嘗試；`years × seasons` 笛卡兒積（F-054）、quota 逾時只 warning（F-051）、Shioaji 例外算 skipped（F-052）、期貨籌碼月份失敗不計入（F-053）同屬此類。
- **做法**：候選日期 ＝ 交易日曆（`price` 表或 `FuturesCalendar`）− 表內已有日期，而非 `MAX(date)+1`；提供 `--from` 覆寫；每批結束印統計行；`B008` 的 `today()` 預設改在函式內取值（F-002）。
- **產出**：上表所列 updater、`tasks/update_db.py`。
- **驗證方式**：以 tmp DB 建三天資料、刪中間一天、跑 updater 斷言該日被請求；統計行有測試比對字串。
- **相依**：S2、S3。

### S5. cleaner 邊界 ⬜

- **目的**：無成交的 `--` 被 `fillna(0)` 成 0 價（F-037，`price` 表 104,046 列）、TPEX 位置命名無欄位數檢查（F-038）、dividend 三來源去重依檔名字典序（F-047）。
- **做法**：無成交日 OHLC 保留 `NULL`（或另加 `is_traded` 欄），下游 `StockQuoteAdapter` 濾掉；位置命名前 `assert len(columns) == N`；去重改以來源優先序排序後 `keep="last"`。**注意**：改 `--` 語意會改變 `price` 表既有的 104,046 列，需一次性修復腳本（比照 `scripts/fix_price_etf_stock_id.py`，含 `--dry-run`）。
- **產出**：兩支 cleaner、`stock_dividend_loader.py`、`scripts/fix_price_no_trade_rows.py`。
- **驗證方式**：cleaner 單元測試；修復腳本 dry-run 列數 ＝ 104,046；LONG 回歸若因此改變需與 [回測口徑與日期邊界收斂.md](./回測口徑與日期邊界收斂.md) S2 同批重產 baseline。
- **相依**：無。

### S6. 入口與日誌 ⬜

- **目的**：預設 `no_tick` 含 `futures_tick`（F-078）讓每晚預設更新永遠紅；`delete_price_data` 無 dry-run（F-079）；loguru sink 未帶 `filter=`（F-001）且 `logs/api/` 每天長 100 MB（F-097）；`TICK_DB_PATH` 在 `.env` 缺 `DDB_PATH` 時變成 `NonetickDB`（F-015）；LINE Notify 已停服（F-017）；`stock_price_loader` 每批把整表主鍵讀進記憶體（F-044）。
- **做法**：`no_tick` 排除 `{TICK, FUTURES_TICK}`；`delete_price_data` 加 `--dry-run`／`--yes`；`LogManager.setup_logger()` 帶 `filter=lambda r: r["extra"].get("module") == name`，api 桶檔案 sink 預設 `WARNING`；`tests/conftest.py` 以 `pytest_sessionstart` 把 `setup_logger`／`setup_backtest_logger` 換成 no-op（健檢期間已用 scratchpad 外掛驗證可行）；`clean_logs --apply --bucket api --days 7` 掛在 `update_db` 收尾；`TICK_DB_PATH` 缺值即 raise；`notify.py` 改 LINE Messaging API 或移除；主鍵去重改成 `INSERT OR IGNORE` 後比對 `rowcount`。
- **產出**：`tasks/update_db.py`、`tasks/delete_price_data.py`、`core/utils/log_manager.py`、`core/utils/notify.py`、`core/config/schema.py`、`tests/conftest.py`。
- **驗證方式**：見進度表。
- **相依**：`log_manager.py` 部分等期貨回補結束；其餘無。
