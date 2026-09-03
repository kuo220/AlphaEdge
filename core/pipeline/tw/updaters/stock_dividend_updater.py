import datetime
import random
import sqlite3
import time
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import DIVIDEND_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.shared.base_crawler import CrawlResult
from core.pipeline.shared.base_updater import BaseDataUpdater, UpdateStats
from core.pipeline.tw.cleaners.stock_dividend_cleaner import StockDividendCleaner
from core.pipeline.tw.crawlers.stock_dividend_crawler import StockDividendCrawler
from core.pipeline.tw.loaders.stock_dividend_loader import StockDividendLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils
from core.utils import TimeUtils
from core.utils.log_manager import LogManager

"""
除權除息計算結果表爬蟲資料時間表：
1. TWSE（上市）
    - TWT49U：官方自民國 90 年起提供，本專案實測 2013 年起表格結構未再改制
2. TPEX（上櫃）
    - 櫃買中心 `bulletin/exDailyQ`：官方頁面標示資料自 2008/01/02 起提供

兩個來源皆支援日期區間，故一律**以「年」為單位請求**，2013~今日各僅需十餘次請求，
不退化成逐日爬取（一年 250 次 vs 1 次）。
"""


class StockDividendUpdater(BaseDataUpdater):
    """Stock Dividend Updater"""

    # TWSE 區間請求之間的節流（一年一次請求，不需要像逐日爬蟲那樣長時間休息）
    YEAR_REQUEST_DELAY_MIN: int = 3
    YEAR_REQUEST_DELAY_MAX: int = 8

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: StockDividendCrawler = StockDividendCrawler()
        self.cleaner: StockDividendCleaner = StockDividendCleaner()
        self.loader: StockDividendLoader = StockDividendLoader()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)
        LogManager.setup_logger("update_dividend.log")

    def update(
        self,
        start_date: datetime.date,
        end_date: datetime.date = datetime.date.today(),
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Dividend Data...")

        # Step 1: Crawl
        # 取得要開始更新的日期
        start_date: datetime.date = self.get_actual_update_start_date(
            default_date=start_date
        )
        logger.info(f"Latest data date in database: {start_date}")

        if start_date > end_date:
            logger.info("Dividend data is already up to date")
            return

        # TWSE：以年為單位請求，一年一次
        years: List[int] = TimeUtils.generate_year_range(start_date.year, end_date.year)
        stats: UpdateStats = UpdateStats()

        for year in years:
            year_start: datetime.date = max(start_date, datetime.date(year, 1, 1))
            year_end: datetime.date = min(end_date, datetime.date(year, 12, 31))

            period: str = (
                f"{TimeUtils.format_date(year_start)}_{TimeUtils.format_date(year_end)}"
            )

            twse: CrawlResult = self.crawler.crawl_twse_dividend(year_start, year_end)
            tpex: CrawlResult = self.crawler.crawl_tpex_dividend(year_start, year_end)
            stats.record(twse, tpex)

            # Step 2: Clean
            if twse.is_ok:
                cleaned_twse_df: Optional[pd.DataFrame] = (
                    self.cleaner.clean_twse_dividend(
                        twse.data, file_name=f"twse_{period}"
                    )
                )
                if cleaned_twse_df is None or cleaned_twse_df.empty:
                    logger.warning(f"Cleaned TWSE dataframe empty for {year}")

            if tpex.is_ok:
                cleaned_tpex_df: Optional[pd.DataFrame] = (
                    self.cleaner.clean_tpex_dividend(
                        tpex.data, file_name=f"tpex_{period}"
                    )
                )
                if cleaned_tpex_df is None or cleaned_tpex_df.empty:
                    logger.warning(f"Cleaned TPEX dataframe empty for {year}")

            delay: int = random.randint(
                self.YEAR_REQUEST_DELAY_MIN, self.YEAR_REQUEST_DELAY_MAX
            )
            time.sleep(delay)

        # `requested` 這裡的單位是「年」而不是「天」：本來源支援區間查詢，一年一次請求
        stats.report("dividend（單位：年）")

        # Step 3: Load
        self.loader.add_to_db(remove_files=False)

        # 更新後重新取得Table最新的日期
        table_latest_date: str = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=DIVIDEND_TABLE_NAME,
            col_name="date",
        )
        if table_latest_date:
            logger.info(
                f"Stock dividend data updated. Latest available date: {table_latest_date}"
            )
        else:
            logger.warning("No new stock dividend data was updated")

    def get_actual_update_start_date(
        self, default_date: datetime.date
    ) -> datetime.date:
        """Get the actual start date for updating (1 day after latest date in table, or default_date)"""

        latest_date: Optional[str] = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=DIVIDEND_TABLE_NAME,
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
