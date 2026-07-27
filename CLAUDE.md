# AlphaEdge 專案規則（Claude Code）

> 本檔案對齊 `.cursor/rules/commit-message-zh.mdc`（alwaysApply: true）,供 Claude Code 在本專案中永遠套用。

## Commit 與 Push 回覆規格

當使用者要求「commit + push」時，請遵守以下規範：

1. Commit message 使用中文說明（可保留 conventional commit 前綴）。
2. Commit 內文需用編號條列，格式為 `1.`, `2.`, `3.`，逐項描述每個變更。
3. 回覆使用者時，需清楚列出：
   - 分支名稱
   - commit hash
   - push 目標（例如 `origin/main`）
   - 本次變更檔案清單
4. 若同時有多種變更，先依主題分組，再在各組內維持編號條列。
5. 若使用者未明確要求英文，預設以繁體中文回覆與撰寫說明。

## Coding Style 與註解規範

> 本節對齊 `.cursor/rules/coding-style-zh.mdc`（globs: `**/*.py`）。
> 以下規則由現有 `core/`、`strategy_lab/` 程式碼歸納而成，新增或修改程式碼時一律沿用，不要引入新風格。

### 1. 註解語言

1. **註解一律以繁體中文為主**，除非是本來就以英文表達的專有名詞（例如 `tick`、`bid/ask`、`ROI`、`OHLC`、`Long/Short`、`Ridge`、`API`、`SQLite`）。
2. 中英夾雜時保留英文原詞，不要硬翻，例如：`# 內外盤別{1: 外盤, 2: 內盤, 0: 無法判定}`、`self.volume: int = volume  # 成交量（Unit: Lot）`。
3. 中文標點使用全形（`，`、`：`、`（）`），英文專有名詞前後不強制加空白，但同一檔案內保持一致。
4. 註解說明「為什麼」與業務語意，不要複述程式碼字面行為。

### 2. Docstring

1. 每個 class 與 public method 都要有 docstring；單行說明用一行三引號寫完：

   ```python
   def get(self, date: datetime.date) -> pd.DataFrame:
       """取得所有股票指定日期的 Price"""

       query: str = f"""..."""
   ```

2. **docstring 之後空一行才開始寫程式**（本專案通用習慣）。
3. 抽象基底類別（`core/**/base.py`）與需要詳列參數的函式，使用專案自訂的結構化格式：

   ```python
   """
   - Description:
       開倉策略（Long & Short），需要包含買賣的標的、價位和數量
   - Parameter:
       - stock_quotes: List[StockQuote]
           目標股票的報價資訊
   - Return:
       - List[StockOrder]
           開倉訂單
   """
   ```

   不要改用 Google style 的 `Args:` / `Returns:`（專案中僅零星出現，屬例外）。
4. 策略類別的 class docstring 用條列描述交易邏輯，區塊固定為「買進條件 / 賣出條件 / 停損條件」，並註明未實作的部分：

   ```python
   class MomentumStrategy1(BaseStockStrategy):
       """
       動能策略 1（日線）

       買進條件（全部滿足）：
       - 當日收盤相對「前一交易日」收盤漲幅 ≥ 門檻（預設 9%）

       停損條件：
       - 未實作（一律不回傳停損單）
       """
   ```

### 3. 模組層級說明字串

1. 模組總覽說明字串放在 **import 區塊之後、第一個 class/function 之前**（本專案主流寫法，`core/api/`、`core/models/`、`core/pipeline/` 皆如此）：

   ```python
   from core.api.base import BaseDataAPI

   """Stock Price API: query SQLite price table"""


   class StockPriceAPI(BaseDataAPI):
   ```

2. 內容較長時用多行三引號，依序寫「模組用途 → Features 條列 → 使用場景」（見 `core/utils/instrument.py`）。

### 4. Type Hints

1. **所有函式參數與回傳值都要標註型別**，包含回傳 `None` 的 `-> None`。
2. **區域變數與 instance 屬性也標註型別**，這是本專案明顯特徵，務必沿用：

   ```python
   self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
   df: pd.DataFrame = pd.read_sql_query(query, self.conn, params=(date,))
   open_positions: List[StockQuote] = []
   ```

3. 使用 `typing` 的 `List` / `Dict` / `Optional` / `Tuple` / `Union` 大寫寫法，不要改成 `list[...]` / `X | None`。
4. 可選欄位一律 `Optional[T]`，並在 `__init__` 給預設值 `None`。

### 5. Import 排序

依 Ruff/isort 預設分組，組間空一行，組內字母排序：

```python
# 1. 標準函式庫
import datetime
from typing import List, Optional

# 2. 第三方套件
import pandas as pd
from loguru import logger

# 3. 專案內部（core.* 以絕對路徑；同目錄可用相對 .module）
from core.api.base import BaseDataAPI
from core.config import DB_PATH, PRICE_TABLE_NAME
```

### 6. 命名

| 對象 | 規則 | 範例 |
| --- | --- | --- |
| 模組 / 檔案 | `snake_case` | `stock_price_api.py` |
| 類別 | `PascalCase`，資料 API 結尾 `API`、清洗器 `Cleaner`、更新器 `Updater`、爬蟲 `Crawler`、管理器 `Manager` | `StockChipAPI`、`StockTickCleaner` |
| 函式 / 變數 | `snake_case`；查詢類前綴 `get_`、設定類 `setup_`、訊號判斷 `check_*_signal`、計算 `calculate_` | `get_stock_price()`、`check_open_signal()` |
| 模組私有 | 前綴底線 | `_ridge_fit_predict()`、`_PROJECT_ROOT` |
| 常數 | `UPPER_SNAKE_CASE`，策略參數放 class 層級常數並附中文單位註解 | `MIN_VOLUME_LOTS: int = 5000  # 最小成交量（張）` |
| 策略類別 | 類別名即策略識別名稱，需與 `run.py --strategy` 對應 | `MomentumStrategy1` |

### 7. 常數與 Enum

1. 字串常數先定義模組層級 `UPPER_SNAKE_CASE`，再由 `class XxxEnum(str, Enum)` 引用（見 `core/utils/constant.py`），不要直接在 Enum 內寫字面值。
2. 分類常數上方加中文分組註解：`# 定義下單類型常量`。

### 8. 區塊分隔註解

1. 設定檔等長檔案用等寬分隔線標題（見 `core/config.py`）：

   ```python
   # -----------------------------------------------------------------------
   # === General Directory Path ===
   # -----------------------------------------------------------------------
   ```

2. `__init__` 內部屬性分組，可沿用既有的三引號分組標記（`""" === Strategy Setting === """`）或一般 `#` 註解；新程式碼建議用 `#`，不要再新增三引號分組。

### 9. 日誌

1. 一律使用 `from loguru import logger`，不要用 `print()`（現存 `print` 屬既有例外，不要擴散）。
2. 需要落地檔案的模組在 `setup()` 內呼叫 `LogManager.setup_logger("xxx.log")`。

### 10. 格式化工具

1. 程式碼由 formatter 產生（Ruff/Black 風格，行寬 88、雙引號、magic trailing comma），提交前確保格式一致，不要手動調整成其他排版。
2. SQL 查詢用三引號多行字串，參數一律走 `params=(...)` 佔位符，不要用 f-string 拼接使用者輸入。

## Backlog 索引維護規範

`backlog/index.md` 是所有待辦事項的單一索引表，記錄每個 `.md` 的優先級與完成狀態。**每次動到 `backlog/` 的內容，都必須同步更新 `index.md`**：

1. **新增**待辦 `.md` 檔案時，在 `index.md` 表格新增對應的一列，填寫優先級、狀態、說明、進度與相依關係。
2. **實作推進**時（子任務完成、階段狀態變更），同步更新該列的「狀態」與「進度」欄位，不可只改單一文件內的進度表。
3. **項目完成整份移出** `backlog/` 時，同步刪除 `index.md` 與 `backlog/README.md` 中對應那一列。
4. 檔名、標題或優先序調整時，一併更新 `index.md`，確保索引與各文件內容一致。

## 目錄專屬規則

- `strategy_lab/` 目錄有自己的規則,見 [`strategy_lab/CLAUDE.md`](strategy_lab/CLAUDE.md)（對應 `.cursor/rules/strategy-lab-layout.mdc`，只在該目錄下工作時套用）。
