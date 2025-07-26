import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

from trader.utils import ShioajiAPI
from trader.utils.path import (
    get_env_resolved_path,
    get_static_resolved_path
)

# Load environment variables from .env file
load_dotenv()


# Root Directory (trader/)
BASE_DIR_PATH: Path = Path(__file__).resolve().parent


# === General Directory Path ===
DATABASE_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="database")
BACKTEST_RESULT_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="backtest/performance/results")
LOGS_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="logs")

# === Strategy Directory Path ===
STOCK_STRATEGY_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="strategies/stock")


# === Crawl Data Downloads Path ===
CRAWLER_DOWNLOADS_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="pipeline/downloads")
FINANCIAL_STATEMENT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH,
    dir_name="pipeline/downloads/financial_statement"
)
MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH: Path = get_static_resolved_path(
    base_dir=BASE_DIR_PATH,
    dir_name="pipeline/downloads/monthly_revenue_report"
)
PRICE_DOWNLOADS_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="pipeline/downloads/price")
CHIP_DOWNLOADS_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="pipeline/downloads/chip")
TICK_DOWNLOADS_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="pipeline/downloads/tick")

# === Crawler Downloads Metadata Directory Path ===
DOWNLOADS_METADATA_DIR_PATH: Path = get_static_resolved_path(base_dir=CRAWLER_DOWNLOADS_PATH, dir_name="meta")
FINANCIAL_STATEMENT_META_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH,
    dir_name="financial_statement"
)
MONTHLY_REVENUE_REPORT_META_DIR_PATH: Path = get_static_resolved_path(
    base_dir=DOWNLOADS_METADATA_DIR_PATH,
    dir_name="monthly_revenue_report"
)


# === Certs.cer ===
CERTS_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="certs")
CERTS_FILE_PATH: Path = get_static_resolved_path(base_dir=CERTS_DIR_PATH, dir_name="certs.cer")


# === Tick Metadata Directory Path ===
DB_METADATA_DIR_PATH: Path = get_static_resolved_path(base_dir=BASE_DIR_PATH, dir_name="database/meta")
TICK_METADATA_PATH: Path = get_static_resolved_path(
    base_dir=DB_METADATA_DIR_PATH,
    dir_name="tick_metadata.json"
)


# === Database Files Full Paths ===
DB_NAME: str = "data.db"
TICK_DB_NAME: str = "tickDB"

DB_PATH: Path = get_static_resolved_path(base_dir=DATABASE_DIR_PATH, dir_name=DB_NAME)
TICK_DB_PATH: str = f"{os.getenv('DDB_PATH')}{TICK_DB_NAME}"


# === Database Table names ===
PRICE_TABLE_NAME: str = "price"
CHIP_TABLE_NAME: str = "chip"
TICK_TABLE_NAME: str = "tick"
MONTHLY_REVENUE_TABLE_NAME: str = "monthly_revenue"
BALANCE_SHEET_TABLE_NAME: str = "balance_sheet"
COMPREHENSIVE_INCOME_TABLE_NAME: str = "comprehensive_income"
CASH_FLOW_TABLE_NAME: str = "cash_flow"
EQUITY_CHANGE_TABLE_NAME: str = "equity_change"
TICK_METADATA_TABLE_NAME: str = "TICK_METADATA_TABLE_NAME"


# === DolphinDB server setting ===
DDB_PATH: str = os.getenv("DDB_PATH")
DDB_HOST: str = os.getenv("DDB_HOST")
DDB_PORT: int = int(os.getenv("DDB_PORT"))
DDB_USER: str = os.getenv("DDB_USER")
DDB_PASSWORD: str = os.getenv("DDB_PASSWORD")


# === Shioaji API ===
API_KEY: str = os.getenv("API_KEY")
API_SECRET_KEY: str = os.getenv("API_SECRET_KEY")


# === API list for crawling tick data ===
NUM_API: int = 4
API_LIST: List[ShioajiAPI] = []

# Add API from 11 ~ 17 and add API_1 (Mine)
for num in range(NUM_API):
    api: ShioajiAPI = ShioajiAPI(
        os.getenv(f"API_KEY_{num + 1}"), os.getenv(f"API_SECRET_KEY_{num + 1}")
    )
    API_LIST.append(api)
