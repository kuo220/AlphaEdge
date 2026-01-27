# 資料查詢範例

本頁面提供各種資料查詢的進階範例。

## 價格資料查詢

### 查詢多檔股票的價格

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()

# 方法 1: 批次查詢
stock_ids = ["2330", "2317", "2454"]
start_date = datetime.date(2024, 1, 1)
end_date = datetime.date(2024, 12, 31)

all_data = []
for stock_id in stock_ids:
    prices = api.get_stock_price(stock_id, start_date, end_date)
    if not prices.empty:
        all_data.append(prices)

if all_data:
    combined = pd.concat(all_data, ignore_index=True)
    print(combined.groupby('stock_id')['close'].mean())

# 方法 2: 先查詢全部再篩選（更有效率）
all_prices = api.get_range(start_date, end_date)
selected = all_prices[all_prices['stock_id'].isin(stock_ids)]
```

### 計算技術指標

```python
import datetime
import pandas as pd
from trader.api.stock_price_api import StockPriceAPI

api = StockPriceAPI()

def calculate_indicators(stock_id, start_date, end_date):
    """計算技術指標"""
    prices = api.get_stock_price(stock_id, start_date, end_date)
    
    if prices.empty:
        return None
    
    prices = prices.sort_values('date')
    
    # 移動平均線
    prices['ma5'] = prices['close'].rolling(window=5).mean()
    prices['ma20'] = prices['close'].rolling(window=20).mean()
    prices['ma60'] = prices['close'].rolling(window=60).mean()
    
    # RSI
    delta = prices['close'].diff()
    gain = (delta.where(delta > 0, 0)).rolling(window=14).mean()
    loss = (-delta.where(delta < 0, 0)).rolling(window=14).mean()
    rs = gain / loss
    prices['rsi'] = 100 - (100 / (1 + rs))
    
    # MACD
    exp1 = prices['close'].ewm(span=12, adjust=False).mean()
    exp2 = prices['close'].ewm(span=26, adjust=False).mean()
    prices['macd'] = exp1 - exp2
    prices['signal'] = prices['macd'].ewm(span=9, adjust=False).mean()
    prices['histogram'] = prices['macd'] - prices['signal']
    
    # 布林通道
    prices['bb_middle'] = prices['close'].rolling(window=20).mean()
    bb_std = prices['close'].rolling(window=20).std()
    prices['bb_upper'] = prices['bb_middle'] + (bb_std * 2)
    prices['bb_lower'] = prices['bb_middle'] - (bb_std * 2)
    
    return prices

# 使用範例
indicators = calculate_indicators(
    "2330",
    datetime.date(2024, 1, 1),
    datetime.date(2024, 12, 31)
)
print(indicators[['date', 'close', 'ma5', 'ma20', 'rsi', 'macd']].tail())
```

## Tick 資料查詢

### 分析盤中交易模式

```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()

def analyze_intraday_pattern(stock_id, date):
    """分析盤中交易模式"""
    ticks = api.get_stock_ticks(stock_id, date, date)
    
    if ticks.empty:
        return None
    
    # 按小時分組
    ticks['hour'] = ticks['time'].dt.hour
    hourly_stats = ticks.groupby('hour').agg({
        'volume': 'sum',
        'price': ['mean', 'min', 'max']
    })
    
    # 找出交易最活躍的時段
    peak_hour = hourly_stats['volume'].idxmax()
    
    return {
        'hourly_stats': hourly_stats,
        'peak_hour': peak_hour,
        'total_volume': ticks['volume'].sum(),
        'vwap': (ticks['price'] * ticks['volume']).sum() / ticks['volume'].sum()
    }

# 使用範例
pattern = analyze_intraday_pattern("2330", datetime.date(2024, 1, 1))
if pattern:
    print(f"交易最活躍時段: {pattern['peak_hour']} 點")
    print(f"總成交量: {pattern['total_volume']:,.0f}")
    print(f"VWAP: {pattern['vwap']:.2f}")
```

### 計算逐筆成交的技術指標

```python
import datetime
from trader.api.stock_tick_api import StockTickAPI

api = StockTickAPI()

def calculate_tick_indicators(stock_id, date):
    """計算逐筆成交的技術指標"""
    ticks = api.get_stock_ticks(stock_id, date, date)
    
    if ticks.empty:
        return None
    
    ticks = ticks.sort_values('time')
    
    # 計算累積成交量
    ticks['cumulative_volume'] = ticks['volume'].cumsum()
    
    # 計算價格變動
    ticks['price_change'] = ticks['price'].diff()
    ticks['price_change_pct'] = ticks['price'].pct_change() * 100
    
    # 計算買賣力道（簡化版）
    ticks['buy_pressure'] = ticks['volume'].where(ticks['price_change'] > 0, 0)
    ticks['sell_pressure'] = ticks['volume'].where(ticks['price_change'] < 0, 0)
    
    return ticks

# 使用範例
indicators = calculate_tick_indicators("2330", datetime.date(2024, 1, 1))
if indicators is not None:
    print(indicators[['time', 'price', 'volume', 'price_change_pct']].tail())
```

## 籌碼資料查詢

### 分析法人動向

```python
import datetime
from trader.api.stock_chip_api import StockChipAPI

api = StockChipAPI()

def analyze_institutional_flow(start_date, end_date):
    """分析法人資金流向"""
    all_chips = []
    
    current_date = start_date
    while current_date <= end_date:
        chips = api.get(current_date)
        if not chips.empty:
            chips['date'] = current_date
            all_chips.append(chips)
        current_date += datetime.timedelta(days=1)
    
    if not all_chips:
        return None
    
    combined = pd.concat(all_chips, ignore_index=True)
    
    # 計算每日法人買賣超
    daily_flow = combined.groupby('date').agg({
        'foreign_net': 'sum',
        'investment_trust_net': 'sum',
        'dealer_net': 'sum'
    })
    
    # 計算累積買賣超
    daily_flow['foreign_cumulative'] = daily_flow['foreign_net'].cumsum()
    daily_flow['it_cumulative'] = daily_flow['investment_trust_net'].cumsum()
    daily_flow['dealer_cumulative'] = daily_flow['dealer_net'].cumsum()
    
    return daily_flow

# 使用範例
flow = analyze_institutional_flow(
    datetime.date(2024, 1, 1),
    datetime.date(2024, 1, 31)
)
if flow is not None:
    print(flow.tail())
```

## 月營收資料查詢

### 分析營收趨勢

```python
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI

api = MonthlyRevenueReportAPI()

def analyze_revenue_trend(stock_id, start_year, end_year):
    """分析營收趨勢"""
    all_data = []
    
    for year in range(start_year, end_year + 1):
        for month in range(1, 13):
            mrr = api.get(year, month)
            if not mrr.empty:
                stock_data = mrr[mrr['stock_id'] == stock_id]
                if not stock_data.empty:
                    all_data.append(stock_data)
    
    if not all_data:
        return None
    
    combined = pd.concat(all_data, ignore_index=True)
    combined = combined.sort_values(['year', 'month'])
    
    # 計算移動平均
    combined['revenue_ma3'] = combined['revenue'].rolling(window=3).mean()
    combined['revenue_ma12'] = combined['revenue'].rolling(window=12).mean()
    
    return combined

# 使用範例
trend = analyze_revenue_trend("2330", 2023, 2024)
if trend is not None:
    print(trend[['year', 'month', 'revenue', 'revenue_yoy', 'revenue_ma3']].tail())
```

## 財報資料查詢

### 計算財務比率

```python
from trader.api.financial_statement_api import FinancialStatementAPI

api = FinancialStatementAPI()

def calculate_financial_ratios(stock_id, year, season):
    """計算財務比率"""
    # 取得綜合損益表
    income = api.get("comprehensive_income", year, season)
    stock_income = income[income['stock_id'] == stock_id]
    
    # 取得資產負債表
    balance = api.get("balance_sheet", year, season)
    stock_balance = balance[balance['stock_id'] == stock_id]
    
    if stock_income.empty or stock_balance.empty:
        return None
    
    # 合併資料（假設有共同的 key）
    merged = stock_income.merge(
        stock_balance,
        on=['stock_id', 'year', 'season'],
        suffixes=('_inc', '_bs')
    )
    
    ratios = {}
    
    # 計算 ROE（假設欄位名稱）
    if 'net_income' in merged.columns and 'equity' in merged.columns:
        ratios['roe'] = merged['net_income'].iloc[0] / merged['equity'].iloc[0] * 100
    
    # 計算 ROA
    if 'net_income' in merged.columns and 'total_assets' in merged.columns:
        ratios['roa'] = merged['net_income'].iloc[0] / merged['total_assets'].iloc[0] * 100
    
    # 計算負債比率
    if 'total_liabilities' in merged.columns and 'total_assets' in merged.columns:
        ratios['debt_ratio'] = merged['total_liabilities'].iloc[0] / merged['total_assets'].iloc[0] * 100
    
    return ratios

# 使用範例
ratios = calculate_financial_ratios("2330", 2024, 1)
if ratios:
    print("財務比率:")
    for key, value in ratios.items():
        print(f"{key}: {value:.2f}%")
```

## 組合查詢

### 結合多種資料來源

```python
import datetime
from trader.api.stock_price_api import StockPriceAPI
from trader.api.stock_chip_api import StockChipAPI
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI

def comprehensive_analysis(stock_id, date):
    """綜合分析：結合價格、籌碼、月營收"""
    price_api = StockPriceAPI()
    chip_api = StockChipAPI()
    mrr_api = MonthlyRevenueReportAPI()
    
    # 查詢價格
    prices = price_api.get_stock_price(
        stock_id, date, date
    )
    
    # 查詢籌碼
    chips = chip_api.get(date)
    stock_chip = chips[chips['stock_id'] == stock_id]
    
    # 查詢月營收
    mrr = mrr_api.get(date.year, date.month)
    stock_mrr = mrr[mrr['stock_id'] == stock_id]
    
    result = {
        'stock_id': stock_id,
        'date': date,
    }
    
    if not prices.empty:
        result['close_price'] = prices['close'].iloc[0]
        result['volume'] = prices['volume'].iloc[0]
    
    if not stock_chip.empty:
        result['foreign_net'] = stock_chip['foreign_net'].iloc[0]
        result['it_net'] = stock_chip['investment_trust_net'].iloc[0]
    
    if not stock_mrr.empty:
        result['revenue'] = stock_mrr['revenue'].iloc[0]
        result['revenue_yoy'] = stock_mrr['revenue_yoy'].iloc[0]
    
    return result

# 使用範例
analysis = comprehensive_analysis("2330", datetime.date(2024, 1, 1))
print(analysis)
