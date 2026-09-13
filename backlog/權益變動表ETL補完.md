# 權益變動表 ETL 補完

> **📌 2026-08-29：長期參考內容已抽出至 [`docs/pipeline/equity-change.md`](../docs/pipeline/equity-change.md)。**
> 該文件涵蓋資料形狀（長表 schema、主鍵、單位）、涵蓋範圍、四項已知限制與爬取節流；
> 入庫語意早已在 [ETL 入庫約定](../docs/pipeline/etl-ingestion.md)。
> **本文件剩下的是實作過程紀錄與 S5 的執行追蹤——S5 跑完即可整份刪除，不需要再搬任何內容出去**
> （見 [`manage-backlog` skill §5](../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理)）。

## Abstract（摘要）

- **背景／問題**：財報 ETL 的權益變動表（Statement of Changes in Equity）做到一半即遺留：`FinancialStatementCrawler.crawl_equity_changes()` 已完整實作（MOPS `ajax_t164sb06`，逐檔查詢），`FinancialStatementUpdater.update_equity_changes()` 殼也在；但 `FinancialStatementCleaner.clean_equity_changes()` 只有 `# TODO: 有空再做` ＋ `pass`，loader 建表時跳過 `EQUITY_CHANGE`，`update()` 主流程不呼叫，DB 無 `equity_change` 表。更嚴重的是 **updater 以參數呼叫 cleaner（`clean_equity_changes(...)`，updater L432），但 cleaner 簽名不收參數**——即使把 `update()` 接上也會直接 `TypeError`，證明這條鏈從未跑通過。
- **目標**：補完 cleaner／loader／updater 三件套，`tasks/update_db.py --target fs` 一併更新 `equity_change` 表，2013Q1 起歷史資料可回補。
- **範圍界線**：不動既有三張財報表（balance_sheet／comprehensive_income／cash_flow）的流程；不新增獨立的 `--target`（沿用 `fs`）；**替代方案**——若確認策略研究用不到權益變動表，改走「刪殼」：刪除 cleaner／loader／updater 的空殼與 TODO、`EQUITY_CHANGE_TABLE_NAME` 常數與 `FinancialStatementType.EQUITY_CHANGE` 相關分支，crawler 可保留或一併刪除。動工前先做 S1 的需求決策。
- **驗收標準**：（補完路線）`equity_change` 表存在且有 2013Q1 起資料，`update()` 每季可增量更新；（刪殼路線）`grep -ri "equity" core/pipeline/` 無殘留 TODO 與死碼。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 需求決策：補完或刪殼 | 本文件（記錄決策） | 決策與理由寫入本文件 | ✅ | 2026-08-22 由使用者決定走**補完路線** |
| S2 | cleaner：實作 `clean_equity_changes()` | `core/pipeline/tw/cleaners/financial_statement_cleaner.py` | 單元測試（不連網、不連 DB），比照 `tests/test_stock_margin_cleaner.py` | ✅ | 攤平成**長表**（見 S2）；`tests/test_financial_statement_cleaner_equity_change.py` 8 項通過 |
| S3 | loader：建表與欄位定義 | `core/pipeline/tw/loaders/financial_statement_loader.py` | `create_missing_tables()` 後 `equity_change` 表存在 | ✅ | PK 偏離原規格（不含 `公司名稱`、改含攤平後的兩個維度），見 S3 |
| S4 | updater 接線與簽名修正 | `core/pipeline/tw/updaters/financial_statement_updater.py` | `--target fs` 跑通、增量更新正確 | ✅ | resume 改為**逐檔**而非逐年季，理由見 S4 |
| S5 | 歷史回補與驗證 | DB `equity_change` 表 | 2013Q1 起資料入庫，抽樣與 MOPS 原站比對 | 🔄 | **執行追蹤已移交 [權益變動表回補續跑.md](權益變動表回補續跑.md)**（2026-09-05）；以下為移交前的紀錄。 2020Q1 完成（2026-08-22）。**2026-09-04 S6／S7 完成後 2020Q2 重跑驗證通過**（1,404 檔 / 0 cleaned empty / 0 unreachable），同日 10:12 起跑整段回補，11:32 因缺 `html5lib` 中止（資料零遺失）、修正後 **11:38 重啟**（估約 60~66 小時） |
| S6 | 修正非 Q1 的期別標籤比對 | `core/pipeline/tw/cleaners/financial_statement_cleaner.py` | 2020 四季各抽一檔，四季都選得到本期表且不誤取去年同期 | ✅ | 2026-09-04 完成；2330 逐季實查四季全中，統計行補上 `cleaned empty`（見 S6） |
| S7 | 中斷韌性：訊號收工、進度存檔、磁碟對帳 | `core/pipeline/shared/graceful_stop.py`、`core/pipeline/shared/season_planner.py`、`financial_statement_updater.py` | 離線 32 項測試 ＋ 實際送 SIGINT 的實測 | ✅ | 2026-09-04 完成；中斷不再丟掉手上那批，「查無資料」跨行程記住（見 S7） |

## 步驟詳述

### S1. 需求決策：補完或刪殼 ✅

- **目的**：權益變動表與其他三張財報不同，MOPS 端點（`ajax_t164sb06`）是**逐檔查詢**（`crawl_equity_changes(year, season, stock_id)`），全市場 × 全季回補的請求量是其他報表的千倍量級。先確認是否有策略研究需求，再決定投入。
- **做法**：檢視現有與規劃中的策略是否用到權益變動表欄位（庫藏股變動、資本公積轉增資等）；若無，走 Abstract 的「刪殼」替代方案並直接結案本文件。
- **產出**：決策與理由記錄在本步驟章節末尾。
- **驗證方式**：人工——決策已記錄且後續步驟依決策調整。
- **相依**：無。

> **✅ 決策紀錄（2026-08-22）**
> 使用者決定走**補完路線**。理由：`URLManager` 已備妥 `EQUITY_CHANGE_STATEMENT_URL`、crawler 也已完整實作，缺口只在 cleaner／loader／updater 三層；而現行的半成品狀態本身就是負債（updater 以參數呼叫不收參數的 cleaner，一旦接上主流程即 `TypeError`）。
> **逐檔查詢的成本沒有消失，只是被移到 S5**：程式面（S2~S4）完成後，日常增量更新一季約兩千次請求；一次性的歷史回補則以十萬次計，見 S5。

### S2. cleaner：實作 `clean_equity_changes()` ✅

- **目的**：`financial_statement_cleaner.py` L318~L326 目前是 `pass` 空殼，是整條鏈的第一個缺口。
- **做法**：比照 `clean_cash_flow()` 的既有模式——欄位名清洗（`clean_report_column_names()`）、`equity_change_col_map` 對照、輸出 CSV 至 `equity_change_dir`；簽名須與 updater 的呼叫（帶入 crawl 結果與 year/season）對齊，這是既有 `TypeError` 缺陷的修正點。注意權益變動表是**二維表**（權益項目 × 變動原因），攤平方式需在實作時定案並記錄於此。
- **產出**：`core/pipeline/tw/cleaners/financial_statement_cleaner.py`、`equity_change_cleaned_columns.json`。
- **驗證方式**：新增 cleaner 單元測試（離線、用固定 fixture），欄位數與攤平規則有明確斷言。
- **相依**：S1（決策為補完）。

> **✅ 完成紀錄（2026-08-22）**
>
> **攤平方式定案：長表（one row per 權益項目 × 變動原因）**
>
> | 欄位 | 說明 |
> |------|------|
> | `year`、`season`、`stock_id` | 查詢維度 |
> | `權益項目` | 來源表的**欄**（普通股股本、資本公積、保留盈餘合計、庫藏股票…） |
> | `變動原因` | 來源表的**列**（期初餘額、本期淨利（淨損）、普通股現金股利、期末餘額…） |
> | `金額` | 單位：新台幣仟元 |
>
> **為什麼不用寬表**：各公司的權益項目集合差異極大——實測 2024Q1，2330 台積電 15 項、2891 中信金 17 項（多出「特別股股本」「採用覆蓋法重分類之其他綜合損益」）、6488 環球晶 14 項。寬表得存全市場的欄位聯集，且每遇到一個新項目就要改 schema；長表的欄位固定六個，不隨資料成長。
>
> **實作要點**（都是實測撞到才知道的）：
> 1. **真表頭在內容第一列**：`pd.read_html` 讀到的 column 名稱是無意義的「單位：新台幣仟元」「單位：新台幣仟元.1」…，`會計項目`／`普通股股本`／… 在 `df.iloc[0]`。
> 2. **同一頁附了去年同季的比較表**，版面與本期表一模一樣，只有 column 第一層的「民國 X 年第 N 季」能區分。由 `select_equity_changes_period_table()` 以該標籤比對；**比對不到就回傳空表，不做退而求其次的 fallback**——抓錯會把去年的數字記成今年，且因主鍵相同會安靜地佔住正確資料的位置。
> 3. **右側固定帶著一串表頭為 NaN 的空白欄**（來源表宣告 33~37 欄，實際只用 14~19 欄），依表頭是否為空來丟。
> 4. **空白儲存格不入表**（例如台積電沒有庫藏股票），長表只留實際有金額的組合，不存整排 NULL。
> 5. **全形／半形括號正規化**：同一項目跨年度會擺盪（2013 年「權益增加（減少）總額」、2024 年「權益增加(減少)總額」），一律過 `DataUtils.standardize_column_name()`，否則同一張表裡會變成兩個項目。
> 6. **CSV 以「批」為單位落地**（`save_equity_changes()`，檔名 `equity_change_{year}Q{season}_{batch:04d}.csv`）。逐檔一個 CSV 會產生十萬個小檔，而 loader 每次都掃整個目錄。
>
> **偏離原規格**：未使用 `equity_change_col_map` 與 `clean_report_column_names()`。長表的欄位是攤平規則決定的固定六欄，不是從來源表頭蒐集而來，故 `equity_change_all_columns.json` 與 `equity_change_column_map.json` 兩份 metadata 不需要存在；`load_all_column_names()` / `load_column_maps()` 已把 `EQUITY_CHANGE` 移出對照表，否則每次建構 cleaner 都會警告缺檔。`equity_change_cleaned_columns.json` 仍照常產出，讓 loader 沿用相同的建表流程。
>
> **驗證**：`tests/test_financial_statement_cleaner_equity_change.py` 8 項全數通過（不連網路、不連 DB，CSV 導向 `tmp_path`）。

### S3. loader：建表與欄位定義 ✅

- **目的**：`financial_statement_loader.py` L157~L158 的 `create_missing_tables()` 目前跳過 `EQUITY_CHANGE`（`continue  # TODO: 實作後移除`）。
- **做法**：移除該 skip 分支；確認 `equity_change_cleaned_cols_path` 指向 S2 產出的欄位定義；Primary Key 比照其他財報表 `(year, season, stock_id, 公司名稱)`，若 S2 攤平後多出「權益項目」維度則一併納入 PK。
- **產出**：`core/pipeline/tw/loaders/financial_statement_loader.py`。
- **驗證方式**：`create_missing_tables()` 後 `PRAGMA table_info('equity_change')` 非空。
- **相依**：S2。

> **✅ 完成紀錄（2026-08-22）**
> - `create_missing_tables()` 的 skip 分支已移除，改為「欄位定義 JSON 不存在才跳過並警告」——靜默跳過會讓錯誤晚到入庫階段才炸在 `no such table`，離真正的原因太遠。
> - **偏離原規格：主鍵不含 `公司名稱`**，定為 `(year, season, stock_id, 權益項目, 變動原因)`。兩個原因：① 攤平成長表後一家公司一季有數十列，不把兩個維度納入主鍵就不唯一；② **來源端點根本不回傳公司名稱**——`ajax_t164sb06` 是逐檔查詢，回傳的只有報表矩陣本身，其他三張報表的 `公司名稱` 來自全市場表格的欄位。若硬要補，只能去 `taiwan_stock_info` 查現名，那是「現在的名稱」而非「當季的名稱」，寫進主鍵反而會製造假的唯一性。
> - `create_db()` 新增 `primary_keys` 參數（預設值即原本寫死的四欄），其他三張報表行為零改變。
> - `add_to_db()` 新增 `only_files` 參數供分批入庫使用；`None` 時維持原本掃整個目錄的行為。
> - 實測建出的 schema：`year INT NOT NULL`、`season INT NOT NULL`、`stock_id TEXT NOT NULL`、`權益項目 TEXT NOT NULL`、`變動原因 TEXT NOT NULL`、`金額 REAL`。

### S4. updater 接線與簽名修正 ✅

- **目的**：`financial_statement_updater.py` L153~L154 的 `update()` 目前不呼叫 `update_equity_changes()`（`# TODO: Update Equity Changes`）；L405 註明「cleaner & loader 還未完成」。
- **做法**：修正 `update_equity_changes()` 內對 cleaner 的呼叫簽名（對齊 S2）；決定逐檔爬取的股票清單來源（建議 `taiwan_stock_info`）；在 `update()` 接上呼叫並移除兩處 TODO。
- **產出**：`core/pipeline/tw/updaters/financial_statement_updater.py`。
- **驗證方式**：以單季、少量股票在暫存 DB 跑通 `--target fs`；resume（`get_actual_update_start_year_season`）回傳正確的下一季。
- **相依**：S2、S3。

> **✅ 完成紀錄（2026-08-22）**
> - **簽名修正**：cleaner 呼叫改為 `clean_equity_changes(df_list, year, season, stock_id)`，原本的 `TypeError` 缺陷解除。
> - **偏離原規格：resume 不用 `get_actual_update_start_year_season()`**。那個函式以「表內最新年季 +1」為準，對逐檔查詢是錯的——一個年季爬到一半中斷時，該年季已經有資料，會被判定為已完成而**整季跳過**，沒爬到的公司永遠補不回來。改為 `get_crawled_stock_ids(year, season)` 逐年季查出已入庫的 `stock_id`，只補差集。這也讓「中斷 → 重跑」的成本等於已完成的部分，而非整季重來。
> - **股票清單來源**：`taiwan_stock_info`，條件為 `type IN ('twse','tpex')`、排除 ETF、代號為 4 碼數字，實測 **2,086 檔**。**已知限制**：該表是「現在的」上市櫃清單，歷史回補會漏掉已下市的公司，也不含興櫃。
> - **分批入庫**：每 100 檔寫一個 CSV 並立即入庫（`EQUITY_CHANGE_LOAD_BATCH_SIZE`），符合 [ETL 入庫約定](../docs/pipeline/etl-ingestion.md) §4.1——中斷最多只損失最後一批。
> - **尚未申報的年季會早退**：`is_season_filed()` 試探三檔 2013 年前就上市的權值股（`EQUITY_CHANGE_PROBE_STOCK_IDS`＝2330／2317／1101），全部查無資料才判定該季未申報並跳過。沒有這道門檻，每次日常更新都要為當季白打兩千次請求。⚠️ **初版用的是「連續 30 檔查無資料」，實際造成 323 檔靜默漏抓，已於 2026-08-22 修正**——事故經過見 S5 與 [ETL 入庫約定 §4.5](../docs/pipeline/etl-ingestion.md)。
> - **crawler 一併修的三件事**（都是這次實測才發現的）：
>   1. **改用 `step=2`**。原本的 `step=1` 對金控這類多實體公司只回子公司選單頁而非報表——實測 2891 中信金拿回的是一張 38 列的子公司清單，`clean` 完會是空表且不會有任何錯誤。`step=2` 對各類公司一律直接回報表。
>   2. **`step` 與 `co_id` 用完即還原**。`Payload` 由四張報表共用，`crawl_equity_changes()` 原本把 `co_id` 設成單一股票後就不復原；其餘三張是「全市場一次查完」，被殘留的 `co_id` 縮成單一公司會靜默少資料。目前 `update()` 的呼叫順序讓這個 bug 還沒發作，但它一直都在。
>   3. **區分「查無資料」與「站方過載」**。MOPS 過載時回 HTTP 200，內容卻只有 `Unreachable Server`（實測 2603 長榮 2024Q2 就撞到），與 `查無資料！` 是兩回事。回傳語意因此定為：`None` = 暫時性失敗（就地重試 3 次仍失敗，該檔留待重跑）、`[]` = 確定沒有資料、非空 list = 正常。跑完會彙總 warning 提示有幾筆需要重跑——把暫時性失敗當成「這檔沒資料」正是 [ETL 入庫約定](../docs/pipeline/etl-ingestion.md) §4.2 記錄過的事故樣式。
> - **`update()` 已接上**，放在三張報表之後：即使這裡耗時或中斷，前三張已經入庫完成。
> - **驗證方式與實際結果**：以暫存 DB（不動正式 DB）跑 `update_equity_changes(2024, 2024, 1, 1, stock_ids=["2330", "2891", "6488"])`：
>   1. `equity_change` 表建立成功，schema 與主鍵如 S3 所列。
>   2. 入庫 476 列：2330 = 225、2891 = 153、6488 = 98。
>   3. **抽樣比對**：2330 2024Q1 的「期初餘額」15 個權益項目與 MOPS 原站表格逐格比對，mismatch = 0（普通股股本 259,320,710／保留盈餘合計 3,158,030,792／權益總額 3,483,262,847…），且台積電沒有庫藏股票的空白欄正確地未入表。
>   4. **金控可取得**：2891 的「特別股股本」有 9 列資料，證明 `step=2` 的修正生效（`step=1` 時該公司完全拿不到報表）。
>   5. **分批入庫**：刻意把批次大小調成 2，確認產出 `equity_change_2024Q1_0000.csv`、`equity_change_2024Q1_0001.csv` 兩批並各自入庫。
>   6. **Resume**：同參數第二次執行，log 顯示 `2024Q1 already complete, skipped`，耗時 0.0 秒、零次請求，列數維持 476。
>   7. **回歸**：`tests/` 全數 241 項通過（`test_tick_crawler.py`／`test_tick_updater.py` 的 4 個 error 為既有問題，在未改動的 tree 上同樣重現）。

### S5. 歷史回補與驗證 🔄

- **目的**：補齊 2013Q1 起的歷史資料。
- **做法**：執行回補並抽樣比對 MOPS 原站。**注意**：逐檔 × 逐季的請求量極大（約 2,000 檔 × 50+ 季），須估算耗時與反爬節流；回補的中斷風險與入庫時序約定見 [ETL 入庫約定](../docs/pipeline/etl-ingestion.md)；分批入庫已於 2026-08-16 完成，本步驟直接受益。
- **產出**：DB `equity_change` 表資料。
- **驗證方式**：`SELECT COUNT(*) FROM equity_change` 涵蓋 2013Q1 起；抽樣 10 檔 × 3 季與原站逐格比對。
- **相依**：S4。

> **🔄 進行中：2020Q1 已完成（2026-08-22）**
> 先跑 2020Q1 全市場試水溫，結果如下；其餘 55 個年季尚未執行。
>
> | 項目 | 實際結果 |
> |------|----------|
> | 入庫 | **230,163 列 / 1,743 檔**（目標 2,086 檔） |
> | 查無資料 | 343 檔（2020Q1 當時尚未上市），1,743 ＋ 343 = 2,086 ✅ |
> | `unreachable` | **0**（連續近 4 小時未被 MOPS 擋） |
> | 入庫失敗 | 0 |
> | 耗時 | 2:56（首輪，中途誤中止）＋ 0:56（補跑 556 檔）＝ 約 3.9 小時 |
> | 抽樣稽核 | 2330／2891／6488／9933／1101／8996 共 6 檔 **1,993 列**重爬後逐格比對，**mismatch = 0** |
>
> **⚠️ 過程中發現並修掉一個會靜默漏資料的 bug**（詳見 [ETL 入庫約定 §4.5](../docs/pipeline/etl-ingestion.md)）：
> 原本的早退條件是「連續 30 檔查無資料就判定該年季尚未申報」。首輪跑到代號 6874 附近撞上
> 一段 2020 年後才上市的連續新股，被誤判成整季未申報而中止，**代號 6874~9962 共 323 檔從未被嘗試**
> （抽驗 9933 中鼎、9945 潤泰新、9958 世紀鋼、8996 高力、7402 邦特，全部確實有資料）。
> 行程以結束碼 0 正常結束、log 無任何錯誤。根因是拿「順序」當統計樣本——股票代號是排序過的，
> 某個號段連續都是新股完全正常。這個 bug 連 resume 都會壞：重跑時 pending 清單開頭就是一串
> 無資料的公司，會在同一處再次誤判中止。
> **修法**：改為 `is_season_filed()` 試探三檔 2013 年前就上市的權值股（2330／2317／1101），
> 全部查無資料才判定未申報；該年季 DB 已有資料則直接視為已申報、連請求都不打；
> 暫時性失敗一律視為已申報繼續跑。另補上每季收尾的 `N requested, N no data, N unreachable`
> 統計行——這次正是因為缺這行，才需要事後撈 log 才發現少了 323 檔。
>
> **速率與節流（2026-08-28 已放寬）**
>
> | | 舊設定 | 現行設定 |
> |---|---|---|
> | 每檔隨機延遲 | 1~5 秒 | **0.5~1.5 秒** |
> | 每 N 檔多睡 | 10 檔 / 30 秒 | **50 檔 / 15 秒** |
> | 平均 sleep | 5.7 秒/檔 | **1.28 秒/檔** |
> | 實測含請求 | 6 秒/檔 | 約 1.6 秒/檔（推估，尚未實測） |
> | 一個年季 | 3.5 小時 | 約 0.9 小時 |
> | 剩餘 55 個年季 | 約 200 小時 | **約 50 小時** |
>
> 放寬的依據是 2020Q1 全市場回補連續近 4 小時 `unreachable = 0`，代表舊設定過於保守；
> 但**「放寬多少才會被擋」沒有實測過**，這組值是估計而非驗證過的安全上限。
> 常數改為權益變動表專用（`EQUITY_CHANGE_RANDOM_DELAY_MIN`／`_MAX`、
> `EQUITY_CHANGE_BATCH_SLEEP_EVERY_N_FILES`／`_DURATION_SECONDS`），
> 其他三張報表仍用原本的共用值——那三張是「全市場一次查完」，整段回補才幾十次請求，沒有放寬的必要。
> ⚠️ **下一個年季跑完務必看收尾那行 `N requested, N no data, N unreachable`**：
> `unreachable` 明顯大於 0 就代表放太寬，調回中間值（1~3 秒 / 每 30 檔睡 15 秒，約 2.4 秒/檔）。
>
> **第一批資料要等 100 檔之後才落地**（`EQUITY_CHANGE_LOAD_BATCH_SIZE`），約 10 分鐘。
> 啟動後前幾分鐘查 DB 是 0 列屬正常，不是失敗。
>
> ~~**每次重跑會重打「查無資料」的那些檔**（2020Q1 是 343 檔）~~
> **——已於 2026-09-04 由 S7 解決**：查無資料的公司記進
> `data/downloads/tw_stock/meta/no_data/equity_change_season_progress.json`，
> 重跑不再重打（申報期已關閉的年季才記，理由見 S7）。
> 這與 [券商分點 NO_DATA 的 metadata 語意](../docs/pipeline/broker-trading-no-data.md)
> 是同一個問題，該文件仍是選型未實作。
>
> - **執行方式**：`python -m tasks.update_db --target fs`。逐檔 resume 已就緒，中斷後重跑會自動只補差集，不需要手動記錄進度。
>   **中斷方式（2026-09-04 起）**：直接 Ctrl+C 或 `kill <pid>`（SIGTERM）即可——手上那批會先入庫、
>   進度會存檔、統計行會印完才離開；急著離開就再按一次 Ctrl+C（那時未入庫的那批會遺失）。
> - **要分段跑**就直接呼叫 `FinancialStatementUpdater().update_equity_changes(start_year, end_year, start_season, end_season)` 指定較窄的年季區間；`--target fs` 走的是 `DEFAULT_START_YEAR` ~ 今年、Q1~Q4 的完整區間。
> - **已知限制**（回補完成後仍會存在，寫在這裡免得事後被當成 bug）：
>   1. 股票清單取自 `taiwan_stock_info` 的**現況**，已下市公司的歷史權益變動表不會被補到。
>   2. 不含興櫃（`emerging`）。
>   3. 站方過載造成的暫時性失敗會在 log 尾端彙總（`N requests unreachable after retries`），重跑即可補上，但**必須真的去看那行 log**。

> **🔄 2026-09-03 21:59：2020Q2 節流驗證梯次起跑**
>
> **為什麼先跑單季而不是直接開 54 季**：2026-08-28 放寬的節流（0.5~1.5 秒/檔、每 50 檔睡 15 秒）
> 至今**沒有實測過**，上方表格自己標了「推估，尚未實測」。直接開整段回補，若放太寬會在
> 幾小時後才以一整片 `unreachable` 呈現，而那些檔在 DB 裡不留任何列，與「還沒爬」無法區分。
> 故先跑一季，看收尾的 `N requested, N no data, N unreachable` 再決定要不要調回中間值。
>
> - 範圍：`update_equity_changes(2020, 2020, 2, 2)`，`is_season_filed()` 探測通過，
>   **2,087 檔 pending**（DB 內該季 0 列）。
> - 開跑前確認：`tests/test_financial_statement_cleaner_equity_change.py` 11 項全綠；
>   無其他程序寫 `tw_stock.db`（同時在跑的期貨行情回補寫的是 `tw_futures.db`，不衝突）。
> - **今日的 F-054 修正正好是本步驟的前提**：`update_equity_changes()` 原本用
>   `years × seasons` 笛卡兒積，跨年季區間（例如 2013Q1~2026Q2）會整季整季漏掉且無錯誤；
>   已於 `05e55f5` 改用 `TimeUtils.generate_year_period_range()`，實測 2013Q1~2026Q2 得 54 個年季。
>   **在那之前，S5 的整段回補跑下去會是錯的。**
> - 下一步：本季跑完看統計行 → 決定節流值 → 再開整段（剩 52 季，依現行速率估約 47 小時）。

> **⛔ 2026-09-03 23:27：2020Q2 梯次結束——節流過關，但入庫 0 列**
>
> | 項目 | 結果 |
> |------|------|
> | 統計行 | `2020Q2 done: 2087 requested, 244 no data, 0 unreachable` |
> | 耗時 | 1 小時 28 分（2.5 秒/檔，比推估的 1.6 秒慢，但仍是舊設定的 2.4 倍快） |
> | 結束碼 | 0 |
> | **實際入庫** | **0 列**（DB 內 `equity_change` 仍只有 2020Q1） |
>
> **節流部分是通過的**：2,087 次請求連續 1.5 小時 `unreachable = 0`，
> 0.5~1.5 秒/檔 ＋ 每 50 檔睡 15 秒這組值可以維持，不需要調回中間值。
>
> **但 1,843 檔有資料的公司全部清洗成空表**，log 裡是 3,689 條
> `No equity changes table matched: XXXX 2020Q2` ＋ `Cleaned equity changes dataframe empty`。
> 根因見 S6。
>
> ⚠️ **這次跑掉的 1.5 小時是全額損失**：查無資料的公司不留列、清洗成空的公司也不留列，
> 兩者在 resume 眼中都是「還沒爬」，所以 S6 修好之後 2020Q2 要整季重跑。
>
> ⚠️ **而且它看起來完全像成功**：統計行三個數字都正常、結束碼 0、沒有任何 ERROR。
> 統計行只數「請求」層的結果，不數「清洗後有幾檔真的產出資料」——
> 這正是 [ETL失敗語意與缺口回補](ETL失敗語意與缺口回補.md) 在收斂的同一類問題，
> 建議 S6 一併把 `cleaned_empty` 加進統計行。

> **🔄 2026-09-04 10:12：整段回補起跑（S6／S7 完成後）**
>
> **先重跑 2020Q2 驗證 S6**（10:12 主動以 SIGTERM 收工，因為要換成整段回補；未跑完的部分由整段回補接手）：
>
> | 項目 | 結果 |
> |------|------|
> | 統計行 | `1404 requested / 1305 ok / 99 no data / 0 unreachable / **0 cleaned empty**` |
> | 入庫 | 1,305 檔 / 214,614 列（＝ `ok` 數，收工時手上那批完整落地、零遺失） |
> | 進度檔 | `no_data: {"2020Q2": 99}`、`incomplete: {}` |
> | 速率 | 約 2.1 秒/檔（一個年季約 1.2 小時） |
>
> 2026-09-03 同一季跑出來是 2,087 檔全數清成空表、入庫 0 列；**S6 修正後 1,305 檔全部清出資料、`cleaned empty` 為 0**。
> 這也是 S7 的第二次實地驗證——這次是全市場規模，SIGTERM 後手上那批照樣完整入庫。
>
> - **範圍**：`update_equity_changes(2013, 2026, 1, 4)`＝56 個年季（2026Q3／Q4 會由 `is_season_filed()` 早退，各花 3 次試探）。
> - **預估**：約 113,700 次請求 × 2.1 秒 ≈ **60~66 小時**。
> - **已完成的年季不重打**：2020Q1（1,743 檔）與 2020Q2（1,305 檔）只會補各自的差集；
>   2020Q1 的 343 檔查無資料因為早於進度檔機制，會被重問一次並就此記入永久名單。
> - **中斷方式**：`kill <pid>` 或 Ctrl+C，手上那批會先入庫、進度存檔、印完統計行才離開；重跑不需任何參數。
> - **要看的那行**：每季收尾的
>   `N requested / N ok / N no data / N unreachable / N cleaned empty`——
>   `unreachable` 明顯大於 0 代表節流放太寬，`cleaned empty` 大於 0 代表版面又變了（程式要修，重跑沒用）。

> **⛔ → 🔄 2026-09-04 11:32：首次整段回補炸在缺套件，修好後 11:38 重啟**
>
> 跑完 2013Q1（`2087 requested / 1443 ok / 644 no data / 0 unreachable / 0 cleaned empty`）
> 之後，在 2013Q2 的第 5 檔（代號 1107）以 `ImportError` 中止：
> 該頁讓 lxml 解不動，`pd.read_html` 回退到 bs4 flavor 時發現**缺 `html5lib`**。
>
> **資料零遺失**：2013Q1 的 1,443 檔與 644 筆查無資料都已落地，
> 2013Q2 已爬的 4 檔也由 S7 的收尾入庫寫進去了——例外一路往上炸，
> `finally` 仍然把手上那批寫下來。
>
> **三個修正**：
> 1. `html5lib==1.1` 補進 `requirements.txt` 並安裝（`lxml` 已在，缺的是回退用的那個）。
> 2. **爬取層加上與清洗層對等的例外隔離**（`crawl_equity_changes_one()`）。
>    S7 當時只隔離了 cleaner，crawler 的非預期例外仍會炸穿整段回補——
>    而「一頁的問題不該炸掉幾十小時的回補」跟缺哪個套件無關，是結構問題。
> 3. 隔離的代價是「環境壞了」會退化成一長串失敗，故加**連續例外斷路器**
>    （`EQUITY_CHANGE_MAX_CONSECUTIVE_ERRORS = 20`）。
>    ⚠️ 這與 §4.5 的「連續 N 檔查無資料就早退」**不是**同一種東西：
>    那裡拿「沒有資料」這種正常結果當統計樣本（錯的），這裡數的是例外——
>    例外從來不是合法的業務結果。
>
> 順帶修掉一條同源的靜默漏資料路徑：crawler 解析不出表格時原本回 `[]`
> （＝確定沒有資料），會讓該檔被寫進永久名單從此不再嘗試；
> 改回 `None`（待重試），與 `BaseDataCrawler` 的三態判準一致。
>
> **測試**：`tests/test_equity_change_interruption.py` 32 → 35 項，全套 902 項通過。
> **重啟後 resume 正確**：2013Q1 `already complete, skipped`（0 次請求），
> 2013Q2 從 2,083 檔（＝2,087 − 已爬的 4 檔）續跑。

### S6. 修正非 Q1 的期別標籤比對 ✅

- **目的**：`select_equity_changes_period_table()` 把本期表的標籤寫死為
  `f"民國{roc_year}年第{season}季"`（`financial_statement_cleaner.py:415`），
  **只有 Q1 對得上**。2026-09-03 以 2330 逐季實查 MOPS：

  | 季別 | MOPS 實際標籤 | 現行程式比對的字串 | 結果 |
  |:----:|---------------|--------------------|:----:|
  | Q1 | `民國109年第1季` | `民國109年第1季` | ✅ |
  | Q2 | `民國109年上半年度` | `民國109年第2季` | ❌ |
  | Q3 | `民國109年前3季` | `民國109年第3季` | ❌ |
  | Q4 | `民國109年度` | `民國109年第4季` | ❌ |

  2020Q1 之所以成功，純粹因為它是 Q1。**照現況跑完整段回補，54 個年季裡只有
  14 個 Q1 會有資料，其餘 40 季全部空轉**——每季白打兩千次請求、跑 1.5 小時、
  印出正常的統計行、退出碼 0、DB 零列。
- **做法**：
  1. 標籤改為依季別產生的集合，而非單一字串：
     Q1 → `第1季`、Q2 → `上半年度`、Q3 → `前3季`、Q4 → `年度`。
     **維持「比對不到就回傳 None」的既有設計**（S2 已論證過：抓錯會把去年的
     數字記成今年，且主鍵相同會安靜地佔住正確資料的位置），只是把可接受的
     標籤補齊。
  2. 同一頁的去年同期表標籤同樣是這四種形式（實查為 `民國108年上半年度` 等），
     以「民國{roc_year}年」前綴區分本期與去年，這點不變。
  3. 統計行補上 `cleaned_empty` 計數——本次事故正是因為統計行只數請求層的結果，
     才會讓「兩千次請求、零列入庫」看起來像成功。
- **產出**：`core/pipeline/tw/cleaners/financial_statement_cleaner.py`、
  `core/pipeline/tw/updaters/financial_statement_updater.py`（統計行）、
  `tests/test_financial_statement_cleaner_equity_change.py`（四季各一條 fixture）。
- **驗證方式**：以 2020 四季各抽一檔實跑，四季都選得到本期表；
  斷言選到的是本期而非去年同期（金額與 MOPS 原站比對）。
- **相依**：無（S5 反過來相依本步驟）。

> **✅ 完成紀錄（2026-09-04）**
>
> **標籤改為每季一組候選**（`FinancialStatementCleaner.EQUITY_CHANGE_PERIOD_LABELS`）：
> Q1 `民國{roc}年第1季`、Q2 `民國{roc}年上半年度`、Q3 `民國{roc}年前3季`、Q4 `民國{roc}年度`。
> 每季額外接受「第N季」的寫法，措辭若再調整不會整季空轉；
> **比對不到仍一律回 `None`**（S2 已論證過的設計沒有放寬），
> 本期與去年同期依舊只靠「民國{roc_year}年」前綴區分。
>
> **統計行補上 `cleaned empty`**：現在收尾是
> `N requested / N ok / N no data / N unreachable / N cleaned empty`，
> 且 `cleaned_empty`、`clean_failed`、`unreachable` 任一非 0 就升為 warning。
> 舊版三個數字全正常卻入庫 0 列的情況不會再看起來像成功。
> 清成空表**計為待重試**（寫進進度檔的 `incomplete`），不寫進「查無資料」永久名單——
> 那是版面問題，不是「這檔沒有資料」。
>
> **驗證（2330，2020 四季實查 MOPS）**：
>
> | 季別 | 頁面上的標籤 | 選中 | 清洗結果 | 保留盈餘合計／期末餘額 |
> |:----:|--------------|:----:|----------|------------------------|
> | Q1 | `民國109年第1季`／`民國108年第1季` | 本期 ✅ | 165 列 / 15 項 | 1,385,495,748 |
> | Q2 | `民國109年上半年度`／`民國108年上半年度` | 本期 ✅ | 210 列 / 15 項 | 1,441,491,990 |
> | Q3 | `民國109年前3季`／`民國108年前3季` | 本期 ✅ | 210 列 / 15 項 | 1,513,976,388 |
> | Q4 | `民國109年度`／`民國108年度` | 本期 ✅ | 225 列 / 15 項 | 1,588,686,081 |
>
> 保留盈餘逐季遞增，且**同一頁的去年同期表另外驗過一次**：2020Q2 頁面上
> `民國108年上半年度` 那張的期末是 1,245,575,785，與本期的 1,441,491,990 明顯不同——
> 兩張表確實被正確分開，不是碰巧選到同一張。
>
> **測試**：`tests/test_financial_statement_cleaner_equity_change.py` 由 11 項增為 19 項
> （四季各一條標籤比對、三條非 Q1 的「不得誤取去年同期」、一條「補齊標籤不得放寬年份」）。

### S7. 中斷韌性：訊號收工、進度存檔、磁碟對帳 ✅

- **目的**：S5 的整段回補是十萬次請求、數十小時，**中斷是常態不是例外**。
  但原本的四個缺口讓「中斷」的代價遠高於必要：

  | 缺口 | 代價 |
  |------|------|
  | `KeyboardInterrupt` 從當下那行炸出去 | 記憶體裡等湊滿一批的資料（最多 100 檔、約兩分鐘請求）全部作廢，且它們在表裡不留任何列，重跑無法與「還沒爬」區分 |
  | 「查無資料」不留紀錄 | 每次重跑重打（2020Q1 是 343 檔、佔 16%） |
  | CSV 已落地、入庫前被中止 | 那批的請求成本白付 |
  | cleaner 例外、單批入庫失敗會往上炸 | 一頁版面異常或一個壞批次中止剩下幾十小時 |
- **做法**：
  1. `core/pipeline/shared/graceful_stop.py`：`GracefulStop` 把 SIGINT／SIGTERM
     轉成可輪詢的旗標，第一次只記旗標、第二次立即中止；節流改用
     `stop.sleep()`（`time.sleep()` 被訊號打斷會自動續睡，見 PEP 475）。
  2. `core/pipeline/shared/season_planner.py`：`SeasonProgressStore` ＋ `SeasonPlanner`，
     把 `date_planner.py` 的差集公式換成「年季 × 個股」的單位。
  3. `update_equity_changes_season()` 以 `try/finally` 收尾入庫；
     cleaner 例外由 `clean_equity_changes_one()` 隔離在單檔；
     批次入庫失敗收集後於整段結束才拋 `DataLoadError`。
  4. `reconcile_season_csv_files()`：該年季還有待補公司時，先把磁碟上已落地的
     CSV 補進資料庫再算待補清單。
- **產出**：`core/pipeline/shared/graceful_stop.py`、`core/pipeline/shared/season_planner.py`、
  `core/pipeline/tw/updaters/financial_statement_updater.py`、
  `tests/test_equity_change_interruption.py`。
- **驗證方式**：離線測試 ＋ 實際送 SIGINT 的實地驗證。
- **相依**：S4。

> **✅ 完成紀錄（2026-09-04）**
>
> **「查無資料」寫進進度檔的前提**（`data/downloads/tw_stock/meta/no_data/equity_change_season_progress.json`）：
> **申報期已關閉才寫**。財報是逐家公司申報的，申報期間查某一檔沒有資料多半只代表
> 它還沒送件；那時就寫進永久名單，它送件之後再也不會被抓——每季申報期間跑一次
> 日常更新就會踩到。期限取各行業中最晚的那天再加 30 天寬限
> （Q1 5/30、Q2 8/31、Q3 11/29、年報次年 3/31），與逐日來源「當天不寫入 `no_data`」
> 是同一道防線。
>
> **`record_complete()` 刻意不存「已完成」集合**：哪些公司已經有資料，唯一真相是
> 資料表本身。另存一份名單就會有不一致的窗口——行程在「進度存檔了、CSV 還沒入庫」
> 之間被強制中止時，那份名單會宣稱完成而資料庫裡沒有列，那些公司從此不會再被爬。
>
> **實地驗證（2026-09-04，暫存 DB、真的打 MOPS）**：
>
> | 階段 | 動作 | 結果 |
> |------|------|------|
> | 1 | 2024Q1 六檔，開跑 7 秒後送 SIGINT | 已爬的 4 檔**全數入庫**（1,319 列），統計行 `4 requested / 4 ok`＋`依中止訊號收工，本季待補 2 檔`，結束碼 0 |
> | 2 | 同參數重跑 | 只請求 `['2891', '6488']`——已入庫的 4 檔連 `is_season_filed()` 的試探都省下；磁碟對帳報 `新寫入 0 檔、已存在跳過 1 檔` |
> | 3 | 2013Q1 查 2330／6488（6488 為 2015 年才上市） | `2 requested / 1 ok / 1 no data`，進度檔記下 `{"no_data": {"2013Q1": ["6488"]}}` |
> | 4 | 2013Q1 重跑 | **請求數 0**（`already complete, skipped`） |
>
> 過程中還撞到一次真實的 MOPS 502，`RequestUtils` 的重試層正常吸收，
> 未被誤判成「查無資料」。
>
> **測試**：`tests/test_equity_change_interruption.py` 32 項（訊號語意 5、申報期關閉判定 9、
> 進度檔 5、差集 2、中斷與續跑 3、查無資料／過載 2、磁碟對帳 2、失敗隔離 4）。
> 全套回歸 880 項通過。
>
> **偏離原規格**：本步驟不在原規劃內，是 2026-09-04 依使用者要求「處理隨時會中斷爬蟲的問題」
> 而新增。`GracefulStop` 與 `SeasonProgressStore`／`SeasonPlanner` 放在
> `core/pipeline/shared/` 而非權益變動表專屬目錄——前者對任何長時間爬取都適用，
> 後者是逐檔來源的通用形狀（目前只有權益變動表在用，語意與 `date_planner.py` 對稱）。

---

## 關聯與狀態

- **優先級**：P3（S5 歷史回補純屬執行，可隨時中斷續跑）
- **進度**：6 / 7 項 ✅（S1~S4 於 2026-08-22、S6~S7 於 2026-09-04）；S5 🔄 僅 2020Q1 有資料（230,163 列 / 1,743 檔），2020Q2 需整季重跑，其餘 52 個年季待跑。**S6 的阻塞已解除，S5 可直接開跑**
- **相關程式**：`core/pipeline/tw/crawlers/financial_statement_crawler.py`、`core/pipeline/tw/cleaners/financial_statement_cleaner.py`、`core/pipeline/tw/loaders/financial_statement_loader.py`、`core/pipeline/tw/updaters/financial_statement_updater.py`、`core/pipeline/shared/graceful_stop.py`、`core/pipeline/shared/season_planner.py`、`core/config.py`（`EQUITY_CHANGE_TABLE_NAME`）、`tests/test_financial_statement_cleaner_equity_change.py`、`tests/test_equity_change_interruption.py`
- **相關文件**：
  - [權益變動表](../docs/pipeline/equity-change.md)——2026-08-29 由本文件抽出的長期參考內容（資料形狀、涵蓋範圍、已知限制、節流）
  - [ETL 入庫約定](../docs/pipeline/etl-ingestion.md)（新增 updater 時的檢查表；§二的對照表已補上 `equity_change` 與其餘三張報表的差異）
- **結案方式**：S5 的執行追蹤已於 2026-09-05 移交 [權益變動表回補續跑.md](權益變動表回補續跑.md)；該文件的 S4 會把本文件與它一併刪除、移除 `index.md` 的兩列；該留的內容已在上述兩份 `docs/`，另需同步更新 `docs/pipeline/equity-change.md` §二的涵蓋範圍與 `docs/exchanges/data_coverage.md`
