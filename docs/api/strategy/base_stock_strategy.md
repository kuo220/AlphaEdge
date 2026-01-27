# BaseStockStrategy

`BaseStockStrategy` 是所有股票交易策略的基礎抽象類別。

## 類別定義

```python
from trader.strategies.stock import BaseStockStrategy
```

## 類別結構

```python
class BaseStockStrategy(ABC):
    """Stock Strategy Framework (Base Template)"""
    
    def __init__(self):
        # 帳戶設定
        self.account: StockAccount = None
        
        # 策略設定
        self.strategy_name: str = ""
        self.market: str = Market.STOCK
        self.position_type: str = PositionType.LONG
        self.enable_intraday: bool = True
        self.init_capital: float = 0
        self.max_holdings: Optional[int] = 0
        
        # 回測設定
        self.is_backtest: bool = True
        self.scale: str = Scale.DAY
        self.start_date: datetime.date = None
        self.end_date: datetime.date = None
        
        # 資料 API
        self.tick: Optional[StockTickAPI] = None
        self.price: Optional[StockPriceAPI] = None
        self.chip: Optional[StockChipAPI] = None
        self.mrr: Optional[MonthlyRevenueReportAPI] = None
        self.fs: Optional[FinancialStatementAPI] = None
```

## 抽象方法

所有繼承 `BaseStockStrategy` 的策略都必須實作以下方法：

### `setup_account(account: StockAccount)`

載入虛擬帳戶資訊，用於回測時管理資金和倉位。

**參數：**
- `account` (StockAccount): 交易帳戶資訊

**範例：**
```python
def setup_account(self, account: StockAccount):
    self.account = account
```

---

### `setup_apis()`

載入所需的資料 API，根據回測級別選擇性載入。

**範例：**
```python
def setup_apis(self):
    from trader.api.stock_price_api import StockPriceAPI
    from trader.api.stock_chip_api import StockChipAPI
    
    self.price = StockPriceAPI()
    self.chip = StockChipAPI()
    
    if self.scale in (Scale.TICK, Scale.MIX):
        from trader.api.stock_tick_api import StockTickAPI
        self.tick = StockTickAPI()
```

---

### `check_open_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`

開倉策略邏輯，判斷哪些股票應該開倉。

**參數：**
- `stock_quotes` (List[StockQuote]): 目標股票的報價資訊

**返回：**
- `List[StockOrder]`: 開倉訂單列表

**範例：**
```python
def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
    open_positions = []
    
    for stock_quote in stock_quotes:
        # 你的開倉條件判斷
        if your_condition:
            open_positions.append(stock_quote)
    
    return self.calculate_position_size(open_positions, Action.BUY)
```

---

### `check_close_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`

平倉策略邏輯，判斷哪些持倉應該平倉。

**參數：**
- `stock_quotes` (List[StockQuote]): 目標股票的報價資訊

**返回：**
- `List[StockOrder]`: 平倉訂單列表

**範例：**
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

---

### `check_stop_loss_signal(stock_quotes: List[StockQuote]) -> List[StockOrder]`

停損策略邏輯，判斷哪些持倉應該觸發停損。

**參數：**
- `stock_quotes` (List[StockQuote]): 目標股票的報價資訊

**返回：**
- `List[StockOrder]`: 停損訂單列表

**範例：**
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

---

### `calculate_position_size(stock_quotes: List[StockQuote], action: Action) -> List[StockOrder]`

計算下單股數，依據當前資金、價格、風控規則決定部位大小。

**參數：**
- `stock_quotes` (List[StockQuote]): 目標股票的報價資訊
- `action` (Action): 動作類型（`Action.BUY` 或 `Action.SELL`）

**返回：**
- `List[StockOrder]`: 建議下單的訂單列表

**範例：**
```python
def calculate_position_size(
    self, stock_quotes: List[StockQuote], action: Action
) -> List[StockOrder]:
    orders = []
    
    if action == Action.BUY:
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

## 策略設定參數

在 `__init__` 方法中設定策略參數：

```python
def __init__(self):
    super().__init__()
    
    # === 策略基本資訊 ===
    self.strategy_name: str = "MyStrategy"
    self.market: str = Market.STOCK
    self.position_type: str = PositionType.LONG
    self.enable_intraday: bool = True
    
    # === 帳戶設定 ===
    self.init_capital: float = 1000000.0
    self.max_holdings: Optional[int] = 10
    
    # === 回測設定 ===
    self.is_backtest: bool = True
    self.scale: str = Scale.DAY
    self.start_date: datetime.date = datetime.date(2020, 1, 1)
    self.end_date: datetime.date = datetime.date(2025, 5, 31)
    
    # 載入資料 API
    self.setup_apis()
```

## 回測級別

策略可以設定不同的回測級別：

- `Scale.DAY`: 日線資料回測
- `Scale.TICK`: 逐筆成交資料回測
- `Scale.MIX`: 混合級別回測（目前尚未完全實作）

## 使用範例

完整的策略開發範例請參考：
- [策略開發範例](../../examples/strategy.md)
- [策略開發指南](../../../trader/strategies/README.md)

## 相關文檔

- [資料 API](../data/overview.md)
- [策略開發範例](../../examples/strategy.md)
- [最佳實踐](../../best-practices.md)
