import datetime
import os
import random
import shutil
import sys
import threading
import time
import urllib.request
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from pathlib import Path
from typing import List, Optional, Any
import ipywidgets as widgets
import numpy as np
import pandas as pd
import requests
import shioaji as sj
from shioaji.data import Ticks
from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, rrule
from fake_useragent import UserAgent
from IPython.display import display
from loguru import logger
from requests.exceptions import ConnectionError, ReadTimeout
from tqdm import tqdm, tnrange, tqdm_notebook

from trader.data import TickDBTools, TickDBManager
from trader.utils import ShioajiAccount, ShioajiAPI, log_thread
from .utils.crawler_tools import CrawlerTools
from .stock_info_crawler import StockInfoCrawler
from trader.config import (
    LOGS_DIR_PATH,
    TICK_DOWNLOADS_PATH,
    TICK_DB_PATH,
    TICK_DB_NAME,
    TICK_TABLE_NAME,
    API_LIST,
    DDB_PATH,
    DDB_HOST,
    DDB_PORT,
    DDB_USER,
    DDB_PASSWORD
)


"""
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today

目前資料庫資料時間：
From 2020/04/01 ~ 2024/05/10
"""

class StockTickCrawler:
    """ 爬取上市櫃股票 ticks """

    def __init__(self):
        """ 初始化爬蟲設定 """

        self.tick_db_manager: TickDBManager = TickDBManager()                   # Tick DolphinDB Manager
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
        TickDBTools.generate_tick_metadata_backup()


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
            formatted_df: pd.DataFrame = TickDBTools.format_tick_data(tick_df, code)
            formatted_df = TickDBTools.format_time_to_microsec(formatted_df)

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
                formatted_df: pd.DataFrame = TickDBTools.format_tick_data(merged_df, code)
                formatted_df = TickDBTools.format_time_to_microsec(formatted_df)

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
        TickDBTools.update_tick_table_latest_date(self.table_latest_date)

        total_time: float = time.time() - start_time
        total_file: int = len(list(TICK_DOWNLOADS_PATH.glob("*.csv")))
        logger.info(f"All crawling tasks completed and metadata updated. Total file: {total_file}, Total time: {total_time:.2f} seconds")


    def update_table(self, dates: List[datetime.date]) -> None:
        """ Tick Database 資料更新（Multi-threading） """

        self.crawl_ticks_multithreaded(dates)
        self.add_to_sql()


    def widget(self) -> None:
        """ Tick Database 資料更新 UI """

        # Set update date
        date_picker_from: widgets.DatePicker = widgets.DatePicker(description='from', disabled=False)
        date_picker_to: widgets.DatePicker = widgets.DatePicker(description='to', disabled=False)

        date_picker_from.value = TickDBTools.get_table_latest_date() + datetime.timedelta(days=1)
        date_picker_to.value = datetime.date.today()

        # Set update button
        btn: widgets.Button = widgets.Button(description='update')

        # Define update button behavior
        def onupdate(_):
            start_date: Optional[datetime.date] = date_picker_from.value
            end_date: Optional[datetime.date] = date_picker_to.value

            if not start_date or not end_date:
                print("Please select both start and end dates.")
                return

            dates: List[datetime.date] = CrawlerTools.generate_date_range(start_date, end_date)

            if not dates:
                print("Date range is empty. Please check if the start date is earlier than the end date.")
                return

            print(f"Updating data for table '{TICK_TABLE_NAME}' from {dates[0]} to {dates[-1]}...")
            self.update_table(dates)

        btn.on_click(onupdate)

        label: widgets.Label = widgets.Label(f"""{TICK_TABLE_NAME} (from {TickDBTools.get_table_earliest_date()} to
                              {TickDBTools.get_table_latest_date()})
                              """)
        items: List[widgets.Widget] = [date_picker_from, date_picker_to, btn]
        display(widgets.VBox([label, widgets.HBox(items)]))


    def add_to_sql(self) -> None:
        """ 將資料夾中的所有 CSV 檔存入 tick 的 DolphinDB 中 """

        self.tick_db_manager.append_all_csv_to_dolphinDB(TICK_DOWNLOADS_PATH)
        shutil.rmtree(TICK_DOWNLOADS_PATH)