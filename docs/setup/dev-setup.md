# 開發環境設定（Dev Setup）

本文件針對目前 `AlphaEdge` 專案實際結構整理（以 `run.py`、`tasks/update_db.py`、`core/` 為主）。

## 前置需求

- Python 3.11+（建議 3.11 或 3.12）
- pip（隨 Python 安裝；以下請用 `python -m pip`，以確保安裝在目前使用的直譯器環境）
- Git
- （選用）DolphinDB：若要使用 tick 相關 API/更新

## 1) 建立虛擬環境

```bash
python3 -m venv .venv
source .venv/bin/activate
```

## 2) 安裝套件

專案已提供 `requirements.txt`（尚未使用 `pyproject.toml`）：

```bash
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

`requirements.txt` 已包含 `pytest`，安裝後即可直接執行測試。

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
mkdir -p core/database core/data core/logs core/backtest/results
```

## 5) 基本驗證

```bash
# 檢查主要模組可載入
python -c "from core.backtest import Backtester; from core.strategies import StrategyLoader; print('OK')"

# 顯示主程式參數
python run.py --help

# 顯示資料更新參數
python -m tasks.update_db --help
```

完成後可參考 [開發部署](../deployment/dev-deployment.md)。
