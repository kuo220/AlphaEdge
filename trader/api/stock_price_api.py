import datetime
import sqlite3
from typing import Optional

import pandas as pd
from loguru import logger

from trader.api.base import BaseDataAPI
from trader.config import DB_PATH, PRICE_TABLE_NAME
from trader.utils.log_manager import LogManager

"""Stock Price API: query SQLite price table"""


class StockPriceAPI(BaseDataAPI):
    """Stock Price API"""

    def __init__(self):
        self.conn: Optional[sqlite3.Connection] = None

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Data API"""

        self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
        LogManager.setup_logger("stock_price_api.log")

    def get(self, date: datetime.date) -> pd.DataFrame:
        """取得所有股票指定日期的 Price"""

        query: str = f"""
        SELECT * FROM {PRICE_TABLE_NAME}
        WHERE date = ?
        """
        return pd.read_sql_query(
            query,
            self.conn,
            params=(date,),
        )

    def get_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得所有股票指定日期範圍的 Price"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {PRICE_TABLE_NAME}
        WHERE date BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(start_date, end_date),
        )
        return df

    def get_stock_price(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定個股的 Price"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {PRICE_TABLE_NAME}
        WHERE stock_id = ?
        AND date BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(stock_id, start_date, end_date),
        )
        return df
