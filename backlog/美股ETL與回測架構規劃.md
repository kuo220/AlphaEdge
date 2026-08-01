# 美股 ETL 與回測架構規劃

## Abstract

- **背景／問題**：現有資料模型與 API 命名幾乎都是台股語意（`stock_id`、台股資料表），缺少 provider 抽象層，回測也偏單市場單資產流程，無法直接支撐美股（多交易所、時區、交易日曆、拆股／配息）。
- **目標**：以「平行模組」方式建置美股 ETL 與回測（`us/` 子模組），共享核心工具與執行框架，但市場欄位、交易日曆與成本模型分開；跑通最小閉環後再逐步抽共用元件。
- **範圍界線**：**保留現有台股流程不動**，不做一次性大重構；本規劃**不含**日內／高頻資料、不含實盤下單路徑、不含選擇權與 ETF 衍生商品；台股歸位到 `tw/` 排在最後階段且為可選。
- **驗收標準**：`us_universe` 與 `us_price_daily` 可日更且支援 checkpoint／upsert；一支 `USMomentumStrategy` 可跑完回測並產出可比較的資產曲線與交易明細；raw／adjusted 兩種回測模式可切換。

---

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| Phase1-1 | 建立 `us/` 目錄骨架與 provider 介面 | `core/pipeline/us/`、`core/api/us/`、`core/strategies/us/` | 骨架可 import，`base.py` 介面定義完成 | ⬜ | 目錄結構見「建議目錄調整」 |
| Phase1-2 | `us_universe` ＋ `us_price_daily` ETL（含 checkpoint、upsert） | `core/pipeline/us/*`、`core/api/us/price_api.py` | 中斷後可 resume；重跑不產生重複資料 | ⬜ | 相依 Phase1-1 |
| Phase1-3 | `USMomentumStrategy`（日線）跑通回測 | `core/strategies/us/momentum_us_strategy.py` | 產出資產曲線與交易明細 | ⬜ | 相依 Phase1-2；報表沿用既有 `reporter` |
| Phase2-1 | `us_corporate_actions` ＋ raw/adjusted 回測切換 | `core/pipeline/us/*`、`core/backtest/datafeed/us_datafeed.py` | 同一策略在兩種模式下結果可解釋 | ⬜ | 相依 Phase1-2；`BaseDataFeed` 介面由 [回測引擎多市場抽象.md](回測引擎多市場抽象.md) Phase2-5 提供 |
| Phase2-2 | 美股成本模型（手續費 ＋ SEC fee ＋ 滑價） | `core/backtest/models/cost_model.py` | 費用計算有單元測試 | ⬜ | 相依 Phase1-3；路徑對齊 [回測引擎多市場抽象.md](回測引擎多市場抽象.md) 的 `BaseCostModel` |
| Phase2-3 | 資料品質檢核與異常告警 | `core/pipeline/us/*` | 缺洞天數、成交量異常可被偵測 | ⬜ | 相依 Phase1-2 |
| Phase3-1 | `us_fundamentals` ETL 支援因子策略 | `core/pipeline/us/*`、`core/api/us/fundamentals_api.py` | 財報欄位可查詢且無未來資料污染 | ⬜ | 相依 Phase2-1 |
| Phase3-2 | 參數掃描框架（walk-forward / grid search） | `core/backtest/` | 可批次產出參數組合的績效比較 | ⬜ | 相依 Phase2-2 |
| Phase3-3 | 多市場共用介面，台股逐步歸位 `tw/` | 全專案 | 台股回歸測試逐筆相同 | ⏸ | 暫緩：影響面大，等美股閉環驗證後再啟動。**引擎層的共用介面已由 [回測引擎多市場抽象.md](回測引擎多市場抽象.md) 提前完成**，本步驟只剩目錄歸位 |

---

## 一、現況評估：目前架構需不需要改？

結論：**需要做「增量式調整」，不需要大翻修。**

### 目前可沿用的優點

- `core/pipeline` 已採用 `crawlers` / `cleaners` / `loaders` / `updaters` 分層，這是標準 ETL 架構。
- `tasks/update_db.py` 已有多 target 的更新入口，適合新增美股更新 target。
- `core/backtest`、`core/strategies` 已有策略執行與結果輸出流程，可複用核心回測引擎概念。

### 目前主要缺口

- 現有資料模型與 API 命名幾乎都是台股語意（如 `stock_id`、台股資料表），美股需求（`ticker`、`exchange`、`adjusted close`、拆股／配息）需要新層。
- 資料來源會多樣化（Polygon、Alpaca、Yahoo、IEX、SEC、FMP），目前缺乏「provider 抽象層」來統一外部 API。
- 回測目前偏單市場單資產流程，若要做美股（含多交易所、時區、日曆）需要標準化市場 metadata。

### 建議原則

- **保留現有台股流程不動**，美股採「平行模組」建置，降低回歸風險。
- **共享核心，不共享市場細節**：共用工具層／執行框架，但市場欄位、交易日曆、成本模型分開。

---

## 二、建議目錄調整（最小可行重構）

建議以「市場維度」補一層，避免未來再擴到港股／期貨時重工。

```text
core/
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
│   ├── engine/                      # 新增：撮合／事件循環／成本模型
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

### 3.1 資料域切分（Data Domains）

建議先做四個最核心 domain：

1. **Universe（股票池）**：ticker、交易所、是否可交易、產業分類、上市／下市狀態。
2. **Prices（行情）**：OHLCV（日線先行）、adjusted close、資料來源與版本。
3. **Corporate Actions（公司行為）**：split、dividend，用來還原／調整回測價格序列。
4. **Fundamentals（基本面）**：財報關鍵欄位（營收、EPS、毛利率），先做低頻資料。

### 3.2 ETL 分層責任

- `crawler`：單純對外 API 拉資料（含 retry、rate limit、timeout、raw schema）。
- `cleaner`：欄位標準化（`ticker`、`trade_date`、`open/high/low/close/adj_close/volume`）、型別校正、重複去除。
- `loader`：寫入 DB（upsert、批次寫入、唯一鍵約束）。
- `updater`：流程編排（日期範圍切片、checkpoint、錯誤重試策略）。

### 3.3 關鍵工程機制

- **Checkpoint / Resume**：以 `(dataset, ticker, date)` 或 `(dataset, batch_window)` 記錄進度。
- **Idempotent 寫入**：DB 用 `UNIQUE` ＋ `UPSERT`，同批重跑不重複。
- **Data Quality Gate**：在 loader 前檢查空值率、價格邏輯（`low <= open/close <= high`）。
- **Source Priority**：主來源失敗時 fallback（例如 Polygon → Yahoo）。
- **Metadata 審計**：保留 `source`、`ingested_at`、`schema_version`、`job_id`。

### 3.4 建議資料表（SQLite 先行，未來可升級）

- `us_universe`
- `us_price_daily`
- `us_corporate_actions`
- `us_fundamentals_quarterly`
- `etl_job_runs`（批次執行紀錄）
- `etl_checkpoints`（斷點續跑）

建議唯一鍵：

- `us_price_daily`：`(ticker, trade_date, source)`
- `us_corporate_actions`：`(ticker, action_date, action_type, source)`
- `us_fundamentals_quarterly`：`(ticker, fiscal_period_end, source)`

---

## 四、美股回測架構設計（業界常見模式）

### 4.1 回測核心分層

1. **DataFeed**：供應策略所需資料（價格、公司行為、基本面）。
2. **Signal / Strategy**：產生交易訊號（不直接操作資金帳本）。
3. **Execution Simulator**：模擬成交（滑價、手續費、最小交易單位）。
4. **Portfolio / Risk**：倉位、現金、風險控制（單檔上限、曝險限制）。
5. **Performance / Report**：績效指標與圖表輸出。

### 4.2 美股特有設計點

- **交易日曆**：使用 NYSE/NASDAQ 交易日，不可直接沿用台股日曆。
- **時區統一**：建議內部統一 UTC 儲存，顯示轉 `America/New_York`。
- **價格調整模式**：支援 `raw` 與 `adjusted` 兩種回測模式（由策略參數決定）。
- **成本模型**：手續費、SEC fee、最小費用、滑價模型需可插拔。
- **流動性過濾**：回測前過濾平均成交量太低標的，避免不實際成交假象。

### 4.3 回測輸入契約（建議）

策略最少依賴以下欄位：`ticker`、`datetime`（或 `trade_date`）、`open`、`high`、`low`、`close`、`adj_close`、`volume`、`is_trading_day`。

若使用基本面，另需：`report_date`、`publish_date`、財務欄位（如 `revenue`、`eps_ttm`）。

---

## 五、任務入口與執行流程建議

### 5.1 CLI target 建議（對齊現有 `tasks/update_db.py` 風格）

`us_universe`、`us_price`、`us_actions`、`us_fundamentals`、`us_all`（不含高頻）。

### 5.2 典型日更流程

1. 更新 `us_universe`（新增／下市股票狀態）。
2. 更新 `us_price`（昨日到今日）。
3. 更新 `us_actions`（拆股／配息）。
4. 依需要更新 `us_fundamentals`（低頻，週更或月更）。
5. 寫入 `etl_job_runs` 與資料品質統計。

---

## Phase 1：最小可跑版本

### Phase1-1. 建立 `us/` 目錄骨架與 provider 介面 ⬜

- **目的**：先把平行模組的骨架與對外 API 抽象定下來，後續兩步才有落點。
- **做法**：依 §二建立 `core/pipeline/us/`、`core/api/us/`、`core/strategies/us/`；`providers/base.py` 定義 provider 介面（`fetch_xxx`），先實作一個 provider（建議 Yahoo，免金鑰）。
- **產出**：上述三個目錄的骨架檔。
- **驗證方式**：骨架可 import；provider 介面可用一支假 provider 通過型別檢查。
- **相依**：無。

### Phase1-2. `us_universe` ＋ `us_price_daily` ETL ⬜

- **目的**：完成最核心的兩個資料域，讓策略有資料可跑。
- **做法**：四層 ETL 全套；落實 §3.3 的 checkpoint／resume 與 idempotent 寫入（`UNIQUE` ＋ `UPSERT`）；在 `tasks/update_db.py` 新增 `us_universe`、`us_price` 兩個 target。
- **產出**：`core/pipeline/us/*`、`core/api/us/price_api.py`、`core/api/us/universe_api.py`、`tasks/update_db.py`。
- **驗證方式**：中斷後重跑可 resume 且不產生重複資料；抽樣比對來源網站數據。
- **相依**：Phase1-1。

### Phase1-3. `USMomentumStrategy` 跑通回測 ⬜

- **目的**：驗證最小閉環（資料 → 策略 → 報表）可跑通。
- **做法**：新增一支日線動能策略；回測報表沿用既有 `reporter`，先完成可比較的資產曲線與交易明細；交易日曆改用 NYSE/NASDAQ（§4.2）。
- **產出**：`core/strategies/us/momentum_us_strategy.py`、`core/backtest/calendars/us_calendar.py`。
- **驗證方式**：可產出資產曲線與交易明細；交易日數與 NYSE 日曆一致。
- **相依**：Phase1-2。

---

## Phase 2：回測可信度提升

### Phase2-1. `us_corporate_actions` ＋ raw/adjusted 切換 ⬜

- **目的**：沒有公司行為資料，回測價格序列在拆股／配息日會出現假跳空。
- **做法**：補 `us_corporate_actions` ETL；`us_datafeed` 支援 `raw` 與 `adjusted` 兩種模式，由策略參數決定。
- **產出**：`core/pipeline/us/*`、`core/backtest/datafeed/us_datafeed.py`。
- **驗證方式**：挑一檔有拆股紀錄的標的，`adjusted` 模式下拆股日無假跳空；兩種模式的績效差異可解釋。
- **相依**：Phase1-2。

### Phase2-2. 美股成本模型 ⬜

- **目的**：手續費結構與台股不同（含 SEC fee、最小費用），不可沿用台股模型。
- **做法**：於 `core/backtest/engine/fee_models.py` 實作可插拔的成本模型：手續費、SEC fee、最小費用、滑價。
- **產出**：`core/backtest/engine/fee_models.py`。
- **驗證方式**：各項費用有單元測試，含最小費用的邊界案例。
- **相依**：Phase1-3。

### Phase2-3. 資料品質檢核與異常告警 ⬜

- **目的**：資料缺洞會靜默地讓回測結果失真。
- **做法**：落實 §3.3 的 Data Quality Gate——空值率、價格邏輯（`low <= open/close <= high`）、缺洞天數、成交量異常，並寫入 `etl_job_runs`。
- **產出**：`core/pipeline/us/*`、`etl_job_runs` 表。
- **驗證方式**：人為注入缺洞與異常價格，檢核機制可偵測並告警。
- **相依**：Phase1-2。

---

## Phase 3：策略研究效率提升

### Phase3-1. `us_fundamentals` ETL ⬜

- **目的**：支援因子與基本面策略。
- **做法**：補 `us_fundamentals_quarterly` 四層 ETL；**須同時記錄 `report_date` 與 `publish_date`**，回測一律以 `publish_date` 為可見時點，避免未來資料污染。
- **產出**：`core/pipeline/us/*`、`core/api/us/fundamentals_api.py`。
- **驗證方式**：查詢指定日期只回傳該日之前已公布的財報。
- **相依**：Phase2-1。

### Phase3-2. 參數掃描框架 ⬜

- **目的**：讓策略參數的敏感度可被系統性檢驗。
- **做法**：建立 walk-forward / grid search 框架，批次產出參數組合的績效比較。
- **產出**：`core/backtest/` 下新增掃描模組。
- **驗證方式**：可對一支策略批次跑出參數矩陣與績效表。
- **相依**：Phase2-2。

### Phase3-3. 多市場共用介面，台股逐步歸位 `tw/` ⏸

- **目的**：把驗證過的共用元件抽出，讓台股與美股共享核心。
- **做法**：規劃多市場共用介面，逐步把台股流程整理為 `tw/` 子模組。
- **產出**：全專案目錄調整。
- **驗證方式**：台股回歸測試逐筆相同。
- **相依**：Phase1-1~Phase3-2。
- **暫緩原因與解除條件**：影響面大且會動到台股既有路徑，違反「保留現有台股流程不動」的原則；待美股最小閉環（Phase 1~2）驗證完成、共用元件的邊界確定後再解除。

---

## 結論

- 專案現在的核心設計是健康的，**不用重寫**。
- 但要支撐美股且維持可維運性，建議做「市場分層 ＋ provider 抽象 ＋ 回測核心拆分」。
- 最佳做法是先做平行模組（`us/`），跑通最小閉環後再逐步抽共用元件，避免一次性大改造成風險。

---

## 關聯與狀態

- **優先級**：P3（長期架構規劃）
- **相關程式**：`core/pipeline/`、`core/api/`、`core/backtest/`、`core/strategies/`、`core/models/`、`tasks/update_db.py`
- **相關 backlog**：
  - [台期貨ETL與回測架構規劃.md](台期貨ETL與回測架構規劃.md)（共用「平行市場模組、共享核心、不共享市場細節」原則）
  - [回測引擎當沖執行順序重構.md](回測引擎當沖執行順序重構.md)（`engine/event_loop` 的長期方向對齊）
  - [PostgreSQL遷移計畫.md](PostgreSQL遷移計畫.md)（美股資料量較大，建議 DB 遷移先收斂）
