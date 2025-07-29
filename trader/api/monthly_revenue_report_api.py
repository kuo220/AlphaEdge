import shutil
import sqlite3
from loguru import logger
from pathlib import Path
from typing import List
import pandas as pd

from trader.api.base import BaseDataAPI
from trader.pipeline.utils import DataType
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.config import (
    DB_PATH,
    LOGS_DIR_PATH,
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
    MONTHLY_REVENUE_TABLE_NAME,
)


class MonthlyRevenueReportAPI(BaseDataAPI):
    """Monthly Revenue Report Data API"""

    def __init__(self):
        self.conn: sqlite3.Connection = None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        # Set Up Connection
        self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/monthly_revenue_report_api.log")