import sys
import os
import shutil
import numpy as np
import pandas as pd
import datetime
import time
import re
import random
import requests
from pathlib import Path
from requests.exceptions import ReadTimeout
from requests.exceptions import ConnectionError
import shutil
import sqlite3
import shioaji as sj
from bs4 import BeautifulSoup
from io import StringIO
from typing import List
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
from .crawler_tools import CrawlerTools
from .html_crawler import CrawlHTML
from data import TickDBTools
from config import ( TICK_DOWNLOADS_PATH, TICK_DB_PATH, TICK_DB_NAME, TICK_TABLE_NAME, 
                    API_LIST)


""" 
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today

目前資料庫資料時間：
From 2020/04/01 ~ 2024/05/10
"""

class CrawlStockTick:
    """ 爬取上市櫃股票 ticks """
    
    def __init__(self):        
        self.api_list: List[sj.Shioaji] =[]
        self.stock_list: List[str] = CrawlHTML.crawl_stock_list()
        
        for sj_api in API_LIST:
            api = sj.Shioaji()
            self.api_list.append(ShioajiAccount.API_login(api, sj_api.api_key, sj_api.api_secret_key))
            
    
    def crawl_tick_data(self, start_date: datetime.date, end_date: datetime.date):
        """ 透過 Shioaji 爬取個股 tick-level data """
        
        # TODO: 判斷 api 用量並選擇還能使用的 api
        
        for code in self.stock_list:
            # TODO: 先暫定使用 api_list[0]
            api = self.api_list[0]
            cur_date = start_date
            
            while cur_date <= end_date:
                
                try:
                    ticks = api.ticks(contract=api.Contracts.Stocks[code], date=cur_date.isoformat())
                    tick_df = pd.DataFrame({**ticks})
                    tick_df.ts = pd.to_datetime(tick_df.ts)

                    if tick_df.empty:
                        continue
                except Exception as e:
                    print(f"Error Crawling Tick Data: {code}\n{e}")
        