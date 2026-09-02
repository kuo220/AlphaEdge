# 權益變動表（equity_change）

> 本文件描述 `equity_change` 表的**資料形狀、涵蓋範圍與已知限制**——也就是「要用這張表之前
> 必須先知道的事」。入庫批次、resume 依據與失敗語意屬於 pipeline 的共同約定，
> 寫在 [ETL 入庫約定](etl-ingestion.md)（§二對照表、§4.5 事故紀錄），本文件不重複。
>
> 各項設計的理由寫在程式碼 docstring（`FinancialStatementCleaner.clean_equity_changes()` /
> `select_equity_changes_period_table()`、`FinancialStatementUpdater.is_season_filed()`）。

---

## 一、資料形狀：長表，不是寬表

MOPS 的權益變動表原始版面是**二維矩陣**——欄是權益項目（普通股股本、資本公積…），
列是變動原因（期初餘額、本期淨利…）。入庫時攤平成長表，**一列 = 一個「權益項目 × 變動原因」的組合**。

| 欄位 | 型別 | 說明 |
|------|------|------|
| `year` | `INT NOT NULL` | 年 |
| `season` | `INT NOT NULL` | 季（1~4） |
| `stock_id` | `TEXT NOT NULL` | 股票代號 |
| `權益項目` | `TEXT NOT NULL` | 來源表的**欄**：普通股股本、資本公積、保留盈餘合計、庫藏股票… |
| `變動原因` | `TEXT NOT NULL` | 來源表的**列**：期初餘額、本期淨利（淨損）、普通股現金股利、期末餘額… |
| `金額` | `REAL` | **單位：新台幣仟元** |

**主鍵**：`(year, season, stock_id, 權益項目, 變動原因)`。

**為什麼不用寬表**：各公司的權益項目集合差異極大——實測 2024Q1，2330 台積電 15 項、
2891 中信金 17 項（多出「特別股股本」「採用覆蓋法重分類之其他綜合損益」）、6488 環球晶 14 項。
寬表得存全市場的欄位聯集，且每遇到一個新項目就要改 schema；長表的欄位固定六個，不隨資料成長。

**為什麼主鍵不含 `公司名稱`**（其他三張財報表有）：`ajax_t164sb06` 是逐檔查詢，
回傳的只有報表矩陣本身，**來源端點根本不給公司名稱**；其他三張報表的 `公司名稱` 來自全市場表格的欄位。
若硬要補，只能去 `taiwan_stock_info` 查現名，那是「現在的名稱」而非「當季的名稱」，
寫進主鍵反而會製造假的唯一性。需要公司名稱請自行 join `taiwan_stock_info`，並知道它是現名。

### 讀取方式

`FinancialStatementAPI` 以 `table_name` 為參數，`equity_change` 沿用同一組介面：

```python
from core.api.tw.financial_statement_api import FinancialStatementAPI
from core.config import EQUITY_CHANGE_TABLE_NAME

api = FinancialStatementAPI()
df = api.get(EQUITY_CHANGE_TABLE_NAME, year=2020, season=1)
```

### 「沒有這一列」與「金額是 0」是兩件事

- **來源表的空白儲存格不入表**：該公司若根本沒有這個權益項目，就完全不會有那些列。
  例如 2330 台積電沒有庫藏股票，`WHERE stock_id='2330' AND 權益項目='庫藏股票'` 查出來是 **0 列**。
- **來源表明確填 0 的會入表為 `0.0`**：2020Q1 的 230,163 列中有 **138,945 列（60%）金額為 0**，
  這是正常的——大多數「權益項目 × 變動原因」的組合在單一季度並沒有發生變動。
- **`金額` 實測無 `NULL`**（2020Q1 為 0 筆），不會出現整排 `NULL` 的佔位列。

所以 `COUNT(*)` 不等於「有變動的項目數」，要濾 `金額 != 0`。
而「查無此列」有兩種可能——該公司沒有這個項目、或**該年季根本還沒回補**（見§二），
兩者在 DB 裡長得一樣。**做除法或累加前先確認該年季已入庫。**

---

## 二、涵蓋範圍（截至 2026-08-29）

| 項目 | 現況 |
|------|------|
| 已入庫年季 | **僅 2020Q1**（230,163 列 / 1,743 檔） |
| 目標區間 | 2013Q1 起（`DEFAULT_START_YEAR`），共 56 個年季 |
| 未回補 | 55 個年季 |

⚠️ **`docs/exchanges/data_coverage.md` 的「財報：2013 年第 1 季」不適用於本表**——
那是 balance_sheet／comprehensive_income／cash_flow 三張的涵蓋範圍。
歷史回補的執行方式與進度追蹤見 [`backlog/權益變動表ETL補完.md`](../../backlog/權益變動表ETL補完.md) S5。

2020Q1 的品質稽核結果：`unreachable` 0、入庫失敗 0，抽樣 2330／2891／6488／9933／1101／8996
共 6 檔 1,993 列重爬後逐格比對，**mismatch = 0**。

---

## 三、已知限制

以下四項**回補完成後仍然成立**，不是待修的 bug。

1. **漏掉已下市公司**。爬取清單取自 `taiwan_stock_info` 的**現況**（`type IN ('twse','tpex')`、
   排除 ETF、代號為 4 碼數字，實測 2,086 檔）。用歷史區間做研究時，這是一個
   **倖存者偏誤**來源：2013 年當時存在、之後下市的公司，在本表中完全不存在。
2. **不含興櫃**（`emerging`）。
3. **「查無資料」與「還沒爬」在 DB 裡無法區分**。resume 以「該年季 DB 有沒有這檔的列」為準，
   而查無資料的公司（當時尚未上市）不會留下任何列。後果有二：
   - 每個年季重跑會多打約 15% 的無效請求（2020Q1 是 343 檔）。
   - 從 DB 無法回答「這檔當季到底沒申報，還是我沒爬到」。
   這與[券商分點 NO_DATA 的 metadata 語意](broker-trading-no-data.md)是同一個問題，該文件已選型未實作。
4. **站方過載造成的暫時性失敗只在 log 尾端彙總**（`N requests unreachable after retries`）。
   重跑即可補上，但**必須真的去看那行 log**——不看就會變成「跑完了卻莫名少了幾百檔」。

### 兩道刻意設計的防線

- **抓錯期別寧可回空表**：MOPS 同一頁附了去年同季的比較表，版面與本期表一模一樣，
  只有 column 第一層的「民國 X 年第 N 季」能區分。`select_equity_changes_period_table()`
  以該標籤比對，**比對不到就回傳空表，不做退而求其次的 fallback**——抓錯會把去年的數字記成今年，
  且因主鍵相同會安靜地佔住正確資料的位置。
- **全形／半形括號正規化**：同一項目跨年度會擺盪（2013 年「權益增加（減少）總額」、
  2024 年「權益增加(減少)總額」），一律過 `DataUtils.standardize_column_name()`，
  否則同一張表裡會變成兩個項目。

---

## 四、爬取節流

`equity_change` 是 fs 裡唯一逐檔查詢的報表，一個年季要打兩千多次請求，
節流直接決定回補要跑幾天。**常數為權益變動表專用**，與其他三張報表不共用——
那三張是「全市場一次查完」，整段回補才幾十次請求，沒有放寬的必要。

| 常數（`FinancialStatementUpdater`） | 現行值 | 舊值（2026-08-28 前） |
|---|---|---|
| `EQUITY_CHANGE_RANDOM_DELAY_MIN` / `_MAX` | 0.5 / 1.5 秒 | 1 / 5 秒 |
| `EQUITY_CHANGE_BATCH_SLEEP_EVERY_N_FILES` | 50 檔 | 10 檔 |
| `EQUITY_CHANGE_BATCH_SLEEP_DURATION_SECONDS` | 15 秒 | 30 秒 |
| 平均 sleep | 1.28 秒/檔 | 5.7 秒/檔 |
| 一個年季（2,086 檔） | 約 0.9 小時（推估） | 3.5 小時（實測） |

放寬的依據是 2020Q1 全市場回補連續近 4 小時 `unreachable = 0`，代表舊設定過於保守。
但**「放寬多少才會被擋」沒有實測過**，現行值是估計而非驗證過的安全上限。

⚠️ **每個年季跑完要看收尾那行 `N requested, N no data, N unreachable`**：
`unreachable` 明顯大於 0 就代表放太寬，退回中間值（1~3 秒 / 每 30 檔睡 15 秒，約 2.4 秒/檔）。

**第一批資料要等 100 檔之後才落地**（`EQUITY_CHANGE_LOAD_BATCH_SIZE`），約 3 分鐘。
啟動後前幾分鐘查 DB 是 0 列屬正常，不是失敗。

---

## 相關文件

- [ETL 入庫約定](etl-ingestion.md)——§二各 updater 對照表、§4.5「連續 N 筆都沒資料」不能當成「整批都沒資料」
- [券商分點 NO_DATA 的 metadata 語意](broker-trading-no-data.md)——與§三第 3 點同源的問題
- [資料覆蓋範圍](../exchanges/data_coverage.md)——各資料來源的時間涵蓋與已知限制
- [指令教學](../commands/command-usage.md)——`update_db --target fs` 的用法
