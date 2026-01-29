# AlphaEdge

**AlphaEdge** is a *trading framework* designed for backtesting trading strategies, generating backtest reports, and enabling *live trading* through the [Shioaji API](https://sinotrade.github.io/zh_TW/). It supports backtesting and trading for **stocks, futures, and options** (though currently, only stock trading has been implemented).

## 📚 文檔

- **[完整 API 文檔](docs/README.md)** - 使用 MkDocs 建立的完整 API 參考文檔（包含使用說明、文檔結構、特色功能）
- **[架構分析](ARCHITECTURE_REVIEW.md)** - 系統架構詳細分析
- **[策略開發指南](trader/strategies/README.md)** - 策略開發完整說明

### 開啟 MkDocs 文檔網站查看說明

若要本地預覽 API 文檔網站（含搜尋、導航、程式碼範例），請依下列步驟操作：

1. **安裝 MkDocs 與文檔依賴**（在專案根目錄執行）：
   ```bash
   pip install -r docs/requirements.txt
   ```

2. **啟動文檔伺服器**：
   ```bash
   mkdocs serve
   ```

3. **在瀏覽器開啟文檔**：
   - 預設網址：**http://127.0.0.1:8000**
   - 若 8000 埠被佔用，終端會顯示實際使用的埠號（例如 `http://127.0.0.1:8001`），請以終端顯示的網址為準。

4. **（選用）建置靜態網站**：僅建置、不啟動伺服器時可使用：
   ```bash
   mkdocs build
   ```
   產出會放在專案根目錄的 `site/` 資料夾，可自行部署到任意靜態網站主機。

To get started, users should follow the instructions in [Strategy Instruction](trader/strategies/README.md) and complete the following steps:

1. Familiarize themselves with the backtest Data API.
2. Develop a trading strategy.
3. Configure the strategy parameters.

## 目錄

- [AlphaEdge](#alphaedge)
- [文檔](#-文檔)
  - [開啟 MkDocs 文檔網站查看說明](#開啟-mkdocs-文檔網站查看說明)
- [回測方式](#回測方式)
  - [執行回測](#執行回測)
  - [回測級別](#回測級別)
  - [回測結果](#回測結果)
- [Strategy 格式](#strategy-格式)
  - [基本結構](#基本結構)
  - [必須實作的方法](#必須實作的方法)
  - [策略設定參數](#策略設定參數)
  - [資料 API 使用](#資料-api-使用)
  - [FinMind 資料](#finmind-資料)
  - [範例策略](#範例策略)
- [資料庫更新](#資料庫更新)
  - [更新指令](#更新指令)
  - [支援的資料類型](#支援的資料類型)
  - [更新流程](#更新流程)

## 回測方式

### 執行回測

使用 `run.py` 執行回測，基本語法如下：

```bash
python run.py --strategy <StrategyName>
```

**參數說明：**
- `--mode`: 執行模式，可選 `backtest` 或 `live`，預設為 `backtest`
- `--strategy`: 指定要使用的策略類別名稱（必填）

**使用範例：**

```bash
# 執行回測模式，使用名為 "Momentum" 的策略
python run.py --strategy Momentum

# 執行實盤模式（目前尚未實作）
python run.py --mode live --strategy Momentum
```

**注意事項：**
- Strategy Name 是 Class 的名稱
- 策略會自動從 `trader/strategies/stock/` 目錄載入
- 回測結果會儲存在 `trader/backtest/results/<StrategyName>/` 目錄

### 回測級別

AlphaEdge 支援四種回測級別（KBar 級別）：

1. **TICK**: 逐筆成交資料回測
   - 使用 `StockTickAPI` 取得逐筆成交資料
   - 適合需要精確價格和時間的策略
   - 可參考 `trader/strategies/stock/momentum_tick_strategy.py` 範例

2. **DAY**: 日線資料回測
   - 使用 `StockPriceAPI` 取得日線收盤價資料
   - 適合基於日線技術指標的策略
   - 可參考 `trader/strategies/stock/momentum_strategy.py` 或 `trader/strategies/stock/simple_long_strategy.py` 範例

3. **MIX**: 混合級別回測
   - 同時使用 TICK 和 DAY 資料
   - 目前尚未完全實作

4. **ALL**: 使用所有可用資料
   - 同時載入 TICK 和 DAY 資料 API
   - 適合需要同時使用多種資料來源的策略

在策略中設定回測級別：

```python
self.scale: str = Scale.DAY  # 或 Scale.TICK, Scale.MIX, Scale.ALL
```

### 回測結果

回測完成後，系統會自動產生以下內容：

1. **交易報告** (`trading_report.csv`)
   - 包含所有交易記錄、損益統計等

2. **圖表分析**
   - 資產曲線圖 (`balance_curve.png`)
   - 資產與基準比較圖 (`balance_and_benchmark_curve.png`)
   - 最大回撤圖 (`balance_mdd.png`)
   - 每日損益圖 (`everyday_profit.png`)

3. **日誌檔案** (`<StrategyName>.log`)
   - 記錄回測過程中的所有資訊和警告

回測結果儲存路徑：`trader/backtest/results/<StrategyName>/`

## Strategy 格式

### 基本結構

所有策略必須繼承 `BaseStockStrategy` 類別，並實作所有抽象方法。

```python
from trader.strategies.stock import BaseStockStrategy
from trader.models import StockAccount, StockOrder, StockQuote
from trader.utils import Action, Scale, PositionType

class MyStrategy(BaseStockStrategy):
    def __init__(self):
        super().__init__()
        # 策略設定...
```

### 必須實作的方法

#### 1. `setup_account(account: StockAccount)`
載入虛擬帳戶資訊，用於回測時管理資金和倉位。

```python
def setup_account(self, account: StockAccount):
    self.account = account
```

#### 2. `setup_apis()`
載入所需的資料 API，根據回測級別選擇性載入。

```python
def setup_apis(self):
    self.chip = StockChipAPI()  # 籌碼資料
    self.mrr = MonthlyRevenueReportAPI()  # 月營收資料
    self.fs = FinancialStatementAPI()  # 財報資料
    
    if self.scale in (Scale.TICK, Scale.MIX, Scale.ALL):
        self.tick = StockTickAPI()  # 逐筆資料
    
    if self.scale in (Scale.DAY, Scale.MIX, Scale.ALL):
        self.price = StockPriceAPI()  # 日線資料
```

#### 3. `check_open_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`
開倉策略邏輯，判斷哪些股票應該開倉。

```python
def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    open_positions = []
    
    for stock_quote in stock_quotes:
        # 你的開倉條件判斷
        if your_condition:
            open_positions.append(stock_quote)
    
    return self.calculate_position_size(open_positions, Action.BUY)
```

#### 4. `check_close_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`
平倉策略邏輯，判斷哪些持倉應該平倉。

```python
def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    close_positions = []
    
    for stock_quote in stock_quotes:
        if self.account.check_has_position(stock_quote.stock_id):
            # 你的平倉條件判斷
            if your_condition:
                close_positions.append(stock_quote)
    
    return self.calculate_position_size(close_positions, Action.SELL)
```

#### 5. `check_stop_loss_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`
停損策略邏輯，判斷哪些持倉應該觸發停損。

```python
def check_stop_loss_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    stop_loss_orders = []
    
    for stock_quote in stock_quotes:
        if self.account.check_has_position(stock_quote.stock_id):
            position = self.account.get_first_open_position(stock_quote.stock_id)
            # 你的停損條件判斷（例如：虧損超過 5%）
            if (stock_quote.close / position.price - 1) < -0.05:
                stop_loss_orders.append(stock_quote)
    
    return self.calculate_position_size(stop_loss_orders, Action.SELL)
```

#### 6. `calculate_position_size(stock_quotes: List[StockQuote], action: Action) -> List[StockOrder]`
計算下單股數，依據當前資金、價格、風控規則決定部位大小。

```python
def calculate_position_size(
    self, stock_quotes: List[StockQuote], action: Action
) -> List[StockOrder]:
    orders = []
    
    if action == Action.BUY:
        # 計算可買張數
        available_position_cnt = max(
            0, self.max_holdings - self.account.get_position_count()
        )
        
        if available_position_cnt > 0:
            per_position_size = self.account.balance / available_position_cnt
            
            for stock_quote in stock_quotes:
                open_volume = int(
                    per_position_size / (stock_quote.close * Units.LOT)
                )
                
                if open_volume >= 1:
                    orders.append(
                        StockOrder(
                            stock_id=stock_quote.stock_id,
                            date=stock_quote.date,
                            action=action,
                            position_type=PositionType.LONG,
                            price=stock_quote.cur_price,
                            volume=open_volume,
                        )
                    )
                    available_position_cnt -= 1
                    
                    if available_position_cnt == 0:
                        break
    elif action == Action.SELL:
        # 平倉時使用持倉的全部股數
        for stock_quote in stock_quotes:
            position = self.account.get_first_open_position(stock_quote.stock_id)
            if position is None:
                continue
            
            orders.append(
                StockOrder(
                    stock_id=stock_quote.stock_id,
                    date=stock_quote.date,
                    action=action,
                    position_type=position.position_type,
                    price=stock_quote.cur_price,
                    volume=position.volume,
                )
            )
    
    return orders
```

### 策略設定參數

在 `__init__` 方法中設定策略參數：

```python
def __init__(self):
    super().__init__()
    
    # === 策略基本資訊 ===
    self.strategy_name: str = "MyStrategy"  # 策略名稱
    self.market: str = Market.STOCK  # 市場類型
    self.position_type: str = PositionType.LONG  # 部位方向（多/空）
    self.enable_intraday: bool = True  # 是否允許當沖
    
    # === 帳戶設定 ===
    self.init_capital: float = 1000000.0  # 初始資金
    self.max_holdings: Optional[int] = 10  # 最大持倉檔數
    
    # === 回測設定 ===
    self.is_backtest: bool = True  # 是否為回測模式
    self.scale: str = Scale.DAY  # 回測級別
    self.start_date: datetime.date = datetime.date(2020, 1, 1)  # 回測起始日
    self.end_date: datetime.date = datetime.date(2025, 5, 31)  # 回測結束日
    
    # 載入資料 API
    self.setup_apis()
```

### 資料 API 使用

策略中可以透過以下 API 取得資料：

#### StockPriceAPI - 日線價格資料

```python
# 取得指定日期的所有股票價格
prices = self.price.get(date=datetime.date(2024, 1, 1))

# 取得日期範圍的所有股票價格
prices = self.price.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)

# 取得指定個股的價格
stock_prices = self.price.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
```

#### StockTickAPI - 逐筆成交資料

```python
# 取得指定日期的逐筆資料
ticks = self.tick.get(date=datetime.date(2024, 1, 1))

# 取得指定個股的逐筆資料
stock_ticks = self.tick.get_stock_tick(
    stock_id="2330",
    date=datetime.date(2024, 1, 1)
)
```

#### StockChipAPI - 籌碼資料

```python
# 取得指定日期的籌碼資料
chips = self.chip.get(date=datetime.date(2024, 1, 1))
```

#### MonthlyRevenueReportAPI - 月營收資料

```python
# 取得指定年月的月營收資料
mrr = self.mrr.get(year=2024, month=1)
```

#### FinancialStatementAPI - 財報資料

```python
# 取得指定年季的財報資料
fs = self.fs.get(year=2024, season=1)
```

### FinMind 資料

AlphaEdge 支援透過 FinMind API 取得以下資料：

1. **台股總覽(含權證)** (`stock_info`): 包含所有上市、上櫃、興櫃股票及權證的基本資訊
2. **證券商資訊** (`broker_info`): 包含所有證券商的代碼、名稱、地址、電話等資訊
3. **券商分點統計** (`broker_trading`): 每日各券商分點對各股票的買賣統計資料

這些資料已儲存在 SQLite 資料庫中，可透過 SQL 查詢使用。目前尚未提供專用的 API 類別，建議直接在策略中使用 SQL 查詢或 pandas 讀取資料庫。

**資料表名稱：**
- `taiwan_stock_info_with_warrant`: 台股總覽(含權證)
- `taiwan_securities_trader_info`: 證券商資訊
- `taiwan_stock_trading_daily_report_secid_agg`: 券商分點統計

### 範例策略

AlphaEdge 提供了多個策略範例供參考：

- **MomentumStrategy** (`trader/strategies/stock/momentum_strategy.py`): 日線級別的動能策略
- **MomentumTickStrategy** (`trader/strategies/stock/momentum_tick_strategy.py`): TICK 級別的動能策略
- **SimpleLongStrategy** (`trader/strategies/stock/simple_long_strategy.py`): 簡易做多策略範例

詳細的策略撰寫指南請參考 [Strategy Instruction](trader/strategies/README.md)。

## 資料庫更新

### 更新指令

使用 `tasks/update_db.py` 更新資料庫，基本語法如下：

```bash
python -m tasks.update_db --target <data_type>
```

### 支援的資料類型

- `tick`: 逐筆成交資料
- `chip`: 三大法人籌碼資料
- `price`: 收盤價資料
- `fs`: 財報資料
- `mrr`: 月營收報表
- `finmind`: 更新所有 FinMind 資料（台股總覽、證券商資訊、券商分點統計）
- `stock_info`: 僅更新 FinMind 台股總覽（不含權證）
- `stock_info_with_warrant`: 僅更新 FinMind 台股總覽（含權證）
- `broker_info`: 僅更新 FinMind 證券商資訊
- `broker_trading`: 僅更新 FinMind 券商分點統計
- `all`: 更新所有資料（包含 tick 和 finmind）
- `no_tick`: 更新所有資料（不包含 tick，預設值）

### 更新流程

資料更新採用 ETL（Extract, Transform, Load）流程：

1. **Crawl（爬蟲）**: 從資料來源爬取原始資料
2. **Clean（清理）**: 清理和標準化資料格式
3. **Load（載入）**: 將清理後的資料載入資料庫

每個資料類型都有對應的 Updater 類別負責協調整個流程。

**使用範例：**

```bash
# 僅更新 tick 資料
python -m tasks.update_db --target tick

# 更新三大法人與收盤價
python -m tasks.update_db --target chip price

# 更新所有 FinMind 資料
python -m tasks.update_db --target finmind

# 僅更新 FinMind 台股總覽
python -m tasks.update_db --target stock_info

# 僅更新 FinMind 券商分點統計
python -m tasks.update_db --target broker_trading

# 同時更新多個資料類型
python -m tasks.update_db --target chip price finmind

# 更新所有資料（不含 tick，預設）
python -m tasks.update_db --target no_tick
# 或
python -m tasks.update_db

# 更新所有資料（含 tick 和 finmind）
python -m tasks.update_db --target all
```

**資料更新時間範圍：**

- **一般資料**（price, chip, mrr, fs）: 從 2013/1/1 開始
- **Tick 資料**: 從 2020/3/2 開始（Shioaji API 提供）
- **FinMind 資料**:
  - 台股總覽(含權證) (`stock_info`): 一次性更新全部資料
  - 證券商資訊 (`broker_info`): 一次性更新全部資料
  - 券商分點統計 (`broker_trading`): 從 2021/6/30 開始

**更新狀態說明：**

資料更新會返回以下狀態：
- `UpdateStatus.SUCCESS`: 成功更新
- `UpdateStatus.NO_DATA`: 沒有資料（API 返回空結果）
- `UpdateStatus.ALREADY_UP_TO_DATE`: 資料庫已是最新
- `UpdateStatus.ERROR`: 發生錯誤

**注意事項：**

- 更新程式會自動從資料庫中最新日期開始更新，無需手動指定起始日期
- 更新過程中會自動處理延遲和錯誤重試
- 更新日誌會儲存在 `trader/logs/` 目錄
- FinMind 券商分點統計更新支援自動 API Quota 管理和 Metadata 追蹤，詳細流程請參考 [券商分點統計更新流程](docs/broker_trading_update_flow.md)

**財報申報期限提醒：**

一般行業財報申報期限：
- Q1：5月15日
- Q2：8月14日
- Q3：11月14日
- 年報：3月31日
