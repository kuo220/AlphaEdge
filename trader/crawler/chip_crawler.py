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
import zipfile
import pickle
import warnings
import sqlite3
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
from .crawler_tools import CrawlerTools


class CrawlStockChip:
    """ 爬取上市、上櫃股票三大法人盤後籌碼 """
    
    def crawl_twse_chip(self, year: int, month: int, day: int, dir_path: str=os.path.join('..', 'tasks', '三大法人盤後籌碼')):
        """ TWSE 三大法人爬蟲 """
        """ 
        TWSE: 2012/5/2 開始提供（這邊從 2014/12/1 開始爬）
        TWSE 改制時間: 2014/12/1, 2017/12/18
        """
        
        first_reform_date = datetime.datetime(2014, 12, 1)
        second_reform_date = datetime.datetime(2017, 12, 18)

        start_date, end_date = datetime.datetime(year, month, day), datetime.datetime.now()
        cur_date = start_date
        
        # if crawl_cnt == 100, then sleep
        crawl_cnt = 0
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)

        print("* Start crawling TWSE institutional investors data...")
        while cur_date <= end_date:
            print(cur_date.strftime("%Y/%m/%d"))
            twse_url = f'https://www.twse.com.tw/rwd/zh/fund/T86?date={cur_date.strftime("%Y%m%d")}&selectType=ALLBUT0999&response=html'
            headers = CrawlerTools.generate_random_header()
            twse_response = requests.get(twse_url, headers=headers)

            # 檢查是否為假日
            try:
                twse_df = pd.read_html(StringIO(twse_response.text))[0]
            except Exception as e:
                print("It's Holiday!")
                cur_date += datetime.timedelta(days=1)
                continue

            twse_df = pd.read_html(StringIO(twse_response.text))[0]
            twse_df.columns = twse_df.columns.droplevel(0)
            twse_df.insert(0, '日期', cur_date)
            
            old_col_name = ['自營商買進股數(自行買賣)', '自營商賣出股數(自行買賣)', '自營商買賣超股數(自行買賣)', 
                            '自營商買進股數(避險)', '自營商賣出股數(避險)', '自營商買賣超股數(避險)']
            
            new_col_name = ['自營商買進股數_自行買賣', '自營商賣出股數_自行買賣', '自營商買賣超股數_自行買賣', 
                            '自營商買進股數_避險', '自營商賣出股數_避險', '自營商買賣超股數_避險']
            
            # 第一次格式改制前
            if cur_date < first_reform_date:
                CrawlerTools.move_col(twse_df, "自營商買賣超股數", "自營商賣出股數")
            # 第一次格式改制後，第二次格式改制前
            elif first_reform_date <= cur_date < second_reform_date:
                CrawlerTools.move_col(twse_df, "自營商買賣超股數", "自營商買賣超股數(避險)")
                twse_df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)
            # 第二次格式改制後
            else:
                twse_df['外資買進股數'] = twse_df['外陸資買進股數(不含外資自營商)'] + twse_df['外資自營商買進股數']
                twse_df['外資賣出股數'] = twse_df['外陸資賣出股數(不含外資自營商)'] + twse_df['外資自營商賣出股數']
                twse_df['外資買賣超股數'] = twse_df['外陸資買賣超股數(不含外資自營商)'] + twse_df['外資自營商買賣超股數']
                twse_df.drop(columns=['外陸資買進股數(不含外資自營商)', '外陸資賣出股數(不含外資自營商)', '外陸資買賣超股數(不含外資自營商)',
                                    '外資自營商買進股數', '外資自營商賣出股數', '外資自營商買賣超股數'], inplace=True)
                CrawlerTools.move_col(twse_df, '外資買進股數', '證券名稱')
                CrawlerTools.move_col(twse_df, '外資賣出股數', '外資買進股數')
                CrawlerTools.move_col(twse_df, '外資買賣超股數', '外資賣出股數')
                CrawlerTools.move_col(twse_df, "自營商買賣超股數", "自營商買賣超股數(避險)")
                twse_df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)
            
            twse_df = CrawlerTools.remove_redundant_col(twse_df, '三大法人買賣超股數')
            twse_df = CrawlerTools.fill_nan(twse_df, 0)
            twse_df.to_csv(os.path.join(dir_path, f"twse_{cur_date.strftime('%Y%m%d')}.csv"), index=False)
            cur_date += datetime.timedelta(days=1)
            
            crawl_cnt += 1
            
            if crawl_cnt == 100:
                print("Sleep 2 minutes...")
                crawl_cnt = 0
                time.sleep(120)
            else:
                delay = random.randint(1, 5)
                time.sleep(delay)
            
              
    def crawl_tpex_chip(self, year: int, month: int, day: int, dir_path: str=os.path.join('..', 'tasks', '三大法人盤後籌碼')):
        """ TPEX 三大法人爬蟲 """
        """ 
        TPEX: 2007/4/20 開始提供 (這邊從 2014/12/1 開始爬)
        TPEX 改制時間: 2018/1/15
        """
        
        first_reform_date = datetime.datetime(2018, 1, 15)
        start_date, end_date = datetime.datetime(year, month, day), datetime.datetime.now()
        cur_date = start_date
        
        # if crawl_cnt == 100, then sleep
        crawl_cnt = 0
        
        if not os.path.exists(dir_path):
            os.makedirs(dir_path)
        
        print("* Start crawling TPEX institutional investors data...")
        while cur_date <= end_date:
            print(cur_date.strftime("%Y/%m/%d"))
            tpex_url = f'https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={cur_date.strftime("%Y/%m/%d")}&id=&response=html'
            headers = CrawlerTools.generate_random_header()
            tpex_response = requests.get(tpex_url, headers=headers)
            tpex_df = pd.read_html(StringIO(tpex_response.text))[0]
            tpex_df.drop(index=tpex_df.index[0], columns=tpex_df.columns[-1], inplace=True)
            
            # 檢查是否為假日
            if tpex_df.shape[0] == 1:
                print("It's Holiday!")
                cur_date += datetime.timedelta(days=1)
                continue
            
            tpex_df.columns = tpex_df.columns.droplevel(0)
            
            new_col_name = [
                '證券代號', '證券名稱', '外資買進股數', '外資賣出股數', '外資買賣超股數',
                '投信買進股數', '投信賣出股數', '投信買賣超股數', '自營商買賣超股數',
                '自營商買進股數_自行買賣', '自營商賣出股數_自行買賣', '自營商買賣超股數_自行買賣',
                '自營商買進股數_避險', '自營商賣出股數_避險', '自營商買賣超股數_避險', '三大法人買賣超股數'
            ]
            
            # 格式改制前
            if cur_date < first_reform_date:
                old_col_name = [
                    '代號', '名稱', '外資 及陸資 買股數', '外資 及陸資 賣股數', '外資 及陸資 淨買股數',
                    '投信 買股數', '投信 賣股數', '投信 淨買股數', '自營商 淨買股數',
                    '自營商 (自行買賣) 買股數', '自營商 (自行買賣) 賣股數', '自營商 (自行買賣) 淨買股數',
                    '自營商 (避險) 買股數', '自營商 (避險) 賣股數', '自營商 (避險) 淨買股數', '三大法人 買賣超股數'
                ]
                
                tpex_df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)
            # 格式改制後
            else:
                new_tpex_df = pd.DataFrame(columns=new_col_name)
                new_tpex_df['證券代號'] = tpex_df.loc[:, ('代號', '代號')]
                new_tpex_df['證券名稱'] = tpex_df.loc[:, ('名稱', '名稱')]
                new_tpex_df['外資買進股數'] = tpex_df.loc[:, ('外資及陸資', '買進股數')]
                new_tpex_df['外資賣出股數'] = tpex_df.loc[:, ('外資及陸資', '賣出股數')]
                new_tpex_df['外資買賣超股數'] = tpex_df.loc[:, ('外資及陸資', '買賣超股數')]
                new_tpex_df['投信買進股數'] = tpex_df.loc[:, ('投信', '買進股數')]
                new_tpex_df['投信賣出股數'] = tpex_df.loc[:, ('投信', '賣出股數')]
                new_tpex_df['投信買賣超股數'] = tpex_df.loc[:, ('投信', '買賣超股數')]
                new_tpex_df['自營商買賣超股數'] = tpex_df.loc[:, ('自營商', '買賣超股數')]
                new_tpex_df['自營商買進股數_自行買賣'] = tpex_df.loc[:, ('自營商(自行買賣)', '買進股數')]
                new_tpex_df['自營商賣出股數_自行買賣'] = tpex_df.loc[:, ('自營商(自行買賣)', '賣出股數')]
                new_tpex_df['自營商買賣超股數_自行買賣'] = tpex_df.loc[:, ('自營商(自行買賣)', '買賣超股數')]
                new_tpex_df['自營商買進股數_避險'] = tpex_df.loc[:, ('自營商(避險)', '買進股數')]
                new_tpex_df['自營商賣出股數_避險'] = tpex_df.loc[:, ('自營商(避險)', '賣出股數')]
                new_tpex_df['自營商買賣超股數_避險'] = tpex_df.loc[:, ('自營商(避險)', '買賣超股數')]
                new_tpex_df['三大法人買賣超股數'] = tpex_df.loc[:, ('三大法人買賣超 股數合計', '三大法人買賣超 股數合計')]
                tpex_df = new_tpex_df
            
            tpex_df = tpex_df.iloc[:-1] # 刪掉最後一個 row
            tpex_df.insert(0, '日期', cur_date)
            CrawlerTools.move_col(tpex_df, "自營商買賣超股數", "自營商買賣超股數_避險")
            tpex_df = CrawlerTools.remove_redundant_col(tpex_df, '三大法人買賣超股數')
            tpex_df = CrawlerTools.fill_nan(tpex_df, 0)
            tpex_df.to_csv(os.path.join(dir_path, f"tpex_{cur_date.strftime('%Y%m%d')}.csv"), index=False)
            cur_date += datetime.timedelta(days=1)
            
            crawl_cnt += 1
        
            if crawl_cnt == 100:
                print("Sleep 2 minutes...")
                crawl_cnt = 0
                time.sleep(120)
            else:
                delay = random.randint(1, 5)
                time.sleep(delay)

    
    def create_chip_db(self, db_path: str, table_name: str='chip'):
        """ 創建三大法人盤後籌碼db """
        
        conn = sqlite3.connect(db_path)
        cursor = conn.cursor()
        
        create_table_query = f""" 
        CREATE TABLE IF NOT EXISTS {table_name}(
            日期 TEXT NOT NULL,
            證券代號 TEXT NOT NULL,
            證券名稱 TEXT NOT NULL,
            外資買進股數 INT NOT NULL,
            外資賣出股數 INT NOT NULL,
            外資買賣超股數 INT NOT NULL,
            投信買進股數 INT NOT NULL,
            投信賣出股數 INT NOT NULL,
            投信買賣超股數 INT NOT NULL,
            自營商買進股數_自行買賣 INT,
            自營商賣出股數_自行買賣 INT,
            自營商買賣超股數_自行買賣 INT,
            自營商買進股數_避險 INT,
            自營商賣出股數_避險 INT,
            自營商買賣超股數_避險 INT,
            自營商買賣超股數 INT NOT NULL,
            三大法人買賣超股數 INT NOT NULL
        );
        """
        cursor.execute(create_table_query)
        
        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        if cursor.fetchall():
            print(f"Table {table_name} create successfully!")
        else:
            print(f"Table {table_name} create unsuccessfully!")
        
        conn.commit()
        conn.close()

    
    def add_to_sql(self, db_path: str, dir_path: str, table_name: str):
        """ 將資料夾中的所有 CSV 檔存入指定 SQLite 資料庫中的指定資料表。 """
        
        conn = sqlite3.connect(db_path)
        cnt = 0
        for file_name in os.listdir(dir_path):
            df = pd.read_csv(os.path.join(dir_path, file_name))
            df.to_sql(table_name, conn, if_exists='append', index=False)
            print(f"Save {file_name} into database.")
            cnt += 1
        conn.close()
        shutil.rmtree(dir_path)
        print(f"Total file: {cnt}")