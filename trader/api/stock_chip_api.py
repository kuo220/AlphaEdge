import datetime
import os
import sqlite3
import sys
from pathlib import Path
import pandas as pd

from trader.api.base import BaseDataAPI
from trader.config import CHIP_TABLE_NAME, DB_PATH


class StockChipAPI(BaseDataAPI):
    """Institutional investors chip API"""

    def __init__(self):
        self.conn: sqlite3.Connection = None

        self.setup()

    def setup(self):
        """Set Up the Config of Cleaner"""

        self.conn = sqlite3.connect(DB_PATH)

    def get(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得所有股票的三大法人籌碼"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {CHIP_TABLE_NAME} WHERE date BETWEEN '{start_date}' AND '{end_date}'
        """
        df: pd.DataFrame = pd.read_sql_query(query, self.conn)
        return df

    def get_stock_chip(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定個股的三大法人籌碼"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {CHIP_TABLE_NAME} WHERE stock_id = '{stock_id}' AND date BETWEEN '{start_date}' AND '{end_date}'
        """
        df: pd.DataFrame = pd.read_sql_query(query, self.conn)
        return df

    def get_net_chip(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得所有股票的三大法人淨買賣超"""

        if start_date > end_date:
            return pd.DataFrame()

        df: pd.DataFrame = self.get(start_date, end_date)
        df = df.loc[
            :,
            (
                "date",
                "stock_id",
                "證券名稱",
                "外資買賣超股數",
                "投信買賣超股數",
                "自營商買賣超股數",
            ),
        ]
        return df

    def get_stock_net_chip(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定個股的三大法人淨買賣超"""

        if start_date > end_date:
            return pd.DataFrame()

        df: pd.DataFrame = self.get_stock_chip(stock_id, start_date, end_date)
        df = df.loc[
            :,
            (
                "date",
                "stock_id",
                "證券名稱",
                "外資買賣超股數",
                "投信買賣超股數",
                "自營商買賣超股數",
            ),
        ]
        return df
