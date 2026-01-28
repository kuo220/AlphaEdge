import sqlite3
from typing import Optional

import pandas as pd
from loguru import logger

from trader.api.base import BaseDataAPI
from trader.config import DB_PATH
from trader.utils.log_manager import LogManager


class FinancialStatementAPI(BaseDataAPI):
    """Financial Statement Data API"""

    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        # Set Up Connection
        self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        LogManager.setup_logger("financial_statement_api.log")

    def get(
        self,
        table_name: str,
        year: int,
        season: int,
    ) -> pd.DataFrame:
        """取得指定年度跟季度的財報"""

        query: str = f"""
        SELECT * FROM {table_name}
        WHERE year = ? AND season = ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(year, season),
        )
        return df

    def get_range(
        self,
        table_name: str,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
    ) -> pd.DataFrame:
        """取得指定年度跟季度的範圍內的財報"""

        query: str = f"""
        SELECT * FROM {table_name}
        WHERE year BETWEEN ? AND ?
        AND season BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(start_year, end_year, start_season, end_season),
        )
        return df
