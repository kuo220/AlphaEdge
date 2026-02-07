# 魔術數字改為常數／變數建議清單

本文件列出專案中建議將數字改為具名常數或變數的位置，便於後續重構時依序處理。**尚未修改任何程式碼**，僅供規劃用。

---

## 一、Pipeline 相關

### 1. `trader/pipeline/crawlers/utils/request_utils.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 34 | `range(10)` | `SESSION_INIT_MAX_ATTEMPTS = 10` |
| 39 | `timeout=10` | `REQUEST_TIMEOUT_SECONDS = 10` |
| 48 | `time.sleep(10)` | `SESSION_RETRY_DELAY_SECONDS = 10` |
| 61, 78 | `range(3)` | `HTTP_MAX_RETRIES = 3` |
| 63, 80 | `timeout=10` | 同上 `REQUEST_TIMEOUT_SECONDS` |
| 66, 83 | `time.sleep(60)` | `HTTP_RETRY_DELAY_SECONDS = 60` |

同一檔內多處重複的 10、3、60，建議抽成類別常數或模組常數。

---

### 2. `trader/pipeline/crawlers/qx_crawler.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 55 | `range(10)` | Session 建立最大嘗試次數 |
| 60, 82, 102 | `timeout=10` | `REQUEST_TIMEOUT_SECONDS = 10` |
| 67 | `time.sleep(10)` | `SESSION_RETRY_DELAY_SECONDS = 10` |
| 86, 106 | `time.sleep(60)` | `HTTP_RETRY_DELAY_SECONDS = 60` |
| 79, 99 | `i = 3` / 重試次數 | `HTTP_MAX_RETRIES = 3` |
| 1063 | `timeout=30` | `DOWNLOAD_TIMEOUT_SECONDS = 30`（下載用） |
| 1067 | `25 + random.uniform(0, 10)` | `DOWNLOAD_DELAY_BASE = 25`, `DOWNLOAD_DELAY_RANDOM_MAX = 10` |
| 1083, 1267, 1319 | `time.sleep(10)` / `time.sleep(15)` | 具名常數（如 `PAGE_DELAY_SECONDS`, `LARGE_DF_DELAY_SECONDS`） |
| 826, 904 | `html_df[0].shape[0] > 500` | `HTML_TABLE_MIN_ROWS = 500`（或類似閾值） |
| 830, 908 | `df.shape[1] <= 11 and df.shape[1] > 5` | 欄數上下界常數 |
| 1035 | `os.stat(file).st_size > 20000` | `MIN_FILE_SIZE_BYTES = 20000` |
| 1259, 1311 | `len(df) > 50000` | `LARGE_DF_ROW_THRESHOLD = 50000` |
| 1483 | `os.stat(file).st_size < 10000` | `MIN_HTML_FILE_SIZE = 10000` |

---

### 3. `trader/pipeline/updaters/stock_price_updater.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 77, 84 | `len(twse_df) > 2` / `len(tpex_df) > 2` | `MIN_DF_ROWS_AFTER_CLEAN = 2`（可選） |
| 93 | `file_cnt == 100` | `BATCH_SLEEP_EVERY_N_FILES = 100` |
| 96 | `time.sleep(120)` | `BATCH_SLEEP_DURATION_SECONDS = 120` |
| 98 | `random.randint(1, 5)` | `BATCH_RANDOM_DELAY_MIN = 1`, `BATCH_RANDOM_DELAY_MAX = 5` |

---

### 4. `trader/pipeline/updaters/stock_chip_updater.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 94 | `file_cnt == 100` | `BATCH_SLEEP_EVERY_N_FILES = 100` |
| 97 | `time.sleep(120)` | `BATCH_SLEEP_DURATION_SECONDS = 120` |
| 99 | `random.randint(1, 5)` | `BATCH_RANDOM_DELAY_MIN/MAX`（可與 stock_price 共用或各自類別常數） |

---

### 5. `trader/pipeline/updaters/monthly_revenue_report_updater.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 110 | `file_cnt == 10` | `BATCH_SLEEP_EVERY_N_FILES = 10` |
| 113 | `time.sleep(30)` | `BATCH_SLEEP_DURATION_SECONDS = 30` |
| 115 | `random.randint(1, 5)` | `BATCH_RANDOM_DELAY_MIN/MAX` |

---

### 6. `trader/pipeline/updaters/financial_statement_updater.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 198, 276, 354, 431 | `file_cnt == 10` | `BATCH_SLEEP_EVERY_N_FILES = 10` |
| 201, 279, 357, 434 | `time.sleep(30)` | `BATCH_SLEEP_DURATION_SECONDS = 30` |
| 203, 281, 359, 436 | `random.randint(1, 5)` | `BATCH_RANDOM_DELAY_MIN/MAX` |
| 486 | `latest_season == 4` | 可保留（季別語意）或 `LAST_SEASON = 4` |

---

### 7. `trader/pipeline/updaters/stock_tick_updater.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 287, 317 | `remaining_mb < 20` | `TICK_API_MIN_REMAINING_MB = 20`（API 剩餘用量低於此值即停止爬取） |
| 505, 557 | `total_time/60` | 可沿用既有 `SECONDS_PER_MINUTE` 或僅註解（顯示用） |

---

### 8. `trader/pipeline/cleaners/stock_tick_cleaner.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 107 | `time.sleep(0.01)` | `FILE_CLOSE_WAIT_SECONDS = 0.01`（Windows 關檔等待） |
| 110 | `max_retries: int = 3` | 類別常數 `MAX_SAVE_RETRIES = 3`（與他處一致） |
| 111 | `retry_delay: float = 0.1` | `INITIAL_RETRY_DELAY = 0.1` |
| 139 | `retry_delay *= 2` | `RETRY_BACKOFF_MULTIPLIER = 2` |

---

### 9. `trader/pipeline/loaders/stock_tick_loader.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 61 | `max_retries: int = 3`, `retry_delay: float = 1.0` | 可改為類別常數作為預設參數 |
| 97-98 | `start_time: str = "2020.03.01"`, `end_time: str = "2030.12.31"` | `DEFAULT_TICK_DB_START_TIME`, `DEFAULT_TICK_DB_END_TIME` |
| 106 | `HASH([SYMBOL, 25])` | 若 25 為分區數，可為 `TICK_DB_HASH_PARTITIONS = 25` |

---

### 10. `trader/pipeline/utils/stock_tick_utils.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 44, 54 | `datetime.date(2020, 4, 1)` | 模組或類別常數 `TICK_DEFAULT_FALLBACK_DATE` |

---

### 11. `trader/pipeline/cleaners/stock_price_cleaner.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 19 | `datetime.date(2020, 4, 30)` | 已是 instance 屬性；若不會依 instance 變動，可改為類別常數 `TPEX_TABLE_CHANGE_DATE` |
| 131 | `remove_last_n_rows(df, n_rows=2)` | 若 2 會變動可抽成常數；否則可保留 |

---

### 12. `trader/pipeline/cleaners/stock_chip_cleaner.py` / `trader/pipeline/crawlers/stock_chip_crawler.py`

| 檔案 | 行號 | 目前寫法 | 建議常數／說明 |
|------|------|----------|----------------|
| stock_chip_cleaner.py | 23-28 | `datetime.date(2014,12,1)` 等 | 已是 instance 屬性；可考慮類別常數 `TWSE_FIRST_REFORM_DATE` 等（若全專案共用） |
| stock_chip_crawler.py | 34 | `datetime.date(2014, 12, 1)` | 同上，`TPEX_URL_CHANGE_DATE` |

---

### 13. `trader/pipeline/crawlers/financial_statement_crawler.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 260-261 | `start_year: int = 2013`, `end_year: int = 2025` | 預設值可抽成常數（與 tasks/update_db 一致） |
| 300 | `time.sleep(random.uniform(1, 3))` | `CRAWL_DELAY_MIN = 1`, `CRAWL_DELAY_MAX = 3` |

---

### 14. `trader/pipeline/crawlers/monthly_revenue_report_crawler.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 176 | `time.sleep(random.uniform(1, 3))` | 同上 `CRAWL_DELAY_MIN/MAX`（可與 financial_statement_crawler 共用模組常數） |

---

### 15. `trader/pipeline/utils/data_utils.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 301 | `indent: int = 2` | 若希望全專案 JSON 縮排一致，可為 `DEFAULT_JSON_INDENT = 2`（優先級低） |

---

### 16. `trader/pipeline/updaters/finmind_updater.py`

已於先前重構將配額、批次間隔、預設日期等改為類別常數，目前無需再改。以下為可選或文件用：

| 行號 | 目前寫法 | 說明 |
|------|----------|------|
| 859-860 | docstring 範例 `"2021-01-01"`, `"2023-12-31"` | 僅文件範例，可不改 |
| 1043 | `indent=2`（save_json） | 可改為使用 `DataUtils` 的預設或常數（若統一 JSON 縮排） |

---

## 二、Tasks 與設定

### 17. `tasks/update_db.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 124 | `datetime.date(2024, 5, 10)`（TICK start） | 可抽成模組常數或從 config 讀取 |
| 130, 167 | `datetime.date(2013, 1, 1)` | `DEFAULT_CHIP_PRICE_START_DATE` 等 |
| 136, 144, 169, 172 | `2013`, `12`（年/月） | `DEFAULT_START_YEAR`, `DEFAULT_END_MONTH` |
| 152-153, 161-162 | `datetime.date(2021, 6, 30)`, `datetime.date(2026, 1, 23)` 等 | FinMind 預設區間可集中到常數或 config |

建議：若多處共用同一「資料起始日／結束日」，可集中到 `trader/config.py` 或 `trader/pipeline/utils/constant.py`。

---

## 三、策略與回測

### 18. `trader/strategies/stock/momentum_strategy.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 30 | `self.max_holdings: int = 10` | 已是屬性；若希望預設值集中可改為類別常數 `DEFAULT_MAX_HOLDINGS = 10` |
| 33-34 | `datetime.date(2020, 5, 1)`, `datetime.date(2025, 5, 31)` | `DEFAULT_BACKTEST_START_DATE`, `DEFAULT_BACKTEST_END_DATE` |
| 88 | `* 100`（漲跌幅轉百分比） | 可選：`PERCENT_MULTIPLIER = 100`（若多處使用） |
| 90 | `price_chg < 9` | `MIN_PRICE_CHANGE_PCT_FOR_SIGNAL = 9`（漲幅門檻 %） |
| 94 | `stock_quote.volume < 5000` | `MIN_VOLUME_LOTS = 5000`（成交量門檻） |

---

### 19. `trader/strategies/stock/momentum_tick_strategy.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 98 | `price_chg < 9` | 同上 `MIN_PRICE_CHANGE_PCT_FOR_SIGNAL` |
| 106 | `tick.volume < 5000` | 同上 `MIN_VOLUME_LOTS` |

---

### 20. `trader/backtest/report/reporter.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 212 | `diff_pct > 5` | `SPLIT_ADJUSTMENT_WARNING_PCT = 5`（分割調整差異超過此 % 發出警告） |
| 210, 426, 430, 498, 541 | `* 100`（百分比顯示） | 可選：`PERCENT_MULTIPLIER = 100` |
| 660 | `size=15`（matplotlib 等） | 可選：`CHART_FONT_SIZE = 15` |

---

## 四、其他模組

### 21. `trader/utils/market_calendar.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 40 | `stock_test: str = "2330"` | 若僅用於判斷開盤，可為 `MARKET_CALENDAR_TEST_STOCK_ID = "2330"` |

---

### 22. `trader/utils/notify.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 29 | `'code': '2330'` | 若為範例／預設，可為常數（優先級低） |
| 84 | `+ 10`（欄寬） | 可選：`COLUMN_PADDING = 10` |

---

### 23. `trader/utils/account.py`

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 28 | `contracts_timeout=30000` | 若為 API 設定可抽成常數 `CONTRACTS_TIMEOUT_MS = 30000` |

---

### 24. `trader/utils/time.py`

| 行號 | 目前寫法 | 說明 |
|------|----------|------|
| 27-29, 38 | `1912`, `1911` | 民國／西元年轉換，屬領域常數；可抽成 `ROC_EPOCH_YEAR = 1911` 等（可選） |

---

### 25. `trader/others/task.py`（若仍維護）

| 行號 | 目前寫法 | 建議常數／說明 |
|------|----------|----------------|
| 69-70, 73-74, 78-79, 84 等 | 月份、日期範圍（4/26~30, 5/1~31 等） | 財報申報區間等可抽成常數（如 `MRR_APRIL_END_DAY = 30`）以利閱讀與修改 |

---

## 五、建議不抽或低優先級

- **tests/** 內測試資料（如 1000, 800, 100, 2021-01-01）：為測試用假資料，保留即可。
- **HTTP 429**、**status_code == 429**：業界通用碼，保留數字可讀性高。
- **len(x) == 0 / > 0**：布林判斷，一般不抽。
- **iloc 索引、欄位索引**（如 iloc[-2, 6]）：屬資料結構，抽成常數效益不大，除非重複且易變。
- **民國年 1911**：領域常數，可抽但不必須。
- **docstring 內範例數字**：僅說明用，可不改。

---

## 六、實作順序建議

1. **高影響、重複多**：`request_utils.py`、各 updater 的「每 N 筆休息」參數（100/10、120/30、1–5 秒）。
2. **中影響**：`qx_crawler.py` 的 timeout/retry/sleep、`stock_tick_updater` 的 20 MB 門檻、策略的 9%／5000 張。
3. **集中設定**：在 `trader/config.py` 或 `trader/pipeline/utils/constant.py` 定義「預設起始日、結束日、預設年」等，供 `tasks/update_db.py` 與各 updater/crawler 共用。
4. **低優先級**：JSON indent、報表欄寬、字型 size、百分比 100 等。

---

*文件版本：依目前專案狀態整理，實際重構時請以程式碼為準。*
