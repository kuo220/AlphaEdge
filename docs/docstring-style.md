# 註解與 Docstring 規範

本文件定義 AlphaEdge 專案中程式碼註解與 docstring 的撰寫格式，以 `trader/api/finmind_api.py` 為參考範例。

---

## 1. 模組頂部 Docstring

- **位置**：import 之後、第一個 class 或 function 之前。
- **第一行**：一句話說明模組用途（誰、做什麼、用什麼資料）。
- **Usage 區塊**：以 `Usage:` 開頭，底下用簡短程式碼示範主要用法（import、建立實例、常用呼叫）。

```python
"""FinMind 資料 API：查詢 finmind_loader 寫入 SQLite 的四張表。

Usage:
    from trader.api.finmind_api import FinMindAPI

    api = FinMindAPI()

    # 台股總覽（不含權證）
    df = api.get_all_stock_info()
    row = api.get_stock_info("2330")

    # 當日券商分點統計（依股票、日期、券商查詢）
    df = api.get_broker_trading_for_stock_on_date("2330", date)
    df = api.get_broker_trading_for_stock_in_range("2330", start_date, end_date)
    df = api.get_broker_trading_by_date(date)
    df = api.get_broker_trading_by_broker_and_date("永豐金證券", date)
"""
```

---

## 2. 類別 Docstring

- **單行**：說明類別名稱或用途，必要時列出主要功能。

```python
class FinMindAPI(BaseDataAPI):
    """FinMind 資料 API：台股總覽、證券商資訊、券商分點日報"""
```

---

## 3. 方法／函數 Docstring

- **單行**：用中文說明「做什麼」或「回傳什麼」。
- 若參數或回傳值較複雜，可依需求補充 Args / Returns（本專案 API 模組以單行為主）。

```python
def setup(self) -> None:
    """設定連線與 log"""

def get_stock_info(self, stock_id: str) -> pd.DataFrame:
    """取得單一股票的台股總覽（不含權證）"""

def get_broker_trading_for_stock_on_date(
    self, stock_id: str, date: datetime.date
) -> pd.DataFrame:
    """取得指定股票在指定日期的券商分點日報（單日）"""

def get_broker_trading_for_stock_in_range(
    self,
    stock_id: str,
    start_date: datetime.date,
    end_date: datetime.date,
) -> pd.DataFrame:
    """取得指定股票在日期區間內的券商分點日報（多日）"""
```

---

## 4. 區塊註解（區分功能／對應表）

- 用於區分同一類別內的不同功能區塊，或標註對應的資料表與欄位。
- **格式**：
  - 分隔線：`# -----------------------------------------------------------------------`
  - 小標：`# 區塊名稱 (table_name)` 或 `# 區塊名稱`
  - 分隔線：同上
  - 欄位：`# 欄位: col1, col2, ...`（若與前表相同可寫「欄位同上」）
  - 主鍵：`# PK: column_name` 或 `# PK: (col1, col2, ...)`
  - 空一行註解：`#`

```python
    # -----------------------------------------------------------------------
    # 台股總覽 (taiwan_stock_info)
    # -----------------------------------------------------------------------
    # 欄位: industry_category, stock_id, stock_name, type, date
    # PK: stock_id
    #

    def get_stock_info(self, stock_id: str) -> pd.DataFrame:
        """取得單一股票的台股總覽（不含權證）"""
        ...
```

```python
    # -----------------------------------------------------------------------
    # 台股總覽含權證 (taiwan_stock_info_with_warrant)
    # -----------------------------------------------------------------------
    # 欄位同上，PK: stock_id
    #

    def get_stock_info_with_warrant(self, stock_id: str) -> pd.DataFrame:
        """取得單一股票的台股總覽（含權證）"""
        ...
```

---

## 5. 行內註解

- 僅在需要說明「為什麼這樣做」時使用，避免解釋「在做什麼」（程式碼與 docstring 應已能表達）。
- 行內註解與程式碼之間至少空一格，註解前可留一空格：`# 註解內容`。

---

## 6. Docstring 與 `#` 註解的差異

| 項目       | `#` 註解           | Docstring `"""..."""`     |
|------------|--------------------|----------------------------|
| 本質       | 註解，編譯後丟棄   | 字串常數，會存到 `__doc__` |
| 執行時     | 不存在             | 存在，可被 `help()` 讀取   |
| 適用情境   | 區塊說明、實作備註 | 模組／類別／函數的說明文字 |

- **區塊註解**（如「對應哪張表、欄位、PK」）使用 `#`，不改成 `"""`，以避免被當成 docstring 或觸發 docstring 檢查工具警告。
- **模組、類別、函數的對外說明**使用 docstring，方便 `help()` 與 mkdocstrings 產生文檔。

---

## 參考檔案

- [trader/api/finmind_api.py](../trader/api/finmind_api.py) — 本規範的實作範例。
