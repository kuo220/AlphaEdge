# 基本使用範例

本頁面提供 AlphaEdge API 的基本使用範例。

## 查詢價格資料

### 查詢單日價格

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

# 建立 API 實例
price_api = StockPriceAPI()

# 查詢 2024年1月1日的所有股票價格
date = datetime.date(2024, 1, 1)
prices = price_api.get(date)

print(f"共 {len(prices)} 筆資料")
print(prices.head())
```

### 查詢日期範圍價格

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

price_api = StockPriceAPI()

# 查詢 2024年1月的所有股票價格
prices = price_api.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)

print(f"共 {len(prices)} 筆資料")
```

### 查詢特定個股價格

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

price_api = StockPriceAPI()

# 查詢台積電 (2330) 的價格
stock_prices = price_api.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 12, 31)
)

print(stock_prices)
```

## 查詢 Tick 資料

### 查詢日期範圍的 Tick 資料

```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

tick_api = StockTickAPI()

# 查詢 2024年1月1日的所有 tick 資料
ticks = tick_api.get(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)

print(f"共 {len(ticks)} 筆 tick 資料")
print(ticks.head())
```

### 查詢特定個股的 Tick 資料

```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

tick_api = StockTickAPI()

# 查詢台積電 (2330) 的 tick 資料
stock_ticks = tick_api.get_stock_ticks(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)

print(stock_ticks.head())
```

## 查詢籌碼資料

```python
import datetime
from trader.api.stock_chip_api import StockChipAPI

chip_api = StockChipAPI()

# 查詢 2024年1月1日的籌碼資料
chips = chip_api.get(datetime.date(2024, 1, 1))

print(chips.head())
```

## 查詢月營收資料

```python
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI

mrr_api = MonthlyRevenueReportAPI()

# 查詢 2024年1月的月營收資料
mrr = mrr_api.get(year=2024, month=1)

print(mrr.head())
```

## 查詢財報資料

```python
from trader.api.financial_statement_api import FinancialStatementAPI

fs_api = FinancialStatementAPI()

# 查詢 2024年第一季的財報資料
# 注意：需要指定 table_name，例如 "balance_sheet"
fs = fs_api.get(
    table_name="balance_sheet",
    year=2024,
    season=1
)

print(fs.head())
```

## 資料處理範例

### 計算技術指標

```python
import datetime
import pandas as pd
from trader.api.stock_price_api import StockPriceAPI

price_api = StockPriceAPI()

# 取得台積電的價格資料
stock_prices = price_api.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 12, 31)
)

if not stock_prices.empty:
    # 排序資料
    stock_prices = stock_prices.sort_values('date')
    
    # 計算移動平均線
    stock_prices['ma5'] = stock_prices['close'].rolling(window=5).mean()
    stock_prices['ma20'] = stock_prices['close'].rolling(window=20).mean()
    
    # 計算 RSI（簡化版）
    delta = stock_prices['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    stock_prices['rsi'] = 100 - (100 / (1 + rs))
    
    print(stock_prices[['date', 'close', 'ma5', 'ma20', 'rsi']].tail())
```

### 篩選資料

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

price_api = StockPriceAPI()

# 查詢所有股票價格
prices = price_api.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)

# 篩選成交量 > 1000 的股票
high_volume = prices[prices['volume'] > 1000]

# 篩選漲幅 > 5% 的股票
if 'open' in prices.columns and 'close' in prices.columns:
    prices['change_pct'] = (prices['close'] - prices['open']) / prices['open'] * 100
    top_gainers = prices[prices['change_pct'] > 5]
    
    print(f"漲幅超過 5% 的股票有 {len(top_gainers)} 檔")
    print(top_gainers[['stock_id', 'close', 'change_pct']].head())
```

## 錯誤處理

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

price_api = StockPriceAPI()

try:
    prices = price_api.get(datetime.date(2024, 1, 1))
    
    if prices.empty:
        print("查詢結果為空")
    else:
        print(f"成功查詢到 {len(prices)} 筆資料")
        
except Exception as e:
    print(f"查詢時發生錯誤: {e}")
```

## 效能優化

### 批次查詢

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

price_api = StockPriceAPI()

# 一次性查詢日期範圍，比分次查詢更有效率
prices = price_api.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 12, 31)
)

# 然後在記憶體中進行篩選和處理
stock_2330 = prices[prices['stock_id'] == '2330']
```

### 快取結果

```python
import datetime
import pickle
from trader.api.stock_price_api import StockPriceAPI

price_api = StockPriceAPI()

# 查詢資料
prices = price_api.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 12, 31)
)

# 儲存到檔案（可選）
with open('prices_cache.pkl', 'wb') as f:
    pickle.dump(prices, f)

# 之後可以從檔案載入
# with open('prices_cache.pkl', 'rb') as f:
#     prices = pickle.load(f)
```
