# 全專案架構與邏輯健檢（2026-09 完成紀錄）

> **本文件是 2026-09-02 全專案架構與邏輯健檢的完成紀錄**，原為 `backlog/全專案架構與邏輯健檢.md`，
> 23 個步驟全數完成後於 2026-09-03 依 [`manage-backlog` 規範 §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理)
> 移入 `docs/`。附錄 A 的 101 條發現已分流：A／B 級轉入 `backlog/` 的四份新文件，C 級寫進各 `docs/`，
> 每一列的「處置」欄指向具體去處；其他文件以 `F-xxx` 編號連結回本檔附錄 A。


## Abstract

**背景／問題**：本專案已累積 **277 個 Python 檔、60,164 行**（不含 `.venv/`），橫跨 `core/`（ETL、資料 API、回測引擎、策略）、`tasks/`（排程入口）、`tests/`（19,272 行）、`strategy_lab/`（研究）、`frontend/`（Streamlit）、`scripts/` 與建置設定。過去一年的問題**幾乎都不是語法錯誤，而是架構與口徑層級的靜默缺陷**——入庫失敗被降級成 warning 但行程回報成功（[ETL 入庫約定 §4.2](../pipeline/etl-ingestion.md)）、清洗沒改到來源日期讓整批寫成同一個主鍵（commit `154f78c`）、固定 10% 保證金比率在跨年回測系統性偏掉 −38%~+143%（[台期貨保證金ETL.md](../../backlog/台期貨保證金ETL.md)）、以及**一支永遠不會失敗的測試**（整段包在 `try/except` 且 `return False`，見 [FinMind爬蟲清洗儲存流程優化.md](../../backlog/FinMind爬蟲清洗儲存流程優化.md) S8）。`ruff` 與 CI 只擋得住樣式與 import，擋不住這一類。

**目標**：對**整個 repository**（不只 `core/`）做一次有紀錄、可重複的架構與邏輯健檢，把「會算錯錢」「會靜默漏資料」「會讓錯誤看起來像正確」的缺陷全部找出來、分級、分流；健檢完成後，每個頂層目錄都有一份「已檢查過、發現什麼、怎麼處置」的書面結論。

**範圍界線（明確不做）**：
1. **不做重構、不改架構**。本工作只產生「發現清單」與分流結果；C 級（可維護性）發現一律只記錄不動手。
2. **不重寫樣式問題**。`ruff` 已覆蓋的規則（行寬、import 排序、型別寫法）不列入，既有 ignore 清單見 [程式碼品質](../dev/code-quality.md)。
3. **不含以下對象**：`.venv/` 與第三方套件原始碼、`data/` 內的**資料內容**（只檢查 schema 與目錄約定，不做全庫資料稽核）、`results/`／`logs/` 的既有產物內容、`frontend/` 的視覺設計與 UX、`.git` 歷史本身。
4. **不含補測試覆蓋率**。覆蓋率缺口只作為「風險加權」輸入；但**測試本身的有效性要查**（S19），假綠燈屬 A 級。
5. **唯一例外**：A 級發現（會算錯錢／會靜默漏資料／假綠燈）允許在該步驟內即時修復，但必須附測試與回歸雙線通過；修不完的一律轉為新 backlog 文件。

**驗收標準**：
1. S1~S23 全部 ✅，且〈檢查範圍盤點〉表中每一列都有對應步驟且狀態為已檢查。
2. 每一條發現都有嚴重度、位置（`file:line`）、影響、處置四欄，處置欄不得留白。
3. 健檢期間對程式碼的任何改動，`./scripts/run_regression.sh` 回歸雙線逐筆相同、`pytest -m "not slow"` 全綠。
4. A 級發現「全部修完」或「已開出對應 backlog 文件並在 `index.md` 有列」，兩者擇一，不得只留在本文件。

---

## 檢查範圍盤點

**整個 repo 逐一列出，每一列都必須落在某個步驟裡**——這張表是「有沒有漏檢」的唯一判準。

| 對象 | 規模 | 負責步驟 |
|------|------|----------|
| `core/config`、`core/utils` | 15 檔 2,011 行 | S4 |
| `core/models`、`core/adapters` | 23 檔 1,667 行 | S5 |
| `core/api` | 15 檔 2,781 行 | S6 |
| `core/pipeline` | 86 檔 17,779 行 | S7~S10 |
| `core/managers` | 3 檔 1,191 行 | S11 |
| `core/backtest` | 24 檔 7,050 行 | S12、S13 |
| `core/strategies` | 11 檔 1,946 行 | S14 |
| `core/Dockerfile` | 1 檔 | S20 |
| `run.py`、`tasks/` | 7 檔 1,039 行 | S15 |
| `frontend/`（含 `Dockerfile`、`SKILL.md`） | 6 檔 884 行 ＋ 設定 | S16 |
| `strategy_lab/` | 14 檔 3,879 行 | S17 |
| `scripts/` | 6 檔（3 py 599 行 ＋ 3 sh／ps1） | S18 |
| `tests/` | 69 檔 19,272 行 | S19 |
| `pyproject.toml`、`requirements.txt`、`.pre-commit-config.yaml`、`.github/workflows/`、`docker-compose.yml`、`.env.example`、`.gitignore`、`dev/env/*.yml` | 建置與環境設定 | S20 |
| `docs/`（16 份）、`README.md`／`README_zh.md`、`CLAUDE.md`、`.claude/skills/`、`.cursor/` | 文件 | S21 |
| `data/`、`results/`、`logs/` 的目錄約定與 DB schema | 執行期產物 | S22 |
| 跨全專案的相依方向與 import 圖 | — | S3 |

---

## 進度追蹤表

> **「嚴重度」欄是開工前的研判值**，代表該步驟**預期能挖到的最嚴重等級**（定義見下方〈嚴重度分級〉），
> 用來決定施作順序與投入深度——A 級的步驟不可略過、不可只抽樣。它**不是**發現本身的等級：
> 每一條實際發現的等級一律逐條填在〈附錄 A〉，可能高於或低於本欄。研判理由寫在「備註」欄。

| 編號 | 步驟名稱 | 嚴重度 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|:------:|----------|----------|:----:|--------------|
| S1 | 重測品質基線（ruff／覆蓋率／規模，全專案） | C | 本文件〈附錄 B〉 | 三組數字與 2026-08-16 基線逐項對照 | ✅ | 2026-09-02 完成，數字在〈附錄 B〉。要點：測試 207 → 687 passed、覆蓋率 40% → 60%、`BLE001` 85 → 96（全在 `core/pipeline/`）。量測時以 `noguru_plugin`（scratchpad）隔離 loguru sink，避免 F-001 再污染 `logs/` |
| S2 | 複驗既有待收斂清單（21 條） | A | 附錄 A | 逐條確認仍存在／行號漂移／已修 | ✅ | 2026-09-02 完成：21 條**全部仍在**（行號漂移），另新增 4 條（B008 ×3 期貨 updater、B007 ×1 tests）共 25 條。`B008` 由 A **降為 B**——排程路徑 `tasks/update_db.py` 每次呼叫都明傳 `end_date`。見 F-002、F-010~F-012 |
| S3 | 分層相依與 import 圖驗證（全專案） | A | `scripts/check_layer_deps.py`、附錄 A | 產出 import 圖，比對 [module-map](../backtest/module-map.md) §一 | ✅ | 2026-09-02 完成：`scripts/check_layer_deps.py` 上線（278 檔、912 條邊）。A 級 0 條；反向相依 4 條（F-003、F-004）已登錄為 ratchet、循環 1 條（F-006，`strategy_lab`）、市場語意洩漏 0。**現況結束碼為 1**（那條循環），S17 清掉後歸零。文件把呼叫方向寫成相依方向見 F-005 |
| S4 | `core/config`＋`core/utils` 健檢 | A | 附錄 A | 15 檔逐檔過共用五問 | ✅ | 2026-09-02 完成，無 A 級。F-015（`TICK_DB_PATH` 缺 env 靜默成 `NonetickDB`）、F-017（LINE Notify 已停服且不檢查回應）、F-016／F-018／F-019。**交易日判定不在 `utils/time.py`**（那裡只有日期產生器）：回測側在 `datafeed/tw/market_calendar.py`（由 `price` 表推導，F-028），ETL 側有 2 個 updater 用週末近似＋補班日例外（歸 S10） |
| S5 | `core/models`＋`core/adapters` 健檢 | A | 附錄 A、附錄 C | 23 檔；stock／futures 對稱性 | ✅ | 2026-09-02 完成，無 A 級；三方對照表在〈附錄 C〉。F-020（`check_has_position()` 未濾已平倉）、F-021（放空市值退回開倉價）、F-022（tick 路徑 OHLC 全 0）、F-023（O(n²) 過濾）。兩條待 S11／S12 追查的不對稱：`no_quote_days` 只有股票有、`roi_on_capital` 只有股票有 |
| S6 | `core/api` 健檢 | A | 附錄 A | 15 檔；SQL 參數化、連線生命週期 | ✅ | 2026-09-02 完成，無 A 級。17 處 f-string SQL 全部只拼表名／欄名，值一律走 `params`；其中 2 處表名由呼叫端傳入（F-026）。F-024（`get_net_chip()` 一呼叫就 TypeError）、F-025（依賴已 deprecated 的 sqlite date adapter）、F-027、F-028（交易日曆由 `price` 表推導，缺資料＝靜默跳過）、F-029 |
| S7 | `pipeline/crawlers`＋`shared` 健檢 | A | 附錄 A | 14＋6 檔；逾時／重試／失敗語意 | ✅ | 2026-09-02 完成，**抓到 1 條 A 級（F-030）**：台股 5 支 crawler 把連線失敗／被封鎖／5xx 一律記成「{date} is a Holiday!」，`RequestUtils` 從不檢查 HTTP 狀態碼，updater 收到 None 就當當日無資料——那一天永遠缺且沒有統計行浮出。期貨 5 支已是正確做法（失敗語意兩段式、表格用欄名辨識、converters 保留字串）。另 F-031~F-036 |
| S8 | `pipeline/cleaners` 健檢 | A | 附錄 A | 13 檔；主鍵、單位、來源日期 | ✅ | 2026-09-02 完成。**F-037（暫定 A）**：`stock_price_cleaner` 把無成交日的 `--` 填成 0，`price` 表 6.25M 列中有 **104,046 列（1.7%）OHLC 全為 0**，0 價會被當成真實報價流進引擎（S13 確認引擎是否過濾）。13 支「日期來源／主鍵唯一性」逐支結論見完成紀錄；DB 實測 13 張表皆有 PK、近 60 天無重複主鍵。另 F-038~F-042 |
| S9 | `pipeline/loaders` 健檢 | A | 附錄 A | 21 檔；冪等、commit 邊界、失敗浮出 | ✅ | 2026-09-02 完成，**抓到 2 條 A 級**：F-043 `stock_price_loader`（回測最核心的表）至今仍是「逐檔 except 只記 log、不拋 `DataLoadError`」的 §4.2 事故樣式；F-045 FinMind 三條入庫路徑失敗被算成 skipped。`if_exists="replace"` 0 處；7 支已走 `finish_load()`。另 F-044／F-046~F-049 |
| S10 | `pipeline/updaters`＋`pipeline/utils` 健檢 | A | 附錄 A | 20＋6 檔；斷點續跑、日期區間 | ✅ | 2026-09-02 完成，**1 條 A 級（F-050）**：四支台股 updater 的續跑起點是「表內最新日 +1」，任何一天被 F-030 記成假日後**永遠不會回頭補**，且全程沒有 `unreachable` 統計行。期貨線（price／chip）已有重試、退避、上市日夾住、被擋偵測與收尾摘要，是正確的參考實作。另 F-051~F-056 |
| S11 | `core/managers` 健檢 | A | 附錄 A | 3 檔；FIFO、部分回補、保證金追繳 | ✅ | 2026-09-02 完成，無 A 級。§7.1~§7.7 逐條對到實作（見完成紀錄）；LONG／SHORT 記帳口徑經現金流推導一致（開倉成本只扣一次、股利補償除息日扣、平倉加回）。F-057（同標的雙向持倉只擋「先多後空」，文件寫「反之亦然」）、F-058（期貨同契約多空並存時保證金重複佔用）；F-020 降為 C |
| S12 | `core/backtest/models` 健檢 | A | 附錄 A | 5 檔 3,600 行；手算範例逐項對數 | ✅ | 2026-09-02 完成，無 A 級。§6.1（4,768／4.76%）、§6.2（4,548／4.53%／5.03%）與 §6.0 取整（33.33 元保證金 29,997）逐項對數命中；96 tests passed。F-059（SBL 借券費逐 bar 計提 1/365，曆日口徑低估約 31%）、F-060（當沖減半稅率不看交易日，2017-04-28 前的當沖稅少一半）、F-061（漲跌停公式相符率 61.6%，程式已註明）、F-062（期貨損益公式兩套並存）、F-063（`holding_days` bar 數 vs 曆日同名不同義）；F-037 由暫定 A 降為 B（盯市／無報價路徑把 0 價當缺報價，只剩成交路徑漏擋） |
| S13 | 引擎＋datafeed＋report 健檢 | A | 附錄 A | 14 檔；bar 順序、前視偏誤、換月 | ✅ | 2026-09-02 完成，無 A 級。§2.2.1 三層順序逐項對到行號；回歸雙線通過（SHORT 6 passed、LONG 1 passed／16 s）＋ 233 passed。F-064（成交價合理性檢查只在開倉腿且在滑價前）、F-065（`MarketCalendar.get_last_trading_date()` 往前無界迴圈，起始日無更早資料即卡死）、F-066（`is_market_open()` 每個曆日 `SELECT *` 整天資料只為判空）、F-067（reporter：連線不關、`show=True` 每次開 5 個瀏覽器分頁、0050 分割寫死）、F-068（analyzer 的 Sharpe／Sortino 單位不一致且未年化、零筆交易除以零）、F-069（期貨對標近月拼接會挑到週契約與殘留列）、F-070（期貨日曆只看第一個商品）、F-071（`OPEN_INTEREST` 規則下即時轉倉可能回頭轉到較近月，與 `build_roll_schedule()` 的「不回頭」不一致） |
| S14 | `core/strategies` 健檢 | B | 附錄 A | 11 檔；策略契約、`strategy_loader` | ✅ | 2026-09-02 完成，無 A 級。契約／分派鍵／docstring 三區塊逐支對齊；58 passed。F-072（`OvernightLeadEventStrategy` 建構即 `AttributeError`——`self.price` 要到 `setup_apis()` 才有值，實測確認；且在策略內直接 `yfinance.download`）、F-073（`StrategyLoader` 任一策略模組 import 失敗即讓 `run.py` 全部策略不可用；同名類別靜默覆蓋）、F-074（「策略不自建連線」沒有測試釘住，`test_strategy_data_access.py` 只擋欄位字面值）、F-075（`MomentumStrategy1` TICK 級別 `self.price` 為 None 會 `ValueError`；開倉不排除已持有標的但 docstring 未寫）、F-076（`BaseStrategy.max_holdings` 預設 0，漏設的新策略所有開倉單被引擎剔除） |
| S15 | `run.py`＋`tasks/` 健檢 | A | 附錄 A | 7 檔；CLI 分派、退出碼、破壞性腳本 | ✅ | 2026-09-02 完成，無 A 級（原 A 級候選 `run.py` 退出碼降為 B：實測 exit 0，但 `run.py` 未被任何排程包起來）。`--target` 21 個選項與 `main()` 分支一一對應。F-077（`run.py` 策略名錯誤與 `--mode live` 空實作皆 exit 0）、F-078（預設 `no_tick` 只排除 `tick`，**`futures_tick`（需 Shioaji 金鑰＋DolphinDB）仍在預設範圍**，每晚預設更新必踩一個失敗 target 而 exit 1）、F-079（`delete_price_data.py` 無 dry-run／確認／備份，日期解析失敗 exit 0）、F-080（`load_broker_trading_to_db.py` 用 loguru 不支援的 `exc_info=True`，traceback 不會印）、F-081（`migrate_db_naming.py` 為已執行完的一次性遷移，留在 `tasks/` 會被當成常規工具） |
| S16 | `frontend/` 健檢 | A | 附錄 A | 6 檔；報表契約耦合、失敗顯示 | ✅ | 2026-09-02 完成，**抓到 1 條 A**：F-082（`frontend/app.py` 自行重算指標——`平均 ROI` 把已是百分比的 `ROI` 欄再 ×100；資產曲線與日報酬以 `Sell Date` 排序／分組，SHORT 策略的 `Sell Date` 是開倉日；權益口徑用已實現累積餘額而非報表的盯市 `daily_equity`；IR 讀的 benchmark 欄位不存在於任何報表）。F-083（本機預設結果目錄仍指向已不存在的 `core/backtest/results`，環境變數名也與 `core/config` 的 `ALPHAEDGE_RESULTS_DIR` 不同）、F-084（前端沒讀 `daily_equity`／`direction_summary`／`event_report` 三份 CSV 與第 5 張圖；起始資金與回測區間用交易明細「估算」）、F-085（`app.py` 的指標函式在模組層級 Streamlit 呼叫之後，無法被測試 import）；7 passed |
| S17 | `strategy_lab/` 健檢 | A | 附錄 A | 14 檔 3,879 行；與 `core/` 的口徑一致性 | ✅ | 2026-09-02 完成，無 A 級。兩個研究各一份差異表（見完成紀錄）；`ruff check strategy_lab` All checks passed。F-086（`tsmc_overnight_signal` README 寫的成本 0.1425%／0.4425% 是**向量化診斷路徑**的費率，主結果 `metrics_summary.csv` 走的是 `StockUtils` 的折扣後手續費 0.04275%＋最低 20 元）、F-087（研究版與搬進 `core/` 的 `OvernightLeadEventStrategy` 在部位大小與資料截止日兩處口徑不同，且沒有對照測試）、F-088（13 個 `output/*.html` 在 `.gitignore` 規則之前就進了版控；`tech_new_high` 的 `END_DATE` 寫死；存活者偏差未列入限制；`load_price_panel()` 繞過 API 直接寫 SQL） |
| S18 | `scripts/` 與一次性工具健檢 | B | 附錄 A | 6 檔；破壞性操作、是否已過期 | ✅ | 2026-09-02 完成，無 A 級。7 支腳本逐支判定（見完成紀錄）；`run_regression.sh` 實跑通過。F-089（`dataframe_dot_to_bracket.py` 的 `ROOT = parents[2]` 指到**專案上一層**，誤跑會改寫所有同層專案的 `.py`，且無 dry-run；一次性 codemod 已完成）、F-090（`run_regression.sh` 的 LONG 線在沒有 `tw_stock.db` 時被 `skipif` 跳過仍印「回歸雙線通過」；註解寫舊檔名 `stock.db`）、F-091（`clean_pycache.ps1` 往上兩層清到同層其他專案；`generate_docs.py` 只印示範訊息不產出任何檔案） |
| S19 | `tests/` 有效性健檢（假綠燈稽核） | A | 附錄 A、附錄 D | 69 檔；20 處 `return False`、7 檔 `except Exception` 逐處判 | ✅ | 2026-09-02 完成，無 A 級（**pytest 收集範圍內沒有假綠燈**）。19 處 `return False` 與 7 檔 `except Exception` 全部在 9 支不被收集的 `manual_*.py`；文件舉的 `test_broker_trading_updater.py` 已改名為 `manual_broker_trading_updater.py`。13 個 `slow` 涵蓋全部 6 支連 production DB 的測試且皆唯讀＋`skipif`；15 處 skip 理由全為「表／DB 尚未建立」仍成立；4 份 baseline 在版控且回歸通過；`pytest -m "not slow"` 687 passed / 10 deselected 與 S1 基線一致。F-092（9 支 `manual_*.py` 放在 `tests/` 內：不被收集、含 `return False`／`except Exception` 型態、兩支直連 production DB）；F-001 補註：`tests/` 沒有根 `conftest.py`，loguru sink 未隔離 |
| S20 | 建置、CI、容器與環境變數健檢 | B | 附錄 A | 9 份設定檔；本機／CI／容器三處一致性 | ✅ | 2026-09-02 完成，無 A 級（原 A 級候選「容器缺 DB」實測為**大聲失敗**，降 B）。AST 掃描 15 個第三方 import 全部已宣告；`requirements.txt` 鎖定版 ≥ `pyproject` 下限；Python 3.12 六處一致；`docker compose config` OK；`.env` 封鎖完整、硬編碼金鑰 0；乾淨 venv 的 `pip install -e .[dev] && ruff && pytest` 於背景執行（結果補記於完成紀錄）。F-093（`frontend/Dockerfile` 只裝 `streamlit pandas`，`app.py` 卻 import `plotly`——映像起不來）、F-094（`core` 容器沒有 `data/` 也沒有 `tasks/`，compose 承諾的「Trader＋Frontend」回測必在 `sqlite3.connect` 就失敗；映像裝整份 `requirements.txt` 含 Flask／ipython／ta 等 85 個無關套件）、F-095（slow 測試與 `run_regression.sh` 只在本機跑、CI 無任何地方執行；pre-commit 釘 ruff v0.16.3 而 CI 裝 `ruff>=0.6` 最新版，兩邊可能不同版）、F-096（`.env.example` 缺 `API_KEY_1..4`／`ALPHAEDGE_*_DIR`／`ALPHAEDGE_BACKTEST_RESULTS`；`DDB_PATH` 被兩個模組各讀一次；`core/utils/path.py` 與 `core/config/paths.py` 兩套 env 路徑工具；conda yml 用 black／isort 且缺 yfinance） |
| S21 | 文件漂移健檢（`docs/`／README／規則檔） | C | 附錄 A | 16 份 docs 的陳述抽樣核對程式碼 | ✅ | 2026-09-02 完成。16 份 docs 逐份三選一（見完成紀錄）：**已更新 10 份**（module-map、multi-market-engine、etl-ingestion、data_coverage、code-quality、naming-axes、dev-setup、dev-deployment、prod-deployment、command-usage ×2）＋ `README.md`／`README_zh.md`／`strategy_lab/README.md`／`.claude/skills/develop-strategy/SKILL.md`／`CLAUDE.md` §表；不需動 5 份；`.cursor/` 五個指標檔皆只放指標 ✓；`backlog/index.md` 與 7 份文件的進度表逐列一致 ✓。F-100（`pyproject.toml` per-file-ignores 指到已搬走的 `core/pipeline/loaders/stock_tick_loader.py`）、F-101（README 雙語 Docker 段落分岔：en 示範 `--help`／`-p 8501`，zh 示範 `--entrypoint /bin/bash` 進 shell，多 3 個 code block） |
| S22 | 資料與執行期產物約定健檢 | B | 附錄 A | DB schema 對照、目錄約定、`.gitignore` 覆蓋 | ✅ | 2026-09-02 完成，無 A 級。兩個 DB 共 21 張表逐表對照 `core/config/schema.py` 與 `data_coverage.md`（〈附錄 E〉）：程式宣告但實際不存在的只有 `futures_contract`；文件漏列 9 張（交 S21 改文件）。主鍵與 loader 冪等一致；`downloads/` 已全部 `{market}/{domain}/`；`.gitignore` 抽查無漏網也無誤擋。F-097（`logs/` 已達 **3.1 GB**：`api/` 桶 26 天 2.5 GB／277 檔，每次查詢都寫、平均每天 100 MB，`clean_logs` 沒有任何排程在跑；`shioaji.log` 寫在 repo 根目錄）、F-098（`futures_contract` 表名常數有宣告無建表）、F-099（`dividend` 依 `stock_id` 查詢全表掃描、`price`／`chip`／`margin` 依個股取區間只能用主鍵的 `date` 部分——純效能） |
| S23 | 分級收斂與分流 | — | 新 backlog 文件、`index.md`、`docs/` | A 級全數結清或轉單；三處狀態一致 | ✅ | 2026-09-02 完成。附錄 A 共 101 條：**A 級 5**（F-030／F-043／F-045／F-050 → **ETL 失敗語意與缺口回補**；F-082 → [前端指標與報表同源化.md](../../backlog/前端指標與報表同源化.md)）、**B 級 43** 依主題併入 4 份新 backlog（另含 **回測口徑與日期邊界收斂**、[測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md)）、**C 級 51** 寫進 `docs/`（module-map §六、multi-market-engine §九、etl-ingestion §五、code-quality〈健檢 C 級結論〉）或併入相關步驟、**D 級 2** 只計數（附錄 B）。每列「處置」欄以粗體指向具體去處；`pyproject.toml` 的 `ignore` 清單無可移除項（BLE001 反增、其餘 21 條仍在，見 S2）。A 級未在本工作內修：4 條 ETL 需真實爬取驗證且期貨回補仍在跑，F-082 涉及前端重構，皆已轉單為 P0／P1 且 `index.md` 已新增列。 |

**分佈**：A 級 16 步（S2~S13、S15~S17、S19）、B 級 4 步（S14、S18、S20、S22）、C 級 2 步（S1、S21）、無 1 步（S23）。
**施作順序建議**：A 級不可略過也不可抽樣；C 級的 S1 仍須最先做（是其餘各步的量測基準），S21 則必須最後做（要吃前面各步的實測結果）。

---

## 共用審查準則

### 嚴重度分級

| 級別 | 定義 | 處置 |
|:----:|------|------|
| **A** | 會算錯錢、靜默漏資料，或**讓錯誤看起來像正確**（假綠燈測試、失敗被吞、報表誤導） | 本工作內即時修＋補測試，或當場開新 backlog 文件 |
| **B** | 會在特定條件下出錯：邊界值、時區／日期、併發、資源未釋放 | 記錄＋開 backlog，不在本工作內修 |
| **C** | 架構與可維護性：職責混雜、重複實作、跨層相依、命名不一致、文件漂移 | 只記錄，附「若要修的最小切法」 |
| **D** | 樣式與文件細節：docstring 缺漏、註解過期 | 只計數，不逐條列 |

### 每個檔案固定過的五問

逐檔健檢時，**每個檔案都要回答這五題**，答不出來就是發現：

1. **職責**：這個檔案屬於哪一層？有沒有做該層不該做的事（例如 cleaner 直接寫 DB、api 內含策略判斷、`strategy_lab/` 自己重寫一套成本模型）？
2. **失敗路徑**：異常被 catch 之後發生什麼？呼叫端分得出「沒資料」與「抓失敗」嗎？結束碼／回傳值會不會讓上游誤判成功？
3. **重跑**：同一輸入跑兩次，結果一致嗎？中途中斷後重跑，會不會重複寫、漏寫或整批覆蓋？
4. **邊界**：空輸入、單列、跨年、停牌／下市、換月、除權息、假日與夜盤，各走哪條分支？
5. **口徑**：金額、數量、比例的單位與四捨五入方式，與 [放空框架 §6.0](../backtest/short-selling-framework.md) 或該資料源文件一致嗎？

### 紀錄方式

發現一律寫進〈附錄 A〉表格，**不可只留在對話或 commit message**。同一檔案多個發現拆成多列。

---

## Phase 1：基線與跨層

### S1. 重測品質基線（ruff／覆蓋率／規模，全專案）✅

- **目的**：[程式碼品質](../dev/code-quality.md) 的兩份基線量測於 2026-08-16，距今已逾半年，期間新增了整條期貨線。先確認漂移量，才知道哪些目錄風險升高。
- **做法**：
  ```bash
  ruff check . --statistics                       # 與〈例外處理現況〉表逐條比對
  pytest -m "not slow" --cov=core --cov-report=term
  find . -name '*.py' -not -path './.venv/*' | xargs wc -l | sort -rn | head -50
  ```
  數字寫進〈附錄 B〉，並標出：`BLE001` 由 85 條變成幾條、新增檔案中覆蓋率為 0 者、單檔行數突破 500 行者（`settlement_model.py` 1,219、`futures_margin_cleaner.py` 879、`reporter.py` 872、`financial_statement_updater.py` 716、`backtester.py` 687、`frontend/app.py` 637、`tasks/update_db.py` 527）。
- **產出**：〈附錄 B 基線快照〉。
- **驗證方式**：三組數字齊全，且每個「與 2026-08-16 不同」的項目都有一行說明是新增程式碼還是既有程式碼變差。
- **相依**：無。
> **✅ 完成紀錄（2026-09-02）**
> - 指令：`ruff check . --statistics`（現行設定下 0 條）、`ruff check . --select BLE001 --no-cache`（96 條）、`pytest -m "not slow" -p noguru_plugin --cov=core`（687 passed / 10 deselected，5.9 秒）、`find … | xargs wc -l`。
> - 與 2026-08-16 的差異全部是**新增程式碼**（期貨線＋測試），沒有既有程式碼變差：`core/` 覆蓋率 40% → 60% 是因為期貨線帶著測試進來；仍為 0% 的只剩 `core/api/tw/finmind_api.py` 與 `core/utils/path.py`（後者為死碼，F-016）。
> - 量測注意事項：pytest 外掛若在**模組載入時**就 import `core.config`，會讓 `core/config`／`core/utils` 在 pytest-cov 啟動前被載入而記成 0%——第一次量測就踩到，改用 `pytest_sessionstart` hook 才正確。

### S2. 複驗既有待收斂清單（21 條）✅

- **目的**：`pyproject.toml` 的 `ignore` 清單裡有 7 條標註「潛在缺陷，待收斂」，對應 21 個位置。這些是已知會出錯的地方，健檢必須先確認它們還在不在，而不是重新發現一次。
- **做法**：逐條打開 [程式碼品質〈待收斂清單〉](../dev/code-quality.md) 的 21 個 `file:line`，標記三種狀態之一：已修（可從 `ignore` 移除）／仍在（行號更新）／已不適用。重點確認兩條：
  - `B008` ×5：`end_date: datetime.date = datetime.date.today()` 在 import 當下固定，長駐排程跨午夜會靜默漏最新一天——屬 A 級。
  - `F841` ×3：`stock_price_crawler.py:39/40` 把 `crawl_twse_price()`／`crawl_tpex_price()` 的回傳值指派後完全沒用，需確認是缺陷還是設計。
- **產出**：〈附錄 A〉；若有已修者，同步在 `pyproject.toml` 移除該規則並註明。
- **驗證方式**：`ruff check . --select B006,B008,B904,B007,E722,F841,F811 --no-cache` 的實際命中數與清單一致。
- **相依**：S1。
> **✅ 完成紀錄（2026-09-02）**
> - `ruff check . --select B006,B008,B904,B007,E722,F841,F811 --no-cache` 命中 25 處：原 21 條全部仍在（行號漂移：`financial_statement_crawler.py` 269 → 332、`finmind_updater.py` 157 → 137、`callback.py` 7 → 6），新增 `futures_price_updater.py:227/268`、`futures_tick_updater.py:147`（B008）與 `tests/test_futures_continuous.py:347`（B007）。
> - **B008 降級的依據**：`tasks/update_db.py` 的 `get_time_config()` 是函式，`datetime.date.today()` 在每次呼叫時才取值並明傳給 `update()`；預設值只影響直接呼叫 `update()` 且不傳 `end_date` 的程式（目前只有 `tests/manual_*`）。
> - F841 的 `crawl()` 確認為**死碼**（無呼叫端且無副作用，F-010）；F811 的兩個 `OrderState` 值完全相同（F-011）；E722 三處全在清理暫存檔的段落且隨後 `raise e`；B006 四處全為唯讀（F-012）。

### S3. 分層相依與 import 圖驗證（全專案）✅

- **目的**：[module-map §一](../backtest/module-map.md) 宣告相依**單向由上往下、同層之間不互相 import**，且引擎不認識任何市場。這條線被違反過兩次（見 [多市場引擎 §6.4](../backtest/multi-market-engine.md)），需要可重複執行的檢查而非人工 grep。本步驟把檢查面**從 `core/` 擴到全專案**：`tasks/`／`frontend/`／`strategy_lab/` 只能單向依賴 `core/`，反向依賴屬 A 級。
- **做法**：寫 `scripts/check_layer_deps.py`，以 `ast` 掃 `core/`、`tasks/`、`frontend/`、`strategy_lab/`、`scripts/`、`run.py` 的 import，建圖後檢查五件事：
  1. **反向相依**：`core/` 內是否 import 了 `tasks`／`frontend`／`strategy_lab`／`tests`（任何一處都是 A 級）；`core/api` → `core/backtest`、`core/models` → `core/managers` 之類的上行 import。
  2. **循環 import**（含套件層 `__init__.py` 的 eager import）。
  3. **市場語意洩漏**：`core/backtest/backtester.py` 內 `Stock`／`Futures`／`Tw` 出現次數應為 0；`if market ==` 僅允許出現在 `factory.py`。
  4. **跨軸目錄污染**：對照 [命名軸線](../dev/naming-axes.md)，`models`／`strategies`／`managers` 底下不得出現市場軸目錄。
  5. **`sys.path` 注入**：`strategy_lab/` 有 8 處 `sys.path.insert`、`tests/` 有 11 處。專案已可 `pip install -e .`，逐處確認是否仍必要（C 級，但會遮蔽 import 錯誤）。
- **產出**：`scripts/check_layer_deps.py`、〈附錄 A〉。
- **驗證方式**：腳本可執行且對現況輸出報告；既有 `tests/test_naming_axes.py` 仍通過；抓到的違規逐條記錄，不即時修（除非屬 A 級）。
- **相依**：S1。
> **✅ 完成紀錄（2026-09-02）**
> - `scripts/check_layer_deps.py`：AST 掃 `core/`、`tasks/`、`frontend/`、`strategy_lab/`、`scripts/`、`tests/`、`run.py` 共 278 檔、912 條專案內 import 邊；檢查 A 反向 import 非 core／B 低層 import 高層／C 循環／D 市場語意洩漏／E 跨軸目錄／E' 策略門面 eager import／F 同層互相 import（僅列）／G `sys.path`（僅列）。
> - 第一版誤判三處，已修：相對匯入在套件 `__init__` 內少算一層、docstring 裡的 `StockQuote` 被當成引擎洩漏（改用 `tokenize` 略過字串與註解）、腳本比對到自己的 `sys.path` 字樣。
> - **設計決策**：`core/strategies/base.py`、`stock/base.py`、`futures/base.py` 與兩個套件門面定為「策略契約」層（與可插拔 model 同層）——引擎、factory、報表都要認得它們；具體策略仍在策略層，引擎一 import 具體策略就會被抓。已知的 4 條反向相依放進 `_KNOWN_REVERSE`（ratchet），新出現者才影響結束碼。
> - 結果：A 級 0；反向相依（新）0、已登錄 4（F-003、F-004）；循環 1（F-006）；市場語意洩漏 0（`backtester.py` 程式碼確無 `Stock`／`Futures`／`Tw`）；跨軸目錄 0；`sys.path` 15 處（F-009）。`tests/test_naming_axes.py` 6 條仍通過。

---

## Phase 2：`core/` 基礎層

### S4. `core/config`＋`core/utils` 健檢 ✅

- **目的**：這兩層被其他所有層 import，一個口徑錯會擴散到全專案。`core/utils/path.py` 覆蓋率為 0，`os.getenv`／`os.environ` 在 `core/` 有 14 處，需確認設定來源是否唯一。
- **做法**：15 檔逐檔過共用五問，另加四項重點：
  1. `config/paths.py`／`settings.py`／`schema.py`：路徑是否全部集中、有無檔案繞過 config 自行拼路徑；`.env` 缺項時是啟動即失敗還是靜默用預設值。
  2. `utils/time.py`：交易日判定**不可用「非週末」近似**（[ETL 入庫約定 §3.3](../pipeline/etl-ingestion.md)）；補班日、颱風假、夜盤跨日的處理各在哪一行。
  3. `utils/constant.py`（501 行）：Enum 是否都由模組層級常數引用（`CLAUDE.md` §2.7）；有無兩個 Enum 表達同一件事。
  4. `utils/log_manager.py`／`notify.py`：日誌落地路徑、失敗通知是否會在 ETL 靜默失敗時被觸發。**已知發現 F-001（2026-09-02 於健檢外發現，先登錄）**：`logger.add()` 未帶 `filter=`，loguru 的 sink 預設廣播，34 處 `setup_logger()` 只要被 import 就註冊一個 sink，同一 process 內每一筆訊息會同時寫進所有已註冊的 log 檔——本步驟負責確認修法（`setup_logger()` 增設 `module_prefix` 並轉成 `filter=`）與 34 處呼叫端的改動面。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_config_paths.py -q` 通過；重點四項每項有書面結論。
- **相依**：S1。
> **✅ 完成紀錄（2026-09-02）**
> - 15 檔逐檔過五問；`pytest tests/test_config_paths.py -q` 通過。
> - 重點 1（路徑／env）：路徑全部集中在 `config/paths.py`，`grep "data/db"` 在程式碼中 0 處；`load_dotenv()` 由 `find_dotenv()` 從呼叫檔往上找，CWD 不同也能載到專案根的 `.env`。缺項行為不一致——`get_int_env()` 靜默退回 0（文件化的取捨）、`TICK_DB_PATH` 靜默成 `"NonetickDB"`（F-015）、Shioaji／DDB 憑證為 `None` 交由呼叫端。`.env.example` 少列 12 個程式會讀的鍵（F-018）。
> - 重點 2（交易日判定）：`utils/time.py` **沒有**交易日判定，只有 `generate_date_range()` 等含週末的曆日產生器。實際判定在兩處：回測側 `datafeed/tw/market_calendar.py` 以 `price` 表「當日有資料」為準（F-028，缺資料＝靜默跳過）；ETL 側 `stock_margin_updater.py:93/138` 與 `futures_price_updater.py:182/212` 用 `weekday() >= 5` 近似＋ `traded_weekends` 補班日例外，是否違反 [ETL 入庫約定 §3.3](../pipeline/etl-ingestion.md) 歸 S10 判。
> - 重點 3（`constant.py`）：Enum 值多數由模組層級常數引用；`OrderState`／`Status`／`Market`／`InstrumentType`／`Scale`／`PositionType` 直接寫字面值（樣式，D）。沒有兩個 Enum 表達同一件事；`OrderState` 與 `shioaji.constant.OrderState` 值相同（F-011）。`FUTURES_MULTIPLIER`／`STOCK_FUTURES_TYPE_BY_CONTRACT_SIZE` 刻意不給預設值的設計正確。
> - 重點 4（日誌／通知）：F-001 已登錄（本步驟不動 `log_manager.py`，期貨回補進行中）。**ETL 失敗沒有任何通知掛點**；`Notification` 只服務實盤 callback，且打的 LINE Notify 已停服（F-017）。
> - 其他：`core/utils/path.py` 為 `config/paths.py` 的死複本（F-016）；`decorators.log_thread` 缺 `functools.wraps`、`time.py` 型別註解與實作不符（F-019，D）。

### S5. `core/models`＋`core/adapters` 健檢 ✅

- **目的**：`models/` 是 base／stock／futures 三套平行結構（19 檔），最容易出現「股票改了、期貨沒跟上」的不對稱。`adapters/` 負責報價轉換，是前視偏誤與重複報價的入口。
- **做法**：
  1. 對三組的 `account`／`order`／`position`／`quote`／`record` 做**欄位與方法的三方對照表**，列出只存在於單邊者並判斷是否為刻意（期貨有結算、股票有除權息）。
  2. `Optional[T]` 欄位在 `__init__` 是否都給 `None`（§2.4.4），以及讀取端有沒有假設非 None。
  3. `stock_quote_adapter.py`／`futures_quote_adapter.py`：同一日多筆報價的去重與排序、夜盤與日盤的合併口徑。
- **產出**：〈附錄 A〉、〈附錄 C〉三方對照表。
- **驗證方式**：`pytest tests/test_futures_quote_adapter.py tests/backtest/test_quote_adapter_duplicates.py tests/test_futures_session_combine.py -q` 通過；對照表無「不明原因的單邊欄位」。
- **相依**：S4。
> **✅ 完成紀錄（2026-09-02）**
> - 23 檔逐檔；`pytest tests/test_futures_quote_adapter.py tests/backtest/test_quote_adapter_duplicates.py tests/test_futures_session_combine.py -q` 通過（含 S4 共 45 passed）。三方對照表在〈附錄 C〉，單邊欄位都能說明原因，兩條待下游確認（`no_quote_days`、`roi_on_capital`）。
> - `Optional` 檢查：所有 model 的 `date`／`scale`／`tick` 參數都是 `X = None` 而非 `Optional[X]`（§2.4.4，共 12 處，D）；讀取端 `setup_entry_exit()` 等未假設非 None，實際初始化都由 manager 補齊。
> - adapter：股票去重只警告不排除（設計如此，`{symbol: quote}` 留最後一筆）；期貨 `combine_quote()` 對夜盤缺值不補 0、對 `close=0` 視為無夜盤，邊界處理正確。發現 F-020~F-023。

### S6. `core/api` 健檢 ✅

- **目的**：15 檔 2,781 行，是回測與策略取數的唯一入口。SQL 拼接 17 處 `execute(f"`、`sqlite3.connect` 在 `core/` 有 41 處；且 [PostgreSQL遷移計畫](../../backlog/PostgreSQL遷移計畫.md) 的改動面能否收斂到這層，取決於本層有沒有洩漏 SQLite 專屬語法。
- **做法**：
  1. **參數化**：逐一檢視 17 處 `execute(f"`／54 處 `read_sql_query`，確認使用者輸入一律走 `params=(...)`（§2.10）；f-string 只用於表名等內部常數，且該常數來自 `config`。
  2. **連線生命週期**：誰建立、誰關閉、有無 `with`；回測期間是否共用單一連線（[module-map §二](../backtest/module-map.md) 宣告 datafeed 建立唯一連線）。
  3. **空結果語意**：查無資料回傳空 `DataFrame` 還是 `None`？呼叫端分得出「該日休市」與「資料沒補到」嗎？
  4. **日期邊界**：起訖是否含端點、跨年與跨月分支、還原價開關的預設值（[資料覆蓋 §股價還原](../exchanges/data_coverage.md)）。
  5. **跨市場主鍵**：主鍵是否含市場欄（[ETL 入庫約定 §4.4](../pipeline/etl-ingestion.md) 的事故型態）。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_stock_data_api.py tests/test_adjusted_price_api.py tests/test_futures_price_api.py tests/test_futures_margin.py tests/test_futures_stock_universe_api.py -q` 通過；17 處 f-string SQL 逐處有結論。
- **相依**：S4。
> **✅ 完成紀錄（2026-09-02）**
> - 15 檔逐檔；驗證測試見進度表（`pytest -m "not slow"` 涵蓋 `test_stock_data_api`／`test_adjusted_price_api`／`test_futures_price_api`／`test_futures_margin`／`test_futures_stock_universe_api`，全綠）。
> - 參數化：17 處 `execute(f"`／54 處 `read_sql_query` 逐處看過，**值一律走 `params`**，f-string 只拼表名與欄名；表名除 `FinancialStatementAPI.get(table_name)` 與 `FuturesChipAPI.*(table=…)` 兩處由呼叫端傳入外皆來自 `core.config`（F-026）。`FuturesStockUniverseAPI.get_products()` 的 `IN (...)` 以 placeholder 展開，正確。
> - 連線生命週期：12 支 API 接受 `conn` 注入並以 `owns_conn` 決定誰關；`FinMindAPI`／`StockTickAPI` 例外（F-029）。`BaseDataAPI.close()` 對共用連線不關，正確。
> - 空結果語意：`get()` 系列查無資料一律回空 DataFrame／空 dict／None，**API 層無法區分「休市」與「沒補到」**——這是設計，但意味著完整性檢查得在別處補（F-028）。`FuturesPriceAPI.get_trading_days()`／`FuturesMarginAPI.get_margin()` 對「表不存在」回空值，`get_margin_rates()` 卻會拋錯（F-027）。
> - 日期邊界：所有 `get_range` 都含頭含尾且 `start > end` 回空；`StockDividendAPI.get_cumulative_factor()` 用 `searchsorted(side="right")` 讓除權息日當日即套用新係數，與後復權定義一致；`FuturesChipAPI.get_available()` 用嚴格 `<` 對齊盤後公布，前視偏誤防線正確。還原價開關預設由 factory 決定（S13 再核）。
> - 跨市場主鍵：台股表以 `(date, stock_id)` 為鍵、無市場欄，adapter 已實測到「上市股與上櫃 ETF 共用 4 碼」的重複——資料表層的主鍵設計歸 S22。
> - 其餘：`get_net_chip()` 是壞掉的公開方法（F-024）；`datetime.date` 直接當 sqlite 參數依賴已 deprecated 的預設 adapter（F-025）。

---

## Phase 3：`core/pipeline`（86 檔 17,779 行）

### S7. `pipeline/crawlers`＋`pipeline/shared` 健檢 ✅

- **目的**：14 個 crawler ＋ 6 個 shared 基底，是資料正確性的第一道關口。抓失敗被當成「當天沒資料」是最貴的錯，[台期貨保證金ETL](../../backlog/台期貨保證金ETL.md) 已記錄兩類實際被咬的坑（固定檔名附件被站方覆寫、以標題判斷公告類型）。
- **做法**：
  1. **逾時／重試／節流**：`core/` 37 處 `sleep(` 的節流值是否集中管理；有無 crawler 直接用 `requests.get`（2 處）繞過 `shared/request_utils.py` 的重試與 UA 輪替。
  2. **失敗語意**：HTTP 4xx／5xx／空 body／HTML 錯誤頁各自回傳什麼；`unreachable` 統計是否會被上游看到（[§3.2](../pipeline/etl-ingestion.md)）。
  3. **來源變動偵測**：欄位數或表頭變了是拋錯還是照樣寫入錯位資料。
  4. **落檔命名**：`{exchange}_{YYYYMMDD}.csv` 慣例是否所有 crawler 一致（`base_loader.select_csv_files()` 依賴此慣例）；有無固定檔名互相覆寫。
  5. `shared/base_crawler.py`／`base_cleaner.py` 的抽象只有 `setup`／`crawl`，約束力弱——記錄各子類介面是否已漂移（C 級）。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_request_utils.py tests/test_futures_price_crawler.py -q` 通過；14 個 crawler 每個有「失敗語意」一行結論。
- **相依**：S1。
> **✅ 完成紀錄（2026-09-02）**
> - 20 檔逐檔（14 crawler ＋ `shared/` 6 檔 ＋ `utils/url_manager.py`）；`pytest tests/test_request_utils.py tests/test_futures_price_crawler.py -q` 18 passed。
> - **重點 1（逾時／重試／節流）**：全部走 `RequestUtils`（`requests.get` 直呼 0 處；grep 到的那一處是 docstring）。逾時 10 秒、HTTP 重試 3 次 × 60 秒、session 探測 10 次 × 10 秒；**但從不檢查 `status_code`**，4xx／5xx／被擋流量的 HTML 都當成功回傳（F-030）。節流政策散在三處且各異（F-034）。
> - **重點 2（失敗語意）**，14 支逐支結論：
>
>   | crawler | 連線失敗（`requests_get` 回 None） | 頁面無表格 | 結論 |
>   |---|---|---|---|
>   | `stock_price` | `res.text` AttributeError → 記「Holiday」 | 記「Holiday」 | **混淆（A）** |
>   | `stock_chip`／`stock_margin` | `return None` **不留 log** | 記「Holiday」 | **混淆（A）** |
>   | `stock_dividend` | `return None` 不留 log；另有 TPEX 區間回讀檢查 ✅ | warning | 混淆（A） |
>   | `stock_info` | AttributeError 直接炸 | 無處理 | 失敗會浮出但訊息指不到原因（F-032） |
>   | `financial_statement`（三張全市場） | warning「Cannot get」後 `continue` | warning「No tables found」 | 兩者都只是 warning、都被當成該季無資料（A） |
>   | `financial_statement`（權益變動表） | None／[]／list 三態 ＋ Unreachable 重試 ✅ | ✅ | 正確 |
>   | `monthly_revenue_report` | warning 後 `continue` | 同左 | 混淆（A） |
>   | `finmind` | quota 例外分流 ✅，其餘 `logger.error` 回 None | — | 弱（F-035） |
>   | `stock_tick`／`futures_tick` | Shioaji 例外 `logger.error` 回 None | — | quota 與無資料同型（S10 查 updater 的配額檢查） |
>   | `futures_price` | `if response is None: return None` ＋ `ValueError`（假日）vs `Exception`（真壞）兩段式 ✅ | ✅ | 正確 |
>   | `futures_margin`／`futures_stock_universe` | warning ＋ None | warning（標的清單「沒有假日」故一律 warning）✅ | 正確 |
>   | `futures_chip` | warning ＋ None；HTML 以表頭關鍵字辨識 ✅ | info | 正確，但「被擋 vs 沒資料」仍推給 updater（F-036） |
>
> - **重點 3（來源變動偵測）**：期貨線用欄名辨識表格、`converters` 保留字串、`keep_default_na=False`；台股線的 `read_html(...)[0]`／`[-1]` 是位置索引，表頭變了會靜默錯位——但 S8 的 cleaner 有欄位對照，由 S8 判是否擋得住。
> - **重點 4（落檔命名）**：crawler 一律不落檔，CSV 由 cleaner 寫（27 處 `to_csv`），`{exchange}_{YYYYMMDD}.csv` 慣例是否一致歸 S8。
> - **重點 5（基底）**：`BaseDataCrawler.crawl(*args, **kwargs)` 無約束力，5 支的 `crawl()` 是空殼（F-033）。

### S8. `pipeline/cleaners` 健檢 ✅

- **目的**：13 個 cleaner 是「資料被寫錯但完全不報錯」的高風險層。`154f78c` 的 PCR 事故正是清洗沒改到來源日期，整批被寫成同一個主鍵。
- **做法**：逐檔確認四件事，並**特別對每個 cleaner 追問「日期欄位從哪來」**：
  1. **來源日期**：取自檔名、表頭還是內容？多檔合併時每列日期會不會全部取到同一個值（`154f78c` 型態）。
  2. **主鍵完整性**：以實資料跑 `df.duplicated(subset=主鍵).sum()`。
  3. **型別與單位**：張／股、元／千元、百分比／小數；`NaN`、`--`、全形符號、千分位逗號的處理。
  4. **列數守恆**：清洗前後列數差異是否可解釋。
  另檢查 `futures_margin_cleaner.py`（879 行）與 `financial_statement_cleaner.py`（615 行）是否已混入 loader 職責（C 級）。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_futures_price_cleaner.py tests/test_stock_margin_cleaner.py tests/test_stock_dividend_cleaner.py tests/test_financial_statement_cleaner_equity_change.py -q` 通過；13 個 cleaner 每個有「日期來源」與「主鍵唯一性」兩行結論。
- **相依**：S7。
> **✅ 完成紀錄（2026-09-02）**
> - 13 檔逐檔；`pytest tests/test_futures_price_cleaner.py tests/test_stock_margin_cleaner.py tests/test_stock_dividend_cleaner.py tests/test_financial_statement_cleaner_equity_change.py -q` 38 passed。
> - **DB 實測**（`tw_stock.db` 唯讀）：13 張表全部有 `PRIMARY KEY`；`price`／`chip`／`margin`／`dividend` 近 60 天（2026-07-01 起）重複主鍵 0；`price` 同日同代號跨市場重複 0（PK 含 `證券名稱` 允許但目前沒有）。**`price` 表 6,247,050 列中 104,046 列 OHLC 全為 0**（`成交股數=0` 者 96,089 列）→ F-037。
> - 13 支逐支結論（日期來源／主鍵去重／欄位數防線）：
>
>   | cleaner | 日期來源 | 主鍵去重 | 版面改制防線 |
>   |---|---|---|---|
>   | `stock_price` | 呼叫端傳入的查詢日（每次請求一天，正確） | `(date, stock_id, 證券名稱)` keep first | ✗ TPEX 依位置改名無欄位數檢查（F-038） |
>   | `stock_chip` | 查詢日 | 同上 | ✗ `zip(old, new)` 截斷、`df.get(col, 0)` 靜默補 0（F-038） |
>   | `stock_margin` | 查詢日 | `(date, stock_id)` | ✓ 欄位數＋代號 regex |
>   | `stock_dividend` | **列內容**（民國日期，解析失敗列剔除並記數）✓ | `(date, stock_id)` | ✓ 欄位數／欄名對照 |
>   | `stock_tick` | tick 時間戳 | 無（DolphinDB `keepDuplicates=ALL`） | n/a |
>   | `financial_statement` | 呼叫端 year/season（URL 參數）；權益變動表以表頭「民國X年第N季」挑本期 ✓ | 四欄／權益變動表五欄 | 對照表驅動，缺檔靜默降級（F-039） |
>   | `monthly_revenue_report` | 呼叫端 year/month | `(year, month, stock_id, 公司名稱)` | 對照表驅動（F-039） |
>   | `finmind` | API 回傳的 `date` 欄 | 各表主鍵 | ✓ 必要欄位檢查 |
>   | `futures_price` | 查詢日（POST form；TAIFEX 對無效日期回無表格而非最新日）✓ | `(date, product, expiry, session)` | ✓ 欄位數 |
>   | `futures_chip` | **CSV 內容的日期欄**（`154f78c` 修後）✓ | 三表各自主鍵；主鍵空值列剔除 ✓ | ✓ 表頭欄名 |
>   | `futures_stock_universe` | 執行日＝快照日（設計如此） | `(snapshot_date, product_id)` | ✓ 欄位數 |
>   | `futures_tick` | tick 時間戳；session 由時間判定 | 無 | n/a |
>   | `futures_margin` | **CSV 內「更新日期」逐段解析** ✓；公告用標題生效日（F-041） | `(effective_date, product)` | ✓ 表頭＋分家族乘數比例檢查 |
>
> - 型別與單位：張／股、元、比例（`13.50%` → `0.1350`）的換算都在 cleaner 內集中處理；`NaN` 政策分兩派——股票類 `fill_nan(0)`（margin 的餘額 0 有意義、**price 的 0 價沒有意義**，F-037），期貨類一律保留 NaN → NULL（正確）。
> - 列數守恆：股票類清洗只做 drop_duplicates 與去掉合計列，前後列數差可解釋；`stock_dividend` 對無效價格列有計數 warning；`futures_chip` 對檔尾說明列以主鍵空值濾掉並說明理由。
> - 職責混雜：`futures_margin_cleaner`（879 行）雖大但仍只做解析與落檔，沒有寫 DB；`financial_statement_cleaner` 亦然。不需拆。

### S9. `pipeline/loaders` 健檢 ✅

- **目的**：21 個 loader 是 [ETL 入庫約定 §三](../pipeline/etl-ingestion.md) 三個必守性質的落點，且已有一次「入庫失敗被降級成 warning、行程回報成功、缺 1,553 列」的實際損失。
- **做法**：
  1. **冪等**（§3.1）：`INSERT OR REPLACE`／`ON CONFLICT` 還是先 `DELETE`；主鍵是否涵蓋所有維度（含市場欄，§4.4）。
  2. **失敗浮出**（§3.2）：`core/` 91 處 `except Exception` 中屬 loader 者逐處判斷——吞掉後回傳什麼、上游會不會照樣印成功；`DataLoadError` 是否已普及。
  3. **交易邊界**：38 處 `.commit()` 是逐列、逐檔還是逐批；中途失敗時已 commit 的部分算什麼狀態。
  4. **批次寫入**：8 處 `to_sql` 的 `chunksize` 與 `if_exists`；`if_exists="replace"` 出現在任何增量 loader 都是 A 級。
  5. **連線與資源**：例外路徑上連線是否關閉。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_loader_failure_reporting.py tests/test_batched_loading.py tests/test_futures_price_loader.py tests/test_finmind_reference_table_loader.py -q` 通過；21 個 loader 每個有「冪等機制」與「失敗回傳」兩行結論。
- **相依**：S8。
> **✅ 完成紀錄（2026-09-02）**
> - 21 檔逐檔（含 `shared/base_loader.py`、`utils/sqlite_utils.py`、`utils/exceptions.py`）；`pytest tests/test_loader_failure_reporting.py tests/test_batched_loading.py tests/test_futures_price_loader.py tests/test_finmind_reference_table_loader.py -q` 38 passed。
> - **冪等機制**逐支：`INSERT OR IGNORE`（`insert_dataframe()`）— chip／margin／fs／futures_price／futures_stock_universe／futures_chip／futures_margin（一覽表）；`INSERT OR REPLACE` — dividend（跨來源合法重疊）、futures_continuous（衍生表，重建應覆蓋）、futures_margin 公告（公告比一覽表權威）；**預載主鍵＋`to_sql(append)`** — price、mrr、finmind 四表（F-044）；DolphinDB `loadTextEx`／`PartitionedTableAppender` — tick ×2。`if_exists="replace"` **0 處**。主鍵皆含所有維度（含市場欄的替身 `證券名稱`，F-048）。
> - **失敗回傳**逐支：走 `finish_load()`（失敗→`DataLoadError`）— chip、margin、dividend、fs、mrr、futures_price、futures_stock_universe（7 支）；回傳寫入列數、sqlite 例外直接上拋 — futures_chip、futures_continuous、futures_margin（3 支，可接受）；**失敗被吞** — `stock_price_loader`（F-043）、finmind 三條路徑（F-045）、tick ×2（F-046）。
> - **交易邊界**：sqlite loader 一律每個 `add_to_db()`（＝ updater 的一批）commit 一次；中途炸掉最多損失本批，且重跑靠 `INSERT OR IGNORE` 接續——除了 price／finmind（靠預載主鍵過濾，重跑也安全但慢）。`futures_chip`／`futures_margin` 以「寫入前後 `COUNT(*)` 差」算新增列數，比 `rowcount` 準。
> - **連線與資源**：所有 sqlite loader 在 `add_to_db()` 收尾 `disconnect()`；例外路徑上 `finish_load()` 前已 `disconnect()`，連線不會洩漏。`FuturesTickLoader` 連不上 DolphinDB 留 `session=None` 只保中繼檔（設計正確）。
> - `DataLoadError` 由誰接：updater 全部**不接**（直接上拋），由 `tasks/update_db.py` 統一處理——是否真的變成非零結束碼歸 S15。

### S10. `pipeline/updaters`＋`pipeline/utils` 健檢 ✅

- **目的**：20 個 updater 是排程實際呼叫的入口，錯的代價是「以為每天有更新、其實缺一段」。已知 5 處 `datetime.date.today()` 預設參數缺陷即在這層。
- **做法**：
  1. **日期區間**：起訖含不含端點、`today()` 的取用時機（S2 的 B008）、跨午夜排程、回補與日常更新是否走同一條路徑（§4.3 的事故：修好可見度反而讓日常更新每天失敗）。
  2. **交易日判定**：是否呼叫 `utils/time.py` 而非自行判斷週末（§3.3）。
  3. **斷點續跑**：中斷後重跑只補差集嗎；「連續 N 筆無資料」的早退條件是否會靜默漏抓（§4.5，權益變動表曾漏 323 檔）。
  4. **結束碼與統計行**：全部成功／部分失敗／全部失敗三種情形的輸出與 exit code。
  5. `pipeline/utils/`：`sqlite_utils.py`／`data_utils.py`（361 行，含 4 處 B006）／`url_manager.py`／`stock_tick_utils.py` 逐檔過五問。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_futures_price_updater.py tests/test_finmind_broker_trading_batch.py -q` 通過；20 個 updater 每個有「重跑行為」與「失敗結束碼」兩行結論。
- **相依**：S8、S9。
> **✅ 完成紀錄（2026-09-02）**
> - 26 檔逐檔（20 updater ＋ `pipeline/utils/` 6 檔）；`pytest tests/test_futures_price_updater.py tests/test_finmind_broker_trading_batch.py -q` 通過。
> - **重點 1（日期區間）**：所有 `update()` 起訖含端點。`today()` 只在預設參數（F-002，排程路徑不受影響）。**回補與日常更新走同一條路徑**，且台股四支的起點一律被 `get_actual_update_start_date()` 覆寫為「表內最新日 +1」——呼叫端傳的 `start_date` 只在表為空時生效，**沒有 `resume=False`** 這種往前回補的開關（期貨 price／chip 有）。跨午夜：`update_db.get_time_config()` 每次呼叫取 `today()`，長駐無影響。
> - **重點 2（交易日判定）**：`utils/time.py` 沒有交易日判定。price／chip **每個曆日都送請求**（含週末，只是多花請求）；margin／futures_price 用 `weekday() >= 5` 跳過週末，並以 `price` 表實際有資料的週末當**補班日例外**——這不是 §3.3 禁止的「用非週末近似交易日」（假日仍會送請求、由回應判定），可接受；已知限制是 price 表落後時補班日會被跳過（程式內有註明）。
> - **重點 3（斷點續跑）**逐支：
>
>   | updater | 續跑依據 | 中斷後重跑 | 早退條件 |
>   |---|---|---|---|
>   | `stock_price`／`chip`／`margin`／`dividend` | 表內 `MAX(date)+1` | 只補最新日之後；**中間缺口永不回補**（F-050） | 無 |
>   | `monthly_revenue_report`／`financial_statement`（三張全市場） | `MAX(year, season/month)` 的下一期 | 同上；且 `years × seasons` 用笛卡兒積展開，跨年續跑會漏掉次年前幾期（F-054，下次執行自癒） | 無 |
>   | `financial_statement`（權益變動表） | **逐檔差集**（`get_crawled_stock_ids`）✓ | 只補缺的檔 ✓ | 以 3 檔權值股試探「是否已申報」，不用「連續 N 檔無資料」✓（§4.5 修法） |
>   | `stock_tick` | `tick_metadata.json` 的每檔 `last_date` | `date <= last_date` 一律跳過，**中間缺口永不回補**；Shioaji 例外回 None 被算成 skipped（F-052） | 配額 < 20 MB 停手 |
>   | `futures_price` | **逐商品** `MAX(date)+1`，`resume=False` 可整段回補 ✓ | 空產出重試＋遞增退避；上市日夾住 ✓ | 連續 20 天空產出 **raise**（不是靜默）✓ |
>   | `futures_chip` | 逐表 `MAX(date)` 次日；月批次 ✓ | 「該有交易日卻沒 CSV」判為被擋並重試 ✓ | 三大法人夾到兩年內 ✓；被擋月份只 warning **不列入失敗**（F-053） |
>   | `futures_stock_universe`／`futures_margin`／`futures_continuous` | 快照日／主鍵 IGNORE／整段重建 | 冪等 ✓ | n/a |
>   | `finmind` broker_trading | metadata 的 `(earliest, latest)` 區間 | 區間**內**的缺口被視為已存在（F-055）；quota 用盡等待重試 ✓ | 等待上限 120 分鐘後 `quota_exhausted` 只 warning，`update_all` 仍印「✅ updated successfully」（F-051） |
>
> - **重點 4（結束碼與統計行）**：`tasks/update_db.py` 的 `target_guard` 接 `DataLoadError` 與任何例外 → 記錄後繼續其餘 target，最後 `sys.exit(1)` ✓（S15 再核 CLI 面）。但 updater 自己的收尾只印「Latest available date」，**台股四支沒有 requested／no data／unreachable 統計**（期貨與權益變動表有）——這是 F-030 修法的第三項。
> - **重點 5（`pipeline/utils/`）**：`sqlite_utils.get_table_latest_value()` 把 `sqlite3.Error` 吞成 None（F-056）；`data_utils` 4 處 B006 為唯讀（F-012）；`url_manager` 集中且未知 key 拋錯 ✓；`stock_tick_utils` 的 metadata 讀寫有鎖與原子替換 ✓；`exceptions.py` 只有 FinMind 與 `DataLoadError`，crawler 層沒有自訂例外（F-030 修法需新增）。

---

## Phase 4：`core/` 回測與策略

### S11. `core/managers` 健檢 ✅

- **目的**：3 個檔案 1,191 行，掌管部位進出與帳務，是「算錯錢」的最短路徑。[放空框架 §七](../backtest/short-selling-framework.md) 列了 7 種邊界情況，需逐條確認實作有對應分支。
- **做法**：
  1. 逐條對 §7.1~§7.7：當沖日終未回補、維持率追繳／斷頭、強制回補日與股利補償、部分回補與 FIFO、同標的雙向持倉、成交價合理性（前視偏誤防線）、已知簡化。
  2. `futures/position_manager.py`（553 行）：`FuturesMarginAPI` 查表模式查不到即 raise 的行為、換月時部位的處理。
  3. `stock/position_manager.py`（497 行）：LONG／SHORT 成本口徑是否同一套公式（[多市場引擎 §6.6](../backtest/multi-market-engine.md) 曾有一個未修的口徑缺陷）。
  4. 四捨五入：每一處金額計算與 §6.0 數值處理規則對齊。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/backtest/test_position_manager.py tests/test_futures_position_manager.py tests/test_futures_margin_control.py -q` 通過；§7.1~§7.7 七條每條有「對應實作位置」一行。
- **相依**：S5。
> **✅ 完成紀錄（2026-09-02）**
> - 3 檔 1,191 行逐行；`pytest tests/backtest/test_position_manager.py tests/test_futures_position_manager.py tests/test_futures_margin_control.py -q` 55 passed。
> - **§7.1~§7.7 對應實作位置**：
>
>   | 邊界情況 | 實作位置 | 結論 |
>   |---|---|---|
>   | §7.1 當沖日終未回補（三種政策、漲停鎖死判定） | `settlement_model.py`（`enforce_day_trade_cover`，S12 核） | manager 端無關；`StockPosition.is_day_trade` 由引擎補值 ✓ |
>   | §7.2 維持率追繳／斷頭 | 股票：`settlement_model.py` 用 `StockAccount.get_short_market_value()`（F-021 無報價退回開倉價）；期貨：`FuturesPositionManager.calculate_maintenance_margin()`（查表，查不到退回已繳原始保證金＝偏嚴格）✓ | 期貨側 fallback 方向保守，正確 |
>   | §7.3 停券回補與股利補償 | `settlement_model.py`（S12）；manager 只負責 `close_short_position()` 把 `prop_dividend_compensation` 加回現金流 ✓ | 口徑與 §7.3「除息日扣、平倉加回」一致 |
>   | §7.4 部分回補與 FIFO | `base/position_manager.py:81-141`（FIFO 主幹、方向篩選、平倉量不足只警告）；`stock/position_manager.py:341-483` 等比例攤提；`futures/position_manager.py:433-540` `settled_pnl` 亦等比例 ✓ | 現金流推導：開倉 `balance −= margin + entry_cost`；平倉 `balance += margin + realized_pnl + entry_cost + div_comp` ＝ `margin + proceeds − buyback − close_comm − accrued_fee + interest` ✓ 無雙重扣費 |
>   | §7.5 同標的雙向持倉 | `stock/position_manager.py:156-160` **只在開空時檢查有無多單** | 開多時**不檢查**有無空單（F-057） |
>   | §7.6 成交價合理性 | `fill_model.py`（S12） | manager 端無關 |
>   | §7.7 已知簡化 | — | manager 端與表列一致（LONG 全額現金、無 net position） |
>
> - **`futures/position_manager.py`**：保證金**預設查表、查不到 raise**（與 `FUTURES_MULTIPLIER` 同一原則）✓；`settle_daily()` 對 `settle_price is None`（夜盤）不動作 ✓；平倉損益 ＝ `settled_pnl` 攤提 ＋ 最後一段 − 成本 ✓；`roi` 以保證金為分母 ✓；`record.buy_price` 用 `entry_price` 而非被結算重設的 `price` ✓。**未檢查同契約反向部位**（F-058）。
> - **四捨五入**：手續費／稅／借券費 `int()` 捨去、保證金由 cost model `ceil`、`realized_pnl` `round(2)`，與 §6.0 一致；`prop_margin`／`prop_proceeds` `round(2)` 後逐次扣減，最後一段吃殘差（不會漏也不會多）。
> - **F-020 複核**：三條平倉路徑（`backtester.py:592/616`、`settlement_model.py:430/1104`）全部走 `close_position()`，收尾一律 `remove_closed_positions()`，已平倉部位不會殘留到下一次查詢——F-020 降為 C（`check_has_position()` 與 `get_positions()` 濾法不一致，只是可維護性）。

### S12. `core/backtest/models` 健檢 ✅

- **目的**：`settlement_model.py`（1,219 行）、`cost_model.py`（855 行）、`fill_model.py`（677 行）、`instrument_spec.py`、`sizing.py` 共 3,600 行，是引擎的全部政策。單檔破千行本身就是「職責是否還單一」的問號。
- **做法**：
  1. **對數**：以 [放空框架 §6.1／§6.2](../backtest/short-selling-framework.md) 的兩個手算範例（當沖放空、融券留倉 10 天）逐項驗算成本模型輸出。
  2. **共用狀態**：`new_event_counts()` 的 dict 由引擎、FillModel、SettlementModel **三者共用同一個物件**——確認沒有任何一方重建或覆寫，且 14 個 key 沒有被改名（改名會讓歷史 `*_event_report.csv` 對不上）。
  3. **fill_model**：漲跌停鎖死、成交量上限縮量、成交價合理性三條路徑的優先順序。
  4. **settlement_model**：`mark_position()` 掛點（[多市場引擎〈引擎為期貨補開的唯一掛點〉](../backtest/multi-market-engine.md)）的呼叫時機；期貨每日結算與股票 no-op 的分界。
  5. **sizing**：可開口數／可買張數的下取整與資金不足時的行為。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/backtest/test_cost_model.py tests/backtest/test_fill_model.py tests/backtest/test_position_sizer.py tests/backtest/test_instrument_spec.py tests/test_futures_cost.py -q` 通過；兩個手算範例的每一項與實際輸出相符。
- **相依**：S11。
> **✅ 完成紀錄（2026-09-02）**
> - 5 檔（`instrument_spec`／`sizing`／`cost_model`／`fill_model`／`settlement_model`）逐行；`pytest tests/backtest/test_cost_model.py tests/backtest/test_fill_model.py tests/backtest/test_position_sizer.py tests/backtest/test_instrument_spec.py tests/test_futures_cost.py -q` **96 passed**。
> - **手算範例逐項對數**（直接呼叫 `StockCostModel`）：§6.1 當沖 100→95：手續費 42／稅 150／回補手續費 40／損益 4,768／ROI 4.76% ✓；§6.2 融券 10 日：券費 80／保證金 90,000／利息 10／損益 4,548／ROI 4.53%／資金效率 5.03% ✓；§6.0 保證金浮點消誤差 `ceil(round(33.33×1000×0.9, 6))` ＝ 29,997 ✓。取整規則（費用 `int()` 捨去、保證金進位、損益 `round(2)`）與 §6.0 一致。
> - **`event_counts`**：`new_event_counts()` 定義 14 個 key，grep 各 model／引擎實際寫入 15 個——多出的 `rolled_contract` 由期貨結算模型以 `.get(key, 0) + 1` 動態加入（程式已註明），reporter 以 `items()` 全量輸出不會漏；14 個既有 key 全部有寫入端、無孤兒 ✓。
> - **`fill_model`**：三條路徑順序為 券源 → 滑價 → 成交量上限（`fill()`），`validate()` 另走 區間 → 漲跌停 → 檔位（只警告）；`fill()` 未調整時回傳原物件、調整時 `copy.copy()`，策略持有的 order 不會被就地改 ✓。`validate()` 檢查的是**滑價前**的 `order.price`，滑價後的成交價是否可能落到區間外／漲跌停外，見 S13 引擎端（F-064）。期貨 model 不做漲跌停與券源 ✓、滑價 tick 優先於 bps ✓。
> - **`settlement_model`**：台股順序 當沖回補 → 無報價天數 → 計提 → 股利補償 → 追繳 ✓（股利先於回補，避免回補日＝除息日少扣）；期貨順序 結算 → 換月 → 到期出場 → 追繳 ✓（每輪重取部位、平不掉即停）。`mark_position()` 現金帳戶口徑（LONG 市值、SHORT 保證金＋未實現）與期貨口徑（保證金＋未結算損益）分開 ✓。`get_mark_price()` 與 `update_no_quote_days()` 都把 `close`／`cur_price` 為 0 視為**無報價**（退回前收 → 開倉價；累計 no_quote_days）——這是 F-037 降級的依據。
> - **`sizing`**：`int()` 捨去、至少 1 張、`ref_price <= 0` 跳過 ✓；分母是 `balance` 不是權益（刻意，與 baseline 綁定）。
> - **`instrument_spec`**：漲停捨去／跌停進位方向正確；2015-06-01 前 7% 分段 ✓；期貨 `to_units()` 不乘乘數（乘數走 `FuturesPosition.multiplier`）✓。

### S13. 引擎＋datafeed＋report 健檢 ✅

- **目的**：引擎本體 687 行加 datafeed 5 檔、report 4 檔。bar 內委託順序與前視偏誤防線是回測可信度的根；`reporter.py` 覆蓋率僅 38%，且回歸雙線不經過它（[多市場引擎 §6.2](../backtest/multi-market-engine.md)），等於報表層沒有護欄。
- **做法**：
  1. **bar 內順序**：對照 [多市場引擎 §2.2.1](../backtest/multi-market-engine.md) 宣告的委託順序逐行核（§6.3 記錄過「既有測試沒有釘住結算動作的執行順序」）。
  2. **前視偏誤**：當日訊號用到當日什麼價？`adjusted_price` 預設在 factory 為 True、引擎為 False 的雙預設是否會被誤用。
  3. **datafeed**：`market_calendar.py`／`futures_calendar.py` 的交易日與夜盤定義、`futures_roll.py` 換月價差處理、連線唯一性。
  4. **report**：報表指標公式（年化、回撤、勝率、Sharpe）逐條核；`futures_reporter` 與 `reporter` 的重複實作程度（C 級）。
- **產出**：〈附錄 A〉。
- **驗證方式**：`./scripts/run_regression.sh` 通過；`pytest tests/backtest/ tests/test_futures_calendar.py tests/test_futures_roll_backtest.py tests/test_futures_continuous.py -q` 通過；§2.2.1 的順序逐項有對應行號。
- **相依**：S12。
> **✅ 完成紀錄（2026-09-02）**
> - 逐行：`backtester.py`（687）、`factory.py`、datafeed 5 檔、report 3 檔、analysis 2 檔。驗證：`pytest -m "not slow" tests/backtest/ tests/test_futures_calendar.py tests/test_futures_roll_backtest.py tests/test_futures_continuous.py -q` **233 passed**；回歸雙線 `tests/backtest/test_short_regression.py` **6 passed**、`tests/backtest/test_long_regression.py` **1 passed（16 s）**（兩者即 `scripts/run_regression.sh` 的內容，改以 scratchpad 外掛隔離 loguru sink 執行，避免 F-001 污染 `logs/`）。
> - **§2.2.1 三層順序 → 行號**：第一層 `BarExecutionOrder` → `backtester.py:457-462`（推導表在 `:169-207`）；第二層 停損 → 重掃剩餘部位 → 一般平倉 → `:570-618`；第三層 `sort_orders()` 依 `(date, symbol)` 穩定排序 → `:301`，開倉腿在方向驗證 → 補值 → 排序 → `check_max_holdings` → `validate` → `fill` 之後才進 manager（`:480-503`）。結算掛點順序：兩階段之後 `settlement.on_bar_close`（`:467`）→ `snapshot_daily_equity`（`:469`，因此權益快照已含強制回補）→ `update_prev_close`（`:471`，快照期間的無報價 fallback 仍是「昨收」）✓。§6.3 的「當沖回補 vs 每日檢查對調」仍只由 SHORT baseline 的 `day_trade_on_force_cover_date` 情境釘住，未變。
> - **前視偏誤**：訊號與成交都用當根 bar（收盤決策、收盤成交的假設）；`adjusted_price` 只掛在 `adj_close`、OHLC 維持原始價 ✓；factory 預設 True、引擎預設 False 的雙預設由 `run.py:53` 走 factory，實際生效為 True ✓；期貨一律 False ✓。`apply_price_limit_basis()`／`apply_short_balance()` 在任何委託之前 ✓。
> - **datafeed**：台股與期貨各自單一 `sqlite3` 連線、`run()` 正常結束時 `close()` ✓（例外路徑不會關，屬 C，併入 F-067 備註）；`FuturesCalendar` 以行情表為交易日判準、`postpone_to_trading_day` 順延 ✓、`resolve_session` 凌晨 05:00 前歸前一日夜盤 ✓、`get_night_session_date` 取前一交易日 ✓；`FuturesRollPlanner.build_roll_schedule()` 有「不回頭」護欄、`to_open_interest()` NULL → None 不當 0 ✓。
> - **report**：`get_equity_series()` 為唯一權益入口、盯市優先 ✓；MDD ＝ `equity / cummax − 1` ✓；勝率＝`PnL > 0` 筆數／總筆數 ✓；`generate_event_report()` 以 `items()` 全量輸出（含期貨動態加入的 `rolled_contract`）✓；`FuturesBacktestReporter` 只覆寫三處（明細欄位、多空統計、對標序列），其餘沿用，重複度低 ✓。**年化報酬與 Sharpe 在正式報表（reporter）並未輸出**，只有 analyzer 有 Sharpe／Sortino／IR——公式問題見 F-068。
> - 型別小疵（不另開列）：`execute_close_signal()` 無部位時 `return` None，簽章卻是 `List[BaseTradeRecord]`（`backtester.py:564-565`）。

### S14. `core/strategies` 健檢 ✅

- **目的**：11 檔 1,946 行。`strategy_loader.py` 與 `overnight_lead_event_strategy.py` 覆蓋率均為 0，而策略是唯一由外部（`run.py --strategy`）動態載入的層。
- **做法**：
  1. `base.py`／`stock/base.py`／`futures/base.py`：契約是否一致；`market`＋`instrument_type` 兩個分派鍵是否每個策略都正確宣告（factory 分派依賴它）。
  2. `strategy_loader.py`：動態載入的失敗行為——類名打錯、模組 import 失敗、同名策略各自回什麼。
  3. 三支股票策略＋一支期貨策略：class docstring 的「買進／賣出／停損」三區塊是否與實作一致；未實作的停損是否明寫（`CLAUDE.md` §2.2）。
  4. 策略是否只透過 `setup_apis(data_feed)` 取數、沒有自建連線（`tests/test_strategy_data_access.py` 已釘住此性質，確認涵蓋所有策略）。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_strategy_data_access.py tests/test_futures_strategy.py tests/test_foreign_sell_short_day_trade_strategy.py -q` 通過；每支策略的 docstring 與實作逐條對齊。
- **相依**：S13。
> **✅ 完成紀錄（2026-09-02）**
> - 11 檔 1,947 行逐行；`pytest tests/test_strategy_data_access.py tests/test_futures_strategy.py tests/test_foreign_sell_short_day_trade_strategy.py -q` **58 passed**；`StrategyLoader.load_strategies()` 實際載入 4 支：`ForeignSellShortDayTradeStrategy`、`MomentumFuturesStrategy`、`MomentumStrategy1`、`OvernightLeadEventStrategy`。
> - **契約與分派鍵**：`BaseStrategy` 不設 `market`／`instrument_type`，由 `BaseStockStrategy`（TW＋STOCK）與 `BaseFuturesStrategy`（TW＋FUTURE）填入，策略本身不需設定 ✓；`factory.build_backtester()` 以兩欄位組合分派 ✓；`BaseFuturesStrategy.max_holdings = None` 解除引擎檔數上限（因 `BaseStrategy` 預設 0 會擋掉所有開倉，見 F-076）✓。三個基底的抽象方法對齊（`setup_account`／`setup_apis`／`check_open_signal`／`check_close_signal`／`check_stop_loss_signal`／`calculate_position_size`）✓。
> - **docstring vs 實作**：
>
>   | 策略 | 買進／賣出（開倉）條件 | 賣出／回補條件 | 停損 |
>   |---|---|---|---|
>   | `MomentumStrategy1` | 昨收漲幅 ≥ 9%、量 ≥ 5,000 張 ✓（`:96-107`） | 報價日 ≥ 開倉日＋1 曆日 ✓（`:127`） | 「未實作」✓ |
>   | `ForeignSellShortDayTradeStrategy` | T−1 外資賣超 ≥ 1,000 張、T−1/T−2 漲幅 **>** 8%、T−1 量 ≥ 1,000 張、開盤價 > 0 ✓（`:341-370`） | 當日收盤回補、疑似鎖漲停不送單、留倉改開盤價 ✓（`:405`、`:522-526`） | 「刻意不做」＋實測表 ✓ |
>   | `OvernightLeadEventStrategy` | pred > 0 做多 2330 ✓ | pred ≤ 0 出場 ✓ | 未寫「停損條件」區塊（英文 docstring，不符 `CLAUDE.md` §2.2 三區塊格式）→ 併入 F-072 |
>   | `MomentumFuturesStrategy` | 近月、昨收漲幅 ≥ 1%、無部位 ✓（`:78-88`、`:116-117`） | 持有 ≥ 1 曆日 ✓（`:134-138`） | 「未實作」✓ |
>
> - **資料存取**：四支都只透過 `setup_apis(feed)` 取用 DataFeed 持有的 API，`grep sqlite3|connect(|API()` 在 `core/strategies/` 無命中 ✓；但 `OvernightLeadEventStrategy` 在**建構時**直接 `yf.download()` 打網路，且此時 `self.price` 尚未注入（F-072）。`tests/test_strategy_data_access.py` 釘住的是「策略層不得出現資料庫欄位字面值」（`PriceColumn`／`ChipColumn` 逐一 parametrize），**不是**「不自建連線」——文件 S14 做法第 4 點的描述有誤，已改記為 F-074。
> - **入口退出碼（供 S15）**：`python run.py --strategy NotExist` → exit 0；`--mode live` → exit 0（空實作）。

---

## Phase 5：入口與應用層

### S15. `run.py`＋`tasks/` 健檢 ✅

- **目的**：`run.py`（60 行）與 `tasks/`（6 檔 979 行）是**人與排程實際觸碰的兩個入口**，其中 `tasks/update_db.py`（527 行）掌管所有 ETL 的 `--target` 分派，`tasks/delete_price_data.py` 與 `tasks/migrate_db_naming.py` 則是**會直接刪改資料庫的破壞性腳本**，風險等級高於一般模組。
- **做法**：
  1. **`run.py`**：策略名找不到時只 `print` 後 `return`（退出碼 0）——排程包起來時分不出「跑完了」與「策略名打錯」，屬 A 級候選；`--mode live` 目前是 `pass`（空實作），確認是否會讓人誤以為已支援實盤。
  2. **`tasks/update_db.py`**：`--target` 對照表與實際 updater 是否一一對應（有沒有列在說明卻不存在、或存在卻沒列）；預設 `no_tick` 的涵蓋範圍；多目標時**其中一個失敗會不會讓其餘照跑並回報成功**；`DataLoadError` 的攔截點與最終 exit code。
  3. **破壞性腳本三支**：`delete_price_data.py`（99 行）、`migrate_db_naming.py`（151 行）、`load_broker_trading_to_db.py`（35 行）——有無 dry-run／確認提示、是否先備份、失敗時資料庫停在什麼狀態、能否重跑；`tasks/` 的 3 處 `sqlite3.connect` 是否繞過 `core/api` 直連（C 級，但影響 PostgreSQL 遷移面）。
  4. **`clean_logs.py`**（166 行）：刪除條件與保留天數，會不會刪到還需要的日誌。
- **產出**：〈附錄 A〉。
- **驗證方式**：`python run.py --strategy NotExist; echo $?` 觀察退出碼；`python tasks/update_db.py --help` 的 target 清單與程式碼 grep 結果逐項比對；三支破壞性腳本各有一行「重跑安全性」結論。
- **相依**：S10、S14。
> **✅ 完成紀錄（2026-09-02）**
> - `run.py`（60）＋ `tasks/` 5 檔 978 行逐行。實測：`python run.py --strategy NotExist; echo $?` → **0**；`python run.py --mode live --strategy MomentumStrategy1` → **0**（`pass`）。`python tasks/update_db.py --help` 列出 21 個 target（19 個資料類型＋`all`／`no_tick`），與 `main()` 的 19 個 `if … in targets` 分支及模組 docstring 的「Target 對照表」逐項對上，無「列了不存在」或「存在沒列」。
> - **`update_db.py` 失敗路徑**：每個 target 包在 `target_guard()` 內，`DataLoadError` 與一般 `Exception` 都只記錄並繼續，最後有任一失敗即 `sys.exit(1)` 並列出成功／失敗清單 ✓；`KeyboardInterrupt` 不被 `except Exception` 吞掉 ✓。`FinMindUpdater()` 在 `finmind`＋4 個子 target 各自建構一次（`--target finmind stock_info` 會開兩條連線），屬 C，併入 F-078 備註。
> - **三支破壞性腳本的重跑安全性**：
>
>   | 腳本 | dry-run／確認 | 備份 | 失敗時 DB 狀態 | 重跑 |
>   |---|:---:|:---:|---|---|
>   | `delete_price_data.py` | 無／無 | 無 | `sqlite3.Error` 時 `rollback()`，其餘例外未接（連線在 `finally` 關閉）| 冪等（第二次 0 筆）；但日期格式錯誤時 log error 後 **exit 0** |
>   | `migrate_db_naming.py` | `--dry-run` ✓ | 只備份 `futures.db`（`stock.db` 只改檔名）✓ | 欄位改名 commit 後才改檔名，中途失敗留下「欄位已改、檔名未改」，但兩步都冪等 ✓；目標檔已存在時 `raise` 不覆蓋 ✓；改名前後列數比對 ✓ | 可重跑 ✓（現況 DB 已是 `tw_*.db`，腳本已無事可做） |
>   | `load_broker_trading_to_db.py` | 無（走 loader 的 `INSERT OR IGNORE`）| — | 例外 re-raise → exit 1 ✓ | 冪等 ✓ |
>
> - `tasks/` 的 3 處 `sqlite3.connect`：`delete_price_data.py:45`、`migrate_db_naming.py:39`／`:58`，皆繞過 `core/api`（遷移腳本可接受；刪除腳本應改走 API 或至少共用 `TW_STOCK_DB_PATH` 的連線工具）。
> - **`clean_logs.py`**：預設只預覽、`--apply` 才刪 ✓；只挑檔名帶時間戳的輪替檔、現用檔不動 ✓；以 mtime 判斷 ✓。注意 `pipeline` 桶的統計行（F-050 的缺口分析要回頭讀）也在預設 30 天清理範圍內，若要靠它做缺口稽核需把該桶的保留期拉長或改讀 DB。

### S16. `frontend/` 健檢 ✅

- **目的**：6 檔 884 行（`app.py` 637 行）。前端讀的是 `results/` 底下的 CSV，與 `core/backtest/report/` 的輸出欄位**隱性耦合**——報表改欄位不會有任何測試爆掉，只會在畫面上顯示錯的數字或整頁壞掉。
- **做法**：
  1. **契約耦合**：`services/report_loader.py` 讀哪些檔名與欄位，與 `reporter.py`／`futures_reporter.py` 實際輸出逐欄比對；缺檔或缺欄時是明確報錯還是畫出空圖。
  2. **指標重算**：`services/futures_metrics.py`（159 行）有沒有**自己重算一次**回測指標——若有，公式必須與 `core/backtest/report/` 同源，否則前端與報表兩個數字會不一致（A 級）。既有 `tests/test_frontend_futures_metrics.py` 涵蓋到哪。
  3. **路徑與環境變數**：`config.py` 的 `ALPHAEDGE_BACKTEST_RESULTS` 在本機、Docker、compose 三處的預設是否一致（對照 `docker-compose.yml` 掛載 `alphaedge_results:/results`）。
  4. **`app.py` 637 行**：是否已混入資料處理職責（C 級）；有無直接讀 DB 而非讀報表。
  5. `frontend/SKILL.md` 與 `README.md` 的敘述是否仍與程式一致（併入 S21 處理）。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pytest tests/test_frontend_futures_metrics.py -q` 通過；報表欄位與前端讀取欄位的對照表無缺口。
- **相依**：S13。
> **✅ 完成紀錄（2026-09-02）**
> - 6 檔 884 行逐行；`pytest tests/test_frontend_futures_metrics.py -q` **7 passed**（只涵蓋 `services/futures_metrics.py`）。
> - **報表 → 前端契約對照**：
>
>   | 報表輸出（`reporter.py`／`futures_reporter.py`） | 前端讀取（`config.py`／`report_loader.py`） | 結論 |
>   |---|---|---|
>   | `{name}_trading_report.csv` | `*trading_report.csv` ✓ | 讀到；缺檔時 `st.error`＋`st.stop()`（明確）✓ |
>   | `{name}_balance_curve.png`／`_networth.png`／`_mdd.png`／`_everyday_profit.png` | 四組 glob 候選 ✓ | 讀到；缺圖時 `st.warning`（明確）✓ |
>   | `{name}_everyday_equity_change.png`（盯市口徑） | — | **未讀**（F-084） |
>   | `{name}_daily_equity.csv`（盯市權益，MDD／Sharpe 應以此為準） | — | **未讀**，前端改由交易明細自算（F-082） |
>   | `{name}_direction_summary.csv`、`{name}_event_report.csv` | — | **未讀**（放空尾部風險計數在前端看不到，F-084） |
>   | 欄位 `ROI`（**已是 %**，`cost_model.roi()` ×100 後 round 2） | `avg_roi = roi.mean() * 100` | **再乘 100**（F-082） |
>   | 欄位 `Exit Date`（平倉日，reporter 以此排序） | 前端用 `Sell Date` 排序與分組 | SHORT 的 `Sell Date` ＝ 開倉日（F-082） |
>   | 缺欄時 | `_to_numeric()` 回空序列、指標顯示 0.0／N/A | **靜默**：欄位改名只會讓數字變 0，不會報錯（正是本步驟擔心的隱性耦合） |
>
> - **指標重算（S16 做法第 2 點）**：`app.py` 自己算 勝率／總損益／平均 ROI／Sharpe／Sortino／IR，公式與 `core/backtest/report/`**不同源**——reporter 的權益口徑是盯市 `daily_equity`、以 `Exit Date` 排序；前端是已實現累積餘額、以 `Sell Date` 分組、`ddof=0`、`√252` 年化；`futures_metrics.summarise_margin()` 的 `平均保證金報酬率` 用 `roi.mean()` 沒有再 ×100，同一頁兩個 ROI 口徑互相矛盾。
> - **路徑與環境變數**：`core/config/paths.py:63` 為 `ALPHAEDGE_RESULTS_DIR` → `PROJECT_ROOT/results`（執行期產物已於 2026-08 移出 `core/`）；`frontend/config.py:5-6` 預設 `core/backtest/results`（**目錄已不存在**）、環境變數名 `ALPHAEDGE_BACKTEST_RESULTS`；`docker-compose.yml` 後端掛 `alphaedge_results:/app/results`、前端設 `ALPHAEDGE_BACKTEST_RESULTS=/results` 並掛 `/results`——Docker 內一致，**本機不設環境變數即整頁「找不到任何回測結果資料夾」**（F-083）。
> - **`app.py` 職責**：637 行中約 190 行是 CSS、約 130 行是指標計算（`_extract_daily_returns`／`_calc_*`／`_extract_starting_capital`／`_extract_backtest_date_range`），與 `services/futures_metrics.py` 的「純計算放 services 才測得到」原則相反（F-085）；不直接讀 DB ✓。`frontend/SKILL.md`／`README.md` 的敘述併入 S21。

### S17. `strategy_lab/` 健檢 ✅

- **目的**：14 檔 3,879 行，是**最容易與主線口徑分岔**的地方——研究腳本常自己寫一份簡化的成本／滑價／部位邏輯，結論卻被拿來決定要不要把策略搬進 `core/strategies/`。分岔的代價是「研究說會賺、上線後不賺」。
- **做法**：
  1. **口徑一致性**：`tsmc_overnight_signal/pipeline.py`、`tech_new_high_continuation/analysis.py` 內的成本、滑價、部位大小、進出場時點，逐項與 `core/backtest/models/` 對照，列出每一處差異並判斷是否為刻意簡化；**差異必須寫在該研究的 README，否則屬 A 級**（結論會被誤用）。
  2. **前視偏誤**：研究腳本是否用到了當日收盤後才知道的資訊做當日決策；`sanity_checks.csv`、`ic_pnl_gap.csv` 這類既有輸出說明了什麼。
  3. **可重現性**：8 處 `sys.path.insert` 是否仍必要；隨機種子、資料區間、參數是否寫進 `run_meta.csv`；重跑會不會得到不同數字。
  4. **目錄規範**：對照 `strategy_lab/CLAUDE.md` 的分類決策與硬性規則，確認 `data_analysis/` 與 `strategies/` 的歸類正確、`output/` 未進版控。
  5. **與 `core/` 的相依方向**：只能 `strategy_lab` → `core`，不得反向（S3 的腳本會抓）。
- **產出**：〈附錄 A〉；每個研究一份「與主線口徑差異表」。
- **驗證方式**：兩個研究各有一份差異表且無「未說明的差異」；`ruff check strategy_lab` 無新增問題。
- **相依**：S13。
> **✅ 完成紀錄（2026-09-02）**
> - 14 檔 3,879 行逐行（`pipeline.py` 1,077、`analysis.py` 346、兩支 `run.py`、兩支 `generate_docx.py`、`docx_append.py` 1,360 只核成本敘述）；`ruff check strategy_lab` **All checks passed**；`sys.path.insert` 實為 **4 處**（文件原估 8），全部有 `if not in sys.path` 護欄，只在「以路徑執行腳本」時需要（`python -m strategy_lab.…` 可省）。
> - **`tsmc_overnight_signal` 與主線口徑差異表**（主結果路徑 ＝ `run_backtest_with_signal()`）：
>
>   | 項目 | 研究（realistic 路徑） | 研究（vectorized 診斷路徑） | `core/backtest/models` | README 是否說明 |
>   |---|---|---|---|:---:|
>   | 手續費 | `StockUtils.calculate_transaction_commission()`（0.1425%×0.3、最低 20）✓ 同源 | 固定 `FEE_BUY = 0.001425`（無折扣、無最低費）| `CostConfig`：0.1425%×0.3、最低 20 | **否**——README §1／§4.1 只寫 0.1425%，那是診斷路徑的數字（F-086） |
>   | 證交稅 | `StockUtils.calculate_transaction_tax()` ✓ | 0.3% 併入 `FEE_SELL_PLUS_TAX` | 0.3% | 是 |
>   | 滑價／量上限 | 無 | 無 | `FillConfig` 預設關閉 | 是（§7 執行假設） |
>   | 部位大小 | 全額整張、扣不起手續費就減一張直到買得起 | 100% 名目 | `EqualWeightSizer`：`int(balance / (price×1000))`，manager 再以「現金 ≥ 價金＋手續費」擋單 | 否（F-087） |
>   | 進出場時點 | 收盤決策、收盤成交（訊號來自前一美股交易日）| 同左 | 引擎同一根 bar 收盤成交 | 是 |
>   | 價格還原 | 2330 用 DB 原始收盤；美股特徵 `auto_adjust=True` | 同左 | `adjusted_price=True` 只影響 `signal_close` | 是（`sanity_checks.csv`） |
>   | 資料截止 | `data_end = today`（每次跑不同）| 同左 | `MODEL_DATA_END = 2026-04-25` 寫死 | `run_meta.csv` 有記 `data_end_requested` ✓；兩版不同（F-087） |
>
> - **`tech_new_high_continuation` 差異表**：純統計研究、無成本／滑價／部位；創高判定 `cummax().shift(1)` 嚴格前視安全 ✓；`fwd_close_{n}d` 只用於評估 ✓；未還原價（報告結論已列）✓、產業分類為最新快照（已列）✓；**存活者偏差未列**（universe 取自現行 `taiwan_stock_info`，已下市者不在樣本）；`END_DATE = 2026-05-26` 寫死；`load_price_panel()` 以 `price_api.conn` 直接下 SQL 並引用欄位字面值 `最高價`／`收盤價`（F-088）。
> - **前視偏誤**：`fetch_panel()` 對每個台股交易日取「嚴格早於該日的最後一個美股交易日」✓，且 `placebo_feature_shift_ic()` 以 ±1 列錯位的 IC 崩塌驗證對齊（`placebo_ic_alignment.csv`）；`sanity_checks.csv` 六項（前視、IC 量級、對齊安慰劑、現金缺口、存活者、還原價）與 `ic_pnl_gap.csv`（訊號想做多卻因整張＋手續費空手的比例）都是解讀高 Sharpe 時該一起看的護欄。
> - **可重現性**：無隨機成分；`run_meta.csv` 記 alpha／區間／費率／本金／整張假設 ✓；唯一不可重現來源是 yfinance（資料修訂、`auto_adjust`），README 風險清單已列。
> - **目錄規範**：分類正確（統計研究在 `data_analysis/`、完整 pipeline 在 `strategies/`）；`.gitignore` 有 `strategy_lab/**/output/`，但 `git ls-files` 顯示 13 個 `output/*.html` 已被追蹤（規則加入前就 commit 了）（F-088）；`reports/*.docx` 進版控符合規則 ✓。相依方向只有 `strategy_lab → core` ✓（S3 腳本會抓反向）。

### S18. `scripts/` 與一次性工具健檢 ✅

- **目的**：6 個檔案（3 個 `.py` 599 行 ＋ `run_regression.sh`、兩支 `clean_pycache`）。其中 `fix_price_etf_stock_id.py`（153 行）與 `dataframe_dot_to_bracket.py`（348 行）看起來是**一次性修復／改寫工具**——留著而沒有標註適用條件的一次性腳本，日後被誤跑會直接改壞資料或程式碼。
- **做法**：
  1. 每支腳本回答三題：**還需要嗎**（已完成的一次性任務應刪除或移進 `docs/` 附錄）、**誤跑會怎樣**（是否有 dry-run／備份／確認）、**還能跑嗎**（依賴的欄位／路徑是否還存在）。
  2. `fix_price_etf_stock_id.py`：1 處 `sqlite3.connect` ＋ 1 處寫回，確認是否直接改 production DB。
  3. `run_regression.sh`：`set -euo pipefail` 已有；確認 venv 判斷與「LONG 線需要 `data/db/stock.db`」的路徑名稱是否與現行 DB 檔名一致（現有檔案為 `tw_stock.db`／`tw_futures.db`，**腳本註解寫的是 `stock.db`，需確認何者為準**）。
  4. `generate_docs.py`（98 行，含 1 處 F841）：產出的文件是否還有人用。
- **產出**：〈附錄 A〉；每支腳本一行「保留／刪除／加註警語」的判定。
- **驗證方式**：`./scripts/run_regression.sh` 實跑通過；每支腳本的判定都已寫入附錄 A。
- **相依**：S1。
> **✅ 完成紀錄（2026-09-02）**
> - `scripts/` 現有 8 個檔案（原 6 個＋S3 新增的 `check_layer_deps.py`＋本清單）。逐支判定：
>
>   | 腳本 | 還需要嗎 | 誤跑會怎樣 | 還能跑嗎 | 判定 |
>   |---|---|---|---|---|
>   | `fix_price_etf_stock_id.py`（153） | 是：`price` 主鍵含 `證券名稱` 的結構性問題仍在（見 docstring），6201／6202 可能再被舊資料覆寫 | 直接改 production `tw_stock.db`，但有 `--dry-run`、撞鍵即中止、交易包 `BEGIN…rollback`、冪等 | 能（欄位／路徑仍存在） | **保留**；加一行「已於何時執行過」到 docstring |
>   | `dataframe_dot_to_bracket.py`（348） | 否：`df.col → df["col"]` 的 codemod 已完成（S1 ruff 全綠） | `ROOT = Path(__file__).resolve().parents[2]` ＝ `program_project/`（專案的上一層），會遞迴改寫**同層所有專案**的 `.py`；無 dry-run、無備份 | 能 | **刪除**（F-089） |
>   | `generate_docs.py`（98） | 否：只掃 5 個 API 檔印「已提取」，不寫任何檔案，且清單缺期貨 API | 無害 | 能 | **刪除**（F-091；`docs/api/` 由人工維護） |
>   | `run_regression.sh`（40） | 是 | 無 | 能；實跑 SHORT 6 passed、LONG 1 passed | **保留＋修**：LONG 線 `skipif` 時仍 exit 0 並印「雙線通過」（F-090）；註解 `data/db/stock.db` 改 `tw_stock.db` |
>   | `clean_pycache.sh` | 是 | 只刪 `__pycache__`／`.pyc`，根目錄取腳本上一層 ✓ | 能 | **保留** |
>   | `clean_pycache.ps1` | 視 Windows 需求 | `Resolve-Path "$scriptPath\..\.."` 往上**兩層**，會清到同層其他專案（無害但錯） | 能 | **修正為一層**或刪除（F-091） |
>   | `check_layer_deps.py`（S3 新增） | 是 | 唯讀 | 能；現況結束碼 1（F-006） | **保留**，S20 接進 CI |
>
> - 文件 S18 做法第 3 點的疑問（`stock.db` vs `tw_stock.db`）：以 `core/config` 為準是 `tw_stock.db`，`test_long_regression.py` 也用 `TW_STOCK_DB_PATH`；只有 shell 註解寫舊名。

---

## Phase 6：測試、設定與文件

### S19. `tests/` 有效性健檢（假綠燈稽核）✅

- **目的**：69 檔 19,272 行，比 `core/backtest` 還大。**測試套件本身就是護欄，護欄壞了比沒有護欄更危險**——已有一次實例：`tests/test_broker_trading_updater.py` 整段包在 `try/except` 且 `return False`，**永遠不會失敗**（見 [FinMind爬蟲清洗儲存流程優化.md](../../backlog/FinMind爬蟲清洗儲存流程優化.md) S8）。全套目前有 **20 處 `return False`、7 檔含 `except Exception`、10 處 `skip`／`xfail`、13 處 `slow` 標記**，需逐處確認不是同一個型態。
- **做法**：
  1. **假綠燈稽核**：20 處 `return False` 與 7 檔 `except Exception` 逐處判斷——斷言是否可能被吞掉；把「無論如何都通過」的測試全部列為 A 級。
  2. **斷言密度**：每個測試檔的 `assert` 數 ÷ 行數，抓出「跑了一大段卻沒斷言」的檔案。
  3. **標記正確性**：13 處 `slow` 是否涵蓋所有需要 `data/db/*.db` 或外部 API 的測試——漏標會讓 CI 紅、多標會讓護欄在 CI 失效（`ruff`／CI 只跑 `-m "not slow"`）；10 處 `skip`／`xfail` 逐處確認理由是否仍成立。
  4. **隔離性**：52 處 `sqlite3.connect` 是否都指向 `tests/database/` 的 fixture 而非 production DB（**指向 `data/db/` 且會寫入者屬 A 級**）；測試間有無共用可變狀態、順序相依。**日誌隔離同理要查（F-001）**：pytest 執行時的訊息會經由 loguru sink 寫進 `logs/` 的正式檔案，2026-09-02 一次 pytest 的假失敗訊息落進 211 個 log 檔——確認 `conftest.py` 是否應先 `logger.remove()`。
  5. **9 支 `manual_*.py`**：不是 pytest 收集對象，確認是否仍可執行、是否該移出 `tests/`（C 級）。
  6. **回歸護欄**：`tests/backtest/snapshots/*.csv` 是否在版控內且與現行輸出一致（[多市場引擎 §6.5](../backtest/multi-market-engine.md) 記錄過 baseline 曾不在版控）。
- **產出**：〈附錄 A〉、〈附錄 D 測試有效性盤點〉。
- **驗證方式**：對每一個被判為「可能假綠燈」的測試，**刻意改壞被測程式碼確認它會紅**（改完還原）；`pytest -m "not slow"` 全綠且數量與 S1 基線一致。
- **相依**：S1。
> **✅ 完成紀錄（2026-09-02）**
> - **假綠燈稽核**：`grep "return False"` 19 處（文件估 20）全在 `manual_finmind_pipeline.py`／`manual_broker_trading_updater.py`／`manual_db_tables.py`／`manual_finmind_updater.py`，另 1 處是 `test_finmind_broker_trading_batch.py` **docstring 裡的文字**（該檔 4 個測試各有 2~4 個 assert，是真的會紅的護欄）；7 檔 `except Exception` 全部是 `manual_*`。`pyproject.toml` 未設 `python_files`，pytest 預設只收集 `test_*.py`，`manual_*` 不會執行——**故不需要做「刻意改壞」驗證，候選為 0**。
> - **斷言密度最低 5 檔**：`test_long_regression.py`（2 assert／69 行，整份 DataFrame 逐筆比對，密度低是設計）、`test_strategy_data_access.py`（2／67，parametrize 20 次）、`test_short_regression.py`（4／113）、`test_futures_price_updater.py`（17／436）、`test_futures_roll_backtest.py`（17／416）——沒有「跑一大段沒斷言」的檔案。
> - **標記**：`slow` 13 處（12 檔，含 3 支 manual）；6 支連 `TW_FUTURES_DB_PATH`／`TW_STOCK_DB_PATH` 的測試（`test_futures_{chip,products,continuous,calendar,roll_backtest,stock_universe_api}.py`）全部 `@pytest.mark.slow`＋`skipif(not exists)`，且對 production 連線**只有 SELECT**（`test_futures_chip.py`／`test_futures_stock_universe_api.py` 內的 INSERT／CREATE 都在 `:memory:` fixture）。15 處 `skip`／`skipif` 理由一律是「DB／表尚未建立」，仍成立；無 `xfail`。
> - **隔離性**：52 處 `sqlite3.connect` → `tmp_path`／`:memory:` 44、production 唯讀 8（6 測試＋2 manual）；無寫入 production 的測試 ✓。**日誌隔離**：`tests/` 沒有根 `conftest.py`，`tests/backtest/conftest.py` 只有 fixture，loguru sink 未隔離——正是 F-001 的成因；本輪量測全程以 scratchpad 的 `noguru_plugin`（`pytest_sessionstart` 把 `LogManager.setup_logger`／`setup_backtest_logger` 換成 no-op）避開，等期貨回補結束後應把同一招搬進 `tests/conftest.py`。
> - **manual_\*.py**：9 支皆可 `py_compile`；`manual_db_tables.py` 有一段 fallback 路徑 `core/database/tw_stock.db`（已不存在）；建議整批搬到 `scripts/manual/`（F-092）。
> - **回歸護欄**：`tests/backtest/snapshots/` 4 份 CSV 皆在版控；SHORT 6 passed、LONG 1 passed（S13）。
> - 〈附錄 D〉已填。

### S20. 建置、CI、容器與環境變數健檢 ✅

- **目的**：9 份設定檔決定「本機、CI、容器」三處跑出來是不是同一件事。三處不一致的典型後果是本機綠、CI 紅（或更糟：CI 綠、實際壞），2026-09-01 的 CI 全紅正是相依宣告缺一個傳遞相依造成。
- **做法**：
  1. **相依一致性**：`pyproject.toml` 的 `dependencies` 與實際 import 是否仍對得上（重跑一次 AST 掃描）；`requirements.txt` 的鎖定版本與 `pyproject` 的下限有無矛盾；`dev/env/quant_mac.yml`／`quant_win.yml` 是否已與前兩者漂移。
  2. **ruff 設定**：`ignore` 清單每一條的理由是否仍成立（與 S2 結果連動）；`pre-commit` 釘的 `ruff` 版本（v0.16.3）與 `pyproject` 的 `ruff>=0.6` 是否會讓本機與 CI 用到不同版本、產生不同格式結果。
  3. **CI**：`.github/workflows/ci.yml` 只跑 `-m "not slow"`——確認被排除的 13 個 slow 測試有沒有其他地方在跑（沒有的話，回歸護欄實際上只在本機存在，屬 B 級並應寫進文件）；`--timeout=300` 是否足夠；覆蓋率步驟 `continue-on-error` 是否讓失敗被忽略。
  4. **容器**：`core/Dockerfile`、`frontend/Dockerfile`、`docker-compose.yml` 三者的 Python 版本、相依安裝方式、掛載路徑與 CI 是否一致；`core` 服務沒有掛 `data/`——確認容器內回測要用的 DB 從哪來（缺 DB 時的行為屬 A 級候選）。
  5. **環境變數與密鑰**：`.env.example` 列的 8 個變數與程式實際讀取的 14 處 `os.getenv` 是否一一對應（有讀但沒列＝新人一定踩坑）；`.gitignore` 對 `.env`／`.env.*` 的封鎖是否完整；全專案 grep 確認無硬編碼金鑰（本次盤點為 0 處，需在健檢時複驗）。
- **產出**：〈附錄 A〉。
- **驗證方式**：`pip install -e ".[dev]" && ruff check . && pytest -m "not slow"` 在乾淨環境可完整跑過；`docker compose config` 無警告；`.env.example` 與 `os.getenv` 對照表無缺口。
- **相依**：S1。
> **✅ 完成紀錄（2026-09-02）**
> - **相依一致性**：AST 掃描 `core/tasks/frontend/strategy_lab/scripts/tests` 的第三方 import 共 15 個模組（FinMind、dateutil、docx、dolphindb、dotenv、fake_useragent、loguru、numpy、pandas、plotly、pytest、requests、shioaji、streamlit、yfinance），每一個都在 `pyproject.toml` 的 `dependencies`／`optional-dependencies` 找得到（`tqdm` 為註明的代宣告傳遞相依）；`requirements.txt` 的 `==` 版本全部 ≥ `pyproject` 下限，無矛盾；但 `requirements.txt` 另有 **85 個未被 import 的套件**（Flask、ipython、ta、pyecharts、peewee、sentry-sdk…，conda export 遺留），而 `core/Dockerfile` 就是拿它裝映像。`dev/env/quant_{mac,win}.yml` 已漂移：用 `black`／`isort`（專案用 ruff）、沒有 `yfinance`／`pytest`／`python-docx`，win 版多 `dolphindb`。
> - **ruff**：本機 0.16.3 ＝ pre-commit `rev: v0.16.3`；CI 以 `pip install -e ".[dev]"` 裝 `ruff>=0.6` 的最新版，格式規則跨版本變動時會出現本機綠、CI 紅（F-095）。`ignore` 清單每條都有理由；註解內的計數（BLE001「85 處」等）已與 S2 實測（96）不符，屬 F-002／F-010~F-012 的範圍。
> - **CI**：只跑 `pytest -m "not slow" --timeout=300`（本機實測 1.4 秒，timeout 充裕）；13 個 `slow` 測試與 `scripts/run_regression.sh` **沒有任何 workflow／Makefile／排程在跑**，回歸護欄只存在於本機（F-095）；覆蓋率步驟 `continue-on-error` 只影響報告，測試步驟本身會擋 ✓；pip cache 以 `pyproject.toml` 為鍵 ✓。
> - **容器**：Python 3.12 六處一致（pyproject／CI／兩個 Dockerfile／兩份 yml）；`docker compose config` 無警告；`core` 映像只 COPY `run.py`＋`core/`，**沒有 `data/`、`tasks/`**，compose 也沒掛 `data/` → `TwStockDataFeed.setup()` 的 `sqlite3.connect(data/db/tw_stock.db)` 因目錄不存在直接 `OperationalError`（大聲失敗，故不列 A）；`frontend` 映像找不到 `frontend/requirements.txt`（檔案不存在）就只裝 `streamlit pandas`，`app.py` 第一行 `import plotly.express` 即 ImportError（F-093／F-094）。
> - **環境變數**：程式讀取 `os.getenv` 的鍵共 15 個——`.env.example` 列了 8 個（DDB×5、API_KEY、API_SECRET_KEY、FINMIND_API_TOKEN）✓；**未列**：`API_KEY_1..4`／`API_SECRET_KEY_1..4`（`settings.py:158-161` 多帳號輪替）、`ALPHAEDGE_DATA_DIR`／`ALPHAEDGE_RESULTS_DIR`／`ALPHAEDGE_LOGS_DIR`（`paths.py:62-64`）、`ALPHAEDGE_BACKTEST_RESULTS`（前端）。`.gitignore` 的 `.env`／`.env.*`／`!.env.example` 完整 ✓；硬編碼金鑰 grep 複驗 **0 處** ✓。
> - **乾淨環境驗證**：`python3 -m venv`＋`pip install -e ".[dev]"`＋`ruff check .`＋`ruff format --check .`＋`pytest -m "not slow"` 已於 scratchpad 背景執行（`clean_env_check.log`），結果見本步驟末尾補記。

### S21. 文件漂移健檢（`docs/`／README／規則檔）✅

- **目的**：本專案的判準大量寫在 `docs/`（16 份），健檢的每一步都拿它們當標準答案。**如果文件本身已經過期，前面 20 步的結論就會跟著錯**。
- **做法**：
  1. **對照前面各步的實測結果**：S3~S19 每一步都是在拿程式碼跟某份 docs 對答案——凡是「程式對、文件錯」的，本步驟負責改文件；「文件對、程式錯」的留在附錄 A 走分流。
  2. **抽樣核對可驗證的陳述**：`docs/backtest/module-map.md` 的呼叫序列、`docs/pipeline/etl-ingestion.md` §二 的 updater 現況對照表（標註 2026-08-16，期間新增了期貨線）、`docs/exchanges/data_coverage.md` 的資料表對照與涵蓋起訖、`docs/dev/code-quality.md` 的兩份基線（由 S1 更新）。
  3. **README 雙語一致性**：`README.md` 與 `README_zh.md` 的內容是否同步（兩份各約 13.7KB，容易只改一邊）。
  4. **規則檔指標完整性**：`CLAUDE.md` §5 宣告 `.cursor/` 底下只放指標不放規則本文——確認沒有複製一份規則在那裡（`CLAUDE.md` 開頭已明言兩邊各存一份必然漂移）；`.claude/skills/` 兩份 skill 與 `CLAUDE.md` 的敘述是否一致。
  5. **backlog 一致性**：`backlog/index.md` 每一列的狀態／進度與各文件內的進度表是否相符（`manage-backlog` skill §6 的收尾檢查）。
- **產出**：〈附錄 A〉、`docs/` 的更新。
- **驗證方式**：16 份 docs 每份有「已核對／已更新／不需動」三選一的結論；`backlog/index.md` 與各文件三處一致。
- **相依**：S3~S19。
> **✅ 完成紀錄（2026-09-02）**
> - **16 份 docs 的結論**（「程式對、文件錯」者已由本步驟直接改文件；「文件對、程式錯」者留在附錄 A）：
>
>   | 文件 | 結論 | 改了什麼 |
>   |---|:---:|---|
>   | `docs/backtest/module-map.md` | 已更新 | 刪掉殘留的「三道關卡」句、引擎職責改「四道關卡」、資料源列補 `tw/futures_datafeed.py`、報表列補 `futures_reporter.py`／五張圖。F-005（呼叫方向 vs 相依方向）維持為 C 級，未改圖 |
>   | `docs/backtest/multi-market-engine.md` | 已更新 | §2.4 檔案路徑 `tw_stock_datafeed.py` → `tw/stock_datafeed.py` 並補期貨檔；§五「報表欄位仍為 Stock ID」補期貨已用 `Contract ID` |
>   | `docs/backtest/short-selling-framework.md` | 不需動 | 是判準；§7.5「反之亦然」（F-057）、§3.3 曆日計提（F-059）皆為程式錯 |
>   | `docs/pipeline/etl-ingestion.md` | 已更新 | §二 補 5 列期貨 updater（股期、保證金、連續合約、籌碼、tick），失敗可見度欄以 loader 是否呼叫 `finish_load()` 實查填寫；「兩支期貨 updater」→ 通稱 |
>   | `docs/pipeline/equity-change.md`、`broker-trading-no-data.md` | 不需動 | `equity_change` 仍只 2020Q1（DB 230,163 列與文件一致）；後者為選型紀錄 |
>   | `docs/exchanges/data_coverage.md` | 已更新 | API 路徑補 `tw/`；期貨列改為 `FuturesPriceAPI` 與 7 檔商品；新增連續合約／保證金／籌碼三列、4 支期貨 API、5 個期貨 target；財報表名列出三張；`core/config.py` → `core/config/settings.py` |
>   | `docs/dev/code-quality.md` | 已更新 | §三加入 2026-09-02 重測（687 passed、60%、BLE001 96、待收斂 25）；§4.2 slow 清單改為實況（12 檔；SHORT 線不是 slow）並明寫「回歸雙線只在本機」（F-090／F-095）。§二的 21 條待收斂清單行號已漂移，留給 F-002／F-010~F-012 的處置一併更新 |
>   | `docs/dev/naming-axes.md` | 已更新 | 「未來 `futures/`」→ 已存在 |
>   | `docs/dev/runtime-artifacts.md` | 不需動 | 與 S22 實測一致（logs 分桶大小為當時快照） |
>   | `docs/setup/dev-setup.md` | 已更新 | `mkdir` 清單去掉 `core/data`；環境變數補多帳號與 `ALPHAEDGE_*_DIR`／`ALPHAEDGE_BACKTEST_RESULTS`（F-096） |
>   | `docs/deployment/dev-deployment.md` | 已更新 | 不存在的 `SimpleLongStrategy` 換成 loader 實測的 4 支 |
>   | `docs/deployment/prod-deployment.md` | 已更新 | 「沒有 docker-compose.yml」改為有；`core/data` 掛載改 `data/`＋`logs/`；前端註記改為 plotly 缺相依（F-093）；末段指向 compose 與 F-094 |
>   | `docs/commands/command-usage.md`／`.zh-TW.md` | 已更新 | target 表補齊 7 個期貨 target（zh 原本一個都沒有）；`no_tick` 註明不排除 `futures_tick`（F-078） |
>   | `docs/futures/tw-futures-platform.md` | 不需動 | 已完成工作的實作紀錄，保留原路徑為刻意 |
>
> - **README 雙語**：兩份的 mermaid `Data["core/data"]` → `data/downloads`；專案結構樹刪掉 `core/database/`、`core/backtest/results/`、`core/data/` 三個已不存在的節點，補 `data/`／`results/`／`logs/` 頂層與 `core/strategies/futures/`；zh 補上漏掉的 `pre-commit run --all-files`。Docker 段落的分岔（F-101）保留，由使用者決定要統一成哪一版。
> - **規則檔**：`.cursor/rules/*.mdc` ×4 與 `.cursor/skills/manage-backlog/SKILL.md` 皆只有「去讀哪一份」的指標，無規則本文 ✓；`.claude/skills/develop-strategy/SKILL.md` 只寫台股 → 補期貨基底與 `max_holdings` 提醒（F-076），`CLAUDE.md` §skill 表同步改 `core/strategies/{stock,futures}/`；`.cursor/rules/strategy-development-sdd.mdc` 的 description 仍只提 `core/strategies/stock/`（指標檔，語意不影響，留給下次同步）。
> - **其他**：`strategy_lab/README.md` 的 `from core.utils.market_calendar import MarketCalendar` 是搬家前的路徑，已改；`backlog/index.md` 與 7 份 backlog 文件的 ✅ 計數逐列相符（腳本比對）。

### S22. 資料與執行期產物約定健檢 ✅

- **目的**：`data/`、`results/`、`logs/` 是程式寫出來的東西，[執行期產物](../dev/runtime-artifacts.md) 定義了它們的分界。這層的問題不會讓程式報錯，只會讓「資料看起來有、其實是舊的或錯的」。
- **做法**：
  1. **DB schema 對照**：`tw_stock.db`／`tw_futures.db` 的實際表與欄位（`sqlite_master`）與 `core/config/schema.py`、`docs/exchanges/data_coverage.md` 的宣告逐表比對；抓出「程式會寫但文件沒有」與「文件有但實際不存在」的表。
  2. **主鍵與索引**：每張表的主鍵是否與 loader 的冪等機制相符（S9 的結論）；常用查詢欄位有無索引（影響回測速度，C 級）。
  3. **目錄約定**：`data/downloads/` 的分層是否都已遵守 `{market}/{domain}/` 慣例（台期貨平台 §3.1 的目標結構）；有無殘留在舊路徑的檔案。
  4. **`.gitignore` 覆蓋**：`data/`／`results/`／`logs/`／`strategy_lab/**/output/` 已擋；確認沒有任何產物漏網（`git status --ignored` 抽查），以及**沒有把該進版控的東西誤擋**（例如回歸 snapshot）。
  5. **保留策略**：`logs/` 與 `results/` 會無限成長嗎；`tasks/clean_logs.py` 的保留天數是否有人實際在跑（與 S15 連動）。評估保留天數時要把 **F-001 的日誌互相污染**算進去——`update_futures_price.log` 有約兩成行數不屬於該模組，等於兩成的 10 MB 旋轉配額被別人吃掉，實際能保留的期程比帳面短。
- **產出**：〈附錄 A〉、DB schema 對照表（放〈附錄 E〉）。
- **驗證方式**：schema 對照表無「未說明的差異」；`git status --ignored --short | head -50` 抽查結果符合預期。
- **相依**：S6、S9。
> **✅ 完成紀錄（2026-09-02）**
> - **DB schema 對照**（唯讀連線讀 `sqlite_master`，期貨回補進行中不受影響）：`tw_stock.db` 13 張、`tw_futures.db` 8 張，全部列於〈附錄 E〉。`core/config/schema.py` 宣告 24 個表名常數：21 個對得上實際表、`tick`／`futures_tick` 在 DolphinDB、**`futures_contract` 有常數無建表**（F-098）。`docs/exchanges/data_coverage.md` 只列了 12 張，漏 `balance_sheet`／`cash_flow`／`comprehensive_income`（以「各財報表」帶過）與 6 張期貨表（`futures_continuous`／`futures_institutional_chip`／`futures_large_trader`／`futures_put_call_ratio`／`futures_margin_history`／`stock_futures_margin_rate_history`）——屬「程式對、文件錯」，S21 改文件。
> - **主鍵與冪等**：每張表主鍵皆與 loader 的 `INSERT OR IGNORE`／先查既有鍵一致（S9 結論不變）；`price`／`chip` 主鍵含 `證券名稱`（F-036 的結構性問題，`fix_price_etf_stock_id.py` 為其補丁）。**索引**：全部只有主鍵自動索引＋ 4 個明示索引（`taiwan_stock_trading_daily_report_secid_agg`、`futures_continuous`、`futures_margin_history`、`futures_stock_universe`、`stock_futures_margin_rate_history`）。`EXPLAIN QUERY PLAN` 實測：`price`／`chip` 依 `stock_id` 取區間只能用主鍵的 `date>? AND date<?` 部分（整段日期每天 2,000 列全掃再濾代號）、`dividend WHERE stock_id = ?` 為 **SCAN**、`futures_price_daily` 依商品取區間同樣只吃 `date` 範圍（F-099，效能）。
> - **目錄約定**：`data/downloads/` 兩個市場 16 個 domain 全部符合 `{market}/{domain}/`（`tw_stock/meta` 為 resume 狀態，依 runtime-artifacts 的判準屬產物 ✓）；無舊路徑殘留（`core/database`／`core/data`／`core/backtest/results` 皆不存在）。
> - **`.gitignore`**：`git status --ignored --short` 抽查——`data/`／`logs/`／`results/`／`strategy_lab/**/output/`／`.env`／`.venv`／快取／`alphaedge.egg-info`／`shioaji.log` 皆被擋；該進版控的 `tests/backtest/snapshots/*.csv` 已在版控（S19）；`tests/database/`、`tests/downloads/finmind/`、`tests/temp/` 被擋但它們是 `manual_*` 腳本的暫存區（F-092）。**`shioaji.log` 落在 repo 根目錄**是 shioaji 套件自己寫到 CWD，應導向 `logs/`（併入 F-097）。
> - **保留策略**：`logs/` **3.1 GB**（`api/` 2.5 GB／277 檔，最舊 2026-08-07；`backtest/` 535 MB／62 檔，`SimpleLong.log` 單檔 32 MB 未輪替；`pipeline/` 65 MB／19 檔）。`api/` 桶 26 天長到 2.5 GB ＝ 每天約 100 MB、每 2~3 小時輪替一次 10 MB，來源是 `core/api/tw/` 每次查詢都寫一行（回測每個曆日 `is_market_open` ＋ `get_quotes` 各一次）。`tasks/clean_logs.py` 沒有排程在跑（S15）；F-001 的互相污染讓 `pipeline/` 桶的統計行被 api 訊息稀釋（`update_futures_price.log` 約兩成行數不屬於該模組）。`results/` 2.1 MB 無成長問題。

---

## Phase 7：收斂

### S23. 分級收斂與分流 ✅

- **目的**：健檢的價值在於分流結果，不是清單長度。本步驟把〈附錄 A〉每一條送到它該去的地方，確保沒有任何一條只留在本文件裡自生自滅。
- **做法**：
  1. **A 級**：本工作內修完（附測試＋回歸雙線），或開新 `backlog/*.md` 並在 `index.md` 新增一列。
  2. **B 級**：按主題合併成 2~4 份新 backlog 文件（預期分群：ETL 失敗語意收斂、日期與時區邊界、測試護欄補強、本機／CI／容器一致性）。
  3. **C 級**：架構性結論寫進對應 `docs/`（引擎相關進 `docs/backtest/`、ETL 相關進 `docs/pipeline/`、工具鏈相關進 `docs/dev/`），不另開 backlog。
  4. **D 級**：只在〈附錄 B〉留計數。
  5. 若 S2／S20 有規則已可從 `pyproject.toml` 的 `ignore` 移除，一併處理並更新 [程式碼品質](../dev/code-quality.md)。
  6. 收尾檢查三處一致：本文件進度表、各步驟章節標記、`backlog/index.md` 該列。
- **產出**：新 backlog 文件、`backlog/index.md`、`docs/` 更新。
- **驗證方式**：〈附錄 A〉每一條的「處置」欄都指向一個具體去處（commit hash／backlog 檔名／docs 章節）；A 級無一條處置為「暫不處理」。
- **相依**：S1~S22。
> **✅ 完成紀錄（2026-09-02）**
> - **分流結果**（附錄 A 101 條）：
>
>   | 等級 | 條數 | 去處 |
>   |:---:|---:|---|
>   | A | 5 | **ETL 失敗語意與缺口回補**（P0：F-030、F-043、F-045、F-050 ＋ 19 條 ETL 的 B 級）、[前端指標與報表同源化.md](../../backlog/前端指標與報表同源化.md)（P1：F-082 ＋ F-083／F-084／F-085／F-067） |
>   | B | 43 | 上述兩份之外：**回測口徑與日期邊界收斂**（P1：引擎／model／管理器／策略／API 的 17 條 B 級）、[測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md)（P1：回歸腳本、CI、容器、入口、一次性腳本、環境變數） |
>   | C | 51 | 架構性結論寫進 `docs/backtest/module-map.md` §六、`docs/backtest/multi-market-engine.md` §九、`docs/pipeline/etl-ingestion.md` §五、`docs/dev/code-quality.md`〈健檢 C 級結論〉；與 B 級同一處的 C 級併入該步驟 |
>   | D | 2 | 〈附錄 B〉計數 |
>
> - **A 級為什麼不在本工作內修**：4 條 ETL 的修法都要以真實爬取驗證「連線失敗 vs 休市」與「缺口回補」，而期貨行情回補仍在背景執行（2026-09-02 20:16 起，預估 09-03 完成）；F-082 的正確修法是前端改讀三份 CSV（不是單純把 ×100 拿掉），屬前端重構。兩者都已轉為 P0／P1 的 backlog 並在 `index.md` 新增列，A 級無一條處置為「暫不處理」。
> - **`pyproject.toml` ignore 清單**：S2 複驗 BLE001 由 85 增為 96、待收斂 21 條全部仍在，故本次無可移除的規則；**ETL 失敗語意與缺口回補** S4／S6 與 [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S6 完成後再回頭移除 B008／E722／F841。
> - **本文件的去留**：依 `manage-backlog` §5 應整份移出，但 `docs/` 內多處（code-quality §4.2、prod-deployment、command-usage）與 4 份新 backlog 都以 `F-xxx` 連結回本檔的附錄 A，**已於 2026-09-03 移入 `docs/dev/health-check-2026-09.md`**，所有連結同步更新，`index.md` 該列已刪除（skill §5.3）。

---

## 附錄 A：發現清單

> 每條發現一列。同一檔案多個問題拆成多列。**處置欄不得留白。**

> **「ETL 失敗語意與缺口回補」已於 2026-09-03 全數完成**（S1~S7），規劃文件依
> [`manage-backlog` skill §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理)
> 移出 `backlog/`，故下表「處置」欄中該名稱不再是連結。成果的長期歸屬：
>
> | 內容 | 現在在哪 |
> |------|----------|
> | 失敗語意三分法（`OK`／`NO_DATA`／`FAILED`）與休市判準 | `core/pipeline/shared/base_crawler.py` 模組說明 |
> | 缺口回補的差集公式、`incomplete` 與「當天不寫 no_data」 | `core/pipeline/shared/date_planner.py` 模組說明 ＋ [ETL 入庫約定](../pipeline/etl-ingestion.md)〈Resume 為什麼是「差集」〉 |
> | 各 updater 的 Resume 依據與失敗可見度對照表 | [ETL 入庫約定](../pipeline/etl-ingestion.md) §二 |
> | 日誌分桶 `filter=`、`watch=True` 與 2026-09-03 的日誌消失事故 | [執行期產物](runtime-artifacts.md)〈日誌保留〉 ＋ `core/utils/log_manager.py` 模組說明 |
> | `no_tick`／`--from`／`delete_price_data --apply` 的用法 | [指令教學](../commands/command-usage.zh-TW.md) |

> **「回測口徑與日期邊界收斂」已於 2026-09-04 全數完成**（S1~S8，17 條 B 級），
> 規劃文件同依 [`manage-backlog` skill §5](../../.claude/skills/manage-backlog/SKILL.md#5-完成後的處理)
> 移出 `backlog/`，故下表該名稱亦不再是連結。成果的長期歸屬：
>
> | 內容 | 現在在哪 |
> |------|----------|
> | SBL 借券費改按**曆日**計提，並在回補前補計最後一段 | `core/backtest/models/settlement_model.py` 的 `accrue_holding_cost()` ＋ `StockPositionManager.accrue_final_borrow_fee()` 註解 |
> | 當沖證交稅減半的**起始日**（2017-04-28）與 `tax(date=...)` 語意 | `core/utils/constant.py` 的 `DAY_TRADE_TAX_START` ＋ `is_day_trade_tax_effective()` |
> | 滑價後再驗價：開倉腿夾回區間、平倉腿只警告 | `FillModel.clamp_filled_price()`／`warn_close_price_out_of_range()`；無成交日拒單為 `has_tradable_quote()` |
> | 同標的／同契約**雙向持倉一律拒單**（股票與期貨對稱） | [放空框架 §7.5](../backtest/short-selling-framework.md) ＋ `core/managers/{stock,futures}/position_manager.py`；跨月份價差保證金的已知簡化見 [台期貨平台](../futures/tw-futures-platform.md) Phase2-2 |
> | 交易日曆往前查的上界（`MAX_LOOKBACK_DAYS = 30`）與缺日偵測 | `MarketCalendar` ＋ `TwStockDataFeed.report_calendar_gaps()` 註解 |
> | 換月不回頭、展期兩腿同一種盯市價 | `settlement_model.roll_positions()`／`get_quote_mark_price()` |
> | 風險指標公式（年化 √252、單位一致、零筆回 `None`、Sortino 定義） | `core/backtest/analysis/risk_metrics.py`（純函式，前端同源化 S3 共用） |
> | 研究版與成品版**指向同一個** ridge 訊號函式 | `core/strategies/ridge.py` ＋ `tests/test_research_production_parity.py` |
>
> **量化結果**（各步驟完成時實測）：SBL 年費原低估約 31%（252/365）；LONG 回歸執行
> 時間由 ~18 秒降到 ~9 秒（交易日集合改為一次建立）；`core/api/` 的
> DeprecationWarning 由 14 條降為 0（31 處 `params=` 統一轉 ISO 字串）。
> SHORT 快照重產兩次（借券費計提日、新增兩個全 0 事件欄），**LONG 逐筆自始未變**。

> **⚠️ 2026-09-04 第二輪掃描：下表有 4 條「處置欄寫了但實際沒人接手」**
>
> 全 repo 重掃一次後開了 [健檢殘留項目收斂.md](../../backlog/健檢殘留項目收斂.md)（P2，6 條）。
> 其中 5 條來自本表，**驗收時不要只看標記**：
>
> | 條目 | 本表寫的處置 | 實際狀況 |
> |------|--------------|----------|
> | F-060 | `tax()` 加 `date` ＋ `check_day_trade_tax_expiry()` 改看回測區間 | **只做了前半**；後者仍比對 `datetime.date.today()` |
> | F-068 | 改以日報酬年化 Sharpe／Sortino | Sharpe／Sortino／Volatility 已收斂，**`compute_information_ratio()` 被漏掉**（仍為每筆交易口徑、未年化，`benchmark_return` 寫死 0.0） |
> | F-098 | 刪除死常數，或加註「未建表」 | **兩個動作都沒做** |
> | F-006 | 「S17 處理」 | **未修**；且它是 `scripts/check_layer_deps.py` 永遠 exit 1 的唯一原因，該閘門因此不能掛 CI |
> | F-088 | 研究產物移出版控 | `.gitignore` 規則已加，但 **13 個 `.html` 早已進版控**，規則對已追蹤檔案無效 |
>
> 另有**一條新發現不在本表**：`logger.error(msg, exc_info=True)` 是標準庫寫法，
> loguru 會默默丟棄，全專案 **15 處**這樣寫、**0 處**用 `logger.opt(exception=True)`
> ——所有 ETL 與 tick 的失敗路徑都只留一行訊息、堆疊全無（已實測驗證）。
> 這是 F-080 的完整範圍，本表當時只列了 1 處。


| 編號 | 嚴重度 | 位置（`file:line`） | 現象 | 影響 | 處置 |
|------|:------:|---------------------|------|------|------|
| F-001 | B | `core/utils/log_manager.py:57` | `logger.add()` 未帶 `filter=`。loguru 的 sink 預設接收 process 內**每一筆**訊息，而全專案有 34 處 `setup_logger()`（17 個 updater／crawler ＋ 各 `core/api/` 類別），只要被 import 就註冊一個 sink，因此任一支程式跑起來都會把自己的訊息同時寫進其他二十幾個 log 檔 | 2026-09-02 實測：一次 pytest 的**假失敗**訊息（`[margin] 更新失敗：…失敗檔案：['a.csv']`，出自 `tests/test_loader_failure_reporting.py:248` 的 fixture）同一時間戳出現在 **211 個 log 檔**，含 `logs/api/*`、`logs/pipeline/crawl_finmind.log`、`logs/backtest/Momentum-1.*`——會被誤判成正式 ETL 入庫失敗。另一半影響是**旋轉配額被稀釋**：`update_futures_price.log` 的 55,764 行中只有 44,720 行與期貨有關，約兩成的 10 MB 配額被別的模組吃掉，真事故的紀錄會比預期更早被輪替掉 | **→ **ETL 失敗語意與缺口回補** S6**。**S19 補註（2026-09-02）**：`tests/` 沒有根 `conftest.py`、`tests/backtest/conftest.py` 只有 fixture，loguru sink 完全未隔離；本輪以 scratchpad 外掛（`pytest_sessionstart` 把 `LogManager.setup_logger`／`setup_backtest_logger` 換成 no-op）避開，修法即把同一段搬進 `tests/conftest.py`（等期貨回補結束、`log_manager.py` 解凍後） |
| F-002 | B | `core/pipeline/tw/updaters/`（B008 ×8：`stock_chip_updater.py:82`、`stock_dividend_updater.py:61`、`stock_margin_updater.py:161`、`stock_price_updater.py:84`、`stock_tick_updater.py:99`、`futures_price_updater.py:227`／`:268`、`futures_tick_updater.py:147`） | `end_date: datetime.date = datetime.date.today()` 寫在參數預設值，import 當下即固定；2026-08-16 清單之後又新增 3 處（期貨線） | 排程路徑**不受影響**：`tasks/update_db.py` 的 `get_time_config()` 在每次呼叫時才取 `today()` 並明傳 `end_date`。只有直接呼叫 `updater.update()` 且不傳 `end_date` 的長駐程序會靜默漏最新一天 | **→ **ETL 失敗語意與缺口回補** S4**。由 A 降為 B。S23 開「ruff 待收斂清單收斂」一單：改成 `end_date: Optional[datetime.date] = None` 於函式內取值；修完把 `B008` 從 `pyproject.toml` ignore 移除 |
| F-003 | C | `core/utils/instrument.py:8` | 共用層 import 引擎層（`core.backtest.datafeed.tw.market_calendar`）。`core/utils/__init__.py` 目前刻意不 re-export `instrument`，誰加上就會形成 `core.utils → market_calendar → stock_price_api → core.utils` 循環 | 分層方向反了；`StockUtils` 歸屬未定是 [命名軸線〈遺留與後續〉](../dev/naming-axes.md) 已列項目 | **→ `docs/backtest/module-map.md` §六**。已登錄 `scripts/check_layer_deps.py` 的 `_KNOWN_REVERSE`（ratchet）。最小切法：`get_price_chg()` 是唯一用到 `MarketCalendar` 的方法且只服務 Shioaji 實盤，搬去 `core/utils/account.py` 或改延遲 import |
| F-004 | C | `core/pipeline/tw/cleaners/futures_tick_cleaner.py:8`、`core/pipeline/tw/updaters/futures_continuous_updater.py:8-9` | ETL（資料層）import 回測引擎的 `futures_calendar`／`futures_roll` | 期貨日曆與換月規則是 ETL 與回測**都要**的領域規則，放在 `core/backtest/datafeed/` 讓資料層反向相依引擎層；`futures_calendar` 又 import `FuturesPriceAPI`，鏈變成 pipeline → backtest → api | **→ `docs/backtest/module-map.md` §六**。已登錄 ratchet。最小切法：`futures_calendar.py`／`futures_roll.py` 搬到 `core/utils/`（或新開 `core/calendar/`），import 改 5 處；S23 決定是否開單 |
| F-005 | C | `docs/backtest/module-map.md` §一 vs `core/backtest/{backtester,factory,datafeed,report,analysis}` 共 12 處 import `core.strategies.*` | 文件把「呼叫方向」寫成「相依方向」：圖上策略層在引擎層之上，實際 import 方向是引擎／factory／報表 → 策略契約（三個 base），策略契約再 → `core.backtest.models`／`datafeed` 的型別 | 不是缺陷——策略契約本來就是引擎要認得的介面；但照文件字面寫檢查腳本會誤判 12 處 | **→ `docs/backtest/module-map.md` §六**。`check_layer_deps.py` 把三個策略基底與兩個套件門面定為「策略契約」層，並以 E' 規則釘住「門面只准 re-export base」（§6.4 事故的護欄）；S21 在文件補一句說明 |
| F-006 | C | `strategy_lab/strategies/tsmc_overnight_signal/reports/docx_append.py` ↔ `generate_docx.py` | 全專案唯一的循環 import（研究報表兩檔互相 import） | 目前靠 import 順序僥倖不炸；動任一檔的 import 位置就會 ImportError。也是 `check_layer_deps.py` 現況結束碼為 1 的唯一原因 | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。S17 處理：共用部分抽成第三個模組或改函式內 import |
| F-007 | C | `core/api/tw/{futures_price,stock_chip,stock_price}_api.py`、`core/adapters/tw/futures_quote_adapter.py` → `core.pipeline.utils.constant`；`core/api/tw/stock_margin_api.py:9` → `core.pipeline.utils.sqlite_utils`；反向 4 個 futures updater → `core.api` | 讀取層相依 ETL 的 utils，ETL 又相依讀取層：資料層內 pipeline ↔ api 套件層互相相依（檔案層無循環） | 欄位名 Enum（`PriceColumn`／`ChipColumn`／`FuturesPriceColumn`）其實是**資料表 schema 的一部分**，放在 pipeline 底下讓所有讀取端都得 import ETL 套件；PostgreSQL 遷移時這條相依會擴大改動面 | **→ `docs/backtest/module-map.md` §六**。最小切法：欄位 Enum 搬到 `core/config/schema.py`（與表名同處），`SQLiteUtils.check_table_exist` 搬到 `core/api/base.py`。S23 併入 [PostgreSQL遷移計畫](../../backlog/PostgreSQL遷移計畫.md) Phase2-3 |
| F-008 | C | `core/backtest/models/settlement_model.py:8-19` | `settlement_model` import 了 `futures_roll`（datafeed）、`StockCostModel`、兩個 PositionManager；兩個 PositionManager 又 import `cost_model` → `backtest.models` ↔ `managers` 套件層互相相依 | [module-map §三](../backtest/module-map.md) 寫「model 之間不互相 import」，實際 settlement → cost_model 是型別相依（建構子參數 `cost_model: StockCostModel`） | **→ `docs/backtest/module-map.md` §六**。文件與程式二擇一：S21 把該句改成「model 之間只以型別相依、共用狀態仍以 dict 傳遞」，或把型別改成 `BaseCostModel`。不影響行為 |
| F-009 | C | `strategy_lab/` 4 處、`tests/` 11 處 `sys.path.insert`（清單見 `python scripts/check_layer_deps.py` 的 G 節） | 專案已 `pip install -e .`（CI 亦然），15 處注入全部多餘，且會遮蔽「沒安裝就跑」的 import 錯誤 | 多餘但無害；`tests/` 的 11 處會讓人以為 pytest 需要它 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S5**。S17／S19 各自清掉；清掉後 `pytest -m "not slow"` 應仍全綠 |
| F-010 | C | `core/pipeline/tw/crawlers/stock_price_crawler.py:36-40` | `crawl(date)` 呼叫 `crawl_twse_price()`／`crawl_tpex_price()` 後把 DataFrame 丟掉（F841 ×2），本身**沒有任何副作用**；兩個子方法也不落檔 | 全專案無人呼叫這個 `crawl()`（updater 直接呼叫兩個子方法），是「實作了抽象方法但什麼都不做」的死碼；日後有人照 `BaseDataCrawler` 介面呼叫會靜默拿到 None | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。S7 一併判定：改回傳 `Tuple[Optional[DataFrame], Optional[DataFrame]]`，或刪掉並讓基底不強制 `crawl()` |
| F-011 | C | `core/utils/callback.py:4-6` | `OrderState` 先從 `shioaji.constant` import，再被 `.constant.OrderState` 覆蓋（F811） | 兩個 Enum 四個值完全相同且皆為 `str` 子類，`stat == OrderState.StockDeal` 以值比較，行為不受影響；只影響實盤 callback（`--mode live` 尚未實作） | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。刪掉第 4 行；併入 F-002 的 ruff 收斂單 |
| F-012 | D | B904 ×3（`core/utils/time.py:36/45`、`finmind_updater.py:137`）；E722 ×3（`stock_tick_cleaner.py:155/163`、`stock_tick_utils.py:209`）；B006 ×4（`financial_statement_crawler.py:332`、`data_utils.py:101/106/107`）；B007 ×3（`tests/manual_db_tables.py:129/142`、`tests/test_futures_continuous.py:347`）；F841（`scripts/generate_docs.py:65`） | 待收斂清單其餘 14 條逐處複驗：B904 只是丟失 root cause；E722 全包在「刪暫存檔」的清理段落且隨後 `raise e`，只會吞掉清理期間的 `KeyboardInterrupt`；B006 四個可變預設值全為唯讀（`seasons` 只被迭代、三個對照表只被 `.items()`／迭代） | 皆無行為缺陷 | **→ D 級，〈附錄 B〉計數**。併入 F-002 的 ruff 收斂單一次修完，讓 7 條規則從 ignore 清單移除 |
| F-013 | C | `core/pipeline/`（`ruff check . --select BLE001 --no-cache`） | 盲捕由 85 → **96 條**（+11，全在 `core/pipeline/`：crawlers 26、updaters 25、loaders 18、cleaners 6、utils 5；其餘為 `tests/manual_*` 與 `tasks/update_db.py`） | 數量不是重點，S7~S10 要逐處判斷「吞掉之後回傳什麼」 | **→ `docs/pipeline/etl-ingestion.md` §五**。S7~S10 逐處判定；本列只保留計數 |
| F-014 | C | `docs/dev/code-quality.md` §二、§三 | 兩份基線已過期：測試 207 → **687 passed**、覆蓋率 40% → **60%**（11,348 行、未覆蓋 4,552）、待收斂清單 21 → **25 條**（行號亦漂移）、全專案 179 → 277 檔 | 文件仍宣稱「多數 loader／updater 為 0%」，現況 `pipeline/tw` 加權 46%；仍為 0% 的只剩 `core/api/tw/finmind_api.py`、`core/utils/path.py` | **→ 已於 S21 修正文件**。**S21（2026-09-02）已把重測數字寫進 `docs/dev/code-quality.md` §三、§4.2**；§二的 21 條行號待 F-002／F-010~F-012 處置時一併重列 |
| F-015 | B | `core/config/schema.py:20` | `TICK_DB_PATH = f"{os.getenv('DDB_PATH')}{TICK_DB_NAME}"`：`.env` 缺 `DDB_PATH` 時靜默變成字串 `"NonetickDB"` | DolphinDB 的 `existsDatabase("NonetickDB")` 回 False，`StockTickAPI.setup()` 只 `print("* Database doesn't exist!")` 就往下走，錯誤訊息完全指不到 `.env` | **→ **ETL 失敗語意與缺口回補** S6**。改為缺項即 raise（與 `settings.get_int_env()` 的處理原則對齊）；tick 路徑目前未維護，S23 併入「環境變數與設定收斂」 |
| F-016 | C | `core/utils/path.py`（整檔） | 與 `core/config/paths.py` 重複的兩個 helper（`get_static_resolved_path` 完全相同；`get_env_resolved_path` 全專案無人呼叫），覆蓋率 0% | 兩份同名函式會讓人改錯一份 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S6**。刪除整檔（`core/utils/__init__.py` 未 re-export，無呼叫端） |
| F-017 | B | `core/utils/notify.py:17-23` | `post_line_notify()` 打的是 **LINE Notify**（`notify-api.line.me`），該服務已於 2025-03-31 終止；且 `requests.post()` 不帶 `timeout`、不檢查 `status_code` | 所有通知**靜默失敗**——沒有任何 log；唯一呼叫端是實盤成交回報 callback（`core/utils/callback.py:37`）。另回答本步驟的問題：**ETL 失敗路徑沒有掛任何通知**，`Notification` 只服務實盤 | **→ **ETL 失敗語意與缺口回補** S6**。實盤未實作，暫列 B；S23 開單時決定換 LINE Messaging API 或移除。至少先補 `timeout=` 與 `raise_for_status()` |
| F-018 | C | `.env.example` vs `core/config/{paths,settings}.py`、`frontend/config.py` | 程式會讀但範本沒列：`API_KEY_1`~`API_KEY_4`／`API_SECRET_KEY_1`~`_4`（tick 爬蟲多帳號）、`ALPHAEDGE_DATA_DIR`／`ALPHAEDGE_RESULTS_DIR`／`ALPHAEDGE_LOGS_DIR`（產物根覆寫）、`ALPHAEDGE_BACKTEST_RESULTS`（前端）；範本列的 8 個鍵程式都有讀 | 新人照範本設定後 tick 爬蟲的多帳號輪替會全部拿到 None | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S6**。S20 補齊範本（含註解說明何時需要） |
| F-019 | D | `core/utils/time.py:39-45`、`:56-77`；`core/utils/decorators.py:7-16` | `convert_roc_to_ad_year` 標 `-> str` 實際回傳 `int`；`generate_month_range` 依輸入型別回傳兩種語意不同的清單；`log_thread` 缺 `functools.wraps` | 型別註解與實作不符，呼叫端容易接錯型別 | **→ D 級，〈附錄 B〉計數**。併入 ruff 收斂單順手修 |
| F-020 | C | `core/models/base/account.py:94-105` | `check_has_position()` 掃 `self.positions` 時**沒有過濾 `is_closed`**，與同檔 `get_positions()`（有過濾）不一致 | 平倉後 `is_closed=True` 的部位留在 `positions`，直到 `BasePositionManager` 呼叫 `remove_closed_positions()`（`core/managers/base/position_manager.py:139`）；若兩者之間有任何路徑查 `check_has_position()`，會把已平倉的標的當成仍持有（影響 `max_holdings` 與重複開倉判斷） | **→ **回測口徑與日期邊界收斂** S3**。**S11 複核（2026-09-02）**：三條平倉路徑都走 `close_position()` 且收尾 `remove_closed_positions()`，已平倉部位不會殘留，降為 C；補 `not position.is_closed` 條件即可，不需測試 |
| F-021 | B | `core/models/stock/account.py:66-74` | `get_short_market_value()` 對沒有當日價格的放空部位退回 `position.price`（開倉價）算市值 | 停牌／無報價期間維持率用開倉價算，市值變動被凍結，追繳判斷那幾天失效 | **→ **回測口徑與日期邊界收斂** S3**。S11 對照 `no_quote_days` 保險絲，確認無報價部位是否在維持率計算前就被強制出場；否則改為明確標記「無法評價」 |
| F-022 | B | `core/adapters/tw/stock_quote_adapter.py:201-215` | `Scale.TICK` 路徑建出的 `StockQuote` 只帶 `tick_quote`，`open/high/low/close/cur_price` 全為 0.0 | 任何在 tick 級別讀 `quote.close`／`signal_close` 的程式（fill model 的 OHLC 區間檢查、策略的漲跌幅）會拿到 0；tick 回測目前無人跑（資料在 DolphinDB，`tests/` 無覆蓋） | **→ **回測口徑與日期邊界收斂** S2**。列為 tick 路徑已知限制；S13 確認 `fill_model.py:243/530` 的 TICK 分支是否只用 `tick_quote`；若是則在 `StockQuote` docstring 註明，否則補值 |
| F-023 | C | `core/adapters/tw/stock_quote_adapter.py:117-136` | `filtered_stock_ids` 是 list，`if stock.stock_id in filtered_stock_ids` 對每檔 O(n) 掃描 → 每根 bar O(n²)（約 2,000 檔 → 4×10⁶ 次比較） | 純效能；LONG 回歸線 55 秒有一部分耗在這裡 | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。改成 set；回歸雙線逐筆相同即可合入 |
| F-024 | B | `core/api/tw/stock_chip_api.py:133-155` | `get_net_chip()` 呼叫 `self.get(start_date, end_date)`，但 `get()` 只收一個 `date` → 一呼叫就 `TypeError` | 壞掉的公開方法；全專案無呼叫端，但 API 門面看起來可用 | **→ **回測口徑與日期邊界收斂** S7**。改為呼叫 `get_range()` 並補測試，或刪除 |
| F-025 | B | `core/api/tw/*.py` 全部 `pd.read_sql_query(..., params=(date,))` | 直接把 `datetime.date` 當 sqlite 參數，依賴 Python 的預設 date adapter；**Python 3.12 起該 adapter 已 deprecated**（`pytest` 現在就有一條 `DeprecationWarning`），移除後所有日期查詢會變成 `InterfaceError` | 期貨 API 的 `conn.execute()` 已改用 `str(date)`，`read_sql_query` 系列還沒，兩種風格並存 | **→ **回測口徑與日期邊界收斂** S7**。在 `core/api/base.py` 集中 `sqlite3.register_adapter(datetime.date, str)`（一行全專案生效）或統一改傳 `str(date)`；PostgreSQL 遷移時這層本來就要重寫，S23 併入該計畫 |
| F-026 | C | `core/api/tw/financial_statement_api.py:32-71`、`core/api/tw/futures_chip_api.py:56-119` | `table_name`／`table` 由呼叫端傳入後直接以 f-string 拼進 SQL | 現有呼叫端都傳 `config` 常數，不構成注入；但這是 `core/api/` 唯一兩處「表名不來自本檔常數」的方法 | **→ **回測口徑與日期邊界收斂** S7**。加允許清單斷言（`assert table in {...}`），成本一行 |
| F-027 | B | `core/api/tw/futures_margin_api.py:179-185`、`:226-231` | `get_margin_rates()`／`get_contract_size()` 沒有像 `get_margin()` 那樣包 `sqlite3.OperationalError` | 保證金表尚未建立時，金額型查詢回 None、比例型查詢直接拋錯——同一個 API 對「表不存在」有兩種行為，與檔頭「一律回 None 讓呼叫端決定」的宣告不符 | **→ **回測口徑與日期邊界收斂** S5**。統一成回 None；S12 查 `FuturesMarginConfig` 的呼叫端是否已假設會拋錯 |
| F-028 | B | `core/api/tw/stock_price_api.py:105-144`、`core/backtest/datafeed/tw/market_calendar.py` | 交易日曆**由 `price` 表推導**：「該日有資料」＝開盤日。價格回補若缺了某幾天，回測會把那幾天當休市**靜默跳過**，不會有任何錯誤 | 「查無資料」與「資料沒補到」在 API 層本來就無法區分（設計如此），因此**完整性檢查必須在別處補**：目前沒有任何地方檢查 `price` 表的交易日是否連續 | **→ **回測口徑與日期邊界收斂** S4（根治 → **ETL 失敗語意與缺口回補** S4）**。S22 加「交易日缺口檢查」（週一到週五、非國定假日、表內無資料的日期清單）並跑一次現況；S10 評估在 updater 收尾統計行印出缺口數 |
| F-029 | C | `core/api/tw/finmind_api.py`、`core/api/tw/stock_tick_api.py` | 兩支 API 不接受共用連線（`conn` 注入）、各自開連線；`finmind_api` 覆蓋率 0%；`stock_tick_api` 以 f-string 把 `stock_id` 拼進 DolphinDB script、`setup()` 連線失敗無處理、用 `print` | 與其他 12 支 API 的慣例不一致；tick 路徑未維護 | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。併入 PostgreSQL 遷移計畫的 API 層重寫；tick 路徑另議 |
| F-030 | **A** | `core/pipeline/tw/crawlers/stock_price_crawler.py:57-71`、`stock_chip_crawler.py:56-69`、`stock_margin_crawler.py:58-75`、`stock_dividend_crawler.py:85-100`、`monthly_revenue_report_crawler.py:79-95`、`financial_statement_crawler.py:135-148`（三張全市場報表）；根因在 `core/pipeline/shared/request_utils.py:81-116` | 四層混淆：① `RequestUtils.requests_get/post()` 重試耗盡回 **None**，且**從不檢查 HTTP 狀態碼**（403／5xx／被擋流量的 HTML 都當成功）；② `stock_price` 對 None 沒有先判，`res.text` 的 AttributeError 進 `except Exception` → 記「**{date} is a Holiday!**」；③ 錯誤頁 `read_html` 解析失敗同樣記成假日；④ chip／margin／dividend 對 None 雖有 `return None` 但**不留任何 log**。Updater 收到 None 即視為當日無資料（`stock_price_updater.py:106-127`），沒有 `unreachable` 計數，繼續下一天 | **網路失敗、被封鎖、站方 5xx 會被靜默記成「假日」**，那一天永遠缺資料且不會有任何統計行浮出——直接牴觸 [ETL 入庫約定 §3.2](../pipeline/etl-ingestion.md)。期貨線已知道並做對（`futures_price_crawler.py` 說明第 4 點、`futures_chip_crawler.py` 第 5 點；2026-09-02 籌碼回補實際被咬過一次：250 個交易日記成查無資料），台股線至今仍是「一律當假日吞掉」 | **→ **ETL 失敗語意與缺口回補** S1／S2**。**A 級，本工作內修**，排在期貨回補結束之後（S23 前）：① `RequestUtils` 回傳前檢查 `status_code`（非 2xx 視同失敗），重試耗盡改拋自訂 `DataFetchError` 而非回 None；② 五支台股 crawler 把「連線失敗」與「頁面無表格」分開記，比照 `futures_price_crawler.extract_quote_table()` 的 `ValueError` vs `Exception` 兩段式；③ updater 收尾統計行加 `unreachable` 計數（S10）。附測試：mock `requests_get` 回 None／回 503，斷言不得被記成假日 |
| F-031 | B | `core/pipeline/shared/request_utils.py:56-78`、`:84-89` | `find_best_session()` 10 次都失敗只 log「IP 已被封鎖」然後回 None；`requests_get()` 接著對 `cls.ses`（None）呼叫 `.get()` → `AttributeError`，不在 `RETRYABLE_EXCEPTIONS` 內 | 失敗會浮出（整個回補炸掉），但訊息是 `'NoneType' object has no attribute 'get'`，指不到真正原因；且每個 URL 的 session 探測都是 10 次 × 10 秒 | **→ **ETL 失敗語意與缺口回補** S1**。併入 F-030 一起修：session 建不起來時拋明確例外 |
| F-032 | B | `core/pipeline/tw/crawlers/stock_info_crawler.py:33-36`、`:69-72`、`:48-49` | `crawl_twse_stock_info()`／`crawl_tpex_stock_info()` 直接用 `response.text`，`requests_get` 回 None 時 AttributeError；沒有 log 與重試。另 TWSE 切權證區塊用 `warrant_idx - 1`，權證列若在第 0 列會切成空表 | `crawl_stock_list()` 是 tick 回補的股票清單來源，失敗會讓整批 tick 回補在起點就炸（有浮出，但無診斷訊息） | **→ **ETL 失敗語意與缺口回補** S1**。併入 F-030 的修法；補 None 判斷與 log |
| F-033 | C | `core/pipeline/shared/base_crawler.py`、`base_cleaner.py`、`base_updater.py` | 抽象基底只定義 `setup()`／`crawl()`（`*args, **kwargs`）；14 個 crawler 的 `crawl()` 簽名各異（`date`／`(start, end)`／`(year, month)`／無參數／`**kwargs`），其中 5 支是 `pass` 或丟棄結果的空殼（`stock_price`、`stock_info`、`stock_tick`、`finmind`、`futures_tick`） | 基底沒有約束力：updater 從不透過 `crawl()` 呼叫，都直接呼叫各自的具名方法；新人照介面呼叫 `crawl()` 會拿到 None 或什麼都沒發生（F-010 是其中一例） | **→ `docs/pipeline/etl-ingestion.md` §五**。S23 決定：基底移除 `crawl()` 只留 `setup()`，或統一各 crawler 主入口命名並回傳結果。不影響行為 |
| F-034 | C | `core/pipeline/shared/request_utils.py:18-22`、`financial_statement_crawler.py:29-32`、`monthly_revenue_report_crawler.py:25-26` | 節流常數散在三處且語意各異：`RequestUtils` 的 HTTP 重試 60 秒／session 重試 10 秒；財報與月營收各自 `random.uniform(1, 3)`；期貨行情「本層不 sleep、由 updater 負責」；台股價量爬蟲本身無節流、全靠 updater 的 `BATCH_SLEEP_*` | 各來源的政策不一致但各有理由；沒有集中管理是可維護性問題 | **→ `docs/pipeline/etl-ingestion.md` §五**。只記錄；S10 對照各 updater 的 sleep 後再決定是否集中到 `RequestUtils` |
| F-035 | C | `core/pipeline/tw/crawlers/finmind_crawler.py:65-83`（四個方法同型） | quota 用盡有 `FinMindQuotaExhaustedError` 分流 ✅；其餘例外一律 `logger.error` 後回 None，與「查無資料」同型 | `TaiwanStockInfo` 等靜態表若因網路失敗回 None，updater 可能誤判成「本次無更新」 | **→ `docs/pipeline/etl-ingestion.md` §五**。與 F-030 同型但已有部分分流，併入同一單、優先度較低 |
| F-036 | C | `core/pipeline/tw/crawlers/futures_chip_crawler.py:36-48`、`:157-160` | 模組說明承認「被擋流量與真的沒資料長得一模一樣」，兩者都回 None，把「該不該重試」推給 updater | 這條的 HTML 辨識已比台股線好；但推給 updater 的重試判斷是否真的存在要看 `futures_chip_updater` | **→ `docs/pipeline/etl-ingestion.md` §五**。S10 追查；此處只登錄 |
| F-037 | B | `core/pipeline/tw/cleaners/stock_price_cleaner.py:69-70`、`:146-147`（`DataUtils.fill_nan(df, 0)`） | TWSE／TPEX 對無成交的股票以 `--` 表示 OHLC，`convert_col_to_numeric` 轉成 NaN 後被 `fill_nan(0)` 寫成 0。實測 `price` 表 6,247,050 列中 **104,046 列（1.7%）OHLC 全為 0**（`成交股數=0` 者 96,089 列；例：2013-01-02 的 2718 桃園店、4801 高盛、5301 祥裕） | `StockQuote(close=0, signal_close=0)` 被當成真實報價流進引擎：訊號層會算出 −100% 漲跌幅（三支現有策略各自加了 `<= 0` 防線，`fill_model`／`backtester` 沒有）；還原價 `0 × factor = 0`；**持倉股票遇到無成交日，未實現損益與逐日權益快照會以 0 評價**。這是 F-028 的另一面：0 價比缺列更危險，因為它「看起來有資料」 | **→ **ETL 失敗語意與缺口回補** S5＋→ **回測口徑與日期邊界收斂** S2**。S13 確認 `stock_datafeed`／`snapshot_daily_equity` 是否過濾 0 價：沒有則維持 A。資料層修法是「無成交日價格存 NULL」或「沿用前收且量為 0」，兩者都會改到 6.2M 列與 LONG baseline，屬 S23 決策；短期先在 `StockQuoteAdapter` 濾掉 `close <= 0` 並補測試 **S12 複核（2026-09-02）由暫定 A 降為 B**：盯市（`get_mark_price`）、無報價計數、`on_bar_close` 記前收、`update_intraday_range`、sizing 全部把 0 價當缺報價處理，權益快照不會出現 −100%；**剩下的漏洞在成交路徑**——`get_price_range()` 在 `high`／`low` 為 0 時回 `(None, None)` 直接跳過區間檢查，`max_volume_share` 預設關閉也不看 `volume == 0`，策略若以自算價下單，會在**沒有任何成交的日子成交**。修法：`TwStockFillModel.validate()` 在 DAY 級別對 `not quote.volume`（或 OHLC 皆 0）的 bar 一律拒單並計入 `rejected_fill_price`，adapter 端另加 `close > 0` 過濾（F-022 tick 路徑同） |
| F-038 | B | `core/pipeline/tw/cleaners/stock_price_cleaner.py:92-133`、`stock_chip_cleaner.py:84-107`、`:147-219` | TPEX 價量以**位置**重新命名欄位（兩種版面依 2020-04-30 切換）但**沒有欄位數檢查**；TPEX 三大法人三種版面以 `zip(old, new)` 改名，欄位數不符時 `zip` **靜默截斷**；TWSE 三大法人以 `df.get(col, 0)` 取欄，來源改名時靜默以 0 計算 | 版面改制過去已發生三次（2014-12-01、2017-12-18、2018-01-15），下一次會**錯位入庫而不報錯**；對照組 `stock_margin_cleaner`／`stock_dividend_cleaner`／五支期貨 cleaner 都有「欄位數不符即中止」 | **→ **ETL 失敗語意與缺口回補** S5**。比照 `stock_margin_cleaner.clean_margin()` 補 `df.shape[1] != len(raw_cols)` 檢查、`df.get()` 改為明確 KeyError；併入 F-030 的 ETL 收斂單 |
| F-039 | C | `core/pipeline/tw/cleaners/financial_statement_cleaner.py:102-104`、`:126-137`；`monthly_revenue_report_cleaner.py:55-57`、`:200-238` | 欄位對照表（`*_all_columns.json`／`*_column_map.json`／`*_cleaned_columns.json`）缺檔時只 `logger.warning` 後繼續，`reindex(columns=new_df.columns)` 會把所有資料欄丟掉，產出只剩 `year/season/stock_id/公司名稱` 的空殼 | `config/paths.py` 註解已承認「缺檔只會 warning 後靜默降級清洗」；schema 在版控內故實務上不會缺，但這條防線是文件不是程式 | **→ `docs/pipeline/etl-ingestion.md` §五**。缺檔改為 raise（設定檔缺失屬啟動即失敗，與 `FINMIND_API_TOKEN` 同原則） |
| F-040 | C | `core/pipeline/tw/cleaners/monthly_revenue_report_cleaner.py:240-244` | `fix_broken_char()` 把任何 `�` 一律換成「碁」 | 只針對已知的 big5 缺字；其他罕見字（堃、喆…）被 big5 吃掉時會被改成錯的字且無訊息。只影響 `公司名稱`（非主鍵） | **→ `docs/pipeline/etl-ingestion.md` §五**。記錄；先以 `cp950` 解碼可涵蓋更多字，S23 併入 ETL 收斂單 |
| F-041 | C | `core/pipeline/tw/cleaners/futures_margin_cleaner.py:667-722` | 公告標題解析不出生效日時退回「公告日 +1」並 warning，與同檔第 1 點「解析不到一律整批放棄、不可退回今天」不一致 | 變動序列混入一列猜測的生效日，會讓該商品的保證金區間錯位 1~N 天且看起來正常 | **→ `docs/pipeline/etl-ingestion.md` §五**。改為與快照一致：解析失敗整則跳過並計入統計，由人工補 |
| F-042 | C | `core/pipeline/tw/cleaners/futures_stock_universe_cleaner.py:10-12`、`futures_tick_cleaner.py:8` | cleaner import crawler（`is_valid_base_code`／`to_commodity_id`）與引擎的 `FuturesCalendar`（F-004） | 清洗層相依爬取層屬同層互相 import，其他 cleaner 沒有這種相依；`to_commodity_id` 這類純規則應放 `core/utils` | **→ `docs/pipeline/etl-ingestion.md` §五**。併入 F-004 的搬遷（期貨代碼規則與日曆一起搬出） |
| F-043 | **A** | `core/pipeline/tw/loaders/stock_price_loader.py:214-225` | `add_to_db()` 逐檔 `except Exception → logger.error`，只累加 `error_cnt`，**沒有呼叫 `finish_load()`／拋 `DataLoadError`**，最後印「Total files processed: N new, M skipped, K errors」後正常結束 | 正是 [ETL 入庫約定 §4.2](../pipeline/etl-ingestion.md) 記錄的事故型態（2026-08-16 margin 缺 1,553 列）；margin／chip 已改用 `finish_load()`，**價格表——回測最核心的一張表——沒有改**。`tests/test_loader_failure_reporting.py` 只釘住 margin | **→ **ETL 失敗語意與缺口回補** S3**。**A 級，本工作內修**：改用 `insert_dataframe()`＋`finish_load()`（與 chip 同型）並把 `test_loader_failure_reporting.py` 的參數化擴到 price；順帶解掉 F-044 |
| F-044 | B | `core/pipeline/tw/loaders/stock_price_loader.py:119-140`、`monthly_revenue_report_loader.py:146-153` | 每次 `add_to_db()`（含分批的每一批）都把**整張表的主鍵讀進記憶體**（price 6,247,050 列 → 6M 個三元組）；月營收 loader 更是**每個檔案**重讀一次整表 | 13 年回補分 63 批就是 63 次全表掃描，記憶體峰值以 GB 計；月營收 O(檔案數 × 表大小) | **→ **ETL 失敗語意與缺口回補** S6**。改用 `insert_dataframe()`（`INSERT OR IGNORE`）就不需要預載主鍵，隨 F-043 一併解 |
| F-045 | **A** | `core/pipeline/tw/loaders/finmind/reference_table_loader.py:130-132`、`broker_trading_loader.py:143-175`、`:330-336` | FinMind 三條入庫路徑失敗都被吞：參考表 `except → logger.error`；券商分點 DataFrame 路徑失敗後**退回不查重的 `to_sql(append)`**（撞主鍵再失敗就回 0）；CSV 路徑把失敗**算進 `skipped_files`** 後 `continue`，收尾印「✅ …completed」 | 與 F-043 同型：失敗看起來像跳過。券商分點回補（2021-06-30 起，逐檔逐券商）中途壞掉，缺口只能靠事後對帳 | **→ **ETL 失敗語意與缺口回補** S3**。三處改為收集 `failed_files` 並走 `finish_load()`；刪除 fallback 路徑（撞主鍵應由 `INSERT OR IGNORE` 處理，不該用不查重的 append 再試） |
| F-046 | B | `core/pipeline/tw/loaders/stock_tick_loader.py:187-193`、`:228-234`；`futures_tick_loader.py:207-209` | DolphinDB 寫入失敗一律 `logger.info`／`warning` 後不拋、不回傳失敗數；`append_all_csv_to_dolphinDB` 一次 script 寫全部檔案，失敗時不知道寫到哪一檔 | tick 路徑目前未維護（DolphinDB 未啟動），但與 F-043 同型，啟用時會重演 | **→ **ETL 失敗語意與缺口回補** S3**。記錄；tick 路徑重啟時比照 `finish_load()` |
| F-047 | B | `core/pipeline/tw/loaders/stock_dividend_loader.py:117-140` | 三個來源（twse／tpex／finmind）跨檔去重 `keep="last"`，而檔案順序是 `sorted(dir)` ＝ **檔名字典序**，來源優先序由檔名決定而非明文規則 | 同一筆除權息三個來源值不同時（TPEX 有官方股利拆分、FinMind 沒有），最後留下哪一筆取決於檔名 | **→ **ETL 失敗語意與缺口回補** S5**。明訂優先序（建議 tpex > twse > finmind）並在 loader 內排序，不靠檔名 |
| F-048 | C | `core/pipeline/tw/loaders/stock_price_loader.py:74`、`stock_chip_loader.py:76` | `price`／`chip` 主鍵是 `(date, stock_id, 證券名稱)`，`margin`／`dividend` 是 `(date, stock_id)`；名稱進主鍵是為了容納「上市股與上櫃 ETF 共用 4 碼」，但同一檔更名時同一天可能出現兩列 | 實測目前無重複；這是 [ETL 入庫約定 §4.4](../pipeline/etl-ingestion.md)「沒有市場欄位的主鍵」的變形——用名稱當市場欄的替身 | **→ `docs/pipeline/etl-ingestion.md` §五**。歸 S22／PostgreSQL 遷移：主鍵改為 `(date, stock_id, listing_board)` |
| F-049 | C | `core/pipeline/tw/loaders/futures_margin_loader.py:270-276` | `insert_rows()` 以「第一欄是 `effective_date`」的**位置假設**把日期轉字串 | cleaner 目前確實把 `effective_date` 放第一欄；欄位順序一改就會把別的欄位 `str()` 掉 | **→ `docs/pipeline/etl-ingestion.md` §五**。改為依欄名轉換 |
| F-050 | **A** | `core/pipeline/tw/updaters/stock_price_updater.py:164-183`（`stock_chip`：154-172、`stock_margin`：233-251、`stock_dividend`：135-153 同型） | 續跑起點一律是「表內 `MAX(date)` +1」，呼叫端的 `start_date` 只在表為空時生效；沒有 `resume=False`（期貨線有）；收尾沒有 requested／no data／unreachable 統計 | **與 F-030 合起來就是資料永久缺口的完整機制**：某天因連線失敗被記成「假日」→ 當天無檔案 → 下一次執行從 `MAX(date)+1` 起跑，那一天再也不會被請求，也沒有任何統計行提示。回測端又把「無資料」當「休市」（F-028），三層都靜默 | **→ **ETL 失敗語意與缺口回補** S4**。**A 級，與 F-030 同一單修**：① `update()` 加 `resume` 參數（比照 `futures_price_updater`）；② 收尾統計行印出本次 requested／no data／unreachable；③ S22 的「交易日缺口檢查」跑一次現況，把已存在的缺口列出來回補 |
| F-051 | B | `core/pipeline/tw/updaters/finmind/broker_trading_updater.py:311-321`、`finmind_updater.py:223` | quota 等待逾 120 分鐘後 `quota_exhausted=True` 只 warning 並 break，`update_all()` 收尾仍印「✅ All FinMind Data updated successfully」；`update_db` 看到的是成功 | 券商分點回補跑到一半停掉會被當成完成 | **→ **ETL 失敗語意與缺口回補** S4**。未完成時拋例外或回傳狀態讓 `target_guard` 記為失敗 |
| F-052 | B | `core/pipeline/tw/updaters/stock_tick_updater.py:333-353`、`crawlers/stock_tick_crawler.py:59-69`、`utils/stock_tick_utils.py:262-295` | Shioaji 例外在 crawler 被吞成 None，updater 把 None 算成 `skipped_dates`（「non-trading day or no data」）；`check_date_crawled()` 以每檔 `last_date` 判斷，`date <= last_date` 一律跳過 | 配額用盡或 API 錯誤造成的缺口與假日無法區分，且被 `last_date` 蓋住後永不回補（與 F-050 同型） | **→ **ETL 失敗語意與缺口回補** S4**。tick 路徑目前未維護；重啟時比照 F-050 修法 |
| F-053 | B | `core/pipeline/tw/updaters/futures_chip_updater.py:230-234` | 「該有交易日卻沒拿到 CSV」的月份重試後仍失敗只 `logger.warning`，不列入失敗、不影響結束碼 | 這條線的偵測已經做對（用交易日判被擋），但最後一步沒有讓 `update_db` 知道；被擋的月份要靠人看 log 才會重跑 | **→ **ETL 失敗語意與缺口回補** S4**。`blocked_windows` 非空時拋 `DataLoadError`（或自訂例外），讓 `target_guard` 記為失敗 |
| F-054 | B | `core/pipeline/tw/updaters/financial_statement_updater.py:197-203`（三張報表同型）、`monthly_revenue_report_updater.py:91-96` | `years × seasons`（或 `months`）用**笛卡兒積**展開：續跑起點 (2025, Q3) 會產生 `[2025, 2026] × [3, 4]`，本次執行**不會請求 2026Q1／Q2** | 跨年續跑時次年前幾期被漏掉；下一次執行因 `latest_season == 4` 進位後會自癒，所以是**延遲**不是永久缺口。另 `TimeUtils.generate_season_range()` 被拿來產生年份清單（命名誤用） | **→ **ETL 失敗語意與缺口回補** S4**。改為線性的 `(year, season)` 序列（從起點走到迄點）；順手把 `generate_season_range` 的誤用換成 `generate_year_range` |
| F-055 | C | `core/pipeline/tw/updaters/finmind/common.py:436-483`、`broker_trading_updater.py:205-243` | metadata 只存每個 (券商, 股票) 的 `(earliest, latest)`，`get_existing_dates()` 把區間內**每一個曆日**都當成已存在 | 區間內的缺口（例如一次請求只回傳部分日期）永遠不會被補；但 FinMind 的區間查詢一次回整段，實務上缺口機率低 | **→ `docs/pipeline/etl-ingestion.md` §五**。記錄；若要嚴謹應以 DB 的 `DISTINCT date` 而非區間展開 |
| F-056 | B | `core/pipeline/utils/sqlite_utils.py:44-46`、`:85-87` | `get_table_earliest_value()`／`get_table_latest_value()` 把 `sqlite3.Error`（鎖定、損毀、表不存在以外的錯誤）吞成 `None`，呼叫端把 None 當成「表是空的」 | 資料庫暫時鎖定時，updater 會從 2013 年的預設起點**整段重爬**——`INSERT OR IGNORE` 讓資料不會壞，但要多跑好幾個小時，且 log 只會看到「Latest data date in database: 2013-01-01」 | **→ **ETL 失敗語意與缺口回補** S3**。只對 `no such table` 回 None，其餘 sqlite 錯誤上拋 |
| F-057 | B | `core/managers/stock/position_manager.py:55-127`、`:155-160` | 同標的雙向持倉只在**開空**時檢查「已有多單」；**開多**時不檢查「已有空單」 | [放空框架 §7.5／§7.7](../backtest/short-selling-framework.md) 寫「已有多單時開空單會被拒絕（**反之亦然**）」，實作只做了一半：策略先空後多會同時持有兩個方向，`check_has_position()`／報表的單一方向假設被打破，維持率與曝險統計會算錯 | **→ **回測口徑與日期邊界收斂** S3**。在 `open_position()` 的 LONG 分支補對稱檢查並加測試（既有測試沒有釘住「先空後多」）；同步核對 `backtester.validate_orders()` 是否已在上游擋掉 |
| F-058 | C | `core/managers/futures/position_manager.py:318-394` | 期貨開倉不檢查同契約是否已有反向部位；`FuturesAccount.get_open_lots()` 雖會相抵成淨口數，但兩個方向的部位**各自佔用一份原始保證金** | 同契約多空並存時保證金被重複佔用（交易所對沖部位只收單邊），資金效率被低估——方向保守，不會讓績效變好看；但與 `get_open_lots()` 的「淨口數」語意不一致 | **→ **回測口徑與日期邊界收斂** S3（2026-09-04 完成）**。改以**擋在開倉端**收斂：`open_position()` 對「同契約已有反向未平倉部位」拒單（兩個方向都擋，判準沿用放空框架 §7.5，與 F-057 對稱），該狀態因此不可能發生。**保證金減收不做**——交易所的單邊收取針對同商品**跨月份**的價差部位，而 TAIFEX 價差部位保證金是另一張費率表且本專案無資料源（列為 [台期貨保證金ETL](../../backlog/台期貨保證金ETL.md) S7 ⏸），跨月份兩腿各繳全額、方向保守。順帶釘住 `MomentumFuturesStrategy` 的兩個控管（`lots != 0` 判有無部位、`sum(abs(lots))` 扣 `max_lots`）在淨額為 0 時會被靜默繞過 |
| F-059 | B | `core/backtest/models/settlement_model.py:468-495` | SBL 借券費以**每根 bar** `holding_days=1` 計提（÷365），一年只計 252 次 | 放空框架 §3.3 明寫「利息與 SBL 借券費一律以曆日 ÷ 365」；實測 100 元×10 張、年費率 3%：每 bar 82 元、一年累計 20,664，曆日口徑應為 30,000，**系統性低估 SBL 成本約 31%**（週末、連假前後各差 2~9 天）。MARGIN 利息在平倉時以日期差算則正確，同一份設計兩種口徑 | **→ **回測口徑與日期邊界收斂** S1**。`accrue_holding_cost()` 改以「本 bar 日期 − 上次計提日期」的曆日數計提（需在 `StockPosition` 記 `last_accrual_date`，或直接以 `date − position.date − 已計提天數`）；補一條「跨週末持有 3 曆日只有 1 個 bar」的測試 |
| F-060 | B | `core/backtest/models/cost_model.py:277-284`、`:320-353` | 當沖證交稅減半（0.15%）**不看交易日**：`check_day_trade_tax_expiry()` 用 `datetime.date.today()` 比落日期限，`tax()` 只看 `is_day_trade` | 現股當沖減半自 2017-04-28 起實施（`DAY_TRADE_TAX_EXPIRY` 只寫了結束日，沒有起始日）；資料自 2013 年起，2013~2017/04 的當沖回測賣出稅被少算一半，`ForeignSellShortDayTradeStrategy` 這類當沖策略在該區間的績效偏樂觀 | **→ **回測口徑與日期邊界收斂** S1**。`core/utils` 補 `DAY_TRADE_TAX_START`（2017-04-28），`tax()` 增加 `date` 參數，只在 `[START, EXPIRY]` 內套減半；`check_day_trade_tax_expiry()` 改在回測起訖日落在區間外時警告，而不是看真實今天；補測試 |
| F-061 | C | `core/backtest/models/instrument_spec.py:146-185` | `TwStockSpec.get_price_limits()` 與交易所公告漲跌停的相符率 61.6%（程式 docstring 已註明，2026-08-15 實測 23,972 筆） | 影響兩處：`validate()` 邊界拒單、`check_limit_up_locked()` 的「漲停鎖死轉留倉」判定（`limit_up_cover_failed` 計數會偏差）。多數不符者只差一個檔位，不影響非邊界訂單 | **→ `docs/backtest/multi-market-engine.md` §九**。既然已有 23,972 筆公告值，優先改用資料驅動：DataFeed 已有 `get_price_limit_basis()` 掛點，擴充為直接提供公告的漲跌停價；公式版只做 fallback |
| F-062 | C | `core/backtest/models/cost_model.py:1170-1226`、`core/managers/futures/position_manager.py` | `TwFuturesCostModel.realized_pnl()`／`roi()` 與 `FuturesPositionManager.calculate_pnl()`／`calculate_roi()` 是**同一公式的兩份實作**，manager 只向 cost model 取手續費與稅 | 兩處各算一份必然漂移（cost model 自己的 docstring 也這樣警告 `FuturesCostConfig`）；目前數值一致，但改一邊忘另一邊沒有測試會抓到 | **→ **回測口徑與日期邊界收斂** S5**。二擇一：manager 改呼叫 cost model 的版本，或刪掉 cost model 的 `realized_pnl`／`roi`（保留 `BaseCostModel` 介面所需的最小實作並轉呼叫） |
| F-063 | C | `core/backtest/models/settlement_model.py:483-484`、`core/managers/stock/position_manager.py`（`close_short_position`） | `StockPosition.holding_days` 是**bar 數**（每根 bar +1），`StockTradeRecord.holding_days` 與利息計算是**曆日**（日期差）；`max_holding_days` 比對的是前者 | 同名兩種口徑：策略設 `max_holding_days=10` 實際是 10 個交易日（約 14 曆日），報表卻顯示曆日；使用者對不上 | **→ **回測口徑與日期邊界收斂** S1**。擇一統一（建議部位也改記曆日，與 F-059 一併修），或把部位欄位改名 `holding_bars` |
| F-064 | B | `core/backtest/backtester.py:491-495`、`:582-590`、`core/backtest/models/fill_model.py:205-236` | 成交價合理性檢查（區間／漲跌停）**只在開倉腿**、且檢查的是**滑價前**的 `order.price`；平倉腿（停損與一般平倉）完全不檢查 | 開啟 `slippage_bps_*` 時，掛在 `high` 的買單會以 `high × (1 + bps)` 成交——當天沒印過的價格；平倉腿以任何價格都能成交，策略若誤傳次日價（前視）不會被擋也不會被計數。程式註解說明平倉不檢查是為了不改既有行為 | **→ **回測口徑與日期邊界收斂** S2**。兩段修法：(1) `fill()` 之後對 `filled_order.price` 再做一次區間檢查，超出時夾到 `[low, high]`／漲跌停內並計數；(2) 平倉腿至少做「超出區間只警告＋計數」（新增 key，如 `close_price_out_of_range`），不拒單即不影響 baseline |
| F-065 | B | `core/backtest/datafeed/tw/market_calendar.py:64-103`；呼叫端 `core/strategies/stock/momentum_strategy_1.py:74`、`core/utils/instrument.py:55` | `get_last_trading_date()` 逐日往前查 `api.get(date)` **直到有資料為止，沒有上限** | 回測起始日＝資料庫第一天、或該區段整段缺資料（F-050 的缺口）時，迴圈會一路往前查到 `datetime.date` 下限才因 `OverflowError` 中止（約 73 萬次 SQL）——實務上就是卡死；且 `MomentumStrategy1` **每根 bar** 都呼叫一次，每次都是整天 `SELECT *` | **→ **回測口徑與日期邊界收斂** S4**。加上界（例如往前最多 30 個曆日，超過即 raise 並說明「資料起點之前無交易日」）；策略端改用 `StockPriceAPI.get_trading_days()` 建一次清單後以 `shift_trading_days()` 取前一日（`ForeignSellShortDayTradeStrategy` 已是這種寫法） |
| F-066 | C | `core/backtest/datafeed/tw/stock_datafeed.py:78-81`、`market_calendar.py:18-29` | `is_market_open()` 對回測區間內**每個曆日**執行 `SELECT * FROM price WHERE date = ?`（約 2,000 列 × 全欄位）只為了判斷是否為空；接著 `get_quotes()` 再查同一天一次 | 純效能：每個交易日多一次整天查詢；期貨側已改為一次建 `FuturesCalendar`（交易日集合），台股仍逐日查 | **→ **回測口徑與日期邊界收斂** S4**。台股同樣在 `setup()` 用 `get_trading_days(start, end)` 建一次集合；`MarketCalendar.check_stock_market_open()` 改 `SELECT 1 … LIMIT 1` |
| F-067 | C | `core/backtest/report/reporter.py:57-70`、`:776-828`、`:28-33` | 三處可維護性：(1) `setup()` 自建 `StockPriceAPI()` 第二條連線且從不 `close()`；(2) `set_figure_config(show=True)` 預設每張圖 `fig.show(renderer="browser")`，一次回測開 5 個瀏覽器分頁、無 headless 開關；(3) `STOCK_SPLITS` 寫死 0050 於 2025-06-18 的 1 拆 4，而 `StockPriceAPI` 已支援還原價（`tests/test_adjusted_price_api.py`） | (1) 連線洩漏（`Backtester.run()` 例外路徑也不會關 `data_feed`）；(2) 批次／CI 跑報表會嘗試開瀏覽器；(3) 對標曲線的分割調整與還原價兩套來源，改一邊忘一邊 | **→ [前端指標與報表同源化.md](../../backlog/前端指標與報表同源化.md) S4**。(1) reporter 改吃 `data_feed.price` 或在結束時 `close()`，`run()` 用 `try/finally` 關 feed；(2) 增加 `show` 參數由 `run.py` 或環境變數決定；(3) benchmark 改用 `adjusted=True` 取還原收盤價並刪除 `STOCK_SPLITS` |
| F-068 | B | `core/backtest/analysis/analyzer.py:93-138`、`:141-172` | `StockBacktestAnalyzer` 的風險調整指標公式：Sharpe ＝（每筆 ROI% 平均 − `risk_free_rate=0.02`）／每筆 ROI% 標準差——**分子單位是百分比、無風險利率是小數**，且以每筆交易而非時間序列計算、未年化；Sortino 的下行風險取「虧損子集的標準差」而非 √mean(min(r − T, 0)²)；`compute_win_rate()`／`compute_average_return()` 零筆交易時 `ZeroDivisionError`、`compute_profit_factor()` 無虧損筆時除以零 | Analyzer 定位為「測試與研究驗算」而非正式輸出（`base.py` docstring），故不列 A；但 S13 要求逐條核公式，這幾個數字目前不能拿來比較策略 | **→ **回測口徑與日期邊界收斂** S8**。改以 `daily_equity` 的日報酬序列算年化 Sharpe／Sortino（`√252`），無風險利率轉成日頻同單位；零筆交易與零虧損筆數回傳 `None`／`inf` 並寫 docstring；補測試 |
| F-069 | C | `core/backtest/report/futures_reporter.py:98-104` | 期貨對標序列「近月拼接」以 `sort_values(["date", "expiry"])` 取字典序最小者：月契約到期後至月底，`202601W4`／`W5` 這類週契約排在 `202602` 之前而被當成近月；行情表在結算日後的殘留列（`futures_roll.py:82-83` 已註明會有）也會被選中 | 對標曲線每月有一週接到週契約、偶爾接到已到期契約，假跳空比 docstring 描述的「展期價差」更多；程式已聲明只是粗略參考 | **→ **回測口徑與日期邊界收斂** S5**。重用 `FuturesRollPlanner.filter_expiries()`＋`check_tradable()`（同一份規則）挑近月；Phase1-7 連續合約完成後改讀連續合約 |
| F-070 | C | `core/backtest/datafeed/tw/futures_datafeed.py:188-212` | 期貨交易日曆只以 `products[0]` 建立（docstring 已說明理由） | 多商品策略中第二個以後的商品，在第一個商品沒有行情的日子（不同商品掛牌期間不同、個別停牌）整天被跳過，策略拿不到報價也不會被通知 | **→ **回測口徑與日期邊界收斂** S5**。日曆改為 `products` 的聯集（各商品交易日 union），`is_market_open()` 判聯集；報價仍逐商品取 |
| F-071 | B | `core/backtest/models/settlement_model.py:974-1001`、`core/backtest/datafeed/tw/futures_roll.py:190-242` | 結算模型的即時轉倉逐日呼叫 `resolve_active_expiry()`，只跳過 `active == position.expiry`；`build_roll_schedule()` 才有「換月只往前不回頭」的護欄 | `OPEN_INTEREST` 規則下未沖銷量交叉後再反轉時，持倉會被轉回較近月（平倉＋開倉各付一次成本），與連續合約的序列脫鉤；預設的 `LAST_TRADING_DAY` 規則不會發生。另：轉倉時舊契約以**結算價**平、新契約以**收盤價**開（`roll_single_position()`），展期價差混用兩種價 | **→ **回測口徑與日期邊界收斂** S5**。`roll_positions()` 加 `active < position.expiry` 即跳過（與 `build_roll_schedule()` 同一條護欄），並補 `OPEN_INTEREST` 反轉情境的測試；展期價差統一用同一種價（兩邊都用收盤或都用結算價） |
| F-072 | B | `core/strategies/stock/overnight_lead_event_strategy.py:60`、`:106-133` | 策略在 `__init__` 呼叫 `_build_signals()`，第一行就用 `self.price.get_close_series()`——但 `self.price` 要到引擎的 `setup_apis(feed)` 才會注入；同一函式接著在策略內直接 `yfinance.download()` 打外部網路 | **實測 `OvernightLeadEventStrategy()` 立即 `AttributeError: 'NoneType' object has no attribute 'get_close_series'`**，`run.py --strategy OvernightLeadEventStrategy` 必定失敗（覆蓋率 0% 的原因）。即使修好順序，訊號仍依賴每次執行時的網路下載（無快取、`auto_adjust=True` 會隨 yfinance 版本變動），回測不可重現。docstring 為英文且無「停損條件」區塊 | **→ **回測口徑與日期邊界收斂** S6**。把 `_build_signals()` 移到 `setup_apis()` 之後（例如首次 `check_open_signal` 時 lazy 建立）；美股特徵改由 ETL 入庫、策略只讀 DB；docstring 依 §2.2 改寫三區塊；補一條「建構＋`setup_apis` 後可產生訊號」的測試 |
| F-073 | B | `core/strategies/strategy_loader.py:31-53`、`run.py:39` | `load_strategies()` 逐一 `import_module` 所有策略模組，**任一模組 import 失敗即整個 loader 例外**；同名類別跨套件時 `strategies[name] = obj` 靜默覆蓋 | 一支 WIP 策略的語法錯誤或缺套件（例如 `yfinance` 未安裝）會讓 `run.py` 對**所有**策略都失敗，錯誤訊息指向與使用者無關的模組；同名策略只會跑到後載入的那一支，沒有任何提示 | **→ **回測口徑與日期邊界收斂** S6**。逐模組 `try/except ImportError, SyntaxError` → `logger.error` 並略過該模組；偵測重複類名時 `raise`；補測試（以暫時建立的壞模組驗證） |
| F-074 | C | `tests/test_strategy_data_access.py`、`core/strategies/README.md:194` | 「策略不得自行建立 API／連線」只寫在 README，沒有測試釘住；現有測試只擋資料庫欄位字面值 | 目前 grep 無違規，但下一支策略 `StockPriceAPI()` 自建連線不會有任何測試變紅（一次回測多開連線，見多市場引擎文件） | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S5**。在同一支測試加一條 parametrize：`sqlite3.connect(`、`API()`、`dolphindb` 等字樣在 `core/strategies/` 出現即失敗（`ALLOWED_FILES` 機制已存在） |
| F-075 | C | `core/strategies/stock/momentum_strategy_1.py:52-76`、`:83-110` | (1) `setup_apis()` 在 TICK 級別只設 `self.tick`，`check_open_signal()` 卻無條件呼叫 `MarketCalendar.get_last_trading_date(api=self.price)` → `api=None` 進 `else` 分支 `ValueError("Invalid API type")`；(2) 開倉候選不排除已持有的標的（`ForeignSell…` 有 `check_has_position` 過濾），同一標的可重複加碼，docstring 未說明 | (1) 把 `scale` 改成 TICK 會在第一根 bar 崩潰，docstring 只寫「日線」沒有擋；(2) 是否允許加碼屬策略語意，但沒寫清楚就無法判斷回測結果對不對 | **→ **回測口徑與日期邊界收斂** S6**。(1) `__init__` 或 `setup_apis()` 對 `scale != DAY` 直接 `raise NotImplementedError`；(2) docstring 補「已持有者仍可再開（加碼）」或加 `check_has_position` 過濾——二擇一並更新 LONG baseline 說明 |
| F-076 | C | `core/strategies/base.py:31`、`core/backtest/backtester.py:525-537` | `BaseStrategy.max_holdings` 預設 `0`，引擎只把 `None` 當「不限制」 | 新策略忘了設 `max_holdings` → 每一張開倉單都被 `check_max_holdings()` 剔除，只有 warning 與 `rejected_max_holdings` 計數，回測「跑完但零交易」；`BaseFuturesStrategy` 已因此被迫覆寫成 `None` | **→ **回測口徑與日期邊界收斂** S6**。預設改為 `None`（不限制）或在 `factory` 對 `max_holdings == 0` 直接 `raise`，讓漏設在開跑前就報錯 |
| F-077 | B | `run.py:41-46`、`:55-56` | 策略名找不到只 `print` 後 `return`（exit 0）；`--mode live` 是 `pass`（exit 0，無任何輸出） | 實測兩者退出碼皆 0。目前 `run.py` 沒有被排程或 CI 包起來（只有人手動跑），故不列 A；但一旦接進批次（例如每晚重跑策略）就是假綠燈；`--mode live` 讓 `--help` 看起來已支援實盤 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S3**。找不到策略 → `sys.exit(2)`＋列出可用清單到 stderr；`live` 分支 `raise NotImplementedError` 或從 `choices` 移除；補一條 subprocess 退出碼測試 |
| F-078 | B | `tasks/update_db.py:319-321`、`:397-412` | 預設 `no_tick` ＝ `DataType` 全部 − `TICK`，**沒有排除 `FUTURES_TICK`**；docstring 寫「全部資料（不含 tick）」 | `python -m tasks.update_db`（預設）會跑 `futures_tick`（Shioaji 登入＋DolphinDB），沒有金鑰或 DolphinDB 的環境（本機常態、CI）該 target 必失敗，`target_guard` 記錄後整批以 exit 1 結束——每晚的預設更新永遠是紅的，真正的失敗淹在裡面（與 F-050 的「缺口永不回補」互相掩護）。另：`--target finmind stock_info` 會各建一個 `FinMindUpdater()` | **→ **ETL 失敗語意與缺口回補** S6**。`no_tick` 排除 `{TICK, FUTURES_TICK}`（或改名 `no_tick` → 同時排除所有 tick 類）；docstring 對照表同步；補測試釘住 `no_tick` 的展開結果；FinMind 子 target 共用同一個 updater 實例 |
| F-079 | B | `tasks/delete_price_data.py:32-80` | 直接 `DELETE FROM price WHERE date = ?`：無 `--dry-run`、無確認提示、無備份；日期解析失敗時 `logger.error` 後 `return`（exit 0）；`parse_date()` 的格式清單重複列了 `%Y-%m-%d` 兩次 | 打錯日期（例如少打一位年份）不會有任何攔截；整天資料一刀刪掉後只能重爬（F-050 的續跑邏輯又只從 `MAX(date)+1` 起，**刪掉中間某天後不會被自動補回**） | **→ **ETL 失敗語意與缺口回補** S6**。比照 `migrate_db_naming.py` 加 `--dry-run` 與明確 `--yes`；先 `SELECT COUNT(*)` 列出將刪筆數再要求確認；錯誤一律非零退出；刪除後提示「請以 `update_db --target price` 回補該日」（待 F-050 修好才成立） |
| F-080 | C | `tasks/load_broker_trading_to_db.py:25` | `logger.error(f"…{e}", exc_info=True)`——loguru 的 `error()` 沒有 `exc_info` 參數，多餘的 kwargs 被當成訊息格式化參數靜默吞掉 | 失敗時只有一行訊息、沒有 traceback，與作者意圖相反；不會崩潰所以一直沒被發現 | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。**補充（S16 查證）**：`grep exc_info=` 全專案另有 10 處（`stock_tick_cleaner.py` ×2、`stock_tick_updater.py` ×6、`finmind/broker_trading_updater.py` ×2），同一問題 |
| F-081 | C | `tasks/migrate_db_naming.py` | 一次性遷移（`stock.db → tw_stock.db`、`underlying_market` 欄正名）已於 2026-08 執行完畢，腳本仍放在 `tasks/` 與常規工具並列 | 新人會以為它是常態任務；它與 `core/config.py` 的檔名常數綁死，日後改常數時這支會失效卻沒有測試 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S4**。移到 `scripts/migrations/`（或刪除，git 歷史仍在），`tasks/` 只留週期性任務 |
| F-082 | **A** | `frontend/app.py:197-271`、`:360-378`、`:480-538` | 前端自行重算指標且與報表不同源：(1) `avg_roi = roi.mean() * 100`，而報表 `ROI` 欄已是百分比（`cost_model.roi()` 回傳 `pnl / notional * 100`），**平均 ROI 顯示值放大 100 倍**；(2) 資產曲線、每日損益、Sharpe／Sortino 的日報酬全部以 **`Sell Date`** 排序／分組，SHORT 部位的 `Sell Date` 是**開倉日**（reporter 註明「SHORT 的 sell_date 是開倉日，不可用」而以 `Exit Date` 排序）；(3) 日報酬取自已實現的 `Cumulative Balance` 而非報表的盯市 `daily_equity.csv`，MDD／Sharpe 口徑與四張圖不一致；(4) `_extract_benchmark_returns()` 找的 `Benchmark Return` 等欄位不存在於任何報表，IR 永遠 N/A | 使用者在前端看到的「平均 ROI 476%」與報表 4.76% 差 100 倍；放空策略（`ForeignSellShortDayTradeStrategy`）的資產曲線按開倉日重排，`Cumulative Balance` 是按平倉順序累計的，重排後曲線鋸齒、日報酬與 Sharpe 全錯；同一頁 `平均保證金報酬率`（`futures_metrics`）沒有 ×100，兩個 ROI 互相矛盾 | **→ [前端指標與報表同源化.md](../../backlog/前端指標與報表同源化.md) S1**。前端**只讀不算**：Sharpe／MDD／日報酬改讀 `{name}_daily_equity.csv`，多空統計改讀 `{name}_direction_summary.csv`，事件計數讀 `{name}_event_report.csv`；`ROI` 直接顯示不乘 100；一律以 `Exit Date` 排序；把仍需的計算搬到 `services/` 並與 `core/backtest/analysis` 共用同一份公式；補測試（用 reporter 產出的 fixture CSV 對數） |
| F-083 | B | `frontend/config.py:4-10`、`core/config/paths.py:63`、`docker-compose.yml:18,28-30` | 本機預設 `DEFAULT_RESULTS_ROOT = core/backtest/results`（目錄已隨「執行期產物移出 core/」消失，實際為 `PROJECT_ROOT/results`）；環境變數名 `ALPHAEDGE_BACKTEST_RESULTS` 與後端的 `ALPHAEDGE_RESULTS_DIR` 不同 | 本機直接 `streamlit run frontend/app.py` 整頁 `st.error` 找不到資料夾；Docker 內因 compose 各自寫死 `/results` 才一致；兩個變數名讓「後端寫哪、前端讀哪」要各設一次 | **→ [前端指標與報表同源化.md](../../backlog/前端指標與報表同源化.md) S2**。`frontend/config.py` 改 `from core.config import RESULTS_DIR_PATH` 當預設（或至少改成 `PROJECT_ROOT / "results"`），環境變數統一用 `ALPHAEDGE_RESULTS_DIR`（保留舊名一版相容並警告）；compose 同步；補一條「預設路徑存在」的測試 |
| F-084 | C | `frontend/config.py:13-25`、`frontend/app.py:274-320` | 前端未讀 `_daily_equity.csv`／`_direction_summary.csv`／`_event_report.csv` 與第 5 張圖 `_everyday_equity_change.png`；「策略起始資金」由第一列 `Cumulative Balance` 估算（那是第一筆平倉**之後**的餘額，應再減該列 `Realized PnL`）；「回測日期區間」取交易日期的 min／max（是首末筆交易日，不是回測起訖） | 放空的尾部風險計數（強制回補、斷頭、鎖漲停）在前端完全看不見；起始資金與區間兩個標籤與實際值不同義 | **→ [前端指標與報表同源化.md](../../backlog/前端指標與報表同源化.md) S1**。讀入三份 CSV 各開一個區塊；起始資金＝首列 `Cumulative Balance − Realized PnL`；區間改讀 `daily_equity.csv` 的首末日 |
| F-085 | C | `frontend/app.py:44-188`、`:191-320` | 指標與擷取函式定義在 `st.set_page_config()` 之後的模組層級，測試無法 import `app.py`（`futures_metrics.py` docstring 已說明此限制，卻只把期貨那一組搬出去）；約 190 行 CSS 內嵌在同一檔 | `_calc_sharpe_ratio` 等公式零測試（F-082 才會拖到現在）；改 CSS 與改公式在同一個 diff | **→ [前端指標與報表同源化.md](../../backlog/前端指標與報表同源化.md) S3**。把 `_extract_*`／`_calc_*` 搬到 `frontend/services/metrics.py`，CSS 抽成 `frontend/static/theme.css` 由 `app.py` 讀入；補測試 |
| F-086 | B | `strategy_lab/strategies/tsmc_overnight_signal/README.md` §1／§4.1、`pipeline.py:41-42`、`:256-323` | README 宣稱的交易成本（買 0.1425%、賣 0.1425%＋0.3%）是 `run_vectorized_continuous_backtest()` 診斷路徑的固定費率；主結果 `metrics_summary.csv` 來自 `run_backtest_with_signal()`，用的是 `StockUtils` 的折扣後手續費（0.1425%×0.3 ＝ 0.04275%、最低 20 元）＋證交稅 | 讀者以為主結果已扣 0.1425% 的保守手續費，實際少扣約 70%；兩條路徑費率不同源，`baseline_comparison.csv` 同時列兩者卻沒說費率不同 | **→ **回測口徑與日期邊界收斂** S6**。README 成本段改為「主結果沿用 `core` 費率（列出折扣與最低費）；向量化路徑為未折扣 0.1425%」；`FEE_BUY`／`FEE_SELL_PLUS_TAX` 改由 `Commission` 常數推導 |
| F-087 | B | `strategy_lab/strategies/tsmc_overnight_signal/pipeline.py:271-279`、`core/strategies/stock/overnight_lead_event_strategy.py:36`、`:268-283` | 研究版與「搬進 core 的成品」口徑不同：(1) 部位大小——研究版 `max_buyable_lots()` 扣不起手續費就減一張，core 版 `int(balance/(px×1000))` 不算手續費，遇餘額剛好不足時 `open_position()` 拒單（該日空手）；(2) 資料截止——研究版 `data_end = today`，core 版 `MODEL_DATA_END = 2026-04-25` 寫死；(3) 研究版 `signal` 對沒有美股特徵的台股日填 0，core 版 `signal_by_date.get(date, 0)` 語意相同 ✓ | `strategy_lab/README.md` 說 core 版「就是把研究結論搬進框架的成品」，但沒有任何測試比對兩者在同一區間的訊號序列與交易數；口徑差在餘額臨界日會讓 core 版少做幾天多單 | **→ **回測口徑與日期邊界收斂** S6**。兩版共用同一個訊號建構函式（研究版 import core 版的 `_build_signals` 或反之）；補一條「同區間訊號序列一致」的測試；core 版部位大小改與 `EqualWeightSizer`＋手續費一致 |
| F-088 | C | `strategy_lab/strategies/tsmc_overnight_signal/output/*.html`（13 檔）、`strategy_lab/data_analysis/tech_new_high_continuation/analysis.py:56`、`:90-99`、`reports/generate_docx.py:355-364` | (1) `.gitignore` 已有 `strategy_lab/**/output/`，但 13 個 `output/*.html`（每個 3,887 行的 plotly 檔）在規則加入前就被追蹤；(2) `END_DATE = 2026-05-26` 寫死，重跑不會涵蓋新資料；(3) universe 取自現行 `taiwan_stock_info`，已下市者不在樣本（存活者偏差）而報告限制未列；(4) `load_price_panel()` 用 `price_api.conn` 直接下 SQL 並引用欄位字面值，繞過 `core/api` | (1) repo 體積與 diff 噪音；(2)(3) 研究結論的適用範圍被高估；(4) 欄位改名時研究腳本靜默壞掉（`tests/test_strategy_data_access.py` 只掃 `core/strategies/`） | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。`git rm --cached` 那 13 檔；`END_DATE` 改 `today()` 並寫進輸出的 meta；報告限制補「存活者偏差」；`load_price_panel()` 改用 `StockPriceAPI.get_range()` 或新增具名查詢 |
| F-089 | B | `scripts/dataframe_dot_to_bracket.py:16`、`:329-341` | 一次性 codemod，`ROOT = Path(__file__).resolve().parents[2]` 是**專案的上一層目錄**（`scripts/x.py` → parents[1] 才是專案根），`main()` 對 `ROOT.rglob("*.py")` 就地改寫，無 dry-run、無備份 | 誤跑會遞迴改寫同層所有專案的 Python 檔（含不是 pandas 的 `xxx_df.attr`），且不會有任何確認；任務早已完成（S1 ruff 全綠） | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S4**。直接刪除（git 歷史仍在）；若要保留，改 `parents[1]`、預設 dry-run、加 `--apply` |
| F-090 | B | `scripts/run_regression.sh:26-28`、`tests/backtest/test_long_regression.py:19-21` | LONG 回歸線在 `tw_stock.db` 不存在時被 `skipif` 跳過，pytest 回傳 0，腳本照樣印「=== 回歸雙線通過 ===」；註解寫的是舊檔名 `data/db/stock.db` | 沒有 DB 的機器（CI、新 clone）跑 `run_regression.sh` 會得到假綠燈，而 LONG 線正是多市場重構「逐筆相同」的唯一護欄之一 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S1**。腳本改用 `pytest -rs` 並在輸出含 `SKIPPED` 時以非零結束、明確印「LONG 線未執行：缺 tw_stock.db」；註解改 `tw_stock.db` |
| F-091 | C | `scripts/clean_pycache.ps1:4`、`scripts/generate_docs.py` | `.ps1` 以 `Resolve-Path "$scriptPath\..\.."` 往上兩層（`.sh` 版是一層），會清到同層其他專案的 `__pycache__`；`generate_docs.py` 只印「已提取」不產生任何檔案，API 清單缺期貨 6 支，且 `api_dir = core/api`（實際在 `core/api/tw/`）永遠印「不存在」 | 前者無害但錯；後者是死碼，讓人以為 `docs/api/` 可自動生成 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S4**。`.ps1` 改為一層；`generate_docs.py` 刪除 |
| F-092 | C | `tests/manual_*.py`（9 支）、`tests/manual_db_tables.py:31-34` | 9 支手動腳本放在 `tests/`：不被 pytest 收集（`python_files` 預設 `test_*.py`），卻含 19 處 `return False`／7 檔 `except Exception`，是文件 S19 擔心的「永遠不會失敗」型態的**唯一來源**；兩支直連 production DB（唯讀）；`manual_db_tables.py` 的 fallback 路徑 `core/database/tw_stock.db` 已不存在 | 稽核 `tests/` 時每次都要先排除它們；覆蓋率與 grep 統計被污染；新人會以為它們是測試 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S4**。整批搬到 `scripts/manual/`（或 `tests/manual/` 並在 README 說明不是 pytest 對象）；修掉過期 fallback 路徑 |
| F-093 | B | `frontend/Dockerfile:15-20`、`frontend/app.py:7` | 映像只在 `frontend/requirements.txt` 存在時才裝它，該檔**不存在**，fallback 只裝 `streamlit pandas`；`app.py` 第 7 行 `import plotly.express` | `docker compose up` 的 frontend 服務在啟動時 `ModuleNotFoundError: plotly`，README「方式 3：Docker Compose」的流程在乾淨機器上必失敗 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S2**。新增 `frontend/requirements.txt`（streamlit、pandas、plotly）或改用 `pip install -e ".[frontend]"`；把 plotly 加進 `optional-dependencies.frontend`；CI 加一個 `docker compose build` 步驟 |
| F-094 | B | `core/Dockerfile:47-55`、`docker-compose.yml:2-18` | `core` 映像只 COPY `run.py`＋`core/`，不含 `tasks/`；compose 沒掛 `data/`（只掛 `results`）；映像以整份 `requirements.txt`（含 85 個未 import 的套件）安裝 | 容器內 `python run.py --strategy …` 在 `TwStockDataFeed.setup()` 的 `sqlite3.connect(/app/data/db/tw_stock.db)` 因目錄不存在而 `OperationalError`（大聲失敗，不是假綠燈），亦無法 `python -m tasks.update_db`；映像體積與建置時間被無關套件撐大 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S2**。compose 為 `core` 掛 `./data:/app/data`（唯讀亦可）並 COPY `tasks/`；映像改 `pip install -e .`（只裝 `pyproject` 宣告的相依）；README 明寫「容器需要先在本機準備 `data/db/*.db`」 |
| F-095 | B | `.github/workflows/ci.yml:38`、`.pre-commit-config.yaml:15`、`pyproject.toml:38` | (1) CI 只跑 `-m "not slow"`，13 個 slow 測試（含 LONG 回歸）與 `run_regression.sh` 在任何自動化流程都不執行；(2) pre-commit 釘 `ruff v0.16.3`，CI 裝 `ruff>=0.6` 的最新版 | (1) 多市場引擎的「逐筆相同」護欄只在開發者記得手動跑時才存在，且 F-090 讓沒 DB 的機器連跑了也回綠；(2) ruff 0.17 一出，CI 的 `ruff format --check` 可能紅而本機綠（或反之） | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S1**。(1) 在 `docs/dev/code-quality.md` 明寫「回歸雙線只在本機」並提供最小 fixture DB 讓 CI 至少跑 SHORT 線＋一個縮小版 LONG 線；(2) `dev` extras 改 `ruff==0.16.3`（或 `>=0.16,<0.17`），升版時與 pre-commit 同步 |
| F-096 | C | `.env.example`、`core/config/settings.py:140-161`、`core/config/schema.py:20`、`core/utils/path.py`、`dev/env/*.yml`、`requirements.txt` | (1) `.env.example` 缺 `API_KEY_1..4`／`API_SECRET_KEY_1..4`、`ALPHAEDGE_DATA_DIR`／`RESULTS_DIR`／`LOGS_DIR`、`ALPHAEDGE_BACKTEST_RESULTS`；(2) `DDB_PATH` 在 `settings.py` 與 `schema.py` 各讀一次；(3) `core/utils/path.py`（0% 覆蓋）與 `core/config/paths.py:26` 是兩套 env 路徑工具；(4) conda yml 漂移（black／isort、缺 yfinance）；(5) `requirements.txt` 85 個無關套件 | 新人照 `.env.example` 設完仍缺多帳號與目錄覆寫變數；兩套工具與兩次讀取讓「路徑到底從哪來」要查兩處；yml 與 requirements 都不是可信的安裝依據 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S6**。`.env.example` 補齊並註明選填；`schema.py` 改讀 `settings.DDB_PATH`；刪 `core/utils/path.py` 併入 `config/paths.py`；yml 標註「已停用，請用 venv＋pyproject」或刪除；`requirements.txt` 以 `pip-compile` 從 `pyproject` 重新產生 |
| F-097 | B | `logs/api/`（2.5 GB／277 檔）、`core/api/tw/*.py` 的 `LogManager.setup_logger`、`tasks/clean_logs.py`、repo 根 `shioaji.log` | `logs/` 已 3.1 GB：`api/` 桶每次查詢都寫 INFO，回測一天打兩次全市場查詢，26 天長 2.5 GB；loguru 的 retention 只在 logger 重建時觸發（runtime-artifacts 已說明），而 `clean_logs --apply` 沒有任何排程在跑；`shioaji` 套件把 `shioaji.log` 寫在 CWD | 磁碟持續成長；`pipeline/` 桶要回頭讀的統計行被 api 訊息淹沒（F-001）；`SimpleLong.log` 32 MB 單檔顯示 backtest 桶的輪替也沒生效 | **→ **ETL 失敗語意與缺口回補** S6**。`api/` 桶檔案 sink 預設 `WARNING`（查詢層級 INFO 只進 console 或關掉）；`clean_logs --apply --bucket api --days 7` 排進每日更新之後（或 `update_db` 結束時順手呼叫）；shioaji 的 log 路徑設到 `logs/api/`；等期貨回補結束後與 F-001 一併修 `log_manager.py` |
| F-098 | C | `core/config/schema.py:53`、`docs/futures/tw-futures-platform.md:595-606` | `FUTURES_CONTRACT_TABLE_NAME = "futures_contract"` 有宣告，DB 內無此表，也沒有 loader 建它（規劃時預留給股期乘數，後來改走 `futures_stock_universe.contract_size`） | 死常數；新人會以為有這張表 | **→ `docs/dev/code-quality.md`〈健檢 C 級結論〉**。刪除常數，或在註解註明「未建表，股期乘數見 `futures_stock_universe`」 |
| F-099 | C | `data/db/tw_stock.db`（`price`／`chip`／`margin`／`dividend`）、`tw_futures.db`（`futures_price_daily`） | 只有主鍵自動索引，且主鍵皆以 `date` 開頭：依 `stock_id` 取區間的查詢（`get_stock_price`／`get_close_series`／reporter 的 benchmark）只能用 `date` 範圍掃描；`dividend WHERE stock_id = ?` 全表掃描；`futures_price_daily` 依 `(product, expiry)` 取區間同樣只吃 `date` 範圍 | 純效能：5 年區間的個股查詢要掃約 250 萬列；`MarketCalendar.get_last_trading_date()` 每根 bar 一次整天查詢（F-065）疊加後回測明顯偏慢 | **→ **回測口徑與日期邊界收斂** S4**。加 `(stock_id, date)` 複合索引於 `price`／`chip`／`margin`／`dividend`，`(product, expiry, session, date)` 於 `futures_price_daily`；由 loader 建表時一併 `CREATE INDEX IF NOT EXISTS`，PostgreSQL 遷移時沿用 |
| F-100 | C | `pyproject.toml:134-136`、`docs/dev/code-quality.md` per-file-ignores 表 | per-file-ignores 的 `core/pipeline/loaders/stock_tick_loader.py` 指到搬家前的路徑（實際在 `core/pipeline/tw/loaders/`），該條豁免形同失效；目前不紅只是因為該檔的 `dolphindb` import 已包在 try/except 內 | 下次有人在該檔做「可用性探測」import 就會被 F401 擋，而豁免看起來還在 | **→ [測試護欄與本機CI容器一致性.md](../../backlog/測試護欄與本機CI容器一致性.md) S6**。改成 `core/pipeline/tw/loaders/stock_tick_loader.py`（順手核對 `stock_tick_utils.py` 那條） |
| F-101 | C | `README.md` §Option 2／3、`README_zh.md` §方式 2／3 | 兩份 README 的 Docker 段落已分岔：en 示範 `docker run … --help` 與 `-p 8501`，zh 示範 `--entrypoint /bin/bash` 進 shell 再手動 `python run.py`／`streamlit run`，zh 多 3 個 code block；其餘章節與專案結構樹已於 S21 對齊 | 兩份文件各自演化，日後修其一另一份不會跟著改 | **→ 已於 2026-09-03 處理**：以 `README_zh.md` 為準回填 `README.md` 的 Docker 段落，兩份檔頭互相標註「以中文版為準」。 |

## 附錄 B：基線快照（S1 於 2026-09-02 填寫）

| 項目 | 2026-08-16 | 本次量測（2026-09-02） | 差異說明 |
|------|-----------:|---------:|----------|
| `ruff check .` 總條數 | 1495（首次全量） | 0 | 現行 ignore 清單下 All checks passed；`ruff format --check` 277 檔全部已格式化 |
| `BLE001` 盲捕 | 85 | 96 | +11，全在 `core/pipeline/`（F-013） |
| 待收斂清單（7 條規則） | 21 條 | 25 條 | 21 條全部仍在、行號漂移；+3 B008（期貨 updater）、+1 B007（tests）。見 F-002、F-010~F-012 |
| 全專案 `.py` 檔數／行數 | 179 檔 | 277 檔 / 60,164 行 | 含 `tests/` 69 檔 19,324 行、`strategy_lab/` 14 檔 3,879 行 |
| `core/` 檔數／行數 | — | 178 檔 / 34,439 行 | pipeline 86 檔 17,779 行為最大子套件 |
| `pytest -m "not slow"` | 207 passed / 9 deselected | 687 passed / 10 deselected（5.9 秒） | 以 `noguru_plugin` 的 `pytest_sessionstart` 隔離 loguru sink，本次量測沒有再污染 `logs/`（F-001） |
| `core/` 整體覆蓋率 | 40%（7,112 行） | 60%（11,348 行，未覆蓋 4,552） | 各子套件：managers 95、backtest/models 90、adapters 90、datafeed 83、models 81、pipeline/shared 79、backtester 75、strategies 65、api 60、utils 54、pipeline/tw 46、backtest/report 42、pipeline/utils 36。**0%**：`core/api/tw/finmind_api.py`、`core/utils/path.py` |
| 單檔 > 500 行 | — | 25 檔 | 最大：`strategy_lab/…/docx_append.py` 1,360、`core/backtest/models/settlement_model.py` 1,219、`tests/test_futures_margin.py` 1,178、`strategy_lab/…/pipeline.py` 1,077、`futures_margin_cleaner.py` 879、`reporter.py` 872、`cost_model.py` 855 |
| 分層檢查（S3 新增） | — | 新違規 0／已登錄反向相依 4／循環 1／市場語意洩漏 0／跨軸目錄 0 | `python scripts/check_layer_deps.py`；現況結束碼 1（F-006 那條循環） |

## 附錄 C：`models/` 三方對照表（S5 於 2026-09-02 填寫）

| 概念 | `base/` | `stock/` 獨有 | `futures/` 獨有 | 單邊欄位是否刻意 |
|------|---------|----------|------------|------------------|
| account | `init_capital`／`balance`／`realized_pnl`／`roi`／三個成本總額／`positions`／`trade_records`；FIFO／LIFO 取倉、方向篩選、`check_has_position()` | `margin_used`（放空擔保）、`get_short_market_value()`、`update_transaction_cost()` 納入借券費／利息／股利補償；`stock_id` 關鍵字相容層 | `margin_used`（原始保證金）、`equity` property、`get_open_lots()`（多空相抵淨口數） | 刻意。**注意 `margin_used` 同名不同義**（放空擔保 vs 期貨原始保證金），跨商品彙總不可直接相加。`check_has_position()` 未濾已平倉見 F-020 |
| order | `symbol`／`date`／`action`／`position_type`／`price`／`volume` | `short_method`、`is_day_trade`（由引擎 `enrich_orders()` 補值） | `product`、`expiry`（`symbol = product+expiry`） | 刻意 |
| position | `id`／`symbol`／`is_closed`／開倉日期價量／開倉成本／未實現損益 | 放空六欄（`short_method`／`is_day_trade`／`margin`／`short_proceeds`／`borrow_fee`／`accrued_borrow_fee`）、`dividend_compensation`、`holding_days`、**`no_quote_days`** | `product`／`expiry`／`multiplier`、**`entry_price`**（`price` 會被逐日結算重設）、`margin`、`settled_pnl`、`holding_days` | 多數刻意。**待 S12 確認**：`no_quote_days`（停牌／下市保險絲）只有股票有，期貨部位遇連續無報價靠什麼出場 |
| quote | `symbol`／`scale`／`date`／`cur_price`／`volume`／OHLC／`adj_close`／`signal_close` | `tick_quote`（`TickQuote` **不繼承** `BaseQuote`、仍用 `stock_id`） | `product`／`expiry`／`session`／`settlement_price`／`open_interest`（夜盤為 None）／`multiplier`；`adj_close` 恆 None | 刻意（股期除權息以契約單位承接，不套還原）。`TickQuote` 不對稱屬 C；tick 路徑 OHLC 全 0 見 F-022 |
| record | `id`／`symbol`／`buy_*`／`sell_*`／`entry_*`／`exit_*`／成本／`realized_pnl`／`roi` | `short_method`／`borrow_fee`／`interest`／`dividend_compensation`／`margin`／`holding_days`／**`roi_on_capital`** | `product`／`expiry`／`multiplier`／`margin`／`settled_pnl`／`holding_days` | 刻意。**待 S13 確認**：`roi_on_capital` 只有股票有，`reporter.py:324` 直接讀它，期貨報表須走 `futures_reporter` |

另：所有 model 的 `date`／`scale`／`tick` 等參數寫成 `X = None` 而非 `Optional[X]`（`CLAUDE.md` §2.4.4），共 12 處，屬 D 級只計數。

**D 級計數（S23，2026-09-02）**：附錄 A 共 2 條（F-012 待收斂清單其餘 14 條複驗結論、F-019 型別註解與實際回傳不符）＋ 上述 12 處 `Optional` 寫法；皆不轉單。

## 附錄 D：測試有效性盤點（S19 填寫）

| 測試檔 | assert 數 | 可疑型態 | 刻意改壞後會紅嗎 | 判定 |
|--------|----------:|----------|:----------------:|------|
| `tests/manual_finmind_pipeline.py`／`manual_broker_trading_updater.py`／`manual_db_tables.py`／`manual_finmind_updater.py` | 0（腳本） | `return False`（19 處）＋ `except Exception` | 不適用：不被 pytest 收集（`python_files` 預設 `test_*.py`） | 非測試；搬到 `scripts/manual/`（F-092） |
| `tests/manual_finmind_api.py`／`manual_tick_updater.py`／`manual_init_tick_metadata.py`／`manual_broker_trading_db_query.py`／`manual_tick_crawler.py` | 0（腳本） | `except Exception`；3 支帶 `slow` 標記 | 不適用 | 同上 |
| `tests/test_finmind_broker_trading_batch.py` | 11（4 測試） | `return False` 只出現在 docstring | 是（stub 回傳被斷言筆數釘住） | 有效 |
| `tests/backtest/test_long_regression.py` | 2 | `skipif`（缺 DB） | 是（S13 實跑 1 passed；§6.3 記錄過注入錯誤會被抓到） | 有效，但 `run_regression.sh` 在 skip 時仍回綠（F-090） |
| `tests/backtest/test_short_regression.py` | 4 | — | 是（§6.3 三次注入測試皆抓到） | 有效 |
| `tests/test_strategy_data_access.py` | 2（parametrize 20） | — | 是（在任一策略加入欄位字面值即紅） | 有效；範圍只到欄位字面值（F-074） |
| `test_futures_{chip,products,continuous,calendar,roll_backtest,stock_universe_api}.py` 的真實資料段 | 各 1~3 | `slow`＋`skipif`＋內部 `pytest.skip` | 是（斷言在 SELECT 結果上） | 有效；production 連線唯讀 |
| 全套 `pytest -m "not slow"` | — | — | 687 passed / 10 deselected（與 S1 基線一致） | — |
| | | | | |

## 附錄 E：DB schema 對照表（S22 填寫）

> S22 於 2026-09-02 以唯讀連線讀取 `sqlite_master`／`PRAGMA table_info` 填寫。「宣告」欄指 `core/config/schema.py` 是否有表名常數；「文件」欄指 `docs/exchanges/data_coverage.md` 是否列出。

### E.1 `tw_stock.db`（13 張）

| 表 | 列數 | 欄數 | 主鍵 | 明示索引 | 宣告 | 文件 |
|---|---:|---:|---|---|:---:|:---:|
| `price` | 6,247,050 | 16 | `(date, stock_id, 證券名稱)` | — | ✓ | ✓ |
| `chip` | 5,253,673 | 19 | `(date, stock_id, 證券名稱)` | — | ✓ | ✓ |
| `margin` | 5,743,931 | 18 | `(date, stock_id)` | — | ✓ | ✓ |
| `dividend` | 24,260 | 15 | `(date, stock_id)` | — | ✓ | ✓ |
| `monthly_revenue` | 274,709 | 12 | `(year, month, stock_id, 公司名稱)` | — | ✓ | ✓ |
| `balance_sheet` | 65,338 | 78 | `(year, season, stock_id, 公司名稱)` | — | ✓ | 「各財報表」帶過 |
| `comprehensive_income` | 65,338 | 43 | 同上 | — | ✓ | 同上 |
| `cash_flow` | 64,454 | 11 | 同上 | — | ✓ | 同上 |
| `equity_change` | 230,163 | 6 | `(year, season, stock_id, 權益項目, 變動原因)` | — | ✓ | ✓ |
| `taiwan_stock_info` | 3,143 | 5 | `(stock_id)` | — | ✓ | ✓ |
| `taiwan_stock_info_with_warrant` | 126,284 | 5 | `(stock_id)` | — | ✓ | ✓ |
| `taiwan_securities_trader_info` | 1,007 | 5 | `(securities_trader_id)` | — | ✓ | ✓ |
| `taiwan_stock_trading_daily_report_secid_agg` | 3,103,823 | 8 | `(securities_trader_id, stock_id, date)` | `idx_broker_trading_secid_stock_date` | ✓ | ✓ |

### E.2 `tw_futures.db`（8 張）

| 表 | 列數（回補中） | 欄數 | 主鍵 | 明示索引 | 宣告 | 文件 |
|---|---:|---:|---|---|:---:|:---:|
| `futures_price_daily` | 89,279 | 13 | `(date, product, expiry, session)` | — | ✓ | ✓（但寫「目前僅 TX」） |
| `futures_continuous` | 8,526 | 16 | `(date, product, session, method, roll_rule)` | `idx_futures_continuous_series` | ✓ | ✗ |
| `futures_institutional_chip` | 31,884 | 15 | `(date, product_name, investor)` | — | ✓ | ✗ |
| `futures_large_trader` | 2,926,330 | 10 | `(date, product, expiry, trader_type)` | — | ✓ | ✗ |
| `futures_put_call_ratio` | 2,842 | 7 | `(date)` | — | ✓ | ✗ |
| `futures_margin_history` | 1,101 | 7 | `(effective_date, product)` | `idx_futures_margin_product` | ✓ | ✗ |
| `stock_futures_margin_rate_history` | 1,027 | 9 | `(effective_date, product_id)` | `idx_stock_futures_margin_product` | ✓ | ✗ |
| `futures_stock_universe` | 640 | 10 | `(snapshot_date, product_id)` | `idx_futures_stock_universe_product` | ✓ | ✓ |

### E.3 宣告了但不存在

| 常數 | 值 | 現況 |
|---|---|---|
| `FUTURES_CONTRACT_TABLE_NAME` | `futures_contract` | 無建表、無 loader（F-098） |
| `TICK_TABLE_NAME`／`FUTURES_TICK_TABLE_NAME` | `tick`／`futures_tick` | DolphinDB，不在 SQLite（正常） |

## 相關文件

- [程式碼品質工具鏈與基線](../dev/code-quality.md)：ruff 設定、例外處理現況、待收斂清單（S1／S2／S20 的輸入）
- [ETL 入庫約定](../pipeline/etl-ingestion.md)：三個必守性質與五次事故（S7~S10 的判準）
- [回測執行路徑的模組使用關係](../backtest/module-map.md)：分層與相依方向（S3 的判準）
- [多市場回測引擎架構](../backtest/multi-market-engine.md)：bar 內順序、已知簡化、實作發現（S12／S13 的判準）
- [放空回測框架規格](../backtest/short-selling-framework.md)：成本公式、手算範例、邊界情況（S11／S12／S17 的判準）
- [命名軸線](../dev/naming-axes.md)：四條軸與目錄承載規則（S3 的判準）
- [資料覆蓋範圍](../exchanges/data_coverage.md)：股價還原與已知限制（S6／S22 的判準）
- [執行期產物](../dev/runtime-artifacts.md)：`data/`／`results/`／`logs/` 的分界（S22 的判準）
- [台期貨平台](../futures/tw-futures-platform.md) §3.1：`downloads/` 目標結構（S22 的判準）
- `strategy_lab/CLAUDE.md`：研究目錄的分類決策與硬性規則（S17 的判準）
