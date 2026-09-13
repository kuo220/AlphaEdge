# 開發環境設定（Dev Setup）

本文件針對目前 `AlphaEdge` 專案實際結構整理（以 `run.py`、`tasks/update_db.py`、`core/` 為主）。

## 前置需求

- Python **3.12+**（`pyproject.toml` 的 `requires-python = ">=3.12"`；CI 亦使用 3.12）
- pip（隨 Python 安裝；以下請用 `python -m pip`，以確保安裝在目前使用的直譯器環境）
- Git
- （選用）DolphinDB：若要使用 tick 相關 API/更新

## 1) 建立虛擬環境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2) 安裝套件

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` 是鎖定版本的完整清單，最後一行 `-e .` 會把專案本身也裝成
editable，因此**一行指令就完成環境建置**。

安裝後 `core` / `tasks` / `tests` 於**任意工作目錄**皆可 import，不需再設 `PYTHONPATH`。

要跑測試與 lint 請一併安裝開發相依：

```bash
python -m pip install -e ".[dev]"   # pytest、pytest-timeout、pytest-cov、ruff
```

選用相依（預設不裝，主流程不需要）：`[frontend]` Streamlit 介面、
`[tick]` DolphinDB tick 儲存、`[lab]` `strategy_lab` 報告輸出。

套件 metadata（相依名稱、optional extras、Python 版本下限）定義在 `pyproject.toml`；
`requirements.txt` 則負責鎖定實際版本，Docker build 也用同一份。

`requirements.txt` 只含 `pyproject.toml` 主相依與它們的傳遞相依，不含 `[dev]`／`[frontend]`／
`[tick]`／`[lab]`。清單裡的 Flask、ipython、ta、pytest 看似無關，其實是 FinMind 自己宣告的相依，
移不掉。修改 `pyproject.toml` 的相依後，以乾淨 venv 重產（沿用現有鎖定版本當 constraints，
只有新增的套件會解析新版本）：

```bash
python3 -m venv /tmp/lockenv
grep -v -E '^\s*(-e|#|$)' requirements.txt > /tmp/constraints.txt
/tmp/lockenv/bin/pip install -c /tmp/constraints.txt -e .
/tmp/lockenv/bin/pip check
/tmp/lockenv/bin/pip freeze --exclude-editable   # 貼回 requirements.txt，最後一行保留 `-e .`
```

`tests/test_config_consistency.py` 會檢查 `pyproject.toml` 的每個主相依在 `requirements.txt` 都有鎖定版本。

## 3) 設定環境變數

```bash
cp .env.example .env
```

請依需求填寫 `.env`：

- DolphinDB（tick 需要）：`DDB_PATH`、`DDB_HOST`、`DDB_PORT`、`DDB_USER`、`DDB_PASSWORD`
- Shioaji：`API_KEY`、`API_SECRET_KEY`
- FinMind：`FINMIND_API_TOKEN`
- （選填）多組 Shioaji 帳號輪替：`API_KEY_1`~`API_KEY_4`、`API_SECRET_KEY_1`~`API_SECRET_KEY_4`（`core/config/settings.py` 的 `NUM_API`）
- （選填）執行期產物根目錄覆寫：`ALPHAEDGE_DATA_DIR`／`ALPHAEDGE_RESULTS_DIR`／`ALPHAEDGE_LOGS_DIR`（見 [執行期產物](../dev/runtime-artifacts.md)）。**前端讀的是同一個 `ALPHAEDGE_RESULTS_DIR`**，不設也能跑（預設 `PROJECT_ROOT/results`）；舊名 `ALPHAEDGE_BACKTEST_RESULTS` 仍相容一版並會發出警告
- （選填）回測畫完圖在瀏覽器開啟：`ALPHAEDGE_SHOW_FIGURES=1`（等同 `run.py --show`；預設不開）

`.env.example` 與程式實際讀取的環境變數由 `tests/test_config_consistency.py` 雙向核對：
程式新增一個 `os.getenv("X")` 卻沒補進範本，或範本留著程式已不再讀的鍵，測試都會失敗。

## 4) 初始化資料目錄（選用）

多數目錄會在執行時自動建立；若要先手動準備可建立：

```bash
mkdir -p data/db data/downloads logs results
```

## 5) 基本驗證

```bash
# 檢查主要模組可載入
# 注意：一律用完整模組路徑。core/backtest/__init__.py 與 core/strategies/__init__.py
# 刻意不做套件層 eager import（會造成循環 import），故 `from core.backtest import
# Backtester` 會失敗
python -c "from core.backtest.backtester import Backtester; from core.strategies.strategy_loader import StrategyLoader; print('OK')"

# 顯示主程式參數
python run.py --help

# 顯示資料更新參數
python -m tasks.update_db --help
```

## 6) 程式碼品質檢查（選用但建議）

```bash
ruff check .            # lint
ruff format .           # 格式化
pytest -m "not slow"    # 略過需要 tw_stock.db 與外部 API 憑證的測試
```

可安裝 pre-commit 讓每次 commit 前自動跑同一組檢查：

```bash
pip install pre-commit && pre-commit install
```

設定理由與暫時關閉的規則見 [程式碼品質工具鏈](../dev/code-quality.md)。

---

完成後可參考 [開發部署](../deployment/dev-deployment.md)。
