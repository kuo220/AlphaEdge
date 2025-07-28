import datetime
import random
import time
import sqlite3
from loguru import logger
import pandas as pd
from typing import List, Optional

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.stock_chip_crawler import StockChipCrawler
from trader.pipeline.cleaners.stock_chip_cleaner import StockChipCleaner
from trader.pipeline.loaders.stock_chip_loader import StockChipLoader
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils import TimeUtils
from trader.config import DB_PATH, CHIP_TABLE_NAME, LOGS_DIR_PATH


"""
三大法人爬蟲資料時間表：
1. TWSE
    - TWSE: 2012/5/2 開始提供（這邊從 2014/12/1 開始爬）
    - TWSE 改制時間: 2014/12/1, 2017/12/18
2. TPEX
    - TPEX: 2007/4/20 開始提供 (這邊從 2014/12/1 開始爬)
    - TPEX 改制時間: 2018/1/15
"""


class StockChipUpdater(BaseDataUpdater):
    """Stock Chip Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # ETL
        self.crawler: StockChipCrawler = StockChipCrawler()
        self.cleaner: StockChipCleaner = StockChipCleaner()
        self.loader: StockChipLoader = StockChipLoader()

        # Table latest day
        self.table_latest_date: Optional[datetime.date] = None

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_chip.log")

    def update(
        self,
        start_date: datetime.date,
        end_date: datetime.date = datetime.date.today(),
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Institutional Investors Data...")

        # Step 1: Crawl
        # 取得最近更新的日期
        start_date = self.get_table_latest_date(default_date=start_date)
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
                    logger.warning(f"Cleaned TWSE dataframe empty on {date}.")

            if tpex_df is not None and not tpex_df.empty:
                cleaned_tpex_df: pd.DataFrame = self.cleaner.clean_tpex_chip(
                    tpex_df, date
                )
                if cleaned_tpex_df is None or cleaned_tpex_df.empty:
                    logger.warning(f"Cleaned TPEX dataframe empty on {date}.")

            file_cnt += 1

            if file_cnt == 100:
                logger.info("Sleep 2 minutes...")
                file_cnt = 0
                time.sleep(120)
            else:
                delay = random.randint(1, 5)
                time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(remove_files=False)

    def get_table_latest_date(self, default_date: datetime.date) -> datetime.date:
        """Get table latest date"""

        latest_date: Optional[str] = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=CHIP_TABLE_NAME, col_name="date"
        )
        self.table_latest_date = (
            datetime.datetime.strptime(latest_date, "%Y-%m-%d").date()
            if latest_date is not None
            else default_date
        )
        return self.table_latest_date
