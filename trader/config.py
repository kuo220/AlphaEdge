from pathlib import Path
from dotenv import load_dotenv
import os


# Load environment variables from .env file
load_dotenv()

# Root Directory
BASE_DIR = Path(__file__).resolve().parent


# === Helper: Load and resolve path from .env ===
def get_resolved_path(env_key: str, default: str=None) -> Path:
    value = os.getenv(env_key, default)
    if value is None:
        raise ValueError(f"Missing required environment variable: {env_key}")
    return (BASE_DIR / value).resolve()


# === Absolute paths to directories ===
CRAWLER_DOWNLOADS_PATH = get_resolved_path("CRAWLER_DOWNLOADS_PATH")
CHIP_DOWNLOADS_PATH = get_resolved_path("CHIP_DOWNLOADS_PATH")
DATABASE_DIR_PATH = get_resolved_path("DATABASE_DIR_PATH")
BACKTEST_RESULT_DIR_PATH = get_resolved_path("BACKTEST_RESULT_DIR_PATH")


# === Full paths to database files ===
CHIP_DB_NAME = os.getenv("CHIP_DB_NAME", "chip.db")
TICK_DB_NAME = os.getenv("TICK_DB_NAME", "tickDB")
QUANTX_DB_NAME = os.getenv("QUANTX_DB_NAME", "data.db")

CHIP_DB_PATH = (DATABASE_DIR_PATH / CHIP_DB_NAME).resolve()
TICK_DB_PATH = f"{os.getenv('DDB_PATH')}{TICK_DB_NAME}"
QUANTX_DB_PATH = (DATABASE_DIR_PATH / QUANTX_DB_NAME).resolve()


# === Table names ===
CHIP_TABLE_NAME = os.getenv("CHIP_TABLE_NAME", "chip")
TICK_TABLE_NAME = os.getenv("TICK_TABLE_NAME", "tick")


# === DolphinDB server setting ===
DDB_HOST = os.getenv("DDB_HOST")
DDB_PORT = int(os.getenv("DDB_PORT"))
DDB_USER = os.getenv("DDB_USER")
DDB_PASSWORD = os.getenv("DDB_PASSWORD")


# === Shioaji API ===
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")