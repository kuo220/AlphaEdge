import shutil
import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from trader.api.base import BaseDataAPI
from trader.config import (
    DB_PATH,
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
    MONTHLY_REVENUE_TABLE_NAME,
)
from trader.utils.log_manager import LogManager
from trader.pipeline.utils import DataType
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils.sqlite_utils import SQLiteUtils


class MonthlyRevenueReportAPI(BaseDataAPI):
    """Monthly Revenue Report Data API"""

    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        # Set Up Connection
        self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        LogManager.setup_logger("monthly_revenue_report_api.log")

    def get(
        self,
        year: int,
        month: int,
    ) -> pd.DataFrame:
        """取得指定年度跟季度的月營收報表"""

        query: str = f"""
        SELECT * FROM {MONTHLY_REVENUE_TABLE_NAME}
        WHERE year = ?
        AND month = ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(year, month),
        )
        return df

    def get_range(
        self,
        start_year: int,
        end_year: int,
        start_month: int,
        end_month: int,
    ) -> pd.DataFrame:
        """取得指定年度跟季度的範圍內的財報"""

        query: str = f"""
        SELECT * FROM {MONTHLY_REVENUE_TABLE_NAME}
        WHERE year BETWEEN ? AND ?
        AND month BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(start_year, end_year, start_month, end_month),
        )
        return df
