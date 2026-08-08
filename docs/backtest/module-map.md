# 回測執行路徑的模組使用關係

> 本文件描述「一次回測從 `run.py` 到報表落地」會經過哪些模組、誰呼叫誰、誰持有什麼狀態。
> 引擎為何長成這樣（設計取捨、已知簡化）見 [多市場回測引擎架構](multi-market-engine.md)；
> 方向驅動的記帳原則見 [放空回測框架規格](short-selling-framework.md)。

---

## 一、分層與相依方向

相依**單向由上往下**，同層之間不互相 import。違反這條線的兩次事故都記在[多市場回測引擎架構 §6.4](multi-market-engine.md)。

```
入口層      run.py ── tasks/update_db.py
              │
策略層      core/strategies/          ← 宣告 market，是 factory 的分派鍵
              │
組裝層      core/backtest/factory.py  ← 全專案唯一的 if market ==
              │
引擎層      core/backtest/backtester.py（市場無關，無子類）
              ├── core/backtest/models/      五個可插拔 model 的其中四個
              ├── core/backtest/datafeed/    資料載入與交易日判定
              ├── core/managers/             部位進出與帳務
              └── core/backtest/report/      報表與圖表
              │
資料層      core/api/ ── core/adapters/ ── core/database/
              │
領域層      core/models/（帳戶、訂單、部位、報價、交易紀錄）
共用層      core/utils/（enum、路徑、時間、日誌、StockUtils）
```

**引擎不認識任何市場**：`grep "Stock" core/backtest/backtester.py` 為 0。市場語意全部在 `factory.py` 組裝時注入。

---

## 二、一次回測的呼叫序列

```mermaid
sequenceDiagram
    participant CLI as run.py
    participant Loader as StrategyLoader
    participant F as factory
    participant BT as Backtester
    participant Feed as DataFeed
    participant S as Strategy
    participant PM as PositionManager
    participant SM as SettlementModel
    participant R as Reporter

    CLI->>Loader: load_strategies()
    Loader-->>CLI: {類別名稱: 策略類別}
    CLI->>F: build_backtester(strategy)

    Note over F: 依 strategy.market 組裝<br/>account / position_manager / 四個 model / data_feed
    F->>BT: Backtester(全部注入)
    BT->>Feed: setup(strategy)（建立唯一的 SQLite 連線）
    BT->>S: setup_apis(data_feed)（策略取用 API，不自行建立）

    CLI->>BT: run()
    loop 回測期間的每一天
        BT->>Feed: is_market_open(date)
        BT->>Feed: get_quotes(date, scale)
        Note over BT: execute_bar()：依 BarExecutionOrder 決定開平倉先後
        BT->>S: check_open_signal(quotes)
        BT->>BT: validate_orders() → enrich_orders() → validate_fill_price()
        BT->>PM: open_position(order)
        BT->>S: check_stop_loss_signal() / check_close_signal()
        BT->>PM: close_position(order)
        BT->>SM: on_bar_close(date, quotes, account, event_counts)
        BT->>BT: snapshot_daily_equity(date, quotes)
    end

    BT->>R: generate_trading_report() / direction_summary / event_report
    BT->>R: 四張圖
    BT->>Feed: close()
```

### 單根 bar 的訂單流

訂單從策略回傳到真正成交，中間有**三道關卡**，任何一關被擋都會計數，不會靜默丟棄：

| 順序 | 關卡 | 實作位置 | 擋掉時計入 |
|:----:|------|----------|------------|
| 1 | 方向白名單（`allowed_directions`、開平倉動作是否相符） | `Backtester.validate_orders()` | `rejected_direction` |
| 2 | 市場專屬欄位補值（`short_method`、`is_day_trade`） | `CostModel.enrich_orders()` | —（只補值不擋） |
| 3 | 成交價可信度（OHLC 區間、漲跌停、檔位） | `FillModel.validate()` | `rejected_fill_price` |

通過三關後才交給 `PositionManager.open_position()`。

---

## 三、逐檔案職責

### 入口與組裝

| 檔案 | 職責 | 被誰呼叫 |
|------|------|----------|
| `run.py` | CLI 解析（`--mode`、`--strategy`）、載入策略、建引擎、`run()` | 使用者 |
| `core/strategies/strategy_loader.py` | 掃描 `core/strategies/` 下**所有市場子套件**，找出繼承 `BaseStrategy` 的類別；類別名即策略識別名 | `run.py` |
| `core/backtest/factory.py` | 依 `strategy.market` 組裝 model 組合；`build_cost_config()` 依策略宣告推導成本設定 | `run.py`、測試 |

### 引擎與可插拔 model

| 檔案 | 職責 | 持有的狀態 |
|------|------|------------|
| `core/backtest/backtester.py` | 日期迴圈、單根 bar 流程、訂單三道關卡、逐日權益快照、觸發報表 | `daily_equity`、`event_counts` |
| `core/backtest/models/instrument_spec.py` | 一張／一口的計價單位換算、跳動點對齊、漲跌停區間 | 無（純規則） |
| `core/backtest/models/fill_model.py` | 這張單在這根 bar 有沒有可能以這個價格成交 | `prev_close`、`intraday_range` |
| `core/backtest/models/cost_model.py` | 手續費／證交稅／融券手續費／借券費／保證金／利息；`enrich_orders()` 補市場欄位 | `CostConfig`（含 `ShortConstraint`） |
| `core/backtest/models/settlement_model.py` | 一根 bar 收盤後市場規則強制執行的動作：當沖強制回補、漲停轉留倉、借券費計提、維持率追繳、停券回補 | 參照 `FillModel.prev_close` |
| `core/backtest/datafeed/base.py`／`tw_stock_datafeed.py` | 建立並持有全部資料 API、報價轉換、交易日判定、回測結束時關連線 | **單次回測唯一的 SQLite 連線** |
| `core/backtest/datafeed/market_calendar.py` | 交易日推算（前一交易日、是否開盤） | `DataFeed`、策略 |

**跨 model 的共用狀態只有兩個**，皆以 dict 參照傳遞，model 之間不互相 import：

- `event_counts`：`factory` 建立 → 同時給 `Backtester` 與 `FillModel`。六個 key 與報表相容，**不可更名**。
- `prev_close`：`FillModel` 持有 → `SettlementModel` 建構時取得同一個 dict 的參照。

### 帳務與領域模型

| 檔案 | 職責 |
|------|------|
| `core/managers/base/position_manager.py` | `BasePositionManager`：開倉／平倉／`settle_daily()` 的市場無關骨架 |
| `core/managers/stock/position_manager.py` | 台股實作：FIFO 平倉、多空分流記帳、成本攤提、融券轉換 |
| `core/models/base/` | `BaseAccount`／`BaseOrder`／`BasePosition`／`BaseQuote`／`BaseTradeRecord`；識別欄位一律 `symbol` |
| `core/models/stock/` | 台股實作，含 `stock_id` 與 `symbol` 的對應 |

### 資料存取

| 檔案 | 職責 |
|------|------|
| `core/api/base.py` | `BaseDataAPI`：`owns_conn` 決定 `close()` 是否真的關連線（共用連線由 `DataFeed` 負責關） |
| `core/api/stock_price_api.py` | 日 K 查詢（`get`／`get_range`／`get_stock_price`） |
| `core/api/stock_tick_api.py` | 逐筆成交（DolphinDB） |
| `core/api/stock_chip_api.py`／`stock_margin_api.py` | 三大法人籌碼、融資融券餘額 |
| `core/api/monthly_revenue_report_api.py`／`financial_statement_api.py` | 月營收、財報 |
| `core/adapters/stock_quote_adapter.py` | 日 K／Tick 的 `DataFrame` → `StockQuote` 物件 |

### 報表與分析

| 檔案 | 職責 |
|------|------|
| `core/backtest/report/base.py` | `BaseBacktestReporter`：報表介面與存檔工具 |
| `core/backtest/report/reporter.py` | 台股報表：交易明細、多空統計、事件計數、四張圖、benchmark（`0050`）比較 |
| `core/backtest/analysis/analyzer.py` | 績效指標（Sharpe／Sortino／Profit Factor 等），目前未接進 `run()` 主流程 |

---

## 四、輸出檔案

全部落在 `core/backtest/results/<策略名稱>/`：

| 檔案 | 內容 | 產生者 |
|------|------|--------|
| `<策略>_trading_report.csv` | 已平倉交易逐筆明細（25 欄，含放空專屬的 `Borrow Fee`／`Interest`／`Margin`／`Holding Days`／`ROI on Capital`） | `generate_trading_report()` |
| `<策略>_direction_summary.csv` | 多空分開的勝率、損益、成本統計 | `generate_direction_summary()` |
| `<策略>_event_report.csv` | 六種事件計數（強制回補、斷頭、拒單、漲停回補失敗） | `generate_event_report()` |
| `<策略>_daily_equity.csv` | **含未實現損益**的逐日權益序列 | `Backtester.snapshot_daily_equity()` |
| `<策略>_balance_curve.png` | 權益曲線 | `plot_balance_curve()` |
| `<策略>_networth.png` | 策略 vs `0050` 淨值 | `plot_balance_and_benchmark_curve()` |
| `<策略>_mdd.png` | 策略 vs `0050` 最大回撤 | `plot_balance_mdd()` |
| `<策略>_everyday_profit.png` | 每日損益長條圖（**已實現口徑**） | `plot_everyday_profit()` |
| `<策略>_everyday_equity_change.png` | 每日權益變化（**盯市口徑**，無 `daily_equity` 時不產出） | `plot_everyday_equity_change()` |

日誌落在 `core/backtest/results/logs/`。

### 權益曲線的兩種口徑

前三張圖的資料來源收斂在 `StockBacktestReporter.get_equity_series()` 這個唯一入口，回傳序列與其口徑：

| 口徑 | 何時採用 | 節點 | 風險 |
|------|----------|------|------|
| `Mark-to-market` | `daily_equity` 有值（正常回測路徑） | 每個交易日一點 | — |
| `Realized only` | `daily_equity` 為空 | 只有平倉日有點 | **MDD 被低估**：持倉期間的逆勢被整段抹平，而那正是留倉放空最大的風險來源 |

採用的口徑會標在圖表標題或註腳上，避免不同期的報表被混著看。`StockBacktestAnalyzer.compute_equity_curve()` 兩條路徑也都以初始資金為第一個節點，與圖表同口徑。

**`everyday_profit` 與 `everyday_equity_change` 語意不同、不可互相取代**：前者只在平倉當天有數值，後者是逐日權益的差分，持倉期間被軋的那幾天會有負值。

---

## 五、新增一個市場要動哪些檔案

既有檔案的改動量是**一個 `elif` 分支**：

| 動作 | 檔案 |
|------|------|
| 新增 | `core/models/<market>/`（五個領域模型） |
| 新增 | `core/strategies/<market>/base.py`（設定 `self.market`） |
| 新增 | `core/backtest/models/` 的該市場 `InstrumentSpec`／`FillModel`／`CostModel`／`SettlementModel` |
| 新增 | `core/backtest/datafeed/` 的該市場 `DataFeed` |
| 新增 | `core/managers/<market>/position_manager.py` |
| **修改** | `core/backtest/factory.py`：加一個 `elif strategy.market == Market.FUTURE:` |

`backtester.py`、`strategy_loader.py`、`run.py` 皆為 **0 行改動**——`StrategyLoader` 會自動掃描新的市場子套件，CLI 也不需要 `--market`（市場由策略類別自己宣告）。

---

## 六、動這些模組前要知道的事

1. **不要在 `core/backtest/__init__.py` 與 `core/strategies/__init__.py` 加 re-export。** 兩處都曾因套件層 eager import 造成循環，已刻意移除；呼叫端一律用完整模組路徑。
2. **策略不要自己 `StockPriceAPI()`。** API 實例由 `DataFeed` 統一持有，`setup_apis(feed)` 只是取用；自行建立會讓單次回測開出多條互不相干的連線。
3. **回歸雙線不經過 reporter。** `tests/backtest/make_baseline.py` 直接從 `account.trade_records` 組 `DataFrame`，改壞報表欄位兩條線都一樣綠——動 `reporter.py` 時要靠 `test_reporting.py` 與 `test_reporter_timeline.py`。
4. **報表層另開一條連線且未關閉。** `StockBacktestReporter.setup()` 自行 `StockPriceAPI()` 取 benchmark（`0050`）價格，`owns_conn=True` 但流程中沒有 `close()`。`DataFeed` 那條共用連線與它無關。
5. **任何動到 `core/backtest/`、`core/managers/`、`core/models/` 的改動，先跑 `./scripts/run_regression.sh`。**

---

## 相關文件

- [多市場回測引擎架構](multi-market-engine.md)——設計決策、已知簡化、重構期間的實查發現
- [放空回測框架規格](short-selling-framework.md)——方向驅動的記帳原則
- [策略開發指南](../../core/strategies/README.md)——策略怎麼寫
