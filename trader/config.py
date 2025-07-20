import os
from pathlib import Path
from typing import List, Optional
from dotenv import load_dotenv

from trader.utils import ShioajiAPI

# Load environment variables from .env file
load_dotenv()


# Root Directory
BASE_DIR: Path = Path(__file__).resolve().parent  # trader


# === Helper: Load and resolve path from .env ===
def get_resolved_path(env_key: str, default: str = None) -> Path:
    value: Optional[str] = os.getenv(env_key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {env_key}")
    return (BASE_DIR / value).resolve()


# === General Directory Path ===
DATABASE_DIR_PATH: Path = get_resolved_path("DATABASE_DIR_PATH")
BACKTEST_RESULT_DIR_PATH: Path = get_resolved_path("BACKTEST_RESULT_DIR_PATH")
LOGS_DIR_PATH: Path = get_resolved_path("LOGS_DIR_PATH")

# === Strategy Directory Path ===
STOCK_STRATEGY_DIR_PATH: Path = get_resolved_path("STOCK_STRATEGY_DIR_PATH")


# === Crawl Data Downloads Path ===
CRAWLER_DOWNLOADS_PATH: Path = get_resolved_path("CRAWLER_DOWNLOADS_PATH")
FINANCIAL_STATEMENT_PATH: Path = get_resolved_path("FINANCIAL_STATEMENT_PATH")
MONTHLY_REVENUE_REPORT_PATH: Path = get_resolved_path("MONTHLY_REVENUE_REPORT_PATH")
PRICE_DOWNLOADS_PATH: Path = get_resolved_path("PRICE_DOWNLOADS_PATH")
CHIP_DOWNLOADS_PATH: Path = get_resolved_path("CHIP_DOWNLOADS_PATH")
TICK_DOWNLOADS_PATH: Path = get_resolved_path("TICK_DOWNLOADS_PATH")

# === Crawler Downloads Metadata Directory Path ===
DOWNLOADS_METADATA_DIR_PATH: Path = (CRAWLER_DOWNLOADS_PATH / "meta").resolve()
FINANCIAL_STATEMENT_META_DIR_PATH: Path = (
    DOWNLOADS_METADATA_DIR_PATH / "financial_statement"
).resolve()
MONTHLY_REVENUE_REPORT_META_DIR_PATH: Path = (
    DOWNLOADS_METADATA_DIR_PATH / "monthly_revenue_report"
).resolve()


# === Certs.cer ===
CERTS_DIR_PATH: Path = get_resolved_path("CERTS_DIR_PATH")
CERTS_FILE_NAME: str = os.getenv("CERTS_FILE_NAME")
CERTS_FILE_PATH: Path = (CERTS_DIR_PATH / CERTS_FILE_NAME).resolve()


# === Tick Metadata Directory Path ===
DB_METADATA_DIR_PATH: Path = get_resolved_path("DB_METADATA_DIR_PATH")
TICK_METADATA_NAME: str = os.getenv("TICK_METADATA_NAME")
TICK_METADATA_PATH: Path = (DB_METADATA_DIR_PATH / TICK_METADATA_NAME).resolve()


# === Database Files Full Paths ===
CHIP_DB_NAME: str = os.getenv("CHIP_DB_NAME", "chip.db")
TICK_DB_NAME: str = os.getenv("TICK_DB_NAME", "tickDB")
DB_NAME: str = os.getenv("DB_NAME", "data.db")

CHIP_DB_PATH: Path = (DATABASE_DIR_PATH / CHIP_DB_NAME).resolve()
TICK_DB_PATH: str = f"{os.getenv('DDB_PATH')}{TICK_DB_NAME}"
DB_PATH: Path = (DATABASE_DIR_PATH / DB_NAME).resolve()


# === Table names ===
PRICE_TABLE_NAME: str = os.getenv("PRICE_TABLE_NAME", "price")
CHIP_TABLE_NAME: str = os.getenv("CHIP_TABLE_NAME", "chip")
TICK_TABLE_NAME: str = os.getenv("TICK_TABLE_NAME", "tick")
TICK_METADATA_TABLE_NAME: str = os.getenv("TICK_METADATA_TABLE_NAME", "tick_metadata")


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
