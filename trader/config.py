import os
from pathlib import Path
from typing import List, Optional

from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


# 將固定資料夾名稱解析為 base_dir 下的絕對路徑
def get_static_resolved_path(base_dir: Path, dir_name: str) -> Path:
    """
    將固定資料夾名稱解析為 base_dir 下的絕對路徑。

    Args:
        base_dir: 基礎目錄路徑
        dir_name: 資料夾名稱或相對路徑字串（可包含子目錄，如 "logs/app"）

    Returns:
        解析後的絕對路徑

    Example:
        >>> base = Path('/home/user/project')
        >>> path = get_static_resolved_path(base, 'logs')
        >>> # 結果: PosixPath('/home/user/project/logs')
    """
    return (base_dir / dir_name).resolve()


""" Root Directory (trader/) Path """
BASE_DIR_PATH: Path = Path(__file__).resolve().parent


""" === General Directory Path === """
DATABASE_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="database"
)
LOGS_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="logs")
LOGS_DIR_PATH.mkdir(parents=True, exist_ok=True)  # 確保 logs 目錄存在
DATA_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="data")


""" === Strategy Directory Path === """
STOCK_STRATEGY_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="strategies/stock"
)


""" === Backtest Result Directory Path === """
BACKTEST_RESULT_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="backtest/results"
)
BACKTEST_LOGS_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="backtest/results/logs"
)

""" === Crawl Data Downloads Path === """
PIPELINE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="pipeline/downloads"
)
FINANCIAL_STATEMENT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="financial_statement"
)
MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="monthly_revenue_report"
)
PRICE_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="price"
)
CHIP_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="chip"
)
TICK_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="tick"
)
FINMIND_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="finmind"
)

""" === Crawler Downloads Metadata Directory Path === """
DOWNLOADS_METADATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=PIPELINE_DOWNLOADS_PATH, dir_name="meta"
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

""" === Reference Data Directory Path === """
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


""" === Database Files Full Paths === """
DB_NAME: str = "data.db"
TICK_DB_NAME: str = "tickDB"

DB_PATH: Path = get_static_resolved_path(base_dir=DATABASE_DIR_PATH, dir_name=DB_NAME)
TICK_DB_PATH: str = f"{os.getenv('DDB_PATH')}{TICK_DB_NAME}"


""" === Database Table names === """
PRICE_TABLE_NAME: str = "price"
CHIP_TABLE_NAME: str = "chip"
TICK_TABLE_NAME: str = "tick"
MONTHLY_REVENUE_TABLE_NAME: str = "monthly_revenue"
BALANCE_SHEET_TABLE_NAME: str = "balance_sheet"
COMPREHENSIVE_INCOME_TABLE_NAME: str = "comprehensive_income"
CASH_FLOW_TABLE_NAME: str = "cash_flow"
EQUITY_CHANGE_TABLE_NAME: str = "equity_change"
TICK_METADATA_TABLE_NAME: str = "TICK_METADATA_TABLE_NAME"
STOCK_INFO_WITH_WARRANT_TABLE_NAME: str = "taiwan_stock_info_with_warrant"
SECURITIES_TRADER_INFO_TABLE_NAME: str = "taiwan_securities_trader_info"
STOCK_TRADING_DAILY_REPORT_TABLE_NAME: str = (
    "taiwan_stock_trading_daily_report_secid_agg"
)


""" === Certs.cer === """
CERTS_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="certs"
)
CERTS_FILE_PATH: Path = get_static_resolved_path(
    base_dir=CERTS_DIR_PATH, dir_name="certs.cer"
)


""" === DolphinDB server setting === """
DDB_PATH: str | None = os.getenv("DDB_PATH")
DDB_HOST: str | None = os.getenv("DDB_HOST")
DDB_PORT: int = int(os.getenv("DDB_PORT") or "0")
DDB_USER: str | None = os.getenv("DDB_USER")
DDB_PASSWORD: str | None = os.getenv("DDB_PASSWORD")


""" === Shioaji API === """
API_KEY: str | None = os.getenv("API_KEY")
API_SECRET_KEY: str | None = os.getenv("API_SECRET_KEY")

""" === API list for crawling tick data === """
NUM_API: int = 4
API_KEYS: List[Optional[str]] = [os.getenv(f"API_KEY_{i + 1}") for i in range(NUM_API)]
API_SECRET_KEYS: List[Optional[str]] = [
    os.getenv(f"API_SECRET_KEY_{i + 1}") for i in range(NUM_API)
]
