import sys
import os
from pathlib import Path
import sqlite3
import requests
import pandas as pd
from io import StringIO
from datetime import datetime, timedelta
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
    TPEX: 2007/4/20 開始提供 (但這邊先從 2014 開始爬)
    
    TWSE 改制時間：   TPEX 改制時間：
    1. 2014/12/1    1. 2018/1/15
    2. 2017/12/18
    """
    
    logger.add('tpex_change_date.log')
    start_year = 2024
    start_date = datetime(start_year, 3, 24)
    end_date = datetime.now() # 定義結束日期 (今天)
    cur_date = start_date

    format_list = []
    format_chg_date = []
    
    tmp_stop_cnt = 0
    
    """ 紀錄 TWSE 表格改制日期 """
    while cur_date <= end_date:
        print(f"Current Date: {cur_date.strftime('%Y/%m/%d')}")
        # twse_crawl_date = cur_date.strftime("%Y%m%d")
        tpex_crawl_date = cur_date.strftime("%Y/%m/%d")
        # twse_url = f'https://www.twse.com.tw/rwd/zh/fund/T86?date={twse_crawl_date}&selectType=ALLBUT0999&response=html'
        tpex_url = f'https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={tpex_crawl_date}&id=&response=html'
        headers = generate_random_header()
        # twse_response = requests.get(twse_url, headers=headers)
        tpex_response = requests.get(tpex_url, headers=headers)
        
        try:
            # twse_df = pd.read_html(StringIO(twse_response.text))[0]
            tpex_df = pd.read_html(StringIO(tpex_response.text))[0]
        except Exception as e:
            print("It's Holiday!")
            cur_date += timedelta(days=1)
            continue
        
        columns = tpex_df.columns
        
        """ 檢查是否平日 """
        if len(columns[0]) == 3:
            """ 平日 """
            col_name = [col[1] for col in columns]
        elif len(columns[0]) == 2:
            """ 假日 """
            col_name = [col[0] for col in columns]
        
        if col_name[-1][0] == 'U':
            col_name.pop()
        
        if len(format_list) == 0:
            format_list.append(col_name)
        else:
            """ 發現改制的時間 """
            if format_list[-1] != col_name:
                logger.info(f"* Format Change Date: {cur_date.strftime('%Y/%m/%d')}")
                logger.info(f"Last format: {format_list[-1]}")
                logger.info(f"Current format: {col_name}")
                format_list.append(col_name)
                format_chg_date.append(cur_date)
                
        cur_date += timedelta(days=1)
        tmp_stop_cnt += 1
        
        delay = random.uniform(1, 5)
        time.sleep(delay)
        
        if tmp_stop_cnt == 100:
            print("Sleep 2 minutes...")
            tmp_stop_cnt = 0
            time.sleep(120)
        