import random
import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from trader.config import (
    DB_PATH,
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_TABLE_NAME,
)
from trader.utils.log_manager import LogManager
from trader.pipeline.cleaners.monthly_revenue_report_cleaner import (
    MonthlyRevenueReportCleaner,
)
from trader.pipeline.crawlers.monthly_revenue_report_crawler import (
    MonthlyRevenueReportCrawler,
)
from trader.pipeline.loaders.monthly_revenue_report_loader import (
    MonthlyRevenueReportLoader,
)
from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils import TimeUtils

"""
資料區間
- 上市: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
- 上櫃: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
"""


class MonthlyRevenueReportUpdater(BaseDataUpdater):
    """TWSE & TPEX Monthly Revenue Report Updater"""

    BATCH_SLEEP_EVERY_N_FILES: int = 10
    BATCH_SLEEP_DURATION_SECONDS: int = 30
    BATCH_RANDOM_DELAY_MIN: int = 1
    BATCH_RANDOM_DELAY_MAX: int = 5

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: MonthlyRevenueReportCrawler = MonthlyRevenueReportCrawler()
        self.cleaner: MonthlyRevenueReportCleaner = MonthlyRevenueReportCleaner()
        self.loader: MonthlyRevenueReportLoader = MonthlyRevenueReportLoader()

        # Data Directory
        self.mmr_dir: Path = MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        LogManager.setup_logger("update_monthly_revenue_report.log")

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
        start_year: int
        start_month: int
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
                if df_list is None or not df_list:
                    continue

                cleaned_df: pd.DataFrame = self.cleaner.clean_monthly_revenue(
                    df_list, year, month
                )

                if cleaned_df is None or cleaned_df.empty:
                    logger.warning(
                        f"Cleaned monthly revenue report dataframe empty on {year}/{month}"
                    )
                    continue

                file_cnt += 1
                if file_cnt == self.BATCH_SLEEP_EVERY_N_FILES:
                    logger.info("Sleep 30 seconds...")
                    file_cnt = 0
                    time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
                else:
                    delay: int = random.randint(
                        self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                    )
                    time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(remove_files=False)

        # 更新後重新取得最新年月
        latest_year: Optional[int]
        latest_month: Optional[int]
        latest_year, latest_month = SQLiteUtils.get_max_secondary_value_by_primary(
            conn=self.conn,
            table_name=MONTHLY_REVENUE_TABLE_NAME,
            primary_col="year",
            secondary_col="month",
            default_primary_value=start_year,
            default_secondary_value=start_month,
        )

        if latest_year and latest_month:
            logger.info(
                f"Monthly revenue data updated. Latest available date: {latest_year}/{latest_month}"
            )
        else:
            logger.warning("No new monthly revenue data was updated")

    def get_actual_update_start_year_month(
        self,
        default_year: int = 2025,
        default_month: int = 1,
    ) -> Tuple[int, int]:
        """回傳下一筆應更新的 (year, month)，若無資料則回傳預設值"""

        # Step 1: 先取得資料表中最新的 year
        try:
            latest_year: Optional[int]
            latest_month: Optional[int]
            latest_year, latest_month = SQLiteUtils.get_max_secondary_value_by_primary(
                conn=self.conn,
                table_name=MONTHLY_REVENUE_TABLE_NAME,
                primary_col="year",
                secondary_col="month",
                default_primary_value=default_year,
                default_secondary_value=default_month,
            )
        except Exception as e:
            logger.error(f"Failed to get latest (year, month): {e}")
            return default_year, default_month

        # Step 2: 計算下一個月份（處理進位）
        if latest_month == 12:
            return latest_year + 1, 1
        else:
            return latest_year, latest_month + 1
