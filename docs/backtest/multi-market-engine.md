# 多市場回測引擎架構（單一引擎 ＋ 可插拔 model）

> 本文件描述 `core/backtest/` 的**現行架構**與其設計理由。
> 實作於 2026-08-07 完成（分支 `feature/refactor-backtest`，17 個步驟）；
> 規劃文件已依 [`manage-backlog` skill §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理) 移出 `backlog/`。

---

## 概觀

`Backtester` 是**唯一的回測引擎，市場無關，沒有子類**。市場之間的差異全部下沉為五個可插拔的 model，由 factory 依策略宣告的 `market` 組裝：

```
Backtester                      ← 唯一引擎，市場無關，無子類（679 行）
  ├─ InstrumentSpec             ← 乘數、tick size、漲跌停規則、報價單位換算
  ├─ FillModel                  ← 成交價可信度（前視偏誤與不可能成交的擋板）
  ├─ CostModel                  ← 手續費／稅／借券費（期貨為期交稅）
  ├─ SettlementModel            ← 每根 bar 收盤後由市場規則強制執行的動作
  └─ DataFeed                   ← 資料載入、報價轉換、交易日判定
```

這是 Backtrader `Cerebro`、Zipline `run_algorithm`、QuantConnect Lean `Engine`、Nautilus `BacktestEngine` 的一致做法：**引擎唯一，行為注入**。

**新增一個市場不需要修改 `core/backtest/backtester.py` 一行。**

---

## 一、設計決策：為什麼不是兩個引擎

原始規劃是「平行複製一支 `FuturesBacktester`」。把當時 838 行的引擎逐段分類後否決了這個方向：

| 性質 | 內容 | 佔比 |
|------|------|------|
| **市場無關**（複製會浪費、且會漂移） | `run()` 日期迴圈、`execute_bar()` 執行順序、`validate_orders()` 方向白名單、`resolve_open/close_action()`、`execute_open/close_signal()`、`snapshot_daily_equity()` 骨架、`event_counts`、`generate_backtest_report()` | 約 4 成 |
| **市場規則**（介面共用、實作不同） | `validate_fill_price()`、`get_price_range()`、`check_stock_market_open()` | 約 2 成 |
| **台股信用交易專屬** | `build_cost_config()`、`enrich_orders()`、`enforce_day_trade_cover()`、`convert_to_margin_position()`、`accrue_holding_cost()`、`check_margin_call()` | 約 4 成 |

第三類看似「非分家不可」，但逐一檢查後**全部都能對應到 model 掛點**，沒有一項需要靠繼承分支：

| 原方法 | 下沉到 | 業界對應（Lean） |
|------|--------|------|
| `validate_fill_price` / `get_price_range` | `FillModel` | `FillModel` |
| `build_cost_config` / `enrich_orders` | `CostModel` ＋ factory | `FeeModel` ＋ `SymbolProperties` |
| `check_margin_call` | `SettlementModel` | `BuyingPowerModel` / `MarginCallModel` |
| `accrue_holding_cost` | `SettlementModel` | `MarginInterestRateModel` |
| `enforce_day_trade_cover` / `convert_to_margin_position` | `SettlementModel` | `SettlementModel` |
| `snapshot_daily_equity` 的 `convert_lot_to_share` | `InstrumentSpec.to_units()` | `SymbolProperties.ContractMultiplier` |

**關鍵洞察**：台股的「當沖日終強制回補」與期貨的「每日結算」，在架構上是**同一個掛點的兩種實作**——「一根 bar 收盤後，市場規則強制對部位做的事」。看出這點之後，切兩個引擎就沒有理由了。

---

## 二、架構

### 2.1 引擎的建構子

```python
class Backtester:
    def __init__(
        self,
        strategy: BaseStrategy,
        account: BaseAccount,
        position_manager: BasePositionManager,
        instrument: InstrumentSpec,
        fill_model: BaseFillModel,
        cost_model: BaseCostModel,
        settlement: BaseSettlementModel,
        data_feed: BaseDataFeed,
        reporter_cls: Type[BaseBacktestReporter],
        event_counts: Optional[Dict[str, int]] = None,
    ):
```

`account`、`position_manager` 與 `reporter_cls` 也在注入之列——它們原本同樣是引擎自己 `new` 出來的具體台股類別，不一併注入就達不到「引擎不認識任何市場」。`reporter_cls` 傳的是**類別而非實例**，避免與 `strategy_result_dir` 的建立順序打結。

### 2.2 單根 bar 的流程

```python
def execute_bar(self, date: datetime.date, quotes: List[BaseQuote]) -> None:
    if self.get_execution_order() == BarExecutionOrder.OPEN_THEN_CLOSE:
        self.execute_open_signal(quotes)
        self.execute_close_signal(quotes)
    else:
        self.execute_close_signal(quotes)
        self.execute_open_signal(quotes)

    # 台股：當沖強制回補 ＋ 借券費計提 ＋ 維持率追繳
    # 期貨：每日結算 ＋ 保證金追繳 ＋ 到期換月
    self.settlement.on_bar_close(date, quotes, self.account, self.event_counts)

    self.snapshot_daily_equity(date, quotes)
    self.update_prev_close(quotes)
```

### 2.2.1 單根 bar 的委託順序

單根 bar 內的順序有**三個互相獨立的層次**，缺一層就會出現「同樣的訊號跑出不同結果」：

| 層次 | 由誰決定 | 規則 |
|------|----------|------|
| 開倉階段 vs 平倉階段 | `BarExecutionOrder`（策略宣告或引擎推導） | `CLOSE_THEN_OPEN`（預設）／`OPEN_THEN_CLOSE` |
| 平倉階段內部 | 引擎寫死 | 停損 → 一般平倉；停損執行完會重掃剩餘部位 |
| 同一階段內的多筆委託 | `Backtester.sort_orders()` | 依 `(date, symbol)` **穩定**排序 |

**為什麼第三層要由引擎自己排**：`check_max_holdings()` 的截斷與 `PositionManager` 的餘額不足檢查，都會讓「先處理誰」直接改變成交結果。而委託的到達順序完全繼承自報價順序，報價又來自 `SELECT * FROM price WHERE date = ?`——這句沒有 `ORDER BY`，實際列順序取決於 SQLite 選到哪個索引。今天恰好走 `PRIMARY KEY (date, stock_id, 證券名稱)` 而等同依代號排序，但那是查詢計畫的副產物：多加一個索引就可能翻掉，且翻掉時不會報錯，只會讓回測結果無聲改變。

排序是**穩定**的，同一標的的多筆委託維持策略給定的先後，分批建倉與部分平倉的意圖不會被打散。

**同標的開平倉並存不做 net 合併。** 同一根 bar 內同一標的同時出現在開倉與平倉訊號時，兩腿分別成交：證交稅只課賣出腿、當沖稅率減半也只認當沖的那一腿，合併成淨額委託會讓兩腿的費用與稅無法各自計算；且平倉腿必須實際成交才會產生 `TradeRecord`，net 掉等於整筆交易在報表上消失。兩腿的先後由 `BarExecutionOrder` 決定，這正是它存在的理由。

**已知限制**：Tick 級別的 `order.date` 只到「日」（`StockQuote.date` 對 tick 也是 `datetime.date`），因此同一 bar 內的 tick 委託無法依成交時間排序，會被壓成依代號排序。要恢復真正的時間序，得讓 `check_*_signal` 回傳帶時間戳的委託事件——屬事件迴圈的範圍，見 [§5.1](#51-事件驅動迴圈長期方向)。

### 2.3 方向與市場是兩條獨立的軸

**方向（LONG／SHORT）與市場（股票／期貨）互不相干。** `validate_orders()`、`resolve_open_action()`、`resolve_close_action()` 與市場無關（期貨的多空語意與股票相同），一律留在引擎內。

[放空回測框架規格](short-selling-framework.md) §1 原則 2「方向來自訂單，策略只做白名單」是本架構的**基礎**，不是被取代的對象。

### 2.4 檔案位置

| 層 | 路徑 | 內容 |
|---|---|---|
| 引擎 | `core/backtest/backtester.py` | 唯一引擎，679 行，不含任何 `Stock*` |
| 組裝 | `core/backtest/factory.py` | `build_backtester()`／`build_tw_stock_backtester()`／`build_cost_config()` |
| 行為 model | `core/backtest/models/instrument_spec.py` | `InstrumentSpec` ＋ `TwStockSpec` |
| | `core/backtest/models/fill_model.py` | `BaseFillModel` ＋ `TwStockFillModel` |
| | `core/backtest/models/cost_model.py` | `BaseCostModel` ＋ `CostConfig`／`ShortConstraint`／`StockCostModel` |
| | `core/backtest/models/settlement_model.py` | `BaseSettlementModel` ＋ `TwStockSettlementModel` |
| 資料源 | `core/backtest/datafeed/base.py`／`tw_stock_datafeed.py`／`market_calendar.py` | `BaseDataFeed` ＋ `TwStockDataFeed` |
| 資料模型 | `core/models/base/` | `BaseQuote`／`BaseOrder`／`BasePosition`／`BaseTradeRecord`／`BaseAccount`，識別欄位一律 `symbol` |
| 策略 | `core/strategies/base.py` | `BaseStrategy`，`market` 欄位為 factory 的分派鍵 |
| 部位 | `core/managers/base/position_manager.py` | FIFO 拆單主幹 ＋ `settle_daily()` 掛點 |

---

## 三、各 model 的職責

| Model | 必須回答的問題 | 台股實作的重點 |
|---|---|---|
| `InstrumentSpec` | 一張／一口是多少計價單位？價格要對齊什麼跳動點？漲跌停在哪？ | 1 張 ＝ 1000 股、六段跳動點、前收 ±10%（漲停捨去、跌停進位，方向不可對調） |
| `FillModel` | 這張單在這根 bar 有可能以這個價格成交嗎？ | 日 K 以 OHLC 為界、Tick 以當日已發生的累計高低為界；超出漲跌停拒單；檔位未對齊僅警告 |
| `CostModel` | 這筆交易要付多少錢？損益怎麼算？ | 手續費／證交稅（當沖減半）／融券手續費／SBL 借券費／保證金／融券利息 |
| `SettlementModel` | 這根 bar 收盤後，市場規則強制要做什麼？ | 當沖日終強制回補、漲停鎖死轉融券留倉、SBL 借券費逐日計提、維持率追繳、停券強制回補 |
| `DataFeed` | 今天有開市嗎？報價從哪來？ | 當日有日 K 即視為開市；五個資料 API 共用單一 SQLite 連線 |

### 兩個跨 model 的共用狀態

model 之間刻意**不互相依賴**，需要共享的狀態以 dict 參照傳遞：

- **`event_counts`**：由 factory 建立，同時交給引擎與 `FillModel`。六個 key 與報表相容，不可更名。
- **`prev_close`**：由 `FillModel` 持有（記錄前收是成交價模型的職責），`SettlementModel` 建構時取得同一個 dict 的參照，用於停牌盯市與漲停判定。

`get_mark_price()` 屬 `BaseSettlementModel` 的介面方法而非 `FillModel`——**期貨的盯市價就是每日結算價**，本來就是結算模型的職責；引擎的 `snapshot_daily_equity()` 也用它算未實現損益。

---

## 四、新增一個市場要做什麼

1. `core/models/<market>/`：繼承 `core/models/base/` 的五個 model（識別欄位用 `symbol`）。
2. `core/strategies/<market>/base.py`：繼承 `BaseStrategy`，設定 `self.market`。
3. `core/backtest/models/`：實作該市場的 `InstrumentSpec`／`FillModel`／`CostModel`／`SettlementModel`。
4. `core/backtest/datafeed/`：實作該市場的 `DataFeed`。
5. `core/managers/<market>/position_manager.py`：繼承 `BasePositionManager`，實作 `close_single_position()` 與 `settle_daily()`。
6. `core/backtest/factory.py`：加一個 `elif strategy.market == Market.FUTURE:` 分支。

**既有檔案的改動量：`factory.py` 一個分支。** `backtester.py`、`StrategyLoader`、`run.py` 皆為 0 行——`StrategyLoader` 會自動掃描 `core/strategies/` 下的所有市場子套件，CLI 也不需要 `--market`（市場由策略類別自己宣告）。

> **注意**：`core/backtest/__init__.py` 與 `core/strategies/__init__.py` 刻意**不做套件層 eager import**。任何在此 re-export 的模組都會讓「引擎的相依項無法反向 import 引擎底下的模組」，兩處都因此發生過循環 import。呼叫端一律使用完整模組路徑。

---

## 五、已知簡化

| 項目 | 影響 | 為何不做 |
|------|------|----------|
| **per-instrument 粒度的 model 掛載** | 無法在同一次回測同時持有台股與台指期（跨市場組合／避險） | 業界（Lean 掛在 `Security`、Nautilus 掛在 `Instrument`）確實是這個粒度，本次採 per-run 簡化。升級路徑乾淨：把 model 從 `Backtester` 移到 `InstrumentSpec` 物件上，引擎迴圈不動 |
| 事件驅動 order queue（T+1 延遲成交、限價單未成交、部分成交） | 追繳仍只能以觸發當日收盤價回補 | 本質是引擎典範轉移，見 [§5.1](#51-事件驅動迴圈長期方向) |
| 報表輸出欄位仍為 `Stock ID` 而非 `Symbol` | 期貨報表的欄位名會是股票語意 | 改名會讓 1,889 筆 LONG baseline 失效。等期貨真的要出報表時再處理，屆時 baseline 本來就要重產 |
| `core/utils/instrument.py` 未移出 | `core/utils/` 仍留一個領域模組 | `StockUtils` 有 4 個 `core/backtest/` 以外的使用者（pipeline、adapters、`strategy_lab`）。移進 `core/backtest/` 會讓資料管線反過來相依於回測引擎，是更嚴重的層級問題。其 11 個函式的歸屬需先拆解——「LONG成本模型口徑收斂」（2026-08-15 完成並移出 `backlog/`）未處理此項，**本表即其目前唯一的追蹤位置** |
| `--mode live` 實盤路徑 | 實盤仍是空實作 | `run.py` 的 live 分支目前是 `pass`；factory 已預留讓實盤共用同一組 model |

### 5.1 事件驅動迴圈（長期方向）

> 「回測引擎當沖執行順序重構」（S1~S3 於 2026-08-15 完成）的最後一步 S4 長期暫緩，
> 其內容收錄於此，該規劃文件已移出 `backlog/`。

現行引擎在單根 bar 內是「訊號產生 → 立即撮合」，`check_*_signal()` 回傳的委託沒有時間戳，
帳戶狀態在同一個呼叫堆疊內就更新完畢。事件驅動的版本會把它拆成事件流：
`check_*_signal()` 改為回傳**帶時間／階段的委託事件**，由 engine 依時間戳排序後依序撮合，
`PositionManager` 只負責「收到已成交事件後的狀態更新」。

**為什麼暫緩**：範圍等同重寫回測引擎，且目前沒有任何策略需要它。
**解除條件**：美股／台期貨的多市場需求成形、[美股ETL與回測架構規劃](../../backlog/美股ETL與回測架構規劃.md)
的 `backtest/engine/event_loop.py` 目錄定案之後再啟動。

**已經因此受限的具體項目**（動工時這幾條會一起解掉）：

| 受限項目 | 現況 |
|----------|------|
| Tick 級別的委託排序 | `order.date` 只到「日」（`StockQuote.date` 對 tick 也是 `datetime.date`），故 `Backtester.sort_orders()` 對同一 bar 的 tick 委託只能退回依代號排序，無法還原成交時間序（見 [§2.2.1](#221-單根-bar-的委託順序)） |
| T+1 延遲成交 | 維持率追繳只能以觸發當日收盤價立即回補，少了一天的補繳緩衝（見 [放空回測框架規格](short-selling-framework.md) §7.2） |
| 限價單未成交／部分成交 | 無 pending order 機制，每天從頭跑、訊號當下就撮合完畢 |

**升級路徑**：`sort_orders()` 的排序鍵目前是 `(date, symbol)`；一旦委託帶上真正的時間戳，
該鍵可直接擴充為時間序，引擎的分派結構不需重寫。

---

## 六、實作過程的重要發現

這一節記錄重構期間查證出來、**與原規劃認知不符**的事實。它們的價值不在於歷史，而在於後續實作者若不知道，會重蹈覆轍。

### 6.1 `Scale.ALL` 從來就不存在

`Scale` enum 只有 `TICK`、`DAY`（重構前另有 `MIX`）。但五支策略的 `setup_apis()` 都有一行 `elif self.scale in (Scale.MIX, Scale.ALL)`。

該分支之所以從未爆炸，純粹是 `if/elif` 鏈永遠在前兩個分支短路——它的條件式**從未被求值過**。只要 `Scale` 新增任何第四個成員，五支策略會立刻 `AttributeError`。

規劃文件曾兩度誤述此事（先寫「`Scale.ALL` 已存在且語意重疊」，更正時又寫「`Scale.ALL` 仍會正常命中第三個分支」），直到實測才發現兩者皆錯。**該分支已整段刪除，`Scale.MIX` 亦已自 enum 移除。**

### 6.2 回歸雙線不經過 reporter

`tests/backtest/make_baseline.py` 與 `make_short_baseline.py` 都是**自行從 `account.trade_records` 組 DataFrame**，不呼叫 `generate_trading_report()`。

因此「回歸逐筆相同」對報表層提供**零覆蓋**——reporter 的欄位名改掉或取值改成空字串，兩條回歸線都一樣綠。報表層目前只靠 `tests/backtest/test_reporting.py` 與 `test_reporter_timeline.py` 的單元測試把關。**動 reporter 時不要以為回歸線會擋。**

### 6.3 既有測試沒有釘住結算動作的執行順序

以三次單字元注入測試護欄有效性：

| 注入的錯誤 | 既有 61 項測試 | SHORT 回歸快照 |
|---|:---:|:---:|
| `close_short_position()` 攤提比例 `/` → `//` | ✅ 抓到 | ✅ 抓到 |
| `carry_cost` 的利息符號 `-` → `+` | ✅ 抓到 | ✅ 抓到 |
| `enforce_day_trade_cover()` 與 `execute_daily_position_check()` **對調** | ❌ **全數通過** | ✅ 抓到 |

第三項正是把兩者合併進 `SettlementModel.on_bar_close()` 時最可能出的錯，而它不會讓任何既有測試變紅。`tests/backtest/make_short_baseline.py` 的 `day_trade_on_force_cover_date` 情境是為此新增的，**是目前唯一釘住該順序的護欄**。

### 6.4 兩處套件層 eager import 造成循環

`core/backtest/__init__.py` 與 `core/strategies/__init__.py` 原本各自 eager import `Backtester` 與 `StrategyLoader`。後果是**任何該套件底下的模組都無法被該套件所相依的模組引用**——例如 `core.utils.cost_model` 一 import `core.backtest.models.cost_model`，就會觸發 `core.backtest.__init__` → `backtester` → `core.strategies.stock` → 回到尚未初始化完成的 `core.utils.cost_model`。

兩處皆已移除 eager import。**未來在這兩個 `__init__.py` 加 re-export 會直接重現此問題。**

### 6.5 回歸 baseline 原本不在版控內

`.gitignore` 的 `*.csv` 規則使 `tests/backtest/snapshots/` 從未被提交——全專案反覆引用的「LONG 915 筆 baseline」在 2026-08-07 之前只存在於單一台開發機。已加入例外規則 `!tests/backtest/snapshots/*.csv`。

### 6.6 一個曾未修的口徑缺陷（2026-08-15 已修復）

`convert_to_margin_position()` 把當沖空單轉為融券留倉時，補收了保證金與融券手續費，但**未補徵證交稅差額**（開倉時課的是當沖減半的 0.15%，轉留倉後應為全額 0.3%）。漲停鎖死轉留倉的部位成本因此被系統性低估。

依「行為零改變」的紅線未於重構中修改，後由「回測引擎執行真實度補強」S7 於 2026-08-15 修復：`SettlementModel.get_day_trade_tax_top_up()` 補徵稅差（稅率取自 `CostConfig` 不寫死），SHORT 快照同批重產，測試見 `tests/backtest/test_backtester_short.py::test_convert_to_margin_tops_up_tax`。

---

## 七、回歸護欄

任何動到 `core/backtest/`、`core/managers/`、`core/models/` 的改動，都應通過**回歸雙線**：

```bash
./scripts/run_regression.sh    # 任一條失敗即以非零狀態碼結束，且不續跑
```

| 回歸線 | 內容 | 需求 | 耗時 |
|---|---|---|---|
| SHORT | 8 組腳本情境、3 份快照（交易紀錄／期末未平倉部位／帳戶與事件計數） | 純記憶體，不連 DB | 0.06 秒 |
| LONG | `MomentumStrategy1` 2024-01~06，915 筆 × 13 欄逐筆比對 | 需 `core/database/stock.db` | 約 54 秒 |

SHORT 的 8 組情境刻意各只動一個變因，任一情境快照有變即可直接指向出問題的掛點：當沖同日回補（稅率減半）、融券留倉 10 天、FIFO 部分回補的等比例攤提、維持率斷頭、當沖鎖漲停轉留倉、當沖遇停券回補日（釘住結算順序）、SBL 與 MARGIN 借券費對照。

**重產 baseline 是有代價的**：一旦重產，先前每一次「逐筆相同」的驗證都失去意義。會改變回測結果的工作（股價還原、LONG 成本口徑收斂）應合併排程、只重產一次。

---

## 八、驗收結果（2026-08-07）

| 標準 | 結果 |
|---|---|
| `grep -c "Stock" core/backtest/backtester.py` | **0** |
| 引擎行數 | 838 → **491** |
| LONG 915 筆逐筆相同 | ✅（17 個步驟每一步都驗） |
| SHORT 快照逐筆相同 | ✅（同上） |
| 全專案 `if market ==` 的數量 | **1**（`core/backtest/factory.py`） |
| 單次回測的 `sqlite3.connect` 次數 | 8 → **1**，且回測結束時關閉 |
| `tests/` | 115 passed（4 個 error 為 `tests/test_tick_*` 的既有問題） |

---

## 相關文件

- [模組使用關係](module-map.md)——回測路徑上誰呼叫誰、逐檔案職責、輸出檔案與動手前的注意事項
- [放空回測框架規格](short-selling-framework.md)——方向驅動的記帳原則，是本架構的基礎
- `backlog/台期貨ETL與回測架構規劃.md`——期貨 model 組的實作（阻塞已解除）
- `backlog/美股ETL與回測架構規劃.md`——美股 model 組的實作（阻塞已解除）
- [`core/backtest/README.md`](../../core/backtest/README.md)〈成交假設〉——滑價、成交量上限與券源檢核的使用說明（「回測引擎執行真實度補強」與「回測滑價與執行係數」均已於 2026-08-15 完成並移出 `backlog/`）
