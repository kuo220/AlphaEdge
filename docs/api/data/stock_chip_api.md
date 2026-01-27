# StockChipAPI

`StockChipAPI` 用於查詢股票的三大法人籌碼資料。

## 類別定義

```python
from trader.api.stock_chip_api import StockChipAPI
```

## 初始化

```python
api = StockChipAPI()
```

初始化時會自動：
- 連接到 SQLite 資料庫
- 設定日誌記錄器

## 方法

### `get(date: datetime.date) -> pd.DataFrame`

取得指定日期的所有股票籌碼資料。

**參數：**
- `date` (datetime.date): 查詢日期

**返回：**
- `pd.DataFrame`: 包含所有股票在指定日期的籌碼資料

**範例：**
```python
import datetime
from trader.api.stock_chip_api import StockChipAPI

api = StockChipAPI()
chips = api.get(datetime.date(2024, 1, 1))
print(chips.head())
```

**返回資料欄位：**
- `stock_id`: 股票代號
- `date`: 日期
- `foreign_buy`: 外資買入金額
- `foreign_sell`: 外資賣出金額
- `foreign_net`: 外資淨買賣金額
- `investment_trust_buy`: 投信買入金額
- `investment_trust_sell`: 投信賣出金額
- `investment_trust_net`: 投信淨買賣金額
- `dealer_buy`: 自營商買入金額
- `dealer_sell`: 自營商賣出金額
- `dealer_net`: 自營商淨買賣金額
- （其他欄位依資料庫結構而定）

## 使用範例

### 範例 1: 找出外資買超的股票

```python
import datetime
from trader.api.stock_chip_api import StockChipAPI

api = StockChipAPI()
chips = api.get(datetime.date(2024, 1, 1))

if not chips.empty:
    # 篩選外資買超的股票
    foreign_buy = chips[chips['foreign_net'] > 0]
    foreign_buy = foreign_buy.sort_values('foreign_net', ascending=False)
    
    print("外資買超前 10 名:")
    print(foreign_buy[['stock_id', 'foreign_net']].head(10))
```

### 範例 2: 分析三大法人動向

```python
import datetime
from trader.api.stock_chip_api import StockChipAPI

api = StockChipAPI()
chips = api.get(datetime.date(2024, 1, 1))

if not chips.empty:
    # 計算三大法人總買賣超
    total_net = (
        chips['foreign_net'].sum() +
        chips['investment_trust_net'].sum() +
        chips['dealer_net'].sum()
    )
    
    print(f"三大法人總買賣超: {total_net:,.0f}")
    print(f"外資: {chips['foreign_net'].sum():,.0f}")
    print(f"投信: {chips['investment_trust_net'].sum():,.0f}")
    print(f"自營商: {chips['dealer_net'].sum():,.0f}")
```

### 範例 3: 查詢特定股票的籌碼資料

```python
import datetime
from trader.api.stock_chip_api import StockChipAPI

api = StockChipAPI()
chips = api.get(datetime.date(2024, 1, 1))

if not chips.empty:
    # 查詢特定股票
    stock_chip = chips[chips['stock_id'] == '2330']
    
    if not stock_chip.empty:
        print("台積電籌碼資料:")
        print(stock_chip[['date', 'foreign_net', 'investment_trust_net', 'dealer_net']])
```

## 注意事項

1. **資料更新**: 籌碼資料通常在交易日當天晚上或隔天早上更新
2. **資料完整性**: 某些日期可能沒有資料（例如假日）
3. **單位**: 注意金額的單位（通常是新台幣元）

## 相關 API

- [StockPriceAPI](stock_price_api.md) - 日線價格資料
- [BaseDataAPI](base.md) - 基礎 API 類別
