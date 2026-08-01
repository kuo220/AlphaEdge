# AlphaEdge — Claude Code 專案規則

本檔案是 Claude Code 在本專案的**常駐規則**，所有對話與變更一律套用。

| 章節 | 適用範圍 | 對應 Cursor Rule |
|------|----------|------------------|
| [1. 通用原則](#1-通用原則) | 全專案 | — |
| [2. Coding Style](#2-coding-style) | `**/*.py` | `.cursor/rules/coding-style-zh.mdc` |
| [3. Backlog 管理](#3-backlog-管理) | `backlog/**` | — |
| [4. Commit 與 Push](#4-commit-與-push) | 全專案 | `.cursor/rules/commit-message-zh.mdc`（alwaysApply） |
| [5. 目錄專屬規則](#5-目錄專屬規則) | 各子目錄 | `.cursor/rules/strategy-lab-layout.mdc` |

---

## 1. 通用原則

1. 除非使用者明確要求英文，**回覆、文件與註解一律使用繁體中文**。
2. 專有名詞保留英文原詞，不要硬翻（`tick`、`bid/ask`、`ROI`、`OHLC`、`Long/Short`、`API`、`SQLite`）。
3. 中文標點使用全形（`，`、`：`、`（）`）；同一檔案內標點與空白風格保持一致。
4. 既有程式碼的風格優先於個人偏好：新增或修改時沿用現有寫法，不要引入新風格。

---

## 2. Coding Style

> 以下規則由現有 `core/`、`strategy_lab/` 程式碼歸納而成。

### 2.1 註解語言

1. **註解一律以繁體中文為主**，專有名詞保留英文（見 §1）。
2. 中英夾雜時保留英文原詞，例如：`# 內外盤別{1: 外盤, 2: 內盤, 0: 無法判定}`、`self.volume: int = volume  # 成交量（Unit: Lot）`。
3. 註解說明「為什麼」與業務語意，不要複述程式碼字面行為。

### 2.2 Docstring

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

### 2.3 模組層級說明字串

1. 模組總覽說明字串放在 **import 區塊之後、第一個 class/function 之前**（`core/api/`、`core/models/`、`core/pipeline/` 皆如此）：

   ```python
   from core.api.base import BaseDataAPI

   """Stock Price API: query SQLite price table"""


   class StockPriceAPI(BaseDataAPI):
   ```

2. 內容較長時用多行三引號，依序寫「模組用途 → Features 條列 → 使用場景」（見 `core/utils/instrument.py`）。

### 2.4 Type Hints

1. **所有函式參數與回傳值都要標註型別**，包含回傳 `None` 的 `-> None`。
2. **區域變數與 instance 屬性也標註型別**，這是本專案明顯特徵，務必沿用：

   ```python
   self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
   df: pd.DataFrame = pd.read_sql_query(query, self.conn, params=(date,))
   open_positions: List[StockQuote] = []
   ```

3. 使用 `typing` 的 `List` / `Dict` / `Optional` / `Tuple` / `Union` 大寫寫法，不要改成 `list[...]` / `X | None`。
4. 可選欄位一律 `Optional[T]`，並在 `__init__` 給預設值 `None`。

### 2.5 Import 排序

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

### 2.6 命名

| 對象 | 規則 | 範例 |
| --- | --- | --- |
| 模組 / 檔案 | `snake_case` | `stock_price_api.py` |
| 類別 | `PascalCase`，資料 API 結尾 `API`、清洗器 `Cleaner`、更新器 `Updater`、爬蟲 `Crawler`、管理器 `Manager` | `StockChipAPI`、`StockTickCleaner` |
| 函式 / 變數 | `snake_case`；查詢類前綴 `get_`、設定類 `setup_`、訊號判斷 `check_*_signal`、計算 `calculate_` | `get_stock_price()`、`check_open_signal()` |
| 模組私有 | 前綴底線 | `_ridge_fit_predict()`、`_PROJECT_ROOT` |
| 常數 | `UPPER_SNAKE_CASE`，策略參數放 class 層級常數並附中文單位註解 | `MIN_VOLUME_LOTS: int = 5000  # 最小成交量（張）` |
| 策略類別 | 類別名即策略識別名稱，需與 `run.py --strategy` 對應 | `MomentumStrategy1` |

### 2.7 常數與 Enum

1. 字串常數先定義模組層級 `UPPER_SNAKE_CASE`，再由 `class XxxEnum(str, Enum)` 引用（見 `core/utils/constant.py`），不要直接在 Enum 內寫字面值。
2. 分類常數上方加中文分組註解：`# 定義下單類型常量`。

### 2.8 區塊分隔註解

1. 設定檔等長檔案用等寬分隔線標題（見 `core/config.py`）：

   ```python
   # -----------------------------------------------------------------------
   # === General Directory Path ===
   # -----------------------------------------------------------------------
   ```

2. `__init__` 內部屬性分組，可沿用既有的三引號分組標記（`""" === Strategy Setting === """`）或一般 `#` 註解；新程式碼建議用 `#`，不要再新增三引號分組。

### 2.9 日誌

1. 一律使用 `from loguru import logger`，不要用 `print()`（現存 `print` 屬既有例外，不要擴散）。
2. 需要落地檔案的模組在 `setup()` 內呼叫 `LogManager.setup_logger("xxx.log")`。

### 2.10 格式化工具

1. 程式碼由 formatter 產生（Ruff/Black 風格，行寬 88、雙引號、magic trailing comma），提交前確保格式一致，不要手動調整成其他排版。
2. SQL 查詢用三引號多行字串，參數一律走 `params=(...)` 佔位符，不要用 f-string 拼接使用者輸入。

---

## 3. Backlog 管理

`backlog/` 存放**尚未實作**的待辦與規劃紀錄；說明文件（API 文檔、教學）放 `docs/`。目錄用途與完成後的處理方式見 [`backlog/README.md`](backlog/README.md)。

### 3.1 狀態圖例（全專案統一）

| 標記 | 意義 | 補充要求 |
|:----:|------|----------|
| ⬜ | 未開始 | — |
| 🔄 | 進行中 | 註明目前做到哪一小項 |
| ✅ | 完成 | 註明驗證方式與實際結果 |
| ⛔ | 中斷 | **必填**：中斷於哪一步、原因、已完成到什麼程度、恢復時的下一步 |
| ⏸ | 暫緩 | 註明暫緩原因與解除條件（例如「等資料源」） |

### 3.2 新增 Backlog 文件的必要結構

新增 `backlog/*.md` 時，**必須**依序包含以下區塊：

1. **標題**：一行 `# 標題`，與 `index.md` 的檔名敘述一致。
2. **Abstract（摘要）**：開頭第一個區塊，用 3~6 行說明「這份工作在做什麼」，至少涵蓋：
   - 背景／問題：現況是什麼、為何要做。
   - 目標：完成後系統會變成什麼樣子。
   - 範圍界線：**明確寫出不做什麼**，避免範圍蔓延。
   - 驗收標準：怎樣算整份完成。
3. **進度追蹤表**：全份工作的單一進度來源，欄位固定如下：

   | 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
   |------|----------|----------|----------|:----:|--------------|
   | S1 | … | … | … | ⬜ | — |

   - 編號用 `S1`、`S2`…；有分階段時用 `Phase{階段}-{序號}`（例如 `Phase2-3`）。
   - **不要用 `P2-3` 這種縮寫**：`P` 已被 [`backlog/index.md`](backlog/index.md) 的優先級（`P0`~`P3`）佔用，兩者混用會誤讀。
   - **狀態欄只填 §3.1 的五種標記**，不要自創符號或文字。
4. **步驟詳述**：每個步驟一個 `##` 或 `###` 章節，章節標題帶編號與狀態標記（例如 `### S2. 補上 SHORT 平倉記帳 🔄`），內容至少包含：
   - **目的**：這步要解決什麼。
   - **做法**：具體到檔案、類別、函式層級，必要時附程式碼片段或公式。
   - **產出**：預期新增／修改的檔案。
   - **驗證方式**：測試名稱、回歸比對或人工檢查項目。
   - **相依**：需要先完成的步驟或外部條件。
5. **拆分原則**：每個步驟必須是**可獨立完成、獨立驗證**的最小工作單位；若一個步驟的說明超過一個章節講不完，代表該拆成兩步。步驟間依賴要在「相依」欄寫清楚，不要用隱含順序。

### 3.3 實作過程的狀態更新

1. 步驟完成 → 同時更新**進度追蹤表的狀態欄**與**該步驟章節標題的標記**，兩處不可只改一處。
2. 步驟做到一半被中斷 → 標記 ⛔，並在該步驟章節末尾補一段「中斷紀錄」：

   ```markdown
   > **⛔ 中斷紀錄（2026-07-31）**
   > - 已完成：`StockPositionManager.open_position()` 的 SHORT 分支與單元測試。
   > - 未完成：部分回補的等比例攤提。
   > - 中斷原因：舊 LONG 公式口徑不同，會破壞回歸，需先收斂成本模型。
   > - 恢復下一步：先完成 `LONG成本模型口徑收斂.md` 的 S1，再回來做本步驟。
   ```

3. 日期一律寫**絕對日期**（`2026-07-31`），不要寫「上週」、「昨天」。
4. 實作中發現、但不適合當下修的問題，一律寫進「備註」欄或步驟章節，**不可只留在對話裡**。
5. 若實作結果偏離原規格，必須在該步驟註明「偏離原規格」與原因；影響範圍大到需另立工作時，開新的 `backlog/*.md` 並互相連結。

### 3.4 索引維護規範

[`backlog/index.md`](backlog/index.md) 是所有待辦事項的單一索引表。**每次動到 `backlog/` 的內容，都必須同步更新 `index.md`**：

1. **新增** `.md` 時：在 `index.md` 表格新增一列（優先級、狀態、說明、進度、相依）。檔案清單只維護在 `index.md`，[`backlog/README.md`](backlog/README.md) 只寫資料夾用途與規範，不列檔案。
2. **實作推進**時（子步驟完成、狀態變更）：同步更新該列的「狀態」與「進度」，不可只改單一文件內的進度表。
3. **完成整份移出** `backlog/` 時：刪除 `index.md` 中對應那一列。
4. 檔名、標題或優先序調整時，一併更新 `index.md`，確保索引與各文件內容一致。

---

## 4. Commit 與 Push

當使用者要求「commit + push」時：

1. Commit message 使用中文說明（可保留 conventional commit 前綴，例如 `feat(backtest):`）。
2. Commit 內文用編號條列（`1.`、`2.`、`3.`），逐項描述每個變更。
3. 多種變更並存時，先依主題分組，再在各組內維持編號條列。
4. 回覆使用者時，需清楚列出：
   - 分支名稱
   - commit hash
   - push 目標（例如 `origin/main`）
   - 本次變更檔案清單

---

## 5. 目錄專屬規則

| 目錄 | 規則檔 | 說明 |
|------|--------|------|
| `strategy_lab/` | [`strategy_lab/CLAUDE.md`](strategy_lab/CLAUDE.md) | 對應 `.cursor/rules/strategy-lab-layout.mdc`，只在該目錄下工作時套用 |
