# BaseDataAPI

`BaseDataAPI` 是所有資料 API 的基礎抽象類別。

## 類別定義

```python
from trader.api.base import BaseDataAPI
```

## 類別結構

```python
class BaseDataAPI(ABC):
    """Base Class of Data API"""
    
    def __init__(self):
        pass
    
    @abstractmethod
    def setup(self):
        """Set Up the Config of Data API"""
        pass
```

## 說明

`BaseDataAPI` 定義了所有資料 API 必須實作的基本介面。所有具體的資料 API（如 `StockPriceAPI`、`StockTickAPI` 等）都繼承自這個基礎類別。

## 抽象方法

### `setup()`

設定資料 API 的配置，包括：
- 建立資料庫連線
- 設定日誌記錄器
- 初始化其他必要的資源

**注意**: 這個方法必須在子類別中實作。

## 實作範例

```python
from trader.api.base import BaseDataAPI
import sqlite3

class MyDataAPI(BaseDataAPI):
    def __init__(self):
        self.conn = None
        self.setup()
    
    def setup(self):
        """Set Up the Config of Data API"""
        self.conn = sqlite3.connect("database.db")
        # 其他初始化設定...
```

## 子類別

- [StockPriceAPI](stock_price_api.md)
- [StockTickAPI](stock_tick_api.md)
- [StockChipAPI](stock_chip_api.md)
- [MonthlyRevenueReportAPI](monthly_revenue_report_api.md)
- [FinancialStatementAPI](financial_statement_api.md)
