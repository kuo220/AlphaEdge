import datetime
import time
from concurrent.futures import Future, ThreadPoolExecutor
from typing import List, Optional, Any
import pandas as pd
import shioaji as sj
from loguru import logger
from pathlib import Path

from trader.utils import ShioajiAccount
from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.stock_tick_crawler import StockTickCrawler
from trader.pipeline.cleaners.stock_tick_cleaner import StockTickCleaner
from trader.pipeline.loaders.stock_tick_loader import StockTickLoader
from trader.pipeline.crawlers.stock_info_crawler import StockInfoCrawler
from trader.pipeline.utils.stock_tick_utils import StockTickUtils
from trader.utils import TimeUtils
from trader.config import TICK_DOWNLOADS_PATH, API_LIST, LOGS_DIR_PATH


"""
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today

目前資料庫資料時間：
From 2020/04/01 ~ 2024/05/10
"""


class StockTickUpdater(BaseDataUpdater):
    """Stock Tick Updater"""

    def __init__(self):

        super().__init__()

        # ETL
        self.crawler: StockTickCrawler = StockTickCrawler()
        self.cleaner: StockTickCleaner = StockTickCleaner()
        self.loader: StockTickLoader = StockTickLoader()

        # Crawler Setting
        # Shioaji API List
        self.api_list: List[sj.Shioaji] = [
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

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_tick.log")

    def update(self, start_date: datetime.date, end_date: datetime.date):
        """Update the Database"""

        # Update Tick Period
        dates: List[datetime.date] = TimeUtils.generate_date_range(start_date, end_date)

        # Step 1: Crawl + Clean
        self.update_multithreaded(dates)

        # Step 2: Load
        self.loader.add_to_db(remove_file=False)

    def update_thread(
        self, api: sj.Shioaji, dates: List[datetime.date], stock_list: List[str]
    ) -> None:
        """
        - Description:
            單一 thread 任務：爬 + 清洗

        - Parameters:
            - api: sj.Shioaji
                Shioaji API
            - dates: List[datetime.date]
                日期 List
            - stock_list: List[str]
                Stock List

        - Return: List[pd.DataFrame]
            - 每個 df 是一檔股票日期區間內的所有 tick
        """

        latest_date: Optional[datetime.date] = None

        # Crawl
        for stock_id in stock_list:
            # 判斷 api 用量
            if api.usage().remaining_bytes / 1024**2 < 20:
                logger.warning(
                    f"API quota low for {api}. Stopped crawling at stock {stock_id}."
                )
                break

            logger.info(f"Start crawling stock: {stock_id}")

            df_list: List[pd.DataFrame] = []
            for date in dates:
                df: Optional[pd.DataFrame] = self.crawler.crawl_stock_tick(
                    api, date, stock_id
                )

                if df is not None and not df.empty:
                    df_list.append(df)
                    # Update table latest date
                    latest_date = max(latest_date or date, date)

            if not df_list:
                logger.warning(
                    f"No tick data found for stock {stock_id} from {dates[0]} to {dates[-1]}. Skipping."
                )
                continue

            merged_df: pd.DataFrame = pd.concat(df_list, ignore_index=True)

            # Clean
            try:
                cleaned_df: pd.DataFrame = self.cleaner.clean_stock_tick(
                    merged_df, stock_id
                )

                if cleaned_df is None or cleaned_df.empty:
                    logger.warning(f"Cleaned dataframe empty for {stock_id}.")

            except Exception as e:
                logger.error(f"Error cleaning tick data for {stock_id}: {e}")

        if latest_date:
            self.table_latest_date = max(
                self.table_latest_date or latest_date, latest_date
            )

    def update_multithreaded(self, dates: List[datetime.date]) -> None:
        """使用 Multi-threading 的方式 Update Tick Data"""

        logger.info(
            f"Start multi-thread crawling. Total stocks: {len(self.all_stock_list)}, Threads: {self.num_threads}"
        )
        start_time: float = time.time()  # 開始計時

        # 將 Stock list 均分給各個 thread 進行爬蟲
        self.split_stock_list: List[List[str]] = self.split_list(
            self.all_stock_list, self.num_threads
        )

        futures: List[Future] = []
        # Multi-threading
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            for api, stock_list in zip(self.api_list, self.split_stock_list):
                futures.append(
                    executor.submit(
                        self.update_thread,
                        api=api,
                        dates=dates,
                        stock_list=stock_list,
                    )
                )

            # 等待所有 thread 結束
            for future in futures:
                try:
                    future.result()  # 若有 exception 會在這邊被 raise 出來
                except Exception as e:
                    logger.error(f"Thread task failed with exception: {e}")

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
