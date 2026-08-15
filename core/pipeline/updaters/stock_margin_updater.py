import datetime
import random
import sqlite3
import time
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import DB_PATH, MARGIN_TABLE_NAME
from core.pipeline.cleaners.stock_margin_cleaner import StockMarginCleaner
from core.pipeline.crawlers.stock_margin_crawler import StockMarginCrawler
from core.pipeline.loaders.stock_margin_loader import StockMarginLoader
from core.pipeline.updaters.base import BaseDataUpdater
from core.pipeline.utils.sqlite_utils import SQLiteUtils
from core.utils import TimeUtils
from core.utils.log_manager import LogManager

"""
信用交易（融資融券餘額）爬蟲資料時間表：
1. TWSE
    - MI_MARGN（selectType=ALL）：官方自民國 90/01/01（2001/01/01）起提供，
      本專案實測 2013/1/1 起可取得且表格結構未再改制
2. TPEX
    - 上櫃融資融券餘額：官方自民國 96/01（2007/01）起提供，
      本專案實測 2013/1/1 起可取得且表格結構未再改制
"""


# 週六的 weekday() 值；用於濾掉必不開市的日子
SATURDAY: int = 5


class StockMarginUpdater(BaseDataUpdater):
    """Stock Margin Updater"""

    BATCH_SLEEP_EVERY_N_FILES: int = 100
    BATCH_SLEEP_DURATION_SECONDS: int = 120
    BATCH_RANDOM_DELAY_MIN: int = 1
    BATCH_RANDOM_DELAY_MAX: int = 5

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: StockMarginCrawler = StockMarginCrawler()
        self.cleaner: StockMarginCleaner = StockMarginCleaner()
        self.loader: StockMarginLoader = StockMarginLoader()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
        LogManager.setup_logger("update_margin.log")

    def update(
        self,
        start_date: datetime.date,
        end_date: datetime.date = datetime.date.today(),
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Margin Data...")

        # Step 1: Crawl
        # 取得要開始更新的日期
        start_date: datetime.date = self.get_actual_update_start_date(
            default_date=start_date
        )
        logger.info(f"Latest data date in database: {start_date}")
        # Set Up Update Period
        #
        # **先濾掉週末**：台股週六日必不開市，送出請求只會換回「is a Holiday」，
        # 但一樣要付兩次 HTTP ＋ 節流時間。2013 起的回補約 4,975 個日曆天中有
        # 1,420 天是週末，濾掉可省下約三成的執行時間。
        # 國定假日無法純靠日曆判斷，仍維持「送出請求後由回應判定」。
        dates: List[datetime.date] = [
            date
            for date in TimeUtils.generate_date_range(start_date, end_date)
            if date.weekday() < SATURDAY
        ]
        file_cnt: int = 0

        for date in dates:
            logger.info(date.strftime("%Y/%m/%d"))
            twse_df: Optional[pd.DataFrame] = self.crawler.crawl_twse_margin(date)
            tpex_df: Optional[pd.DataFrame] = self.crawler.crawl_tpex_margin(date)

            # Step 2: Clean
            if twse_df is not None and not twse_df.empty:
                cleaned_twse_df: Optional[pd.DataFrame] = (
                    self.cleaner.clean_twse_margin(twse_df, date)
                )
                if cleaned_twse_df is None or cleaned_twse_df.empty:
                    logger.warning(f"Cleaned TWSE dataframe empty on {date}")

            if tpex_df is not None and not tpex_df.empty:
                cleaned_tpex_df: Optional[pd.DataFrame] = (
                    self.cleaner.clean_tpex_margin(tpex_df, date)
                )
                if cleaned_tpex_df is None or cleaned_tpex_df.empty:
                    logger.warning(f"Cleaned TPEX dataframe empty on {date}")

            file_cnt += 1

            if file_cnt == self.BATCH_SLEEP_EVERY_N_FILES:
                logger.info("Sleep 2 minutes...")
                file_cnt = 0
                time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
            else:
                delay: int = random.randint(
                    self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                )
                time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(remove_files=False)

        # 更新後重新取得Table最新的日期
        table_latest_date: str = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=MARGIN_TABLE_NAME,
            col_name="date",
        )
        if table_latest_date:
            logger.info(
                f"Stock margin data updated. Latest available date: {table_latest_date}"
            )
        else:
            logger.warning("No new stock margin data was updated")

    def get_actual_update_start_date(
        self, default_date: datetime.date
    ) -> datetime.date:
        """Get the actual start date for updating (1 day after latest date in table, or default_date)"""

        latest_date: Optional[str] = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=MARGIN_TABLE_NAME,
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
