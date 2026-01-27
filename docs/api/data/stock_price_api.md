# StockPriceAPI

`StockPriceAPI` 用於查詢股票的日線價格資料。

## 類別定義

```python
from trader.api.stock_price_api import StockPriceAPI
```

## 初始化

```python
api = StockPriceAPI()
```

初始化時會自動：
- 連接到 SQLite 資料庫
- 設定日誌記錄器

## 方法

### `get(date: datetime.date) -> pd.DataFrame`

取得所有股票指定日期的價格資料。

**參數：**
- `date` (datetime.date): 查詢日期

**返回：**
- `pd.DataFrame`: 包含所有股票在指定日期的價格資料

**範例：**
```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()
prices = api.get(datetime.date(2024, 1, 1))
print(prices.head())
```

**返回資料欄位：**
- `stock_id`: 股票代號
- `date`: 日期
- `open`: 開盤價
- `high`: 最高價
- `low`: 最低價
- `close`: 收盤價
- `volume`: 成交量
- （其他欄位依資料庫結構而定）

---

### `get_range(start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame`

取得所有股票指定日期範圍的價格資料。

**參數：**
- `start_date` (datetime.date): 起始日期
- `end_date` (datetime.date): 結束日期

**返回：**
- `pd.DataFrame`: 包含所有股票在指定日期範圍的價格資料

**注意：**
- 如果 `start_date > end_date`，會返回空的 DataFrame

**範例：**
```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()
prices = api.get_range(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
print(f"共 {len(prices)} 筆資料")
```

---

### `get_stock_price(stock_id: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame`

取得指定個股的價格資料。

**參數：**
- `stock_id` (str): 股票代號（例如："2330"）
- `start_date` (datetime.date): 起始日期
- `end_date` (datetime.date): 結束日期

**返回：**
- `pd.DataFrame`: 指定個股在指定日期範圍的價格資料

**注意：**
- 如果 `start_date > end_date`，會返回空的 DataFrame

**範例：**
```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()
stock_prices = api.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 31)
)
print(stock_prices)
```

## 使用範例

### 範例 1: 查詢單日所有股票價格

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()
date = datetime.date(2024, 1, 1)
prices = api.get(date)

# 找出當日漲幅最大的股票
if not prices.empty:
    prices['change_pct'] = (prices['close'] - prices['open']) / prices['open'] * 100
    top_gainers = prices.nlargest(10, 'change_pct')
    print(top_gainers[['stock_id', 'close', 'change_pct']])
```

### 範例 2: 計算移動平均線

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()
stock_prices = api.get_stock_price(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 12, 31)
)

# 計算 5 日移動平均
if not stock_prices.empty:
    stock_prices = stock_prices.sort_values('date')
    stock_prices['ma5'] = stock_prices['close'].rolling(window=5).mean()
    print(stock_prices[['date', 'close', 'ma5']].tail())
```

### 範例 3: 批次查詢多檔股票

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()
stock_ids = ["2330", "2317", "2454"]
start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 1, 31)

all_data = []
for stock_id in stock_ids:
    prices = api.get_stock_price(stock_id, start_date, end_date)
    if not prices.empty:
        all_data.append(prices)

if all_data:
    combined = pd.concat(all_data, ignore_index=True)
    print(combined.groupby('stock_id')['close'].mean())
```

## 注意事項

1. **資料庫連線**: API 會在初始化時建立資料庫連線，請確保資料庫檔案存在且可訪問
2. **日期格式**: 所有日期參數都必須是 `datetime.date` 類型
3. **空資料處理**: 如果查詢結果為空，會返回空的 DataFrame，不會拋出異常
4. **效能**: 查詢大量資料時，建議使用 `get_range` 或 `get_stock_price` 而不是多次呼叫 `get`

## 相關 API

- [StockTickAPI](stock_tick_api.md) - 逐筆成交資料
- [StockChipAPI](stock_chip_api.md) - 籌碼資料
