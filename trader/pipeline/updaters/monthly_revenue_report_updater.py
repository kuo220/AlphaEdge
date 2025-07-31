import time
import random
import sqlite3
import pandas as pd
from loguru import logger
from pathlib import Path
from typing import List, Tuple, Optional

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
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils import TimeUtils
from trader.config import (
    DB_PATH,
    LOGS_DIR_PATH,
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_TABLE_NAME,
)


"""
資料區間
- 上市: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
- 上櫃: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
"""


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

        # Data Directory
        self.mmr_dir: Path = MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_monthly_revenue_report.log")

    def update(
        self,
        start_year: int,
        end_year: int,
        start_month: int,
        end_month: int,
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Monthly Revenue Report Data...")

        # Step 1: Crawl
        # 取得要開始更新的年份、月份
        start_year, start_month = self.get_actual_update_start_year_month(
            default_year=start_year,
            default_month=start_month,
        )

        logger.info(f"Latest data date in database: {start_year}/{start_month}")
        # Set Up Update Period
        years: List[int] = TimeUtils.generate_year_range(start_year, end_year)
        months: List[int] = TimeUtils.generate_month_range(start_month, end_month)
        file_cnt: int = 0

        for year in years:
            for month in months:
                logger.info(f"* {year}/{month}")
                df_list: Optional[List[pd.DataFrame]] = self.crawler.crawl(year, month)

                # Step 2: Clean
                if df_list is not None and df_list:
                    cleaned_df: pd.DataFrame = self.cleaner.clean_monthly_revenue(
                        df_list, year, month
                    )

                    if cleaned_df is None or cleaned_df.empty:
                        logger.warning(
                            f"Cleaned monthly revenue report dataframe empty on {year}/{month}."
                        )
                        continue

                file_cnt += 1
                if file_cnt == 10:
                    logger.info("Sleep 30 seconds...")
                    file_cnt = 0
                    time.sleep(30)
                else:
                    delay = random.randint(1, 5)
                    time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(remove_files=False)

        # 更新後重新取得最新年月
        table_latest_year: Optional[int] = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=MONTHLY_REVENUE_TABLE_NAME, col_name="year"
        )
        table_latest_month: Optional[int] = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=MONTHLY_REVENUE_TABLE_NAME, col_name="month"
        )

        if table_latest_year and table_latest_month:
            logger.info(
                f"* Monthly revenue data updated. Latest available date: {table_latest_year}/{table_latest_month}"
            )
        else:
            logger.warning("* No new monthly revenue data was updated.")

    def get_actual_update_start_year_month(
        self,
        default_year: int = 2025,
        default_month: int = 1,
    ) -> Tuple[int, int]:
        """Return the next (year, month) to update. If no data, return default."""

        latest_year: Optional[int] = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=MONTHLY_REVENUE_TABLE_NAME, col_name="year"
        )
        latest_month: Optional[int] = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=MONTHLY_REVENUE_TABLE_NAME, col_name="month"
        )

        if latest_year is not None and latest_month is not None:
            year = int(latest_year)
            month = int(latest_month)
            # 處理進位（跨年）
            if month == 12:
                return year + 1, 1
            else:
                return year, month + 1
        else:
            return default_year, default_month
