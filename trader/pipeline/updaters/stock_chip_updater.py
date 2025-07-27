import datetime
import random
import time
import sqlite3
from loguru import logger
import pandas as pd
from typing import Optional

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.stock_chip_crawler import StockChipCrawler
from trader.pipeline.cleaners.stock_chip_cleaner import StockChipCleaner
from trader.pipeline.loaders.stock_chip_loader import StockChipLoader
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
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

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        self.table_latest_date = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=CHIP_TABLE_NAME, col_name="date"
        )

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_chip.log")

    def update(
        self,
        start_date: datetime.date = None,
        end_date: datetime.date = datetime.date.today(),
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX institutional investors data...")
        if start_date is None:
            if self.table_latest_date is None:
                raise ValueError("No existing data found. Please specify start_date.")
            start_date = self.table_latest_date

        # Step 1: Crawl + Clean
        cur_date: datetime.date = start_date
        crawl_cnt: int = 0

        while cur_date <= end_date:
            logger.info(cur_date.strftime("%Y/%m/%d"))
            twse_df: Optional[pd.DataFrame] = self.crawler.crawl_twse_chip(cur_date)
            tpex_df: Optional[pd.DataFrame] = self.crawler.crawl_tpex_chip(cur_date)

            # Step 2: Clean
            if twse_df is not None and not twse_df.empty:
                cleaned_twse_df: pd.DataFrame = self.cleaner.clean_twse_chip(
                    twse_df, cur_date
                )
                if cleaned_twse_df is None or cleaned_twse_df.empty:
                    logger.warning(f"Cleaned TWSE dataframe empty on {cur_date}.")

            if tpex_df is not None and not tpex_df.empty:
                cleaned_tpex_df: pd.DataFrame = self.cleaner.clean_tpex_chip(
                    tpex_df, cur_date
                )
                if cleaned_tpex_df is None or cleaned_tpex_df.empty:
                    logger.warning(f"Cleaned TPEX dataframe empty on {cur_date}.")

            cur_date += datetime.timedelta(days=1)
            crawl_cnt += 1

            if crawl_cnt == 100:
                logger.info("Sleep 2 minutes...")
                crawl_cnt = 0
                time.sleep(120)
            else:
                delay = random.randint(1, 5)
                time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(remove_files=False)
