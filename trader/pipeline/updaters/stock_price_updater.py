import datetime
import random
import time
import sqlite3
from loguru import logger
import pandas as pd
from typing import Optional

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.stock_price_crawler import StockPriceCrawler
from trader.pipeline.cleaners.stock_price_cleaner import StockPriceCleaner
from trader.pipeline.loaders.stock_price_loader import StockPriceLoader
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.config import DB_PATH, PRICE_TABLE_NAME, LOGS_DIR_PATH


"""
TWSE 網站提供資料日期：
1. 2004/2/11 ~ present

TPEX 網站提供資料日期：
1. 上櫃資料從 96/7/2 以後才提供
2. 從 109/4/30 開始後 csv 檔的 column 不一樣
"""


class StockPriceUpdater(BaseDataUpdater):
    """Stock Price Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # ETL
        self.crawler: StockPriceCrawler = StockPriceCrawler()
        self.cleaner: StockPriceCleaner = StockPriceCleaner()
        self.loader: StockPriceLoader = StockPriceLoader()

        # Table latest day
        self.table_latest_date: Optional[datetime.date] = None

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        self.table_latest_date = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=PRICE_TABLE_NAME, col_name="date"
        )

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_price.log")

    def update(
        self,
        start_date: datetime.date = None,
        end_date: datetime.date = datetime.date.today(),
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Price data...")
        if start_date is None:
            if self.table_latest_date is None:
                raise ValueError("No existing data found. Please specify start_date.")
            start_date = self.table_latest_date

        # Step 1: Crawl + Clean
        cur_date: datetime.date = start_date
        crawl_cnt: int = 0

        while cur_date <= end_date:
            logger.info(cur_date.strftime("%Y/%m/%d"))
            twse_df: Optional[pd.DataFrame] = self.crawler.crawl_twse_price(cur_date)
            tpex_df: Optional[pd.DataFrame] = self.crawler.crawl_tpex_price(cur_date)

            # Step 2: Clean
            if twse_df is not None and not twse_df.empty:
                cleaned_twse_df: pd.DataFrame = self.cleaner.clean_twse_price(
                    twse_df, cur_date
                )
                if cleaned_twse_df is None or cleaned_twse_df.empty:
                    logger.warning(f"Cleaned TWSE dataframe empty on {cur_date}.")

            if tpex_df is not None and not tpex_df.empty:
                cleaned_tpex_df: pd.DataFrame = self.cleaner.clean_tpex_price(
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
