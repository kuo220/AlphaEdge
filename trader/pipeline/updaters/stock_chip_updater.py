import datetime
import random
import sqlite3
import time
from typing import List, Optional

import pandas as pd
from loguru import logger

from trader.config import CHIP_TABLE_NAME, DB_PATH
from trader.utils.log_manager import LogManager
from trader.pipeline.cleaners.stock_chip_cleaner import StockChipCleaner
from trader.pipeline.crawlers.stock_chip_crawler import StockChipCrawler
from trader.pipeline.loaders.stock_chip_loader import StockChipLoader
from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils import TimeUtils

"""
三大法人爬蟲資料時間表：
1. TWSE
    - TWSE: 2012/5/2 開始提供
    - TWSE 改制時間: 2014/12/1, 2017/12/18
2. TPEX
    - TPEX: 2007/4/20 開始提供
    - TPEX 改制時間: 2018/1/15
"""


class StockChipUpdater(BaseDataUpdater):
    """Stock Chip Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: StockChipCrawler = StockChipCrawler()
        self.cleaner: StockChipCleaner = StockChipCleaner()
        self.loader: StockChipLoader = StockChipLoader()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
        LogManager.setup_logger("update_chip.log")

    def update(
        self,
        start_date: datetime.date,
        end_date: datetime.date = datetime.date.today(),
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Chip Data...")

        # Step 1: Crawl
        # 取得要開始更新的日期
        start_date: datetime.date = self.get_actual_update_start_date(
            default_date=start_date
        )
        logger.info(f"Latest data date in database: {start_date}")
        # Set Up Update Period
        dates: List[datetime.date] = TimeUtils.generate_date_range(start_date, end_date)
        file_cnt: int = 0

        for date in dates:
            logger.info(date.strftime("%Y/%m/%d"))
            twse_df: Optional[pd.DataFrame] = self.crawler.crawl_twse_chip(date)
            tpex_df: Optional[pd.DataFrame] = self.crawler.crawl_tpex_chip(date)

            # Step 2: Clean
            if twse_df is not None and not twse_df.empty:
                cleaned_twse_df: pd.DataFrame = self.cleaner.clean_twse_chip(
                    twse_df, date
                )
                if cleaned_twse_df is None or cleaned_twse_df.empty:
                    logger.warning(f"Cleaned TWSE dataframe empty on {date}")

            if tpex_df is not None and not tpex_df.empty:
                cleaned_tpex_df: pd.DataFrame = self.cleaner.clean_tpex_chip(
                    tpex_df, date
                )
                if cleaned_tpex_df is None or cleaned_tpex_df.empty:
                    logger.warning(f"Cleaned TPEX dataframe empty on {date}")

            file_cnt += 1

            if file_cnt == 100:
                logger.info("Sleep 2 minutes...")
                file_cnt = 0
                time.sleep(120)
            else:
                delay: int = random.randint(1, 5)
                time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(remove_files=False)

        # 更新後重新取得Table最新的日期
        table_latest_date: str = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=CHIP_TABLE_NAME,
            col_name="date",
        )
        if table_latest_date:
            logger.info(
                f"Stock chip data updated. Latest available date: {table_latest_date}"
            )
        else:
            logger.warning("No new stock chip data was updated")

    def get_actual_update_start_date(
        self, default_date: datetime.date
    ) -> datetime.date:
        """Get the actual start date for updating (1 day after latest date in table, or default_date)"""

        latest_date: Optional[str] = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=CHIP_TABLE_NAME,
            col_name="date",
        )

        if latest_date is not None:
            table_latest_date: datetime.date = datetime.datetime.strptime(
                latest_date,
                "%Y-%m-%d",
            ).date()
            return table_latest_date + datetime.timedelta(days=1)
        else:
            return default_date
