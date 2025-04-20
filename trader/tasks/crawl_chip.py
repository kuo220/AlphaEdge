import sys
import os
from pathlib import Path
import sqlite3
import requests
import datetime
import pandas as pd
from io import StringIO
from fake_useragent import UserAgent
import time
from loguru import logger
import random

crawler_path = Path.cwd().parent
sys.path.append(str(crawler_path))

from crawler import (CrawlerTools, CrawlStockChip)


if __name__ == '__main__':
    
    """ 
    TWSE: 2012/5/2 開始提供（這邊從 2014/12/1 開始爬）
    TPEX: 2007/4/20 開始提供 (但這邊先從 2014/12/1 開始爬)
    
    TWSE 改制時間：   TPEX 改制時間：
    1. 2014/12/1    1. 2018/1/15
    2. 2017/12/18
    """
    
    crawler = CrawlStockChip()
    
    # TWSE
    twse_start_date = datetime.datetime(2024, 4, 5)
    twse_end_date = datetime.datetime(2024, 4, 10)
    
    crawler.crawl_twse_chip_range(twse_start_date, twse_end_date)
    
    # TPEX
    tpex_start_date = datetime.datetime(2024, 4, 5)
    tpex_end_date = datetime.datetime(2024, 4, 10)
    
    crawler.crawl_tpex_chip_range(tpex_start_date, tpex_end_date)