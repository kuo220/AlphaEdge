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

## 3) 設定環境變數

```bash
cp .env.example .env
```

請依需求填寫 `.env`：

- DolphinDB（tick 需要）：`DDB_PATH`、`DDB_HOST`、`DDB_PORT`、`DDB_USER`、`DDB_PASSWORD`
- Shioaji：`API_KEY`、`API_SECRET_KEY`
- FinMind：`FINMIND_API_TOKEN`

## 4) 初始化資料目錄（選用）

多數目錄會在執行時自動建立；若要先手動準備可建立：

```bash
mkdir -p data/db core/data logs/pipeline results
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

設定理由與已知的待收斂項目見 [程式碼品質工具鏈與基線](../dev/code-quality.md)。

---

完成後可參考 [開發部署](../deployment/dev-deployment.md)。
