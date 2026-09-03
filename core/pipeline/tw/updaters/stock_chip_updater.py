import datetime
import random
import sqlite3
import time
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import CHIP_TABLE_NAME, PRICE_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.shared.base_crawler import CrawlResult
from core.pipeline.shared.base_updater import BaseDataUpdater, UpdateStats
from core.pipeline.shared.date_planner import DatePlanner, NoDataDateStore
from core.pipeline.tw.cleaners.stock_chip_cleaner import StockChipCleaner
from core.pipeline.tw.crawlers.stock_chip_crawler import StockChipCrawler
from core.pipeline.tw.loaders.stock_chip_loader import StockChipLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils
from core.utils.log_manager import LogManager

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

    # 每爬幾天就入庫一次。整段爬完才入庫的話，中斷等於前功盡棄——
    # 2013 起的回補有 3,300 個交易日、數小時，中途失敗要全部重來。
    # 分批之後最多只損失最後一批（未入庫的部分），重跑會自動接續。
    LOAD_BATCH_SIZE: int = 100
    BATCH_SLEEP_EVERY_N_FILES: int = 100
    BATCH_SLEEP_DURATION_SECONDS: int = 120
    BATCH_RANDOM_DELAY_MIN: int = 1
    BATCH_RANDOM_DELAY_MAX: int = 5

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
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)
        LogManager.setup_logger("update_chip.log")

    def load_batch(self, batch_dates: List[str]) -> None:
        """
        - Description:
            入庫本批爬取的日期

            **只載入本批的檔案**：loader 預設會掃整個 downloads 目錄，若每批都全掃，
            13 年的回補會變成「數十批 × 數千檔」的重複讀取。
        - Parameters:
            - batch_dates: List[str]
                本批的日期字串（`YYYYMMDD`），對應 downloads 內的檔名後綴
        """

        logger.info(
            f"* Loading batch: {len(batch_dates)} 天（{batch_dates[0]} ~ {batch_dates[-1]}）"
        )
        self.loader.add_to_db(remove_files=False, only_dates=set(batch_dates))

    def update(
        self,
        start_date: datetime.date,
        end_date: Optional[datetime.date] = None,
    ) -> None:
        """
        - Description:
            更新三大法人籌碼

            **以 `price` 表的交易日為日曆**：比「非週末」精確，涵蓋國定假日與
            補行交易日；候選日期是差集而非 `MAX(date)+1`（健檢 F-050）。
            `price` 尚未更新到的區間會少幾天，下次執行自然補上。
        - Parameters:
            - start_date: datetime.date
                回補起日
            - end_date: Optional[datetime.date]
                回補迄日；None 取當日（預設值不可在 def 行求值，見 F-002）
        """

        logger.info("* Start Updating TWSE & TPEX Chip Data...")

        end_date: datetime.date = end_date or datetime.date.today()

        # Step 1: Crawl
        no_data_store: NoDataDateStore = NoDataDateStore("chip")
        calendar_dates: Set[datetime.date] = DatePlanner.get_trading_dates(
            self.conn, PRICE_TABLE_NAME, start_date, end_date
        )
        dates: List[datetime.date] = DatePlanner.plan(
            conn=self.conn,
            table_name=CHIP_TABLE_NAME,
            start_date=start_date,
            end_date=end_date,
            no_data_dates=no_data_store.dates,
            calendar_dates=calendar_dates or None,
        )
        logger.info(f"本次待更新日期：{len(dates)} 天（{start_date} ~ {end_date}）")

        file_cnt: int = 0
        batch_dates: List[str] = []
        stats: UpdateStats = UpdateStats()

        for date in dates:
            logger.info(date.strftime("%Y/%m/%d"))
            twse: CrawlResult = self.crawler.crawl_twse_chip(date)
            tpex: CrawlResult = self.crawler.crawl_tpex_chip(date)
            if stats.record(twse, tpex):
                no_data_store.add(date)

            # Step 2: Clean
            if twse.is_ok:
                cleaned_twse_df: pd.DataFrame = self.cleaner.clean_twse_chip(
                    twse.data, date
                )
                if cleaned_twse_df is None or cleaned_twse_df.empty:
                    logger.warning(f"Cleaned TWSE dataframe empty on {date}")

            if tpex.is_ok:
                cleaned_tpex_df: pd.DataFrame = self.cleaner.clean_tpex_chip(
                    tpex.data, date
                )
                if cleaned_tpex_df is None or cleaned_tpex_df.empty:
                    logger.warning(f"Cleaned TPEX dataframe empty on {date}")

            file_cnt += 1
            batch_dates.append(date.strftime("%Y%m%d"))

            # Step 3: Load（分批）
            if len(batch_dates) >= self.LOAD_BATCH_SIZE:
                self.load_batch(batch_dates)
                batch_dates = []

            if file_cnt == self.BATCH_SLEEP_EVERY_N_FILES:
                logger.info("Sleep 2 minutes...")
                file_cnt = 0
                time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
            else:
                delay: int = random.randint(
                    self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                )
                time.sleep(delay)

        # 收尾：載入最後一批未達批量的日期
        if batch_dates:
            self.load_batch(batch_dates)

        no_data_store.save()
        stats.report("chip")

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
