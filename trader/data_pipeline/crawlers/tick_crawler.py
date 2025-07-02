import datetime
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import List, Optional, Any
import pandas as pd
import shioaji as sj
from shioaji.data import Ticks
from loguru import logger
from tqdm import tqdm

from trader.data_pipeline.crawlers.base import BaseCrawler
from trader.utils import ShioajiAccount, ShioajiAPI, log_thread
from trader.data_pipeline.utils.stock_tick_utils import StockTickUtils
from .stock_info_crawler import StockInfoCrawler
from trader.config import (
    LOGS_DIR_PATH,
    TICK_DOWNLOADS_PATH,
    API_LIST,
)


"""
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today

目前資料庫資料時間：
From 2020/04/01 ~ 2024/05/10
"""

class StockTickCrawler(BaseCrawler):
    """ 爬取上市櫃股票 ticks """

    def __init__(self):
        """ 初始化爬蟲設定 """

        super().__init__()

        self.api_list: List[sj.Shioaji] = [                                     # Shioaji API List
            api_instance
            for sj_api in API_LIST
            if (api_instance := ShioajiAccount.API_login(sj.Shioaji(), sj_api.api_key, sj_api.api_secret_key)) is not None
        ]
        self.num_threads: int = len(self.api_list)                              # 可用的 API 數量 = 可開的 thread 數
        self.all_stock_list: List[str] = StockInfoCrawler.crawl_stock_list()           # 爬取所有上市櫃股票清單
        self.split_stock_list: List[List[str]] = []                             # 股票清單分組（後續給多線程用）
        self.table_latest_date: datetime.date = None

        # Set logger
        logger.add(f"{LOGS_DIR_PATH}/crawl_stock_tick.log")

        # Generate downloads directory
        if not os.path.exists(TICK_DOWNLOADS_PATH):
            os.makedirs(TICK_DOWNLOADS_PATH)

        # Generate tick_metadata backup
        StockTickUtils.generate_tick_metadata_backup()


    def crawl(self, dates: List[datetime.date]) -> None:
        """ Crawl Tick Data """

        self.crawl_ticks_multithreaded(dates)


    def crawl_ticks_for_stock(
        self,
        api: sj.Shioaji,
        code: str,
        date: datetime.date
    ) -> Optional[pd.DataFrame]:
        """ 透過 Shioaji 爬取指定個股的 tick data """

        # 判斷 api 用量
        if api.usage().remaining_bytes / 1024**2 < 20:
            logger.warning(f"API quota low for {api}. Stopped crawling at stock {code}.")
            return None

        try:
            ticks: Ticks = api.ticks(contract=api.Contracts.Stocks[code], date=date.isoformat())
            tick_df: pd.DataFrame = pd.DataFrame({**ticks})

            if not tick_df.empty:
                tick_df.ts = pd.to_datetime(tick_df.ts)
                self.table_latest_date = tick_df.ts.max().date()
            else:
                return None
        except Exception as e:
                logger.error(f"Error Crawling Tick Data: {code} {date} | {e}")
                return None

        try:
            formatted_df: pd.DataFrame = StockTickUtils.format_tick_data(tick_df, code)
            formatted_df = StockTickUtils.format_time_to_microsec(formatted_df)

            # Save df to csv file
            formatted_df.to_csv(os.path.join(TICK_DOWNLOADS_PATH, f"{code}.csv"), index=False)
            logger.info(f"Saved {code}.csv to {TICK_DOWNLOADS_PATH}")

        except Exception as e:
            logger.error(f"Error processing or saving tick data for stock {code} | {e}")

        return formatted_df


    @log_thread
    def crawl_ticks_for_stock_list(
        self,
        api: sj.Shioaji,
        stock_list: List[str],
        dates: List[datetime.date]
    ) -> None:
        """ 透過 Shioaji 爬取 stock_list 中的個股 tick data """

        for code in stock_list:
            # 判斷 api 用量
            if api.usage().remaining_bytes / 1024**2 < 20:
                logger.warning(f"API quota low for {api}. Stopped crawling at stock {code}.")
                break

            logger.info(f"Start crawling stock: {code}")

            df_list: List[pd.DataFrame] = []

            for date in dates:
                try:
                    ticks: Ticks = api.ticks(contract=api.Contracts.Stocks[code], date=date.isoformat())
                    tick_df: pd.DataFrame = pd.DataFrame({**ticks})

                    if not tick_df.empty:
                        tick_df.ts = pd.to_datetime(tick_df.ts)
                        self.table_latest_date = tick_df.ts.max().date()
                        df_list.append(tick_df)

                except Exception as e:
                    logger.error(f"Error Crawling Tick Data: {code} {date} | {e}")

            if not df_list:
                logger.warning(f"No tick data found for stock {code} from {dates[0]} to {dates[-1]}. Skipping.")
                continue

            # Format tick data
            try:
                merged_df: pd.DataFrame = pd.concat(df_list, ignore_index=True)
                formatted_df: pd.DataFrame = StockTickUtils.format_tick_data(merged_df, code)
                formatted_df = StockTickUtils.format_time_to_microsec(formatted_df)

                # Save df to csv file
                formatted_df.to_csv(os.path.join(TICK_DOWNLOADS_PATH, f"{code}.csv"), index=False)
                logger.info(f"Saved {code}.csv to {TICK_DOWNLOADS_PATH}")

            except Exception as e:
                logger.error(f"Error processing or saving tick data for stock {code} | {e}")


    def crawl_ticks_multithreaded(self, dates: List[datetime.date]) -> None:
        """ 使用 Multi-threading 的方式 Crawl Tick Data """

        logger.info(f"Start multi-thread crawling. Total stocks: {len(self.all_stock_list)}, Threads: {self.num_threads}")
        start_time: float = time.time()  # 開始計時

        # 將 Stock list 均分給各個 thread 進行爬蟲
        self.split_stock_list: List[List[str]] = self.split_list(self.all_stock_list, self.num_threads)

        # Multi-threading
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures: List[Future] = []
            for api, stock_list in zip(self.api_list, self.split_stock_list):
                futures.append(executor.submit(self.crawl_ticks_for_stock_list, api=api, stock_list=stock_list, dates=dates))

            # 確保執行完所有的 threads 才往下執行其餘程式碼
            for future in tqdm(as_completed(futures), total=len(futures), desc="Thread progress"):
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Thread execution failed with exception: {e}")

        # Update tick table latest date
        StockTickUtils.update_tick_table_latest_date(self.table_latest_date)

        total_time: float = time.time() - start_time
        total_file: int = len(list(TICK_DOWNLOADS_PATH.glob("*.csv")))
        logger.info(f"All crawling tasks completed and metadata updated. Total file: {total_file}, Total time: {total_time:.2f} seconds")


    def split_list(
        self,
        target_list: List[Any],
        n_parts: int
    ) -> List[List[str]]:
        """ 將 list 均分成 n 個 list """

        num_list: int = 0
        rem: int = 0
        num_list, rem = divmod(len(target_list), n_parts)
        return [target_list[i * num_list + min(i, rem) : (i + 1) * num_list + min(i + 1, rem)] for i in range(n_parts)]