# StockTickAPI

`StockTickAPI` 用於查詢股票的逐筆成交資料（Tick 資料）。

## 類別定義

```python
from trader.api.stock_tick_api import StockTickAPI
```

## 初始化

```python
api = StockTickAPI()
```

初始化時會自動：
- 連接到 DolphinDB 資料庫
- 設定日誌記錄器

**注意**: 使用此 API 需要 DolphinDB 服務正常運行。

## 方法

### `get(start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame`

取得所有個股各自排序好的 tick 資料（個股沒有混在一起排序）。

**參數：**
- `start_date` (datetime.date): 起始日期
- `end_date` (datetime.date): 結束日期

**返回：**
- `pd.DataFrame`: 包含所有個股在指定日期範圍的 tick 資料

**注意：**
- 如果 `start_date > end_date`，會返回空的 DataFrame
- 資料按個股分組，但個股之間沒有統一排序

**範例：**
```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()
ticks = api.get(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)
print(ticks.head())
```

---

### `get_ordered_ticks(start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame`

取得排序好的 tick 資料（所有個股混在一起以時間排序），模擬市場盤中情形。

**參數：**
- `start_date` (datetime.date): 起始日期
- `end_date` (datetime.date): 結束日期

**返回：**
- `pd.DataFrame`: 所有個股的 tick 資料，按時間排序

**範例：**
```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()
ordered_ticks = api.get_ordered_ticks(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)
print(ordered_ticks.head())
```

---

### `get_stock_ticks(stock_id: str, start_date: datetime.date, end_date: datetime.date) -> pd.DataFrame`

取得指定個股的 tick 資料。

**參數：**
- `stock_id` (str): 股票代號（例如："2330"）
- `start_date` (datetime.date): 起始日期
- `end_date` (datetime.date): 結束日期

**返回：**
- `pd.DataFrame`: 指定個股在指定日期範圍的 tick 資料

**範例：**
```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()
stock_ticks = api.get_stock_ticks(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)
print(stock_ticks.head())
```

---

### `get_last_tick(stock_id: str, date: datetime.date) -> pd.DataFrame`

取得當日最後一筆 tick。

**參數：**
- `stock_id` (str): 股票代號
- `date` (datetime.date): 查詢日期

**返回：**
- `pd.DataFrame`: 包含最後一筆 tick 的 DataFrame（如果存在）

**範例：**
```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()
last_tick = api.get_last_tick(
    stock_id="2330",
    date=datetime.date(2024, 1, 1)
)
print(last_tick)
```

## 使用範例

### 範例 1: 分析盤中交易模式

```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()

# 取得排序好的 tick 資料（模擬市場）
ticks = api.get_ordered_ticks(
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)

# 分析交易量分佈
if not ticks.empty:
    volume_by_hour = ticks.groupby(ticks['time'].dt.hour)['volume'].sum()
    print("每小時交易量:")
    print(volume_by_hour)
```

### 範例 2: 計算 VWAP（成交量加權平均價）

```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()

stock_ticks = api.get_stock_ticks(
    stock_id="2330",
    start_date=datetime.date(2024, 1, 1),
    end_date=datetime.date(2024, 1, 1)
)

if not stock_ticks.empty:
    # 計算 VWAP
    total_value = (stock_ticks['price'] * stock_ticks['volume']).sum()
    total_volume = stock_ticks['volume'].sum()
    vwap = total_value / total_volume if total_volume > 0 else 0
    print(f"VWAP: {vwap}")
```

## 注意事項

1. **DolphinDB 連線**: 使用此 API 前必須確保 DolphinDB 服務正常運行
2. **資料量**: Tick 資料量非常大，查詢時建議：
   - 縮小日期範圍
   - 使用 `get_stock_ticks` 查詢特定股票
   - 避免一次查詢過多資料
3. **時間格式**: Tick 資料的時間欄位是納秒級時間戳
4. **效能**: DolphinDB 專為時序資料優化，查詢速度通常很快

## 相關 API

- [StockPriceAPI](stock_price_api.md) - 日線價格資料
- [BaseDataAPI](base.md) - 基礎 API 類別
