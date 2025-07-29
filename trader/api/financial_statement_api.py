import shutil
import sqlite3
from loguru import logger
import pandas as pd
from pathlib import Path
from typing import List

from trader.api.base import BaseDataAPI
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.pipeline.utils import FinancialStatementType
from trader.config import (
    DB_PATH,
    LOGS_DIR_PATH,
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_META_DIR_PATH,
)


class FinancialStatement(BaseDataAPI):
    """Financial Statement Data API"""

    def __init__(self):
        self.conn: sqlite3.Connection = None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        # Set Up Connection
        self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/financial_statement_api.log")

    def get(self, table_name: str, start_year: int, end_year: int, start_season: int, end_season: int):
        """取得財報"""