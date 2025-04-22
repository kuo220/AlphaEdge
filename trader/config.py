from pathlib import Path
from typing import List
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


# === General Directory Path ===
DATABASE_DIR_PATH = get_resolved_path("DATABASE_DIR_PATH")
BACKTEST_RESULT_DIR_PATH = get_resolved_path("BACKTEST_RESULT_DIR_PATH")


# === Crawl Data Downloads Path ===
CRAWLER_DOWNLOADS_PATH = get_resolved_path("CRAWLER_DOWNLOADS_PATH")
CHIP_DOWNLOADS_PATH = get_resolved_path("CHIP_DOWNLOADS_PATH")
TICK_DOWNLOADS_PATH = get_resolved_path("TICK_DOWNLOADS_PATH")


# === Metadata Directory Path ===
METADATA_DIR_PATH = get_resolved_path("METADATA_DIR_PATH")
TICK_METADATA_NAME= os.getenv("TICK_METADATA_NAME")
TICK_METADATA_PATH = (METADATA_DIR_PATH / TICK_METADATA_NAME).resolve()


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
TICK_METADATA_TABLE_NAME=os.getenv("TICK_METADATA_TABLE_NAME", "tick_metadata")


# === DolphinDB server setting ===
DDB_PATH = os.getenv("DDB_PATH")
DDB_HOST = os.getenv("DDB_HOST")
DDB_PORT = int(os.getenv("DDB_PORT"))
DDB_USER = os.getenv("DDB_USER")
DDB_PASSWORD = os.getenv("DDB_PASSWORD")


# === Shioaji API ===
API_KEY = os.getenv("API_KEY")
API_SECRET_KEY = os.getenv("API_SECRET_KEY")


# === API list for crawling tick data ===
class ShioajiAPI:
    """ Contains Shioaji API_KEY and API_SECRET_KEY """
    
    def __init__(self, api_key: str, api_secret_key: str):
        self.api_key = api_key
        self.api_secret_key = api_secret_key
        
API_LIST: List[ShioajiAPI] = []

# Add API from 11 ~ 17 and add API_1 (Mine)
for num in range(8):
    if num == 0:
        api = ShioajiAPI(os.getenv(f"API_KEY_{num + 1}"), os.getenv(f"API_SECRET_KEY_{num + 1}"))
        continue
    api = ShioajiAPI(os.getenv(f"API_KEY_{num + 10}"), os.getenv(f"API_SECRET_KEY_{num + 10}"))
    API_LIST.append(api)