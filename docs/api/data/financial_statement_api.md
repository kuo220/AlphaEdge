# FinancialStatementAPI

`FinancialStatementAPI` 用於查詢股票的財務報表資料。

## 類別定義

```python
from trader.api.financial_statement_api import FinancialStatementAPI
```

## 初始化

```python
api = FinancialStatementAPI()
```

初始化時會自動：
- 連接到 SQLite 資料庫
- 設定日誌記錄器

## 方法

### `get(table_name: str, year: int, season: int) -> pd.DataFrame`

取得指定年度和季度的財報資料。

**參數：**
- `table_name` (str): 財報表格名稱
  - `"balance_sheet"`: 資產負債表
  - `"cash_flow"`: 現金流量表
  - `"comprehensive_income"`: 綜合損益表
- `year` (int): 年份（例如：2024）
- `season` (int): 季度（1-4）

**返回：**
- `pd.DataFrame`: 包含所有股票在指定年度和季度的財報資料

**範例：**
```python
from trader.api.financial_statement_api import FinancialStatementAPI

api = FinancialStatementAPI()

# 查詢資產負債表
balance_sheet = api.get(
    table_name="balance_sheet",
    year=2024,
    season=1
)
print(balance_sheet.head())
```

---

### `get_range(table_name: str, start_year: int, end_year: int, start_season: int, end_season: int) -> pd.DataFrame`

取得指定年度和季度範圍內的財報資料。

**參數：**
- `table_name` (str): 財報表格名稱
- `start_year` (int): 起始年份
- `end_year` (int): 結束年份
- `start_season` (int): 起始季度（1-4）
- `end_season` (int): 結束季度（1-4）

**返回：**
- `pd.DataFrame`: 包含所有股票在指定範圍內的財報資料

**範例：**
```python
from trader.api.financial_statement_api import FinancialStatementAPI

api = FinancialStatementAPI()

# 查詢 2023-2024 年的財報
fs = api.get_range(
    table_name="comprehensive_income",
    start_year=2023,
    end_year=2024,
    start_season=1,
    end_season=4
)
print(fs.head())
```

## 可用的財報表格

### 1. 資產負債表 (balance_sheet)

包含資產、負債、股東權益等資訊。

### 2. 現金流量表 (cash_flow)

包含營業活動、投資活動、融資活動的現金流量。

### 3. 綜合損益表 (comprehensive_income)

包含營業收入、營業成本、稅前淨利、稅後淨利等資訊。

## 使用範例

### 範例 1: 查詢特定股票的財報

```python
from trader.api.financial_statement_api import FinancialStatementAPI

api = FinancialStatementAPI()

# 查詢台積電的綜合損益表
income = api.get(
    table_name="comprehensive_income",
    year=2024,
    season=1
)

if not income.empty:
    stock_income = income[income['stock_id'] == '2330']
    print("台積電綜合損益表:")
    print(stock_income)
```

### 範例 2: 分析多個季度的財報趨勢

```python
from trader.api.financial_statement_api import FinancialStatementAPI

api = FinancialStatementAPI()

# 查詢多個季度的資料
all_seasons = []
for season in range(1, 5):  # 1-4季
    fs = api.get(
        table_name="comprehensive_income",
        year=2024,
        season=season
    )
    if not fs.empty:
        all_seasons.append(fs)

if all_seasons:
    combined = pd.concat(all_seasons, ignore_index=True)
    
    # 分析特定股票的營收趨勢
    stock_data = combined[combined['stock_id'] == '2330']
    print("台積電營收趨勢:")
    print(stock_data[['year', 'season', 'revenue']])
```

### 範例 3: 計算財務比率

```python
from trader.api.financial_statement_api import FinancialStatementAPI

api = FinancialStatementAPI()

# 取得資產負債表和綜合損益表
balance_sheet = api.get("balance_sheet", 2024, 1)
income = api.get("comprehensive_income", 2024, 1)

if not balance_sheet.empty and not income.empty:
    # 合併資料
    merged = balance_sheet.merge(
        income,
        on=['stock_id', 'year', 'season'],
        suffixes=('_bs', '_inc')
    )
    
    # 計算 ROE（股東權益報酬率）
    # 假設欄位名稱
    if 'net_income' in merged.columns and 'equity' in merged.columns:
        merged['roe'] = merged['net_income'] / merged['equity'] * 100
        print(merged[['stock_id', 'roe']].head())
```

## 注意事項

1. **財報公布時間**: 
   - Q1：5月15日
   - Q2：8月14日
   - Q3：11月14日
   - 年報：3月31日

2. **表格名稱**: 必須使用正確的表格名稱，否則會返回空資料

3. **資料結構**: 不同表格的欄位結構不同，請參考資料庫結構或 metadata 檔案

4. **資料完整性**: 某些股票可能沒有完整的財報資料

## 相關 API

- [MonthlyRevenueReportAPI](monthly_revenue_report_api.md) - 月營收資料
- [BaseDataAPI](base.md) - 基礎 API 類別
