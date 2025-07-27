import shutil
import sqlite3
from loguru import logger
from pathlib import Path
from typing import List
import pandas as pd

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.utils import DataType
from trader.pipeline.utils.data_utils import DataUtils
from trader.config import (
    DB_PATH,
    MONTHLY_REVENUE_TABLE_NAME,
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
)


class MonthlyRevenueReportUpdater(BaseDataUpdater):
    """TWSE & TPEX Monthly Revenue Report Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None


    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""
        pass


    def update(self, *args, **kwargs) -> None:
        """Update the Database"""
        pass