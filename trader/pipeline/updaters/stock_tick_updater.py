import datetime
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import List, Optional, Any
import pandas as pd
import shioaji as sj
from shioaji.data import Ticks
from loguru import logger
from pathlib import Path

from trader.utils import ShioajiAccount, ShioajiAPI, log_thread
from trader.pipeline.updaters.stock_tick_updater import BaseDataUpdater
from trader.pipeline.crawlers.stock_tick_crawler import StockTickCrawler
from trader.pipeline.cleaners.stock_tick_cleaner import StockTickCleaner
from trader.pipeline.loaders.stock_tick_loader import StockTickLoader
from trader.pipeline.crawlers.stock_info_crawler import StockInfoCrawler
from trader.pipeline.utils.stock_tick_utils import StockTickUtils
from trader.utils import TimeUtils
from trader.config import (
    LOGS_DIR_PATH,
    TICK_DOWNLOADS_PATH,
    API_LIST,
)


class StockTickUpdater(BaseDataUpdater):
    """Stock Tick Updater"""

    def __init__(self):

        super().__init__()

        # ETL
        self.crawler: StockTickCrawler = StockTickCrawler()
        self.cleaner: StockTickCleaner = StockTickCleaner()
        self.loader: StockTickLoader = StockTickLoader()

        # Crawler Setting
        self.api_list: List[sj.Shioaji] = [  # Shioaji API List
            api_instance
            for sj_api in API_LIST
            if (
                api_instance := ShioajiAccount.API_login(
                    sj.Shioaji(), sj_api.api_key, sj_api.api_secret_key
                )
            )
            is not None
        ]

        # 爬取所有上市櫃股票清單
        self.all_stock_list: List[str] = StockInfoCrawler.crawl_stock_list()

        # 可用的 API 數量 = 可開的 thread 數
        self.num_threads: int = len(self.api_list)

        # 股票清單分組（後續給多線程用）
        self.split_stock_list: List[List[str]] = []

        # 目前 tickDB 最新資料日期
        self.table_latest_date: datetime.date = None
        self.tick_dir: Path = TICK_DOWNLOADS_PATH
        self.setup()

    def setup(self):
        """Set Up the Config of Updater"""

        # Generate tick_metadata backup
        StockTickUtils.generate_tick_metadata_backup()

    def update(self, start_date: datetime.date, end_date: datetime.date):
        """Update the Database"""

        # Update Period
        dates: List[datetime.date] = TimeUtils.generate_date_range(start_date, end_date)



    def update_tick_multithreaded(self, dates: List[datetime.date]) -> None:
        """使用 Multi-threading 的方式 Update Tick Data"""

        logger.info(
            f"Start multi-thread crawling. Total stocks: {len(self.all_stock_list)}, Threads: {self.num_threads}"
        )
        start_time: float = time.time()  # 開始計時

        # 將 Stock list 均分給各個 thread 進行爬蟲
        self.split_stock_list: List[List[str]] = self.split_list(
            self.all_stock_list, self.num_threads
        )

        def thread_task(api: sj.Shioaji, dates: List[datetime.date], stock_list: List[str]) -> None:
            df_list: List[pd.DataFrame] = self.crawler_stock_list_tick(api, dates, stock_list)

            for df in df_list:
                tick_df: pd.DataFrame = self.cleaner.clean_stock_tick(df)
        # Multi-threading
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            for api, stock_list in zip(self.api_list, self.split_stock_list):
                executor.submit(
                    self.crawl_ticks_for_stock_list,
                    api=api,
                    dates=dates,
                    stock_list=stock_list,
                )

            # 確保執行完所有的 threads 才往下執行其餘程式碼

        # Update tick table latest date
        StockTickUtils.update_tick_table_latest_date(self.table_latest_date)

        total_time: float = time.time() - start_time
        total_file: int = len(list(TICK_DOWNLOADS_PATH.glob("*.csv")))
        logger.info(
            f"All crawling tasks completed and metadata updated. Total file: {total_file}, Total time: {total_time:.2f} seconds"
        )

    def split_list(self, target_list: List[Any], n_parts: int) -> List[List[str]]:
        """將 list 均分成 n 個 list"""

        num_list: int = 0
        rem: int = 0
        num_list, rem = divmod(len(target_list), n_parts)
        return [
            target_list[
                i * num_list + min(i, rem) : (i + 1) * num_list + min(i + 1, rem)
            ]
            for i in range(n_parts)
        ]

