import sys
import os
import shutil
import numpy as np
import pandas as pd
import datetime
from loguru import logger
import threading
from concurrent.futures import ThreadPoolExecutor
import time
import random
import requests
from pathlib import Path
from requests.exceptions import ReadTimeout
from requests.exceptions import ConnectionError
import shutil
import shioaji as sj
from typing import List, Any
import urllib.request
import ipywidgets as widgets
from IPython.display import display
from fake_useragent import UserAgent
from tqdm import tqdm
from tqdm import tnrange, tqdm_notebook
from dateutil.rrule import rrule, DAILY, MONTHLY
from dateutil.relativedelta import relativedelta
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import ShioajiAccount, ShioajiAPI
from utils import log_thread
from .crawler_tools import CrawlerTools
from .html_crawler import CrawlHTML
from data import TickDBTools
from config import (LOGS_DIR_PATH, TICK_DOWNLOADS_PATH, TICK_DB_PATH, TICK_DB_NAME, TICK_TABLE_NAME, 
                    API_LIST)


""" 
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today

目前資料庫資料時間：
From 2020/04/01 ~ 2024/05/10
"""

class CrawlStockTick:
    """ 爬取上市櫃股票 ticks """
    
    def __init__(self, start_date: datetime.date, end_date: datetime.date):        
        """ 初始化爬蟲設定 """
        
        self.start_date: datetime.date = start_date                             # 爬蟲開始日期
        self.end_date: datetime.date = end_date                                 # 爬蟲結束日期
        self.api_list: List[sj.Shioaji] = [                                     # Shioaji API List
            api_instance
            for sj_api in API_LIST
            if (api_instance := ShioajiAccount.API_login(sj.Shioaji(), sj_api.api_key, sj_api.api_secret_key)) is not None
        ]
        self.num_threads: int = len(self.api_list)                              # 可用的 API 數量 = 可開的 thread 數
        self.all_stock_list: List[str] = CrawlHTML.crawl_stock_list()           # 爬取所有上市櫃股票清單
        self.split_stock_list: List[List[str]] = []                             # 股票清單分組（後續給多線程用）
        self.table_latest_date: datetime.date = None
        
        # Set logger
        logger.add(f"{LOGS_DIR_PATH}/crawl_stock_tick.log")

    
    def split_list(self, target_list: List[Any], n_parts: int) -> List[List[str]]:
        """ 將 list 均分成 n 個 list """
        
        num_list, rem = divmod(len(target_list), n_parts)
        return [target_list[i * num_list + min(i, rem) : (i + 1) * num_list + min(i + 1, rem)] for i in range(n_parts)]


    @log_thread
    def crawl_tick_data(self, api: sj.Shioaji, stock_list: List[str]):
        """ 透過 Shioaji 爬取個股 tick-level data """
        
        if not os.path.exists(TICK_DOWNLOADS_PATH):
            os.makedirs(TICK_DOWNLOADS_PATH)
        
        for code in stock_list:
            # 判斷 api 用量
            if api.usage().remaining_bytes / 1024**2 < 20:
                logger.warning(f"API quota low for {api}. Stopped crawling at stock {code}.")
                break
            
            logger.info(f"Start crawling stock: {code}")
            
            df_list: List[pd.DataFrame] = []   
            cur_date = self.start_date
            
            while cur_date <= self.end_date:
                try:
                    ticks = api.ticks(contract=api.Contracts.Stocks[code], date=cur_date.isoformat())
                    tick_df = pd.DataFrame({**ticks})

                    if not tick_df.empty:
                        tick_df.ts = pd.to_datetime(tick_df.ts)
                        self.table_latest_date = tick_df.ts.max().date()
                        df_list.append(tick_df)

                except Exception as e:
                    logger.error(f"Error Crawling Tick Data: {code} {cur_date} | {e}")
                cur_date += datetime.timedelta(days=1)
                
            # Format tick data
            merged_df = pd.concat(df_list, ignore_index=True)
            formatted_df = TickDBTools.format_tick_data(merged_df, code)
            formatted_df = TickDBTools.format_time_to_microsec(formatted_df)
            
            # Save df to csv file
            formatted_df.to_csv(os.path.join(TICK_DOWNLOADS_PATH, f"{code}.csv"), index=False)
            logger.info(f"Saved {code}.csv to {TICK_DOWNLOADS_PATH}")
            
    
    def crawl_tick_data_multithreaded(self):
        """ 使用 Multi-threading 的方式 Crawl Tick Data """
        
        logger.info(f"Start multi-thread crawling. Total stocks: {len(self.all_stock_list)}, Threads: {self.num_threads}")
        start_time = time.time()  # 🔥 開始計時
        
        # 將 Stock list 均分給各個 thread 進行爬蟲
        self.split_stock_list = self.split_list(self.all_stock_list, self.num_threads)
        
        # Multi-threading
        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            futures = []
            for api, stock_list in zip(self.api_list, self.split_stock_list):
                futures.append(executor.submit(self.crawl_tick_data, api=api, stock_list=stock_list))

            # 確保執行完所有的 threads 才往下執行其餘程式碼
            for future in futures:
                try:
                    future.result()
                except Exception as e:
                    logger.error(f"Thread execution failed with exception: {e}")

        # Update tick table latest date
        TickDBTools.update_tick_table_latest_date(self.table_latest_date)
        
        total_time = time.time() - start_time
        logger.info(f"All crawling tasks completed and metadata updated. Total time: {total_time:.2f} seconds.")