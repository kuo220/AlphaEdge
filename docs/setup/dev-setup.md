# 開發環境設定（Dev Setup）

本文件針對目前 `AlphaEdge` 專案實際結構整理（以 `run.py`、`tasks/update_db.py`、`trader/` 為主）。

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

專案目前未提供統一的 `requirements.txt` / `pyproject.toml`。  
建議先安裝核心執行所需套件：

```bash
python -m pip install --upgrade pip
python -m pip install pandas numpy requests loguru python-dotenv fake-useragent plotly kaleido shioaji
```

如需執行測試，另安裝：

```bash
python -m pip install pytest
```

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
mkdir -p trader/database trader/data trader/logs trader/backtest/results
```

## 5) 基本驗證

```bash
# 檢查主要模組可載入
python -c "from trader.backtest import Backtester; from trader.strategies import StrategyLoader; print('OK')"

# 顯示主程式參數
python run.py --help

# 顯示資料更新參數
python -m tasks.update_db --help
```

完成後可參考 [開發部署](../deployment/dev-deployment.md)。

# 開發環境設定（Dev Setup）

## 前置需求

- **Python** 3.12+
- **Docker** 與 **Docker Compose**（v2）
- **Git**

## 1. 建立 Python 虛擬環境

```bash
cd trading-system
python3.12 -m venv .venv
source .venv/bin/activate
```

## 2. 安裝相依套件

```bash
# 安裝全部（含 dev 工具、各交易所 SDK、通知套件）
python -m pip install -e ".[dev,kalshi,polymarket,notifications]"
```

各 optional dependency group：

| Group           | 內容                                     |
| --------------- | ---------------------------------------- |
| `dev`           | pytest, pytest-asyncio, ruff, pre-commit |
| `kalshi`        | cryptography（RSA 簽章）                 |
| `polymarket`    | py-clob-client                           |
| `notifications` | discord.py, python-telegram-bot          |

## 3. 設定程式碼格式化

本專案使用 [Ruff](https://docs.astral.sh/ruff/) 統一程式碼風格（format + lint），並透過 pre-commit hook 在 commit 時自動檢查。

```bash
# 安裝 git pre-commit hooks（只需執行一次）
pre-commit install
```

安裝後每次 `git commit` 會自動執行 Ruff lint + format，未通過則 commit 會被擋下。

**VS Code / Cursor 使用者**：安裝 [Ruff extension](https://marketplace.visualstudio.com/items?itemName=charliermarsh.ruff)（`charliermarsh.ruff`），專案已內建 `.vscode/settings.json`，存檔時會自動 format。

**手動執行**：

```bash
ruff check --fix .   # lint + auto-fix
ruff format .        # format
```

## 4. 設定環境變數

```bash
cp .env.example .env
# 編輯 .env，填入你的 API key
```

需要填的 key（依使用的交易所而定）：

- `KALSHI_API_KEY` / `KALSHI_PRIVATE_KEY_PATH`（無 key 可降級 REST-only 模式）
- `BINANCE_API_KEY` / `BINANCE_API_SECRET`（選填，公開資料不需 key）
- `OKX_API_KEY` / `OKX_API_SECRET` / `OKX_PASSPHRASE`（選填，公開資料不需 key）
- `DISCORD_BOT_TOKEN` / `DISCORD_SYSTEM_ALERTS_CHANNEL_ID` / `DISCORD_SYSTEM_OPS_CHANNEL_ID` / `DISCORD_SIGNALS_CHANNEL_ID`（選填）
- `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID`（選填）

> Polymarket 的 Gamma API 為公開介面，讀取資料不需認證。
>
> Binance 預設使用 `data-stream.binance.vision` / `data-api.binance.vision` 端點，繞過地區封鎖。如需自訂，可在 `.env` 中設定 `BINANCE_SPOT_WS`、`BINANCE_REST_URL` 等。完整環境變數列表見 [`.env.example`](../../.env.example)。

各交易所 API 詳細設定請參閱：

- [Kalshi API 設定](../exchanges/kalshi_api_setup.md)
- [Polymarket API 設定](../exchanges/polymarket_api_setup.md)

## 5. 驗證

```bash
# 確認 import 正常
PYTHONPATH=. python -c "from core.engine import ReplayEngine; print('OK')"

# 跑測試
pytest
```

設定完成後，參閱 [開發部署](../deployment/dev-deployment.md) 了解如何啟動資料庫與各項服務。
