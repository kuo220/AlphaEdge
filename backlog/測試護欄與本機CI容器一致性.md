# 測試護欄與本機／CI／容器一致性

## Abstract

- **背景／問題**：全專案架構與邏輯健檢（2026-09，紀錄文件已刪除，見 git 歷史） S18~S20 發現「本機綠、CI 不跑、容器起不來」三處不一致：`run_regression.sh` 在沒有 `tw_stock.db` 的機器會跳過 LONG 線仍印「雙線通過」（F-090）、CI 從不跑 slow 測試與回歸線（F-095）、`frontend` 映像缺 `plotly`（F-093）、`core` 容器沒有 `data/` 與 `tasks/`（F-094）、`run.py` 錯誤退出碼 0（F-077）、一次性 codemod 誤跑會改壞同層專案（F-089）。
- **目標**：回歸護欄在任何機器上「要嘛真的跑、要嘛明確說沒跑」；`docker compose up` 能跑完一次回測並在前端看到；一次性腳本清出 `scripts/`。
- **範圍界線**：不改測試框架、不引入新的 CI 服務、不做覆蓋率門檻。
- **驗收標準**：`./scripts/run_regression.sh` 在無 DB 機器結束碼非 0 且訊息明確；CI 至少跑 SHORT 線；`docker compose build && docker compose up` 在準備好 `data/db` 的機器上跑完 `MomentumStrategy1` 並於前端顯示；`python run.py --strategy NotExist; echo $?` 非 0。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 回歸腳本假綠燈與 CI 護欄 | `scripts/run_regression.sh`、`.github/workflows/ci.yml`、`.pre-commit-config.yaml`、`pyproject.toml`、`docs/dev/{code-quality,health-check-2026-09}.md` | 無 DB 時腳本非零結束並印「LONG 線未執行」；CI 新增 SHORT 線步驟 | ✅ | **2026-09-05 完成**。無 DB 實測結束碼 3；CI 另加分層閘門；ruff 釘死 `==0.16.3`。`test_long_regression.py` 未改（`skipif` 是對的，錯的是腳本把 skip 當通過） |
| S2 | 容器可跑：前端相依、`core` 掛 `data/`、只裝 pyproject 相依 | `frontend/requirements.txt`（新增）、`frontend/Dockerfile`、`core/Dockerfile`、`docker-compose.yml`、`README*.md` | `docker compose config` OK；`compose up` 跑完示範策略；映像不含 Flask／ipython 等無關套件 | 🔄 | **2026-09-10 做掉 F-093 與 F-094 的掛載半邊**（`871f74c`）：前端補 plotly、core 掛 `data/`（唯讀）與 `logs/`、映像 COPY `tasks/`。⚠️ **本機 Docker daemon 未啟動，映像未建置**，`compose up` 那條驗收未執行；`pip install -e .` 那半邊亦未做（見 S2 進度紀錄）|
| S3 | 入口退出碼與 `--mode live` | `run.py`、`tests/test_run_entry.py`（新增） | subprocess 測試：找不到策略 exit 2；`live` 明確 `NotImplementedError` | ✅ | **2026-09-10 完成**（`0138ca6`）：策略找不到 0 → 2 且訊息改走 stderr、`--mode live` 0 → 1；8 條 subprocess 測試，實測修正前 7 條會失敗 |
| S4 | 一次性腳本清理與 `tests/manual_*` 搬家 | `scripts/dataframe_dot_to_bracket.py`（刪）、`generate_docs.py`（刪）、`clean_pycache.ps1`（修）、`scripts/migrations/migrate_db_naming.py`（搬）、`scripts/manual/*`（搬 ＋ README） | `git rm` 後 `pytest` 全綠；`grep return False tests/` 為 0 | ✅ | **2026-09-10 完成**（`f9c95e8`）：`tests/` 的 `return False` 由 **19 降為 2**（一個測試替身的 stub、一個 docstring），`except Exception` 剩 1 處且在 docstring |
| S5 | 測試護欄補強：策略不自建連線、loguru 隔離、`sys.path.insert` 清理 | `tests/test_strategy_data_access.py`、`scripts/check_layer_deps.py`、`strategy_lab/**/run.py`、四份 README | 在策略加 `StockPriceAPI()` 即紅；pytest 後 `logs/` mtime 不變；`python -m` 方式可跑研究腳本 | ✅ | **2026-09-10 完成**（`6c3be9b`）：`sys.path.insert` 由 **18 降為 0**；loguru 隔離**實查發現早就做掉了**，實測 pytest 前後 `logs/` mtime 未變 |
| S6 | 環境變數、相依檔與設定檔一致 | `.env.example`、`core/config/{schema,settings}.py`、`core/utils/path.py`（刪）、`dev/env/*.yml`、`requirements.txt`、`pyproject.toml` | `.env.example` 與 `os.getenv` 對照無缺口；`requirements.txt` 由 `pyproject` 重新產生；per-file-ignores 路徑存在 | ⬜ | F-096、F-100、F-015、F-016、F-018 |

## 步驟詳述

### S1. 回歸腳本假綠燈與 CI 護欄 ✅

- **目的**：F-090／F-095。
- **做法**：腳本以 `pytest -rs` 執行並 grep `SKIPPED`，有即 `exit 3` 並印原因；CI 新增「SHORT 回歸線」步驟（純記憶體）；`dev` extras 釘 ruff 版本與 pre-commit 一致；`docs/dev/code-quality.md` §4.2 已於健檢 S21 補「回歸雙線只在本機」。
- **產出**：見進度表。
- **驗證方式**：在暫時改名 `tw_stock.db` 的情況下跑腳本，結束碼非 0。
- **相依**：無。

> **✅ 完成紀錄（2026-09-05）**
> - **`run_regression.sh` 改以 `-rs` 執行並偵測 `SKIPPED`**，有即以**結束碼 3** 結束，
>   印出被 skip 的項目、原因，以及「LONG 線需要 `data/db/tw_stock.db`」。
>   結束碼分三種：`0` 兩條線都實際跑過且通過、`3` 有測試被 skip（護欄未生效）、
>   其他為 pytest 自身的失敗碼。順帶修掉註解裡的舊檔名（`data/db/stock.db` → `tw_stock.db`）。
> - **`test_long_regression.py` 一行未改**。`skipif` 本身是對的——沒有資料庫時那條測試
>   確實跑不了，硬改成 fail 只會讓 CI 永遠紅。錯的是**腳本把 skip 當成通過**，
>   所以修的是腳本。
> - **驗證方式偏離原規格**：原訂「暫時改名 `tw_stock.db`」，但**另一個 session 的權益變動表
>   回補正在寫這個檔**（已跑 11 小時、估 60~66 小時），改名會直接讓它炸掉。
>   改用 `ALPHAEDGE_DATA_DIR` 指向空目錄來模擬「沒有資料庫的機器」——
>   同樣走到 `skipif`，但完全不碰真的 DB。實測結束碼 **3**，事後確認 `tw_stock.db`
>   仍是 3.2 GB、未被動到。
> - **CI 新增兩步**（`.github/workflows/ci.yml`）：
>   1. **分層相依檢查**（`scripts/check_layer_deps.py`，約 0.5 秒）——這支腳本原本
>      永遠 exit 1（`strategy_lab` 的循環 import 把整個閘門鎖住），2026-09-04 解掉之後
>      才有資格當閘門（健檢 F-006）。同時掛進 pre-commit（`pass_filenames: false` ＋
>      `always_run: true`，因為它看的是「邊」不是單檔）。
>   2. **SHORT 回歸線**（純記憶體、不需要資料庫，約 0.7 秒）。已用
>      `ALPHAEDGE_DATA_DIR` 指向空目錄模擬 CI 環境實測通過（6 passed）。
>   LONG 線仍只能在本機——CI 沒有 `tw_stock.db`，這點沒有解法，但腳本現在會明說它沒跑。
> - **ruff 版本釘死 `==0.16.3`**（原 `ruff>=0.6`），與 `.pre-commit-config.yaml` 的
>   `rev: v0.16.3` 一致。選擇完全相等而非 `>=0.16,<0.17`：格式規則跨版本會變，
>   而「本機綠、CI 紅」那種紅燈與程式碼品質無關，只會訓練大家忽略 CI。
> - `docs/dev/code-quality.md` §4.2 改寫為四條護欄的對照表（何處執行、為什麼），
>   `docs/dev/health-check-2026-09.md` 的 F-090／F-095 兩列補上結果。
> - 驗證：`pytest -m "not slow"` **890 passed**、`./scripts/run_regression.sh` 結束碼 0、
>   無 DB 模擬結束碼 3、`check_layer_deps.py` 結束碼 0、`ruff check` 與
>   `ruff format --check` 全綠。

### S2. 容器可跑 🔄

- **目的**：F-093／F-094。
- **做法**：新增 `frontend/requirements.txt`（streamlit、pandas、plotly）或改 `pip install -e ".[frontend]"`；compose 為 `core` 掛 `./data:/app/data:ro` 與 `./logs:/app/logs`，映像 COPY `tasks/`；`core/Dockerfile` 改 `pip install -e .`；README 兩份的方式 3 註明「需先在本機準備 `data/db/*.db`」。
- **產出**：見進度表。
- **驗證方式**：見進度表。
- **相依**：無。

> **🔄 進度紀錄（2026-09-10，commit `871f74c`）**
>
> **已做（F-093）**：新增 `frontend/requirements.txt`（streamlit／pandas／plotly）。
> 前端映像**不安裝本專案**，`pyproject.toml` 的相依完全不生效——沒有這一份時
> Dockerfile 退回 `pip install streamlit pandas`，而 `app.py` 還 import 了 plotly，
> **映像裝得起來、一開頁就 ModuleNotFoundError**。另補一條 AST 測試比對
> requirements 與實際 import，已實測拿掉 plotly 即失敗。
>
> **已做（F-094 的掛載半邊）**：compose 為 core 掛 `./data:/app/data:ro` 與
> `./logs:/app/logs`，`core/Dockerfile` 補 `COPY tasks /app/tasks`，兩份 README
> 加上「必須先在本機備妥 `data/db/*.db`」。**唯讀是刻意的**：容器只跑回測，
> 不該寫到本機資料庫——背景 ETL 可能正在寫同一個檔。
>
> ⚠️ **未做，因此本步驟維持 🔄**：
>
> 1. **`compose up` 跑完示範策略這條驗收沒有執行**——本機 Docker daemon 未啟動。
>    已驗證的只有 `docker compose config` 解析正確（`/app/data` 為
>    `read_only: true`、`/app/logs` 可寫）。
> 2. **`core/Dockerfile` 改用 `pip install -e .`**（F-094 的「映像裝整份
>    requirements.txt 含 85 個無關套件」）。它會重組安裝流程而目前無法建置驗證，
>    改壞了是把「能建但缺資料」變成「建不起來」；且 `requirements.txt` 正被
>    權益變動表那條線改動且未提交。
>
> **恢復下一步**：啟動 Docker daemon → `docker compose build` →
> `docker compose up` 確認示範策略跑完 → 再處理 `pip install -e .` 那半邊。

### S3. 入口退出碼 ✅

- **目的**：F-077。
- **做法**：找不到策略 → `sys.exit(2)`＋stderr 清單；`live` → `raise NotImplementedError`（或自 `choices` 移除）。
- **產出**：`run.py`、新測試。
- **驗證方式**：subprocess 斷言退出碼。
- **相依**：無。

> **✅ 完成紀錄（2026-09-10，commit `0138ca6`）**
>
> | 情況 | 修正前 | 修正後 |
> |------|:---:|:---:|
> | 策略名找不到 | **0** | **2** |
> | `--mode live` | **0**（零輸出） | **1**（`NotImplementedError`）|
> | 缺 `--strategy` | 2 | 2（argparse 既有行為，未動）|
>
> 退出碼選 **2** 是為了與 argparse 自己的用法錯誤同碼——缺 `--strategy` 本來
> 就回 2，對呼叫端兩者是同一類問題，不必再多記一個號碼。
>
> **訊息一併改走 stderr**：退出碼與輸出流向要一起改才有意義，訊息印在 stdout
> 會混進正常輸出，批次作業把 stdout 收去當報表時就看不見那一行。
>
> **`live` 保留在 `choices` 裡，但 help 講明尚未實作**——F-077 的第二半是
> 「`--help` 看起來像已支援實盤」。保留選項並在說明裡講清楚，比從 `choices`
> 移除更誠實：它確實是規劃中的模式，`--mode` 這個參數才有意義。
>
> **測試一律走 subprocess**：退出碼是**行程**的性質，直接呼叫 `main()` 驗不到
> `sys.exit()` 實際交給呼叫端的數字，也驗不到訊息去了哪個輸出流。三種情況
> 都在建 Backtester 之前就結束，不需要 `data/db/*.db`，故不標 `slow`。
> 已實測有牙齒：對修正前的 `run.py` 重跑，8 條中 7 條失敗。

### S4. 一次性腳本清理 ✅

- **目的**：F-089（`parents[2]` 指向專案上一層的 codemod）、F-091、F-081、F-092。
- **做法**：見進度表；`manual_*` 搬家後在 `scripts/manual/README.md` 註明「不是 pytest 對象、如何執行」。
- **產出**：見進度表。
- **驗證方式**：見進度表。
- **相依**：無。

> **✅ 完成紀錄（2026-09-10，commit `f9c95e8`）**
>
> | 項目 | 處置 |
> |------|------|
> | `scripts/dataframe_dot_to_bracket.py` | **刪除**。`parents[2]` 是專案的上一層，`main()` 就地改寫且無 dry-run／備份，誤跑會遞迴改寫同層所有專案 |
> | `scripts/generate_docs.py` | **刪除**。死碼：只 print 不產檔，`api_dir` 還指著搬走前的 `core/api` |
> | `scripts/clean_pycache.ps1` | **修**。往上兩層改一層，與同目錄的 `.sh` 版一致 |
> | `tasks/migrate_db_naming.py` | **搬** `scripts/migrations/`（**2026-09-13 已整支刪除**，一次性遷移執行完畢，git 歷史仍在） |
> | `tests/manual_*.py`（9 支） | **搬** `scripts/manual/` ＋ README |
>
> **搬 `manual_*` 的效果可以量化**：`tests/` 的 `return False` 由 **19 降為 2**
> ——那 19 處全部出自這 9 支。剩下的 2 處逐一確認都不是反樣式（一個是測試
> 替身的 stub `def always_missing(...) -> bool: return False`，一個是 docstring
> 在描述舊反樣式）；`except Exception` 剩 1 處，也在 docstring 裡。
> 它們不被 pytest 收集卻長期被算進 `tests/` 的品質統計，是「永遠不會失敗」
> 型態的唯一來源。
>
> 順帶修掉 `manual_db_tables.py` 的失效退路 `core/database/tw_stock.db`
> （2026-08 產物移出 `core/` 後就不存在），走到那條路只會回報「資料表不存在」。
>
> 也收斂了 `pyproject` 的 E402 豁免：`tests/*` 與 `strategy_lab/*` 兩條原本是為了
> 遷就卡在 import 中間的 `sys.path.insert`，那些清掉後把殘留的 `_PROJECT_ROOT`
> 賦值一併移到 import 之後，兩條豁免不再需要，只留 `scripts/manual/*`
> （那幾支必須在部分 import **之前**載入 `.env`）。

### S5. 測試護欄補強 ✅

- **目的**：F-074、F-001 測試面、F-009。
- **做法**：`test_strategy_data_access.py` 加 parametrize 掃 `sqlite3.connect(`／`API()`；`tests/conftest.py` 以 `pytest_sessionstart` 把 `LogManager.setup_logger`／`setup_backtest_logger` 換成 no-op（等期貨回補結束後再動 `log_manager.py` 本體）；`sys.path.insert` 全部移除、研究腳本改 `python -m strategy_lab.…`。
- **產出**：見進度表。
- **驗證方式**：見進度表。
- **相依**：無。

> **✅ 完成紀錄（2026-09-10，commit `6c3be9b`）**
>
> **F-074（做）**：`test_strategy_data_access.py` 新增 parametrize 擋三種樣式
> （`sqlite3.connect(`、`<Xxx>API(` 實例化、`dolphindb`／`ddb`）。策略層目前
> grep 無違規，所以這是**預防性**護欄。**只擋實例化不擋型別標註**——
> `price: StockPriceAPI` 合法，`StockPriceAPI()` 才是自建，差別就是那個左括號。
> 另補一條以合成違規碼驗證樣式真的抓得到：樣式寫錯而永遠不命中，護欄就是空殼。
>
> **F-009（做）**：`sys.path.insert` 由 **18 降為 0**。`tests/` 14 處直接移除
> （`tests*` 本來就在 packages.find 裡）；`strategy_lab/` 4 支改為一律
> `python -m strategy_lab.…`，四份 README 同步。**`strategy_lab` 不在
> packages.find 裡**，直接跑檔案路徑會 ModuleNotFoundError——那是刻意的，
> 比靠路徑硬塞而安靜地成功要好。注入真正的害處不是多餘，是**遮蔽
> 「沒安裝就跑」的 import 錯誤**。
>
> `scripts/check_layer_deps.py` 的 G 節順手改用 AST 找呼叫節點：舊版逐行比對
> 字串，清乾淨後唯一剩下的一筆正是**解釋這件事的 docstring**——護欄把自己的
> 說明算成違規，就不能拿它當「應為 0」的判準。新增測試沿用該函式，
> 已實測塞回一處即失敗。
>
> **F-001 測試面（實查已完成，未改動）**：`tests/conftest.py` 的
> `pytest_sessionstart` no-op 早就在了。本次實測 `pytest -m "not slow"` 前後
> `logs/` 的 mtime **完全未變**。這是本輪第三次遇到「處置欄寫了、其實早就做掉」，
> 下次處理殘留項目一律先實查現況。

### S6. 環境變數、相依檔與設定檔一致 ⬜

- **目的**：F-096、F-100、F-015、F-016、F-018。
- **做法**：`.env.example` 補齊並標選填；`schema.py` 改讀 `settings.DDB_PATH` 且缺值即 raise；刪 `core/utils/path.py` 併入 `config/paths.py`；conda yml 標註停用或刪除；`requirements.txt` 以 `pip-compile` 重產；pyproject per-file-ignores 路徑修正。
- **產出**：見進度表。
- **驗證方式**：`pytest -m "not slow"`、`ruff check .`、健檢 S20 的 AST 對照腳本重跑無缺口。
- **相依**：無。
