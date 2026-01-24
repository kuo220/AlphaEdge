import os
from pathlib import Path

from dotenv import load_dotenv

from trader.utils.path import get_static_resolved_path

# Load environment variables from .env file
load_dotenv()


""" Root Directory (trader/) Path """
BASE_DIR_PATH: Path = Path(__file__).resolve().parent


""" === General Directory Path === """
DATABASE_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="database"
)
LOGS_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="logs")
DATA_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="data"
)


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


""" === Certs.cer === """
CERTS_DIR_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH, dir_name="certs"
)
CERTS_FILE_PATH: Path = get_static_resolved_path(
    base_dir=CERTS_DIR_PATH, dir_name="certs.cer"
)


""" === DolphinDB server setting === """
DDB_PATH: str = os.getenv("DDB_PATH")
DDB_HOST: str = os.getenv("DDB_HOST")
DDB_PORT: int = int(os.getenv("DDB_PORT"))
DDB_USER: str = os.getenv("DDB_USER")
DDB_PASSWORD: str = os.getenv("DDB_PASSWORD")


""" === Shioaji API === """
API_KEY: str = os.getenv("API_KEY")
API_SECRET_KEY: str = os.getenv("API_SECRET_KEY")

""" === API list for crawling tick data === """
NUM_API: int = 4
API_KEYS = [os.getenv(f"API_KEY_{i + 1}") for i in range(NUM_API)]
API_SECRET_KEYS = [os.getenv(f"API_SECRET_KEY_{i + 1}") for i in range(NUM_API)]
