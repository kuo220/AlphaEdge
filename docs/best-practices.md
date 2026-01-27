# 最佳實踐

本頁面提供使用 AlphaEdge API 的最佳實踐建議。

## API 使用

### 1. 重用 API 實例

**❌ 不好的做法：**
```python
def get_prices():
    api = StockPriceAPI()  # 每次都建立新實例
    return api.get(datetime.date(2024, 1, 1))

# 多次呼叫會建立多個連線
prices1 = get_prices()
prices2 = get_prices()
```

**✅ 好的做法：**
```python
# 在類別或模組層級建立一次
price_api = StockPriceAPI()

def get_prices():
    return price_api.get(datetime.date(2024, 1, 1))

# 重用同一個實例
prices1 = get_prices()
prices2 = get_prices()
```

### 2. 批次查詢優於多次查詢

**❌ 不好的做法：**
```python
api = StockPriceAPI()
for date in date_range:
    prices = api.get(date)  # 多次查詢
    process(prices)
```

**✅ 好的做法：**
```python
api = StockPriceAPI()
# 一次查詢整個範圍
prices = api.get_range(start_date, end_date)
for date in date_range:
    daily_prices = prices[prices['date'] == date]
    process(daily_prices)
```

### 3. 檢查空資料

**✅ 好的做法：**
```python
api = StockPriceAPI()
prices = api.get(date)

if prices.empty:
    logger.warning(f"沒有找到 {date} 的資料")
    return

# 繼續處理資料
process(prices)
```

### 4. 適當的錯誤處理

**✅ 好的做法：**
```python
from loguru import logger

try:
    api = StockPriceAPI()
    prices = api.get(date)
except Exception as e:
    logger.error(f"查詢價格資料時發生錯誤: {e}")
    raise
```

## 策略開發

### 1. 參數化設計

**✅ 好的做法：**
```python
class MyStrategy(BaseStockStrategy):
    def __init__(self):
        super().__init__()
        # 將參數設為類別屬性
        self.short_period = 5
        self.long_period = 20
        self.stop_loss_pct = 0.10
```

### 2. 避免在迴圈中查詢資料

**❌ 不好的做法：**
```python
def check_open_signal(self, stock_quotes):
    for quote in stock_quotes:
        # 在迴圈中查詢資料，效能差
        prices = self.price.get_stock_price(
            quote.stock_id, start_date, end_date
        )
```

**✅ 好的做法：**
```python
def check_open_signal(self, stock_quotes):
    # 預先查詢所有需要的資料
    all_prices = self.price.get_range(start_date, end_date)
    
    for quote in stock_quotes:
        # 從已查詢的資料中篩選
        stock_prices = all_prices[all_prices['stock_id'] == quote.stock_id]
```

### 3. 使用快取

**✅ 好的做法：**
```python
from functools import lru_cache

class MyStrategy(BaseStockStrategy):
    @lru_cache(maxsize=100)
    def _calculate_ma(self, stock_id, date_str, period):
        # 計算結果會被快取
        date = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
        prices = self.price.get_stock_price(stock_id, date, date)
        return prices['close'].mean()
```

### 4. 日誌記錄

**✅ 好的做法：**
```python
from loguru import logger

class MyStrategy(BaseStockStrategy):
    def check_open_signal(self, stock_quotes):
        logger.info(f"檢查開倉訊號，共 {len(stock_quotes)} 檔股票")
        
        open_orders = []
        for quote in stock_quotes:
            if self._should_open(quote):
                logger.debug(f"{quote.stock_id} 符合開倉條件")
                open_orders.append(quote)
        
        logger.info(f"找到 {len(open_orders)} 個開倉訊號")
        return open_orders
```

## 資料處理

### 1. 使用 pandas 高效操作

**✅ 好的做法：**
```python
# 使用向量化操作
prices['change_pct'] = (prices['close'] - prices['open']) / prices['open'] * 100

# 使用 groupby 進行分組操作
daily_stats = prices.groupby('date').agg({
    'close': 'mean',
    'volume': 'sum'
})
```

### 2. 資料驗證

**✅ 好的做法：**
```python
def validate_price_data(prices):
    """驗證價格資料的完整性"""
    if prices.empty:
        return False
    
    required_columns = ['stock_id', 'date', 'open', 'high', 'low', 'close']
    if not all(col in prices.columns for col in required_columns):
        return False
    
    # 檢查是否有異常值
    if (prices['close'] <= 0).any():
        return False
    
    # 檢查高低價邏輯
    if (prices['high'] < prices['low']).any():
        return False
    
    return True
```

### 3. 記憶體管理

**✅ 好的做法：**
```python
# 處理大量資料時，分批處理
def process_large_dataset(api, start_date, end_date, batch_size=1000):
    current_date = start_date
    
    while current_date <= end_date:
        batch_end = min(
            current_date + datetime.timedelta(days=batch_size),
            end_date
        )
        
        prices = api.get_range(current_date, batch_end)
        process_batch(prices)
        
        # 清理記憶體
        del prices
        
        current_date = batch_end + datetime.timedelta(days=1)
```

## 效能優化

### 1. 預先載入常用資料

**✅ 好的做法：**
```python
class MyStrategy(BaseStockStrategy):
    def __init__(self):
        super().__init__()
        self.setup_apis()
        # 預先載入常用資料
        self._preload_data()
    
    def _preload_data(self):
        """預先載入策略需要的資料"""
        self.price_cache = self.price.get_range(
            self.start_date - datetime.timedelta(days=100),
            self.end_date
        )
```

### 2. 使用索引加速查詢

**✅ 好的做法：**
```python
# 設定索引以加速查詢
prices = api.get_range(start_date, end_date)
prices = prices.set_index(['stock_id', 'date'])

# 使用索引查詢
stock_prices = prices.loc['2330']
```

### 3. 避免不必要的計算

**✅ 好的做法：**
```python
# 只在需要時計算技術指標
if need_ma:
    prices['ma'] = prices['close'].rolling(window=20).mean()

# 使用條件計算
prices['signal'] = prices.apply(
    lambda row: 'buy' if row['ma5'] > row['ma20'] else 'sell',
    axis=1
)
```

## 程式碼組織

### 1. 模組化設計

**✅ 好的做法：**
```python
# 將計算邏輯分離到獨立方法
class MyStrategy(BaseStockStrategy):
    def _calculate_indicators(self, stock_id, date):
        """計算技術指標"""
        pass
    
    def _check_conditions(self, quote, indicators):
        """檢查交易條件"""
        pass
    
    def check_open_signal(self, stock_quotes):
        """使用上述方法組合開倉邏輯"""
        pass
```

### 2. 使用常數

**✅ 好的做法：**
```python
class MyStrategy(BaseStockStrategy):
    # 定義常數
    MIN_VOLUME = 1000
    MAX_POSITION_SIZE = 0.1  # 單一部位最大資金比例
    
    def calculate_position_size(self, stock_quotes, action):
        # 使用常數
        if quote.volume < self.MIN_VOLUME:
            continue
```

## 測試

### 1. 單元測試

**✅ 好的做法：**
```python
import unittest
from trader.api.stock_price_api import StockPriceAPI

class TestStockPriceAPI(unittest.TestCase):
    def setUp(self):
        self.api = StockPriceAPI()
    
    def test_get(self):
        prices = self.api.get(datetime.date(2024, 1, 1))
        self.assertIsInstance(prices, pd.DataFrame)
```

### 2. 模擬資料

**✅ 好的做法：**
```python
# 使用模擬資料進行測試
def test_strategy_with_mock_data():
    strategy = MyStrategy()
    mock_quotes = create_mock_quotes()
    orders = strategy.check_open_signal(mock_quotes)
    assert len(orders) > 0
```

## 相關文檔

- [API 參考](api/overview.md)
- [使用範例](examples/basic.md)
- [策略開發範例](examples/strategy.md)
