# 測試護欄與本機／CI／容器一致性

## Abstract

- **背景／問題**：[全專案架構與邏輯健檢（2026-09）](../docs/dev/health-check-2026-09.md) S18~S20 發現「本機綠、CI 不跑、容器起不來」三處不一致：`run_regression.sh` 在沒有 `tw_stock.db` 的機器會跳過 LONG 線仍印「雙線通過」（F-090）、CI 從不跑 slow 測試與回歸線（F-095）、`frontend` 映像缺 `plotly`（F-093）、`core` 容器沒有 `data/` 與 `tasks/`（F-094）、`run.py` 錯誤退出碼 0（F-077）、一次性 codemod 誤跑會改壞同層專案（F-089）。
- **目標**：回歸護欄在任何機器上「要嘛真的跑、要嘛明確說沒跑」；`docker compose up` 能跑完一次回測並在前端看到；一次性腳本清出 `scripts/`。
- **範圍界線**：不改測試框架、不引入新的 CI 服務、不做覆蓋率門檻。
- **驗收標準**：`./scripts/run_regression.sh` 在無 DB 機器結束碼非 0 且訊息明確；CI 至少跑 SHORT 線；`docker compose build && docker compose up` 在準備好 `data/db` 的機器上跑完 `MomentumStrategy1` 並於前端顯示；`python run.py --strategy NotExist; echo $?` 非 0。

## 進度追蹤表

| 編號 | 步驟名稱 | 產出檔案 | 驗證方式 | 狀態 | 備註／中斷點 |
|------|----------|----------|----------|:----:|--------------|
| S1 | 回歸腳本假綠燈與 CI 護欄 | `scripts/run_regression.sh`、`.github/workflows/ci.yml`、`.pre-commit-config.yaml`、`pyproject.toml`、`docs/dev/{code-quality,health-check-2026-09}.md` | 無 DB 時腳本非零結束並印「LONG 線未執行」；CI 新增 SHORT 線步驟 | ✅ | **2026-09-05 完成**。無 DB 實測結束碼 3；CI 另加分層閘門；ruff 釘死 `==0.16.3`。`test_long_regression.py` 未改（`skipif` 是對的，錯的是腳本把 skip 當通過） |
| S2 | 容器可跑：前端相依、`core` 掛 `data/`、只裝 pyproject 相依 | `frontend/requirements.txt`（新增）、`frontend/Dockerfile`、`core/Dockerfile`、`docker-compose.yml`、`README*.md` | `docker compose config` OK；`compose up` 跑完示範策略；映像不含 Flask／ipython 等無關套件 | ⬜ | F-093、F-094、F-096(5) |
| S3 | 入口退出碼與 `--mode live` | `run.py`、`tests/test_run_entry.py`（新增） | subprocess 測試：找不到策略 exit 2；`live` 明確 `NotImplementedError` | ⬜ | F-077 |
| S4 | 一次性腳本清理與 `tests/manual_*` 搬家 | `scripts/dataframe_dot_to_bracket.py`（刪）、`generate_docs.py`（刪）、`clean_pycache.ps1`（修）、`tasks/migrate_db_naming.py`（搬 `scripts/migrations/`）、`tests/manual_*.py`（搬 `scripts/manual/`） | `git rm` 後 `pytest` 全綠；`grep return False tests/` 為 0 | ⬜ | F-089、F-091、F-081、F-092 |
| S5 | 測試護欄補強：策略不自建連線、loguru 隔離、`sys.path.insert` 清理 | `tests/test_strategy_data_access.py`、`tests/conftest.py`、`strategy_lab/**/run.py`、`tests/*.py` | 在策略加 `StockPriceAPI()` 即紅；pytest 後 `logs/` mtime 不變；`python -m` 方式可跑研究腳本 | ⬜ | F-074、F-001（測試面）、F-009；`tests/conftest.py` 的 no-op 作法已在健檢期間驗證 |
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

### S2. 容器可跑 ⬜

- **目的**：F-093／F-094。
- **做法**：新增 `frontend/requirements.txt`（streamlit、pandas、plotly）或改 `pip install -e ".[frontend]"`；compose 為 `core` 掛 `./data:/app/data:ro` 與 `./logs:/app/logs`，映像 COPY `tasks/`；`core/Dockerfile` 改 `pip install -e .`；README 兩份的方式 3 註明「需先在本機準備 `data/db/*.db`」。
- **產出**：見進度表。
- **驗證方式**：見進度表。
- **相依**：無。

### S3. 入口退出碼 ⬜

- **目的**：F-077。
- **做法**：找不到策略 → `sys.exit(2)`＋stderr 清單；`live` → `raise NotImplementedError`（或自 `choices` 移除）。
- **產出**：`run.py`、新測試。
- **驗證方式**：subprocess 斷言退出碼。
- **相依**：無。

### S4. 一次性腳本清理 ⬜

- **目的**：F-089（`parents[2]` 指向專案上一層的 codemod）、F-091、F-081、F-092。
- **做法**：見進度表；`manual_*` 搬家後在 `scripts/manual/README.md` 註明「不是 pytest 對象、如何執行」。
- **產出**：見進度表。
- **驗證方式**：見進度表。
- **相依**：無。

### S5. 測試護欄補強 ⬜

- **目的**：F-074、F-001 測試面、F-009。
- **做法**：`test_strategy_data_access.py` 加 parametrize 掃 `sqlite3.connect(`／`API()`；`tests/conftest.py` 以 `pytest_sessionstart` 把 `LogManager.setup_logger`／`setup_backtest_logger` 換成 no-op（等期貨回補結束後再動 `log_manager.py` 本體）；`sys.path.insert` 全部移除、研究腳本改 `python -m strategy_lab.…`。
- **產出**：見進度表。
- **驗證方式**：見進度表。
- **相依**：無。

### S6. 環境變數、相依檔與設定檔一致 ⬜

- **目的**：F-096、F-100、F-015、F-016、F-018。
- **做法**：`.env.example` 補齊並標選填；`schema.py` 改讀 `settings.DDB_PATH` 且缺值即 raise；刪 `core/utils/path.py` 併入 `config/paths.py`；conda yml 標註停用或刪除；`requirements.txt` 以 `pip-compile` 重產；pyproject per-file-ignores 路徑修正。
- **產出**：見進度表。
- **驗證方式**：`pytest -m "not slow"`、`ruff check .`、健檢 S20 的 AST 對照腳本重跑無缺口。
- **相依**：無。
