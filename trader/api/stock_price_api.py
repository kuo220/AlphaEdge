import datetime
import sqlite3
import pandas as pd
from loguru import logger

from trader.api.base import BaseDataAPI
from trader.config import DB_PATH, PRICE_TABLE_NAME, LOGS_DIR_PATH


class StockPriceAPI(BaseDataAPI):
    """Stock Price API"""

    def __init__(self):
        self.conn: sqlite3.Connection = None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        # Set Up Connection
        self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/stock_price_api.log")

    def get(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得所有股票的 Price"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {PRICE_TABLE_NAME} WHERE date BETWEEN '{start_date}' AND '{end_date}'
        """
        df: pd.DataFrame = pd.read_sql_query(query, self.conn)
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
        SELECT * FROM {PRICE_TABLE_NAME} WHERE stock_id = '{stock_id}' AND date BETWEEN '{start_date}' AND '{end_date}'
        """
        df: pd.DataFrame = pd.read_sql_query(query, self.conn)
        return df