# 美股 ETL 與回測架構規劃

本文件目標：

1. 檢視目前 `AlphaEdge` 檔案架構是否需要調整，才能順利擴充美股。
2. 提出一套貼近業界常見做法的美股 ETL + 回測架構（可逐步落地）。

---

## 一、現況評估：目前架構需不需要改？

結論：**需要做「增量式調整」，不需要大翻修。**

### 目前可沿用的優點

- `trader/pipeline` 已採用 `crawlers` / `cleaners` / `loaders` / `updaters` 分層，這是標準 ETL 架構。
- `tasks/update_db.py` 已有多 target 的更新入口，適合新增美股更新 target。
- `trader/backtest`、`trader/strategies` 已有策略執行與結果輸出流程，可複用核心回測引擎概念。

### 目前主要缺口

- 現有資料模型與 API 命名幾乎都是台股語意（如 `stock_id`、台股資料表），美股需求（`ticker`、`exchange`、`adjusted close`、拆股/配息）需要新層。
- 資料來源會多樣化（Polygon、Alpaca、Yahoo、IEX、SEC、FMP），目前缺乏「provider 抽象層」來統一外部 API。
- 回測目前偏單市場單資產流程，若要做美股（含多交易所、時區、日曆）需要標準化市場 metadata。

### 建議原則

- **保留現有台股流程不動**，美股採「平行模組」建置，降低回歸風險。
- **共享核心，不共享市場細節**：共用工具層/執行框架，但市場欄位、交易日曆、成本模型分開。

---

## 二、建議目錄調整（最小可行重構）

建議以「市場維度」補一層，避免未來再擴到港股/期貨時重工。

```text
trader/
├── api/
│   ├── tw/                          # 既有台股 API（逐步搬遷，先可保留）
│   └── us/                          # 新增：美股查詢 API（對內）
│       ├── price_api.py
│       ├── fundamentals_api.py
│       ├── corporate_actions_api.py
│       └── universe_api.py
├── pipeline/
│   ├── shared/                      # 新增：跨市場共用元件
│   │   ├── base_crawler.py
│   │   ├── base_cleaner.py
│   │   ├── base_loader.py
│   │   ├── base_updater.py
│   │   └── checkpoint_store.py
│   ├── tw/                          # 台股 ETL（現有程式可逐步歸位）
│   └── us/                          # 新增：美股 ETL
│       ├── providers/
│       │   ├── base.py              # Provider 介面（fetch_xxx）
│       │   ├── polygon_provider.py
│       │   └── yahoo_provider.py
│       ├── crawlers/
│       │   ├── us_price_crawler.py
│       │   ├── us_fundamentals_crawler.py
│       │   ├── us_actions_crawler.py
│       │   └── us_universe_crawler.py
│       ├── cleaners/
│       │   ├── us_price_cleaner.py
│       │   ├── us_fundamentals_cleaner.py
│       │   └── us_actions_cleaner.py
│       ├── loaders/
│       │   ├── us_price_loader.py
│       │   ├── us_fundamentals_loader.py
│       │   └── us_actions_loader.py
│       └── updaters/
│           ├── us_price_updater.py
│           ├── us_fundamentals_updater.py
│           └── us_market_updater.py
├── backtest/
│   ├── engine/                      # 新增：撮合/事件循環/成本模型
│   │   ├── event_loop.py
│   │   ├── order_matcher.py
│   │   ├── portfolio.py
│   │   └── fee_models.py
│   ├── datafeed/
│   │   ├── tw_datafeed.py
│   │   └── us_datafeed.py
│   ├── calendars/
│   │   ├── tw_calendar.py
│   │   └── us_calendar.py
│   └── report/                      # 既有 reporter 可延伸
├── strategies/
│   ├── tw/
│   └── us/                          # 新增：美股策略
│       ├── base.py
│       └── momentum_us_strategy.py
└── models/
    ├── shared/
    ├── tw/
    └── us/
```

---

## 三、美股 ETL 設計（業界常見模式）

## 3.1 資料域切分（Data Domains）

建議先做四個最核心 domain：

1. **Universe（股票池）**  
   ticker、交易所、是否可交易、產業分類、上市/下市狀態。
2. **Prices（行情）**  
   OHLCV（日線先行）、adjusted close、資料來源與版本。
3. **Corporate Actions（公司行為）**  
   split、dividend，用來還原/調整回測價格序列。
4. **Fundamentals（基本面）**  
   財報關鍵欄位（營收、EPS、毛利率），先做低頻資料。

## 3.2 ETL 分層責任

- `crawler`: 單純對外 API 拉資料（含 retry、rate limit、timeout、raw schema）。
- `cleaner`: 欄位標準化（`ticker`, `trade_date`, `open/high/low/close/adj_close/volume`）、型別校正、重複去除。
- `loader`: 寫入 DB（upsert、批次寫入、唯一鍵約束）。
- `updater`: 流程編排（日期範圍切片、checkpoint、錯誤重試策略）。

## 3.3 關鍵工程機制

- **Checkpoint / Resume**：以 `(dataset, ticker, date)` 或 `(dataset, batch_window)` 記錄進度。
- **Idempotent 寫入**：DB 用 `UNIQUE` + `UPSERT`，同批重跑不重複。
- **Data Quality Gate**：在 loader 前檢查空值率、價格邏輯（`low <= open/close <= high`）。
- **Source Priority**：主來源失敗時 fallback（例如 Polygon -> Yahoo）。
- **Metadata 審計**：保留 `source`, `ingested_at`, `schema_version`, `job_id`。

## 3.4 建議資料表（SQLite 先行，未來可升級）

- `us_universe`
- `us_price_daily`
- `us_corporate_actions`
- `us_fundamentals_quarterly`
- `etl_job_runs`（批次執行紀錄）
- `etl_checkpoints`（斷點續跑）

建議唯一鍵：

- `us_price_daily`: `(ticker, trade_date, source)`
- `us_corporate_actions`: `(ticker, action_date, action_type, source)`
- `us_fundamentals_quarterly`: `(ticker, fiscal_period_end, source)`

---

## 四、美股回測架構設計（業界常見模式）

## 4.1 回測核心分層

1. **DataFeed**：供應策略所需資料（價格、公司行為、基本面）。
2. **Signal / Strategy**：產生交易訊號（不直接操作資金帳本）。
3. **Execution Simulator**：模擬成交（滑價、手續費、最小交易單位）。
4. **Portfolio / Risk**：倉位、現金、風險控制（單檔上限、曝險限制）。
5. **Performance / Report**：績效指標與圖表輸出。

## 4.2 美股特有設計點

- **交易日曆**：使用 NYSE/NASDAQ 交易日，不可直接沿用台股日曆。
- **時區統一**：建議內部統一 UTC 儲存，顯示轉 `America/New_York`。
- **價格調整模式**：支援 `raw` 與 `adjusted` 兩種回測模式（由策略參數決定）。
- **成本模型**：手續費、SEC fee、最小費用、滑價模型需可插拔。
- **流動性過濾**：回測前過濾平均成交量太低標的，避免不實際成交假象。

## 4.3 回測輸入契約（建議）

策略最少依賴以下欄位：

- `ticker`
- `datetime`（或 `trade_date`）
- `open`, `high`, `low`, `close`, `adj_close`, `volume`
- `is_trading_day`

若使用基本面：

- `report_date`
- `publish_date`
- 財務欄位（如 `revenue`, `eps_ttm`）

---

## 五、任務入口與執行流程建議

## 5.1 CLI target 建議（對齊現有 `tasks/update_db.py` 風格）

- `us_universe`
- `us_price`
- `us_actions`
- `us_fundamentals`
- `us_all`（不含高頻）

## 5.2 典型日更流程

1. 更新 `us_universe`（新增/下市股票狀態）。
2. 更新 `us_price`（昨日到今日）。
3. 更新 `us_actions`（拆股/配息）。
4. 依需要更新 `us_fundamentals`（低頻，週更或月更）。
5. 寫入 `etl_job_runs` 與資料品質統計。

---

## 六、對現有專案的實作順序（建議 3 階段）

## Phase 1：最小可跑版本（2~4 週）

- 建立 `trader/pipeline/us`、`trader/api/us`、`trader/strategies/us`。
- 完成 `us_universe + us_price_daily` ETL（含 checkpoint + upsert）。
- 新增一個 `USMomentumStrategy`（日線）。
- 回測報表沿用既有 `reporter`，先完成可比較的資產曲線與交易明細。

## Phase 2：回測可信度提升（2~3 週）

- 補 `us_corporate_actions`，支援 raw/adjusted 回測切換。
- 新增成本模型（手續費 + 滑價）。
- 補資料品質檢核與異常告警（例如缺洞天數、成交量異常）。

## Phase 3：策略研究效率提升（3~6 週）

- 加入 `us_fundamentals`，支援因子/基本面策略。
- 建立參數掃描（walk-forward / grid search）框架。
- 規劃多市場共用介面，逐步把台股流程也整理為 `tw/` 子模組。

---

## 七、最後結論

- 你的專案現在的核心設計是健康的，**不用重寫**。
- 但要支撐美股且維持可維運性，建議做「市場分層 + provider 抽象 + 回測核心拆分」。
- 最佳做法是先做平行模組（`us/`），跑通最小閉環後再逐步抽共用元件，避免一次性大改造成風險。

