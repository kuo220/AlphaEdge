import datetime
import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# 從 .env 載入環境變數
load_dotenv()


def get_static_resolved_path(base_dir: Path, dir_name: str) -> Path:
    """Resolve dir_name under base_dir to an absolute path"""
    return (base_dir / dir_name).resolve()


# -----------------------------------------------------------------------
# Root Directory (core/) Path
# -----------------------------------------------------------------------
#
BASE_DIR_PATH: Path = Path(__file__).resolve().parent


# -----------------------------------------------------------------------
# === General Directory Path ===
# -----------------------------------------------------------------------
#
DATABASE_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="database"
)
# 目錄**不在此建立**：import 一個設定模組不應該有檔案系統副作用，
# 否則任何只是要讀常數的測試都會被動生出 core/logs/。
# 實際要寫檔時由 `LogManager.setup_logger()` 惰性建立（見 log_manager.py）
LOGS_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="logs")
DATA_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="data")


# -----------------------------------------------------------------------
# === Strategy Directory Path ===
# -----------------------------------------------------------------------
#
STOCK_STRATEGY_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="strategies/stock"
)


# -----------------------------------------------------------------------
# === Backtest Result Directory Path ===
# -----------------------------------------------------------------------
#
BACKTEST_RESULT_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="backtest/results"
)
BACKTEST_LOGS_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="backtest/results/logs"
)

# -----------------------------------------------------------------------
# === Crawl Data Downloads Path ===
# -----------------------------------------------------------------------
#
PIPELINE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="pipeline/downloads"
)

# 中繼檔依「市場」分層，與 core/database/ 的 stock.db／futures.db 同一個維度。
# 程式碼（pipeline / api / adapters）維持命名平行不分目錄——兩者搬遷成本差一個量級，
# 決策理由見 backlog/台期貨ETL與回測架構規劃.md §3.0
TW_STOCK_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="tw_stock"
)
TW_FUTURES_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="tw_futures"
)
FINANCIAL_STATEMENT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="financial_statement"
)
MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="monthly_revenue_report"
)
PRICE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="price"
)
CHIP_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="chip"
)
MARGIN_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="margin"
)
DIVIDEND_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="dividend"
)
TICK_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="tick"
)
FINMIND_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="finmind"
)

# 台期貨中繼檔；目錄與 tw_stock 同構，只是資料類型不同
FUTURES_PRICE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="price"
)
FUTURES_CHIP_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="chip"
)
FUTURES_CONTINUOUS_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="continuous"
)
FUTURES_UNIVERSE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="universe"
)
FUTURES_TICK_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="tick"
)

# -----------------------------------------------------------------------
# === Crawler Downloads Metadata Directory Path ===
# -----------------------------------------------------------------------
#
DOWNLOADS_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=TW_STOCK_DOWNLOADS_PATH, dir_name="meta"
)
FINANCIAL_STATEMENT_META_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="financial_statement"
)
MONTHLY_REVENUE_REPORT_META_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="monthly_revenue_report"
)
TICK_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="tick"
)
TICK_METADATA_PATH: Path = get_static_resolved_path(
    base_dir=TICK_METADATA_DIR_PATH, dir_name="tick_metadata.json"
)
BROKER_TRADING_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH, dir_name="broker_trading"
)
FUTURES_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=TW_FUTURES_DOWNLOADS_PATH, dir_name="meta"
)
BROKER_TRADING_METADATA_PATH: Path = get_static_resolved_path(
    base_dir=BROKER_TRADING_METADATA_DIR_PATH, dir_name="broker_trading_metadata.json"
)

# -----------------------------------------------------------------------
# === Reference Data Directory Path ===
# -----------------------------------------------------------------------
# 股票相關參考資料表存放目錄
STOCK_INFO_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DATA_DIR_PATH, dir_name="stock_info"
)

# 股票列表參考資料（上市、上櫃、興櫃的股票、權證名稱、代碼和產業類別）
STOCK_LIST_JSON_PATH: Path = get_static_resolved_path(
    base_dir=STOCK_INFO_DIR_PATH, dir_name="taiwan_stock_list.json"
)
STOCK_LIST_CSV_PATH: Path = get_static_resolved_path(
    base_dir=STOCK_INFO_DIR_PATH, dir_name="taiwan_stock_list.csv"
)

# 證券商資訊參考資料（用於台股分點資料表，使用券商代碼查詢特定券商所有股票進出）
BROKER_INFO_CSV_PATH: Path = get_static_resolved_path(
    base_dir=STOCK_INFO_DIR_PATH, dir_name="taiwan_securities_trader_info.csv"
)


# -----------------------------------------------------------------------
# === Database Files Full Paths ===
# -----------------------------------------------------------------------
#
DB_NAME: str = "stock.db"
TICK_DB_NAME: str = "tickDB"

DB_PATH: Path = get_static_resolved_path(base_dir=DATABASE_DIR_PATH, dir_name=DB_NAME)
TICK_DB_PATH: str = f"{os.getenv('DDB_PATH')}{TICK_DB_NAME}"

# 期貨與股票分庫：合約碼（contract_id）與 stock_id 語意不同，混在同一個 DB
# 會讓「這張表的主鍵到底是什麼」失去單一答案
FUTURES_DB_NAME: str = "futures.db"

FUTURES_DB_PATH: Path = get_static_resolved_path(
    base_dir=DATABASE_DIR_PATH, dir_name=FUTURES_DB_NAME
)


# -----------------------------------------------------------------------
# === Database Table names ===
# -----------------------------------------------------------------------
#
PRICE_TABLE_NAME: str = "price"
CHIP_TABLE_NAME: str = "chip"
MARGIN_TABLE_NAME: str = "margin"
DIVIDEND_TABLE_NAME: str = "dividend"
TICK_TABLE_NAME: str = "tick"
MONTHLY_REVENUE_TABLE_NAME: str = "monthly_revenue"
BALANCE_SHEET_TABLE_NAME: str = "balance_sheet"
COMPREHENSIVE_INCOME_TABLE_NAME: str = "comprehensive_income"
CASH_FLOW_TABLE_NAME: str = "cash_flow"
EQUITY_CHANGE_TABLE_NAME: str = "equity_change"
STOCK_INFO_TABLE_NAME: str = "taiwan_stock_info"
STOCK_INFO_WITH_WARRANT_TABLE_NAME: str = "taiwan_stock_info_with_warrant"
SECURITIES_TRADER_INFO_TABLE_NAME: str = "taiwan_securities_trader_info"
# 台期貨（皆位於 futures.db）
FUTURES_CONTRACT_TABLE_NAME: str = "futures_contract"  # 合約／商品規格
FUTURES_PRICE_DAILY_TABLE_NAME: str = "futures_price_daily"  # 各月份合約日 K
FUTURES_CONTINUOUS_TABLE_NAME: str = "futures_continuous"  # 連續合約（換月接續後）
FUTURES_INSTITUTIONAL_CHIP_TABLE_NAME: str = (
    "futures_institutional_chip"  # 三大法人／大額交易人
)
FUTURES_MARGIN_HISTORY_TABLE_NAME: str = "futures_margin_history"  # 保證金歷史序列
FUTURES_STOCK_UNIVERSE_TABLE_NAME: str = "futures_stock_universe"  # 股票期貨標的池

STOCK_TRADING_DAILY_REPORT_TABLE_NAME: str = (
    "taiwan_stock_trading_daily_report_secid_agg"
)


# -----------------------------------------------------------------------
# === Default dates for update_db / pipeline（資料更新預設區間）===
# -----------------------------------------------------------------------
#
DEFAULT_CHIP_START_DATE: datetime.date = datetime.date(2013, 1, 1)
DEFAULT_MARGIN_START_DATE: datetime.date = datetime.date(2013, 1, 1)
DEFAULT_DIVIDEND_START_DATE: datetime.date = datetime.date(2013, 1, 1)
DEFAULT_PRICE_START_DATE: datetime.date = datetime.date(2013, 1, 1)
DEFAULT_START_YEAR: int = 2013
DEFAULT_END_MONTH: int = 12
TICK_UPDATE_START_DATE: datetime.date = datetime.date(2024, 5, 10)
FINMIND_BROKER_TRADING_START_DATE: datetime.date = datetime.date(2021, 6, 30)
# 結束日不設常數：與 chip／margin／dividend／price 一致，由呼叫端取 today()


# -----------------------------------------------------------------------
# === DolphinDB server setting ===
# -----------------------------------------------------------------------
#
def get_int_env(name: str, default: int = 0) -> int:
    """
    讀取整數型環境變數；無法轉型時退回預設值

    原本是 `int(os.getenv("DDB_PORT") or "0")`：環境變數被設成任何非數字字串
    （含誤植的空白或註解）都會在 **import 期**拋 ValueError，
    而這個模組被全專案 import，等於整個程式無法啟動且錯誤訊息與設定無關。
    """

    raw: Optional[str] = os.getenv(name)
    if not raw:
        return default

    try:
        return int(raw)
    except ValueError:
        return default


DDB_PATH: str | None = os.getenv("DDB_PATH")
DDB_HOST: str | None = os.getenv("DDB_HOST")
DDB_PORT: int = get_int_env("DDB_PORT")
DDB_USER: str | None = os.getenv("DDB_USER")
DDB_PASSWORD: str | None = os.getenv("DDB_PASSWORD")


# -----------------------------------------------------------------------
# === Shioaji API ===
# -----------------------------------------------------------------------
#
API_KEY: str | None = os.getenv("API_KEY")
API_SECRET_KEY: str | None = os.getenv("API_SECRET_KEY")

# -----------------------------------------------------------------------
# === API list for crawling tick data ===
# -----------------------------------------------------------------------
#
NUM_API: int = 4
API_KEYS: List[Optional[str]] = [os.getenv(f"API_KEY_{i + 1}") for i in range(NUM_API)]
API_SECRET_KEYS: List[Optional[str]] = [
    os.getenv(f"API_SECRET_KEY_{i + 1}") for i in range(NUM_API)
]
