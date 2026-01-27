# MonthlyRevenueReportAPI

`MonthlyRevenueReportAPI` 用於查詢股票的月營收資料。

## 類別定義

```python
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
```

## 初始化

```python
api = MonthlyRevenueReportAPI()
```

初始化時會自動：
- 連接到 SQLite 資料庫
- 設定日誌記錄器

## 方法

### `get(year: int, month: int) -> pd.DataFrame`

取得指定年月的所有股票月營收資料。

**參數：**
- `year` (int): 年份（例如：2024）
- `month` (int): 月份（1-12）

**返回：**
- `pd.DataFrame`: 包含所有股票在指定年月的月營收資料

**範例：**
```python
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI

api = MonthlyRevenueReportAPI()
mrr = api.get(year=2024, month=1)
print(mrr.head())
```

**返回資料欄位：**
- `stock_id`: 股票代號
- `year`: 年份
- `month`: 月份
- `revenue`: 營收金額
- `revenue_yoy`: 年增率（Year-over-Year）
- `revenue_mom`: 月增率（Month-over-Month）
- （其他欄位依資料庫結構而定）

## 使用範例

### 範例 1: 找出月營收成長的股票

```python
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI

api = MonthlyRevenueReportAPI()
mrr = api.get(year=2024, month=1)

if not mrr.empty:
    # 篩選月營收年增率 > 20% 的股票
    growth_stocks = mrr[mrr['revenue_yoy'] > 20]
    growth_stocks = growth_stocks.sort_values('revenue_yoy', ascending=False)
    
    print("月營收年增率前 10 名:")
    print(growth_stocks[['stock_id', 'revenue', 'revenue_yoy']].head(10))
```

### 範例 2: 比較多個月的營收

```python
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI

api = MonthlyRevenueReportAPI()

# 查詢多個月的資料
all_data = []
for month in range(1, 4):  # 1-3月
    mrr = api.get(year=2024, month=month)
    if not mrr.empty:
        all_data.append(mrr)

if all_data:
    combined = pd.concat(all_data, ignore_index=True)
    
    # 分析特定股票的營收趨勢
    stock_data = combined[combined['stock_id'] == '2330']
    print("台積電營收趨勢:")
    print(stock_data[['year', 'month', 'revenue', 'revenue_yoy']])
```

### 範例 3: 查詢特定股票的月營收

```python
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI

api = MonthlyRevenueReportAPI()
mrr = api.get(year=2024, month=1)

if not mrr.empty:
    # 查詢特定股票
    stock_mrr = mrr[mrr['stock_id'] == '2330']
    
    if not stock_mrr.empty:
        print("台積電月營收資料:")
        print(stock_mrr[['year', 'month', 'revenue', 'revenue_yoy', 'revenue_mom']])
```

## 注意事項

1. **資料更新時間**: 月營收資料通常在每月 10 日後陸續公布
2. **資料完整性**: 某些股票可能沒有月營收資料（例如新上市股票）
3. **年增率計算**: 年增率是與去年同期比較的成長率
4. **月增率計算**: 月增率是與上個月比較的成長率

## 相關 API

- [FinancialStatementAPI](financial_statement_api.md) - 財報資料
- [BaseDataAPI](base.md) - 基礎 API 類別
