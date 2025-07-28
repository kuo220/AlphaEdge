import shutil
import datetime
import sqlite3
from loguru import logger
from pathlib import Path
from typing import List, Optional
import pandas as pd

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.monthly_revenue_report_crawler import (
    MonthlyRevenueReportCrawler,
)
from trader.pipeline.cleaners.monthly_revenue_report_cleaner import (
    MonthlyRevenueReportCleaner,
)
from trader.pipeline.loaders.monthly_revenue_report_loader import (
    MonthlyRevenueReportLoader,
)
from trader.pipeline.utils import DataType
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils import TimeUtils
from trader.config import (
    DB_PATH,
    LOGS_DIR_PATH,
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
    MONTHLY_REVENUE_TABLE_NAME,
)


class MonthlyRevenueReportUpdater(BaseDataUpdater):
    """TWSE & TPEX Monthly Revenue Report Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # ETL
        self.crawler: MonthlyRevenueReportCrawler = MonthlyRevenueReportCrawler()
        self.cleaner: MonthlyRevenueReportCleaner = MonthlyRevenueReportCleaner()
        self.loader: MonthlyRevenueReportLoader = MonthlyRevenueReportLoader()

        # Table latest day
        self.table_latest_date: Optional[datetime.date] = None

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_monthly_revenue_report.log")

    def update(
        self, start_year: int, end_year: int, start_month: int, end_month: int
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Monthly Revenue Report Data...")

        # Step 1: Crawl
        # 取得最近更新的日期
        start_date = self.get_table_latest_date(default_date=start_date)
        logger.info(f"Latest data date in database: {start_date}")
        # Set Up Update Period
        dates: List[datetime.date] = TimeUtils.generate_date_range(start_date, end_date)
        file_cnt: int = 0
