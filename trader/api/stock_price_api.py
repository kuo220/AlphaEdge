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
        pass
