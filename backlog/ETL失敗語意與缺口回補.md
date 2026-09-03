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
| S3 | loader 失敗一律拋 `DataLoadError` | `stock_price_loader.py`、`loaders/finmind/*.py`、`stock_tick_loader.py`、`sqlite_utils.py`、`futures_{margin,continuous,chip}_updater.py` | `tests/test_loader_failure_reporting.py` 擴充至 16 條 | ✅ | F-043、F-044、F-045、F-046、F-053、F-056；2026-09-03 完成 |
| S4 | updater 缺口偵測與回補、統計行 | `core/pipeline/shared/date_planner.py`（新）、`core/utils/time.py`、六支 updater、`tasks/update_db.py` | `tests/test_date_gap_backfill.py` 19 條 | ✅ | F-050、F-051、F-052、F-054、F-002；F-053 已於 S3 完成；**`--target price` 實跑實測待期貨回補結束** |
| S5 | cleaner 邊界：無成交日的 OHLC、TPEX 欄位數檢查、dividend 去重順序 | `base_cleaner.py`、`stock_price_cleaner.py`、`stock_chip_cleaner.py`、`stock_dividend_loader.py`、`stock_quote_adapter.py`、`scripts/fix_price_no_trade_rows.py` | `tests/test_cleaner_boundaries.py` 12 條；修復腳本 dry-run ＝ 104,046 | ✅ | F-037、F-038、F-047；**修復腳本尚未實際套用**（見完成紀錄） |
| S6 | 入口與日誌：`no_tick` 排除 `futures_tick`、`delete_price_data` 加 dry-run、loguru sink 隔離與 api 桶保留 | `tasks/{update_db,delete_price_data}.py`、`core/api/tw/*.py`、`core/config/{schema,settings}.py`、`core/utils/{notify,log_manager}.py`、`tests/conftest.py` | `tests/test_entrypoint_and_logging.py` 13 條；pytest 實測不再產生 `logs/` | ✅ | F-078、F-079、F-097、F-015、F-017、F-001；F-044 已於 S3 完成 |

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

### S3. loader 失敗一律拋 `DataLoadError` ✅

- **目的**：`etl-ingestion.md` §3.2「失敗必須浮出來」在 `stock_price_loader`、FinMind 三路徑、三支期貨 loader、tick loader 都沒落實（F-043、F-045、F-046、F-056）。
- **做法**：全部改走 `BaseDataLoader.insert_dataframe()` ＋ `finish_load()`；`sqlite_utils.get_table_*_value()` 不再吞 `sqlite3.Error`。
- **產出**：上表所列 loader、`sqlite_utils.py`。
- **驗證方式**：`tests/test_loader_failure_reporting.py` 對每個 loader 各一條「壞檔 → `DataLoadError`」；`update_db` 結束碼 1。
- **相依**：無（可與 S1／S2 平行）。

> **✅ 完成紀錄（2026-09-03）**
> - `stock_price_loader.add_to_db()` 改走 `insert_dataframe()` ＋ `finish_load()`。
>   **順帶解掉 F-044**：舊版每批都把整張 `price` 表的主鍵（近千萬列）讀進記憶體建 set，
>   改用資料庫自己的主鍵約束後記憶體不再隨資料量成長。
> - `finmind/reference_table_loader.py` 的 `except Exception` 改為 `raise DataLoadError`。
> - `finmind/broker_trading_loader.py`：DataFrame 路徑**移除「失敗後盲插」的 fallback**
>   （舊版失敗回 0，呼叫端把 0 當成「本批皆為重複」而回報 SUCCESS）；
>   CSV 路徑的失敗檔不再併入 `skipped_files`，改由 `finish_load()` 拋出。
> - `finmind/broker_trading_updater.py`：跑完若 `stats[ERROR] > 0` 即拋 `DataLoadError`。
>   單一組合失敗仍不中止整批，但不能當作沒發生。
> - `stock_tick_loader.py`：DolphinDB 寫入失敗**原本記在 `info` 等級**（與正常訊息無異），
>   改為 `logger.error` ＋ `DataLoadError`；建庫失敗同樣拋出。
> - `sqlite_utils.py`：三個查詢函式不再 `except sqlite3.Error` 後回 `None`／預設值。
>   「表不存在」與「表是空的」先明確判斷後回 `None`，其餘往外拋——
>   吞掉會讓 updater 以為表是空的而從預設起日重跑整段回補。
> - **（2026-09-03 複查修正）** `futures_margin_updater` 的兩段隔離迴圈原本寫了
>   `except DataLoadError: raise`，而兩個 step 自己正是用 `DataLoadError` 表達失敗——
>   最常見的失敗會直接往外炸，第二段根本不會跑。已改為一併攔下。
> - 期貨三支 updater 的「warning 後跳過」改為拋 `DataLoadError`：
>   保證金一覽表取得／清洗失敗、連續合約**有行情卻排不出換月表**
>   （新增 `UnbuildableSeriesError`，與「該商品尚未回補」區分開）、
>   籌碼的 `blocked_windows`（該有資料卻沒拿到，多半是被擋流量，F-053）。

### S4. updater 缺口偵測與回補、統計行 ✅

- **目的**：續跑起點一律 `MAX(date)+1`（F-050），中間缺的日子永遠不會再被嘗試；`years × seasons` 笛卡兒積（F-054）、quota 逾時只 warning（F-051）、Shioaji 例外算 skipped（F-052）、期貨籌碼月份失敗不計入（F-053）同屬此類。
- **做法**：候選日期 ＝ 交易日曆（`price` 表或 `FuturesCalendar`）− 表內已有日期，而非 `MAX(date)+1`；提供 `--from` 覆寫；每批結束印統計行；`B008` 的 `today()` 預設改在函式內取值（F-002）。
- **產出**：上表所列 updater、`tasks/update_db.py`。
- **驗證方式**：以 tmp DB 建三天資料、刪中間一天、跑 updater 斷言該日被請求；統計行有測試比對字串。
- **相依**：S2、S3。

> **✅ 完成紀錄（2026-09-03）**
> - 新增 `core/pipeline/shared/date_planner.py`：
>   **候選日期 ＝ 日曆 − 表內已有 − 已確認沒有資料**，取代 `MAX(date)+1`。
>   - `price`：沒有外部日曆可用（它自己就是日曆來源），母集合取平日。
>   - `chip`／`margin`：以 `price` 表的交易日為日曆，涵蓋國定假日與**補行交易日**
>     （原本 margin 有一段專屬邏輯處理開市的週六，現已被日曆自然涵蓋而刪除）。
>   - `NoDataDateStore`：JSON 記錄「已向站方確認過、當天確實沒有資料」的日期，
>     國定假日只問一次。**只有 `CrawlResult.NO_DATA` 才寫入**，連線失敗不寫，
>     所以那些日子下次還會再試——這個分野就是整份工作的核心。
> - `dividend` 改為每次都掃整個區間：本來源支援區間查詢，一年一次請求、13 年
>   只有 26 次，而 `MAX(date)+1` 會讓中間任何一年的缺漏永遠補不回來。
>   入庫本來就走 `INSERT OR REPLACE`，重跑是冪等的。
> - **F-054**：`fs`（4 處）與 `mrr`（1 處）的 `for year in years: for period in periods`
>   笛卡兒積改用新的 `TimeUtils.generate_year_period_range()`。原寫法在起點
>   2024Q3、終點 2026Q4 時 `seasons` 只會是 `[3, 4]`，**2025Q1／Q2 與 2026Q1／Q2
>   整整四季不會被爬**；月營收更糟，起點月份大於終點月份時 `months` 直接是空清單。
> - **F-052**：`stock_tick_updater` 的 `if skipped_dates:` 先於失敗判斷，於是
>   「有幾天連不上、其餘幾天本來就沒資料」的股票被算成 skipped；改為先判斷
>   `failed_dates`，並在 `update()` 收尾時對 `failed_stocks > 0` 拋 `DataLoadError`。
> - **F-051**：`broker_trading_updater` 的配額等不回來也計入失敗——舊版只記 warning，
>   於是一次只做了三成的更新仍以結束碼 0 結束，排程看不出需要重跑。
> - **F-002（ruff B008）**：八處 `end_date: datetime.date = datetime.date.today()`
>   改為 `Optional[...] = None` ＋ 函式內取值。
> - `tasks/update_db.py` 新增 `--from YYYY-MM-DD`，覆寫所有以日期為單位的 target 起日。
>
> **⚠️ 未完成的驗收項**：「刪掉 `price` 表任一天後 `--target price` 會回補該日」的
> **實跑實測**要等期貨行情回補結束（避免搶 DB 鎖）。目前以 tmp DB 的單元測試涵蓋
> 同一條路徑（`tests/test_date_gap_backfill.py::test_middle_gap_is_planned_again`）。
>
> **🔁 2026-09-03 複查後補強**（`/code-review high` 抓到兩條會讓本步驟失效的問題）：
> - **同一天只成功一半的日期永遠補不回來**。price／chip／margin 每天打**兩次**
>   請求（上市＋上櫃）。上市成功、上櫃失敗時，上市那批已入庫，於是下次執行時
>   這天落在「表內已有」裡被差集排除——上櫃那半永遠補不回來，而統計行還印著
>   「unreachable 的日期下次執行會自動重試」。
>   `NoDataDateStore` 因此改為 `DateProgressStore`，同時持有 `no_data`
>   （所有來源都說沒有）與 `incomplete`（至少一個來源沒問到），後者會**蓋過**
>   「表內已有」的排除。`UpdateStats.record()` 的回傳值由 `bool` 改為 `CrawlStatus`。
> - **盤中跑一次就把今天永久列為「沒有資料」**。`NO_DATA` 同時代表「休市」與
>   「盤後尚未公布」，兩者在回應上無法區分。`record_no_data()` 因此拒絕寫入
>   當天（含未來）的日期——收盤後那天的資料還抓得到。
> - **chip／margin 結構性落後 price 一天**：兩者以 `price` 表為日曆，而
>   `update_db` 的 CHIP／MARGIN 區塊原本排在 PRICE **之前**。已把 PRICE 移到最前，
>   並加上 `DatePlanner.extend_calendar_tail()`（日曆尾端補平日）作為第二層保險。
> - **cleaner 的 `ColumnLayoutError` 會炸掉整段回補**：一個異常的歷史日期會讓
>   本批已爬好、尚未入庫的日期全部作廢。新增 `BaseDataUpdater.clean_one()`
>   逐日隔離，計入 `clean_failed` 並標記為待重試。

### S5. cleaner 邊界 ✅

- **目的**：無成交的 `--` 被 `fillna(0)` 成 0 價（F-037，`price` 表 104,046 列）、TPEX 位置命名無欄位數檢查（F-038）、dividend 三來源去重依檔名字典序（F-047）。
- **做法**：無成交日 OHLC 保留 `NULL`（或另加 `is_traded` 欄），下游 `StockQuoteAdapter` 濾掉；位置命名前 `assert len(columns) == N`；去重改以來源優先序排序後 `keep="last"`。**注意**：改 `--` 語意會改變 `price` 表既有的 104,046 列，需一次性修復腳本（比照 `scripts/fix_price_etf_stock_id.py`，含 `--dry-run`）。
- **產出**：兩支 cleaner、`stock_dividend_loader.py`、`scripts/fix_price_no_trade_rows.py`。
- **驗證方式**：cleaner 單元測試；修復腳本 dry-run 列數 ＝ 104,046；LONG 回歸若因此改變需與 [回測口徑與日期邊界收斂.md](./回測口徑與日期邊界收斂.md) S2 同批重產 baseline。
- **相依**：無。

> **✅ 完成紀錄（2026-09-03）**
> - **F-037**：`DataUtils.fill_nan()` 新增 `exclude_cols`，`stock_price_cleaner`
>   讓六個價格欄（OHLC ＋ 最後揭示買／賣價）維持 NaN、入庫為 NULL；
>   成交量／金額／筆數仍填 0（那是對的）。
> - `StockQuoteAdapter` 新增 `has_valid_price()`，**NULL 與 0 都濾掉**——
>   尚未執行修復腳本的資料庫也不會拿 0 元價去成交。
> - 新增 `scripts/fix_price_no_trade_rows.py`（含 `--dry-run`），dry-run 實測
>   **104,046 列**，與健檢數字相符。其中 96,089 列成交股數也是 0（真的沒成交），
>   另 7,957 列**有成交量卻 OHLC 全 0**（版面錯位；例如 `2833A` 台壽甲
>   2013-01-02 成交金額 27,521 ÷ 股數 754 ＝ 每股 36.5 元）。兩種都要修。
> - **F-038**：`BaseDataCleaner.check_column_count()` ＋ 新例外 `ColumnLayoutError`；
>   套用於 `stock_price_cleaner.clean_tpex_price()`（改制前 13 欄／改制後 15 欄）
>   與 `stock_chip_cleaner.clean_tpex_chip()` 的三處 `dict(zip(...))` 重新命名。
>   `zip()` 長度不一時會**安靜地截斷**，多出來的欄位保留原名、之後被 reindex 填成 0。
> - **F-047**：`StockDividendLoader.SOURCE_PRIORITY` ＝ `["finmind", "tpex", "twse"]`，
>   去重改為依此排序後 `keep="last"`。舊版直接對 `sorted(dir.iterdir())` 的結果
>   `keep="last"`，勝出的是誰取決於檔名字母順序——今天剛好是 `twse_`，
>   日後多一個來源或改個前綴就會換人，而且不會有任何跡象。
>
> **⚠️ 修復腳本尚未實際套用**：`--dry-run` 已驗證，實際寫入會改動 `price` 表
> 104,046 列，屬於使用者的正式資料庫，故留給使用者自行執行：
> `python scripts/fix_price_no_trade_rows.py`。
> **回歸不受影響**：`pytest -m slow` 10 條（含 LONG／SHORT 回歸）在 adapter
> 改動後仍全綠——那些列本來就因成交量門檻不會被選進去，故不需重產 baseline。

### S6. 入口與日誌 ✅

- **目的**：預設 `no_tick` 含 `futures_tick`（F-078）讓每晚預設更新永遠紅；`delete_price_data` 無 dry-run（F-079）；loguru sink 未帶 `filter=`（F-001）且 `logs/api/` 每天長 100 MB（F-097）；`TICK_DB_PATH` 在 `.env` 缺 `DDB_PATH` 時變成 `NonetickDB`（F-015）；LINE Notify 已停服（F-017）；`stock_price_loader` 每批把整表主鍵讀進記憶體（F-044）。
- **做法**：`no_tick` 排除 `{TICK, FUTURES_TICK}`；`delete_price_data` 加 `--dry-run`／`--yes`；`LogManager.setup_logger()` 帶 `filter=lambda r: r["extra"].get("module") == name`，api 桶檔案 sink 預設 `WARNING`；`tests/conftest.py` 以 `pytest_sessionstart` 把 `setup_logger`／`setup_backtest_logger` 換成 no-op（健檢期間已用 scratchpad 外掛驗證可行）；`clean_logs --apply --bucket api --days 7` 掛在 `update_db` 收尾；`TICK_DB_PATH` 缺值即 raise；`notify.py` 改 LINE Messaging API 或移除；主鍵去重改成 `INSERT OR IGNORE` 後比對 `rowcount`。
- **產出**：`tasks/update_db.py`、`tasks/delete_price_data.py`、`core/utils/log_manager.py`、`core/utils/notify.py`、`core/config/schema.py`、`tests/conftest.py`。
- **驗證方式**：見進度表。
- **相依**：`log_manager.py` 部分等期貨回補結束；其餘無。

> **🔄 進度紀錄（2026-09-03）**
>
> **已完成：**
> - **F-078**：新增 `TICK_DATA_TYPES = {TICK, FUTURES_TICK}`，`no_tick` 一律排除。
>   舊版只排除 `DataType.TICK`，於是預設的 `python -m tasks.update_db` 會去跑
>   期貨 tick——沒有 Shioaji 金鑰的機器每晚都以結束碼 1 收場，久了就沒人在看那個紅燈。
> - **F-079**：`delete_price_data` 改為**預設只預覽**，`--apply` 才寫入，
>   且互動確認要求輸入完整日期；`--yes` 供排程跳過確認，非互動環境沒有 `--yes`
>   一律拒絕執行。
> - **F-097**：`API_LOG_FILE_LEVEL = "WARNING"` 收在 `core/config/settings.py`，
>   12 支 `core/api/tw/*.py` 共用；console 不受影響。
>   `update_db` 收尾新增 `cleanup_api_logs()`（`clean_logs --apply --bucket api --days 7`），
>   清理失敗只記 warning、不影響更新結果。
> - **F-015**：`TICK_DB_PATH` 缺 `DDB_PATH` 時為 `None` 而非 `"NonetickDB"`，
>   新增 `require_tick_db_path()` 在三處（`stock_tick_loader.connect()`、
>   `futures_tick_loader.connect()`、`stock_tick_api.setup()`）連線前拋出。
>   **刻意不在 import 時 raise**：`core.config` 是全專案共用入口，沒有 DolphinDB
>   的機器（CI、容器、只跑回測的開發機）連 import 都會失敗。
> - **F-017**：`notify.py` 由已停服的 LINE Notify（2025-03-31）改為
>   **LINE Messaging API** 的 push message；未設定 `LINE_CHANNEL_ACCESS_TOKEN`／
>   `LINE_PUSH_TARGET_ID` 時只警告一次並跳過（盤中不該因通知沒設定而中斷下單），
>   但送出失敗一定記 `logger.error`——舊版連回應狀態都不看。`.env.example` 已補上。
> - `tests/conftest.py` 以 `pytest_sessionstart` 把 `setup_logger`／
>   `setup_backtest_logger` 換成 no-op；實測 `rm -rf logs && pytest` 後不再產生 `logs/`。
>
> **F-001（2026-09-03 19:05 期貨回補結束後補上）**：
> - loguru 的 sink **預設收下整個行程的每一行**，而本專案有 33 個
>   `setup_logger()` 呼叫端——`core/api/` 的一次查詢會同時寫進 `logs/api/`、
>   `logs/pipeline/`、`logs/backtest/` 底下的**每一個**檔案。
>   `logs/api/` 每天長 100 MB（F-097），大部分不是 api 自己的日誌。
> - 新增 `LogManager.build_bucket_filter()`，三個桶構成一個**分割**：
>   `api`／`backtest` 用白名單前綴，其餘（含 `pipeline`）用**排除法**收
>   「沒有被其他桶認領」的記錄。
> - **刻意不用 `logger.bind(module=...)` 過濾**：沒有 bind 的模組會整批消失，
>   那比寫太多更糟；排除法則讓新增的套件自動落進 pipeline 桶。
> - ⚠️ **同一個桶內的檔案仍會互收**（`update_price.log` 也會收到
>   `update_chip.log` 的內容）。逐檔隔離必須讓每個呼叫端 bind 自己的名字，
>   屬另一階段的工作；本次先拿掉跨桶重複，那是量體的主要來源。
