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

crawler_path = Path.cwd().parents[0]
sys.path.append(str(crawler_path))

from utils import Crawler
from utils import Data

def generate_random_header():
    ua = UserAgent()
    user_agent = ua.random
    headers = {'Accept': '*/*', 'Connection': 'keep-alive',
            'User-Agent': user_agent}
    return headers

if __name__ == '__main__':
    
    """ 
    TWSE: 2012/5/2 開始提供
    TPEX: 2007/4/20 開始提供 (但這邊先從 2014/12/1 開始爬)
    
    TWSE 改制時間：   TPEX 改制時間：
    1. 2014/12/1    1. 2018/1/15
    2. 2017/12/18
    """
    
    crawler = Crawler().FromHTML
    
    # TWSE
    twse_dir_path = Path(__file__).resolve().parent.parent / 'Downloads' / '三大法人盤後籌碼' / 'TWSE'
    twse_start_year = 2012
    twse_start_month = 5
    twse_start_day = 2
    
    crawler.crawl_twse_institutional_investors(twse_start_year, twse_start_month, twse_start_day, twse_dir_path)
    
    # TPEX
    tpex_dir_path = Path(__file__).resolve().parent.parent / 'Downloads' / '三大法人盤後籌碼' / 'TPEX'
    tpex_start_year = 2014
    tpex_start_month = 12
    tpex_start_day = 1
    
    crawler.crawl_tpex_institutional_investors(tpex_start_year, tpex_start_month, tpex_start_day, tpex_dir_path) 