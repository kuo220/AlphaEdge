# 權益變動表 IFRS 導流訊息辨識

## Abstract（摘要）

- **背景／問題**：`equity_change` 的歷史回補已於 2026-09-11 完成（2013Q1~2026Q2 共 54 個年季零缺口），
  但進度檔留下 **19 筆 `incomplete`**（6 檔公司的 2013~2014 年季）。2026-09-12 查明原因：
  MOPS 對這幾檔的 2013~2014 年季回 HTTP 200 並明示
  「公開發行公司103年(含)以前之財報資料請至採IFRSs前之 個別報表 或 合併報表 查詢！」，
  頁面裡沒有任何 `<table>`。`_request_equity_changes()` 只認得「查無資料」與 `Unreachable Server`
  兩個 marker，遇到這句話會走 `pd.read_html` 的 `ValueError` 分支、回 `None`（待重試）。
  **判斷本身是保守而正確的**（解不出表格就不敢當成沒資料），但這 19 筆永遠不會成功，
  於是每次跑整段回補都會空打 19 次請求。
- **目標**：爬蟲辨識這個 IFRS 導流訊息，把它歸成「確認無資料」，讓進度檔記下來、之後不再重打。
- **範圍界線**：**只改分類，不改抓取範圍**。不去「採 IFRSs 前」的另一組端點補那 19 筆資料
  ——那需要新端點、新版面、新 cleaner，是另一件事（目前不在任何計畫內，已記進
  [權益變動表](../docs/pipeline/equity-change.md) §三第 5 點）。
  也不動其他三張報表的分類邏輯。
- **驗收標準**：跑一次整段回補的 resume，2013Q2／2013Q4／2014Q2／2014Q4 四季顯示
  `0 requested`（而非各打 4~6 次），進度檔 `incomplete` 為空、`no_data` 增加 19 筆；
  單元測試覆蓋「導流訊息 → 查無資料」與「解不出表格但不是導流訊息 → 仍回 `None`」兩條路徑。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 新增 marker 並在 `_request_equity_changes()` 分類 | `core/pipeline/tw/crawlers/financial_statement_crawler.py` | 新增單元測試兩條路徑皆通過 | ⬜ | marker 字串見 S1；**不要用整句比對**，站方文案可能微調 |
| S2 | 實跑 resume 驗證 19 筆收斂 | 進度檔 `equity_change_season_progress.json` | 四季 `0 requested`；`incomplete` 為空 | ⬜ | 相依 S1。**開跑前確認沒有別的 MOPS 爬蟲在跑** |

## 步驟詳述

### S1. 新增 marker 並在 `_request_equity_changes()` 分類 ⬜

- **目的**：讓「站方明示資料在別的端點」跟「版面改了解不出表格」分家——前者是永久狀態，
  後者才需要人來看。
- **做法**：在 `FinancialStatementCrawler` 的 class 常數區（約 L36~L41，緊接
  `EQUITY_CHANGE_NO_DATA_MARKER` 之後）新增一個常數，並在
  `_request_equity_changes()` 的「查無資料」判斷之後、`EQUITY_CHANGE_UNREACHABLE_MARKER`
  判斷之前插入一段分類：

  ```python
  # 站方對「採 IFRSs 前」（民國 103 年含以前）的年季只給導流訊息，不給報表。
  # 用片段比對而非整句，站方文案微調時不會失效
  EQUITY_CHANGE_PRE_IFRS_MARKER: str = "採IFRSs前"
  ```

  ```python
  if self.EQUITY_CHANGE_PRE_IFRS_MARKER in res.text:
      logger.debug(
          f"Pre-IFRS equity changes not served here: {stock_id} {year}Q{season}"
      )
      return []
  ```

  **回 `[]` 而不是 `None`** 是這一步的全部重點：`[]` 代表「確認沒有資料」，
  會被 `season_planner` 寫進 `no_data` 永久名單；`None` 是「待重試」，就是現在空轉的原因。
  三態語意見 `BaseDataCrawler` 的說明。
- **產出**：`core/pipeline/tw/crawlers/financial_statement_crawler.py`，
  以及 `tests/test_financial_statement_crawler_pre_ifrs.py`（或加進既有的權益變動表測試檔）。
- **驗證方式**：兩條路徑各一條測試，用假的 `Response` 餵文字，不連網路：

  | 輸入 | 期望回傳 | 為什麼要測 |
  |------|----------|------------|
  | 含「採IFRSs前」的頁面 | `[]` | 本步驟的主要行為 |
  | 不含任何 marker 且解不出表格 | `None` | **防迴歸**：不能因為新增分類就把「版面改了」也吞成沒資料 |
  | 含「查無資料」 | `[]` | 既有行為不得改變 |

- **相依**：無。

### S2. 實跑 resume 驗證 19 筆收斂 ⬜

- **目的**：確認分類真的讓進度檔記下來，而不只是單元測試過。
- **做法**：跑一次整段回補的 resume（54 個年季已全部入庫，所以除了那 19 筆之外都會
  `already complete, skipped`，零次請求）：

  ```bash
  .venv/bin/python -c "
  import datetime
  from core.config import DEFAULT_START_YEAR
  from core.pipeline.tw.updaters.financial_statement_updater import (
      FinancialStatementUpdater,
  )
  FinancialStatementUpdater().update_equity_changes(
      start_year=DEFAULT_START_YEAR,
      end_year=datetime.date.today().year,
      start_season=1,
      end_season=4,
  )
  "
  ```

  第一次跑會打那 19 次請求並把它們記進 `no_data`；**第二次跑才是驗收**，
  那四季應該顯示 `0 requested`。
- **產出**：`data/downloads/tw_stock/meta/no_data/equity_change_season_progress.json`。
- **驗證方式**：

  ```python
  json.loads(Path(".../equity_change_season_progress.json").read_text())["incomplete"]
  # 應為 {}
  ```

  `no_data` 總筆數應由 17,167 增加到 17,186。
- **相依**：S1。**開跑前確認沒有別的 MOPS 爬蟲在跑**（`pgrep -f financial_statement`）
  ——MOPS 按 IP 節流，2026-09-05 實測過雙爬蟲會讓回補幾乎全逾時。
  本步驟只有 19 次請求，幾秒內結束。

---

## 關聯與狀態

- **優先級**：P3（純效率問題，無資料正確性風險——每輪回補浪費 19 次請求、約 24 秒）
- **進度**：0 / 2 項
- **相關程式**：`core/pipeline/tw/crawlers/financial_statement_crawler.py`
  （`_request_equity_changes()`、`EQUITY_CHANGE_*` 常數）、`core/pipeline/shared/season_planner.py`
- **相關文件**：
  - [權益變動表](../docs/pipeline/equity-change.md)——§三第 5、6 點記載這 19 筆的成因與影響；
    §二是回補完成後的涵蓋範圍
  - [ETL 入庫約定](../docs/pipeline/etl-ingestion.md)——三態語意（`None`／`[]`／非空 list）的由來
- **歷史脈絡**：本文件是 `權益變動表回補續跑.md` S2 判定後開出的唯一程式面後續，
  該文件與 `權益變動表ETL補完.md` 已於 2026-09-13 結案移出 `backlog/`。
  **查核腳本的兩個坑**（重驗時會踩到）：`RequestUtils.fetch()` 預設 `method="get"`，
  只傳 `data=` 不指定 POST 等於對 ajax 端點發帶 body 的 GET，MOPS 不回應、一路逾時；
  手寫 payload 必須清掉 `TYPEK`，否則會收到誤導訊息「該 XXXX 公開發行公司不繼續公開發行！」。
  要重驗一律借 `crawl_equity_changes()` 自己組的 payload。
- **結案方式**：S2 完成後**整份刪除**並移除 `index.md` 對應列；
  同時把 [權益變動表](../docs/pipeline/equity-change.md) §三第 6 點改寫成「已解決」。
