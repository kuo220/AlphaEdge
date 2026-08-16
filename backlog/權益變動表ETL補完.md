# 權益變動表 ETL 補完

## Abstract（摘要）

- **背景／問題**：財報 ETL 的權益變動表（Statement of Changes in Equity）做到一半即遺留：`FinancialStatementCrawler.crawl_equity_changes()` 已完整實作（MOPS `ajax_t164sb06`，逐檔查詢），`FinancialStatementUpdater.update_equity_changes()` 殼也在；但 `FinancialStatementCleaner.clean_equity_changes()` 只有 `# TODO: 有空再做` ＋ `pass`，loader 建表時跳過 `EQUITY_CHANGE`，`update()` 主流程不呼叫，DB 無 `equity_change` 表。更嚴重的是 **updater 以參數呼叫 cleaner（`clean_equity_changes(...)`，updater L432），但 cleaner 簽名不收參數**——即使把 `update()` 接上也會直接 `TypeError`，證明這條鏈從未跑通過。
- **目標**：補完 cleaner／loader／updater 三件套，`tasks/update_db.py --target fs` 一併更新 `equity_change` 表，2013Q1 起歷史資料可回補。
- **範圍界線**：不動既有三張財報表（balance_sheet／comprehensive_income／cash_flow）的流程；不新增獨立的 `--target`（沿用 `fs`）；**替代方案**——若確認策略研究用不到權益變動表，改走「刪殼」：刪除 cleaner／loader／updater 的空殼與 TODO、`EQUITY_CHANGE_TABLE_NAME` 常數與 `FinancialStatementType.EQUITY_CHANGE` 相關分支，crawler 可保留或一併刪除。動工前先做 S1 的需求決策。
- **驗收標準**：（補完路線）`equity_change` 表存在且有 2013Q1 起資料，`update()` 每季可增量更新；（刪殼路線）`grep -ri "equity" core/pipeline/` 無殘留 TODO 與死碼。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 需求決策：補完或刪殼 | 本文件（記錄決策） | 決策與理由寫入本文件 | ⬜ | 逐檔爬取的成本是決策關鍵，見 S1 |
| S2 | cleaner：實作 `clean_equity_changes()` | `core/pipeline/cleaners/financial_statement_cleaner.py` | 單元測試（不連網、不連 DB），比照 `tests/test_stock_margin_cleaner.py` | ⬜ | 相依 S1（走補完路線才做） |
| S3 | loader：建表與欄位定義 | `core/pipeline/loaders/financial_statement_loader.py` | `create_missing_tables()` 後 `equity_change` 表存在 | ⬜ | 相依 S2 |
| S4 | updater 接線與簽名修正 | `core/pipeline/updaters/financial_statement_updater.py` | `--target fs` 跑通、增量更新正確 | ⬜ | 相依 S2、S3 |
| S5 | 歷史回補與驗證 | DB `equity_change` 表 | 2013Q1 起資料入庫，抽樣與 MOPS 原站比對 | ⬜ | 相依 S4；注意逐檔爬取量極大 |

## 步驟詳述

### S1. 需求決策：補完或刪殼 ⬜

- **目的**：權益變動表與其他三張財報不同，MOPS 端點（`ajax_t164sb06`）是**逐檔查詢**（`crawl_equity_changes(year, season, stock_id)`），全市場 × 全季回補的請求量是其他報表的千倍量級。先確認是否有策略研究需求，再決定投入。
- **做法**：檢視現有與規劃中的策略是否用到權益變動表欄位（庫藏股變動、資本公積轉增資等）；若無，走 Abstract 的「刪殼」替代方案並直接結案本文件。
- **產出**：決策與理由記錄在本步驟章節末尾。
- **驗證方式**：人工——決策已記錄且後續步驟依決策調整。
- **相依**：無。

### S2. cleaner：實作 `clean_equity_changes()` ⬜

- **目的**：`financial_statement_cleaner.py` L318~L326 目前是 `pass` 空殼，是整條鏈的第一個缺口。
- **做法**：比照 `clean_cash_flow()` 的既有模式——欄位名清洗（`clean_report_column_names()`）、`equity_change_col_map` 對照、輸出 CSV 至 `equity_change_dir`；簽名須與 updater 的呼叫（帶入 crawl 結果與 year/season）對齊，這是既有 `TypeError` 缺陷的修正點。注意權益變動表是**二維表**（權益項目 × 變動原因），攤平方式需在實作時定案並記錄於此。
- **產出**：`core/pipeline/cleaners/financial_statement_cleaner.py`、`equity_change_cleaned_columns.json`。
- **驗證方式**：新增 cleaner 單元測試（離線、用固定 fixture），欄位數與攤平規則有明確斷言。
- **相依**：S1（決策為補完）。

### S3. loader：建表與欄位定義 ⬜

- **目的**：`financial_statement_loader.py` L157~L158 的 `create_missing_tables()` 目前跳過 `EQUITY_CHANGE`（`continue  # TODO: 實作後移除`）。
- **做法**：移除該 skip 分支；確認 `equity_change_cleaned_cols_path` 指向 S2 產出的欄位定義；Primary Key 比照其他財報表 `(year, season, stock_id, 公司名稱)`，若 S2 攤平後多出「權益項目」維度則一併納入 PK。
- **產出**：`core/pipeline/loaders/financial_statement_loader.py`。
- **驗證方式**：`create_missing_tables()` 後 `PRAGMA table_info('equity_change')` 非空。
- **相依**：S2。

### S4. updater 接線與簽名修正 ⬜

- **目的**：`financial_statement_updater.py` L153~L154 的 `update()` 目前不呼叫 `update_equity_changes()`（`# TODO: Update Equity Changes`）；L405 註明「cleaner & loader 還未完成」。
- **做法**：修正 `update_equity_changes()` 內對 cleaner 的呼叫簽名（對齊 S2）；決定逐檔爬取的股票清單來源（建議 `taiwan_stock_info`）；在 `update()` 接上呼叫並移除兩處 TODO。
- **產出**：`core/pipeline/updaters/financial_statement_updater.py`。
- **驗證方式**：以單季、少量股票在暫存 DB 跑通 `--target fs`；resume（`get_actual_update_start_year_season`）回傳正確的下一季。
- **相依**：S2、S3。

### S5. 歷史回補與驗證 ⬜

- **目的**：補齊 2013Q1 起的歷史資料。
- **做法**：執行回補並抽樣比對 MOPS 原站。**注意**：逐檔 × 逐季的請求量極大（約 2,000 檔 × 50+ 季），須估算耗時與反爬節流；回補的中斷風險與入庫時序約定見 [ETL 入庫約定](../docs/pipeline/etl-ingestion.md)；分批入庫已於 2026-08-16 完成，本步驟直接受益。
- **產出**：DB `equity_change` 表資料。
- **驗證方式**：`SELECT COUNT(*) FROM equity_change` 涵蓋 2013Q1 起；抽樣 10 檔 × 3 季與原站逐格比對。
- **相依**：S4。

---

## 關聯與狀態

- **優先級**：P3（無現行策略需求，先決策再投入）
- **進度**：0 / 5 項
- **相關程式**：`core/pipeline/crawlers/financial_statement_crawler.py`（已完成，L223~）、`core/pipeline/cleaners/financial_statement_cleaner.py`、`core/pipeline/loaders/financial_statement_loader.py`、`core/pipeline/updaters/financial_statement_updater.py`、`core/config.py`（`EQUITY_CHANGE_TABLE_NAME`）
- **相關文件**：[ETL 入庫約定](../docs/pipeline/etl-ingestion.md)（新增 updater 時的檢查表；歷史回補的分批與冪等前置已完成）
