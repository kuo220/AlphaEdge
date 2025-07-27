import time
import random
import datetime
import sqlite3
import pandas as pd
import requests
from io import StringIO
from pathlib import Path
from loguru import logger
from typing import List, Dict, Tuple, Optional

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.financial_statement_crawler import (
    FinancialStatementCrawler,
)
from trader.pipeline.cleaners.financial_statement_cleaner import (
    FinancialStatementCleaner,
)
from trader.pipeline.loaders.financial_statement_loader import FinancialStatementLoader
from trader.pipeline.crawlers.utils.payload import Payload
from trader.pipeline.utils import (
    URLManager,
    MarketType,
    FinancialStatementType,
)
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import (
    DB_PATH,
    LOGS_DIR_PATH,
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_META_DIR_PATH,
    BALANCE_SHEET_TABLE_NAME,
    COMPREHENSIVE_INCOME_TABLE_NAME,
    CASH_FLOW_TABLE_NAME,
    EQUITY_CHANGE_TABLE_NAME,
)


"""
* Crawl Balance Sheet (資產負債表)
資料區間（但是只有 102 年以後才可以爬）
上市: 民國 78 (1989) 年 ~ present
上櫃: 民國 82 (1993) 年 ~ present

* Crawl Statement of Comprehensive Income (綜合損益表)
資料區間（但是只有 102 年以後才可以爬）
上市: 民國 77 (1988) 年 ~ present
上櫃: 民國 82 (1993) 年 ~ present

* Crawl Cash Flow Statement (現金流量表)
資料區間
上市: 民國 102 (2013) 年 ~ present
上櫃: 民國 102 (2013) 年 ~ present

* Crawl Statement of Changes in Equity (權益變動表)
資料區間
上市: 民國 102 (2013) 年 ~ present
上櫃: 民國 102 (2013) 年 ~ present
"""


class FinancialStatementUpdater(BaseDataUpdater):
    """Financial Statement Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # ETL
        self.crawler: FinancialStatementCrawler = FinancialStatementCrawler()
        self.cleaner: FinancialStatementCleaner = FinancialStatementCleaner()
        self.loader: FinancialStatementLoader = FinancialStatementLoader()

        # Table latest year & season
        self.table_latest_year: Optional[int] = None
        self.table_latest_season: Optional[int] = None

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

    def update(self) -> None:
        """Update the Database"""
        pass

    def update_balance_sheet(self) -> None:
        """Update Balance Sheet"""

        logger.info("* Start Updating TWSE & TPEX Price data...")

    def get_table_latest_year(self, table_name: str) -> Optional[Tuple[int, int]]:
        """取得 Financial Statement 中的最新年份跟季度"""

        if self.conn == None:
            return None

        query: str = f"SELECT year FROM {table_name} ORDER BY year DESC LIMIT 1"
        cursor: sqlite3.Cursor = conn.execute(query)
        result: Optional[Tuple[Any]] = cursor.fetchone()
