# Standard library imports
import sys
import os
import shutil
import random
import sqlite3
import datetime
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from io import StringIO

import numpy as np
import pandas as pd
import requests
import ipywidgets as widgets
from IPython.display import display
from fake_useragent import UserAgent
from tqdm import tqdm, tnrange, tqdm_notebook
from dateutil.rrule import rrule, DAILY, MONTHLY
from dateutil.relativedelta import relativedelta
from requests.exceptions import ReadTimeout, ConnectionError

from .crawler_tools import CrawlerTools
from .url_manager import URLManager
from trader.data import SQLiteTools
from trader.config import (
    CHIP_DOWNLOADS_PATH,
    CHIP_DB_PATH, 
    CHIP_TABLE_NAME
)



""" 
三大法人爬蟲資料時間表：
1. TWSE
    - TWSE: 2012/5/2 開始提供（這邊從 2014/12/1 開始爬）
    - TWSE 改制時間: 2014/12/1, 2017/12/18
2. TPEX
    - TPEX: 2007/4/20 開始提供 (這邊從 2014/12/1 開始爬)
    - TPEX 改制時間: 2018/1/15
"""


class CrawlStockChip:
    """ 爬取上市、上櫃股票三大法人盤後籌碼 """
    
    def __init__(self):
        
        # SQLite Connection
        self.conn: sqlite3.Connection = sqlite3.connect(CHIP_DB_PATH)
        
        # The date that TWSE chip data format was reformed
        self.twse_first_reform_date: datetime.date = datetime.date(2014, 12, 1)
        self.twse_second_reform_date: datetime.date = datetime.date(2017, 12, 18)
        
        # The date that TPEX chip data format was reformed
        self.tpex_first_reform_date: datetime.date = datetime.date(2018, 1, 15)
        
        # Generate downloads directory
        if not os.path.exists(CHIP_DOWNLOADS_PATH):
            os.makedirs(CHIP_DOWNLOADS_PATH)
    
    
    def crawl_twse_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ TWSE 三大法人單日爬蟲 """
        
        date_str: str = date.strftime("%Y%m%d")
        readable_date: str = date.strftime("%Y/%m/%d")
        print("* Start crawling TWSE institutional investors data...")
        print(readable_date)
        
        twse_url: str = URLManager.get_chip_url("TWSE_CHIP_URL", date=date_str)
        headers: Dict[str, str] = CrawlerTools.generate_random_header()
        twse_response: requests.Response = requests.get(twse_url, headers=headers)
        
        # 檢查是否為假日 or 單純網站還未更新
        try:
            twse_df: pd.DataFrame = pd.read_html(StringIO(twse_response.text))[0]
            if twse_df.empty:
                print("No data in table. Possibly not yet updated.")
                return None
        except Exception as e:
            print("It's Holiday!")
            return None
        
        twse_df.columns = twse_df.columns.droplevel(0)
        twse_df.insert(0, '日期', date)
        
        old_col_name: List[str] = ['自營商買進股數(自行買賣)', '自營商賣出股數(自行買賣)', '自營商買賣超股數(自行買賣)', 
                        '自營商買進股數(避險)', '自營商賣出股數(避險)', '自營商買賣超股數(避險)']
        
        new_col_name: List[str] = ['自營商買進股數_自行買賣', '自營商賣出股數_自行買賣', '自營商買賣超股數_自行買賣', 
                            '自營商買進股數_避險', '自營商賣出股數_避險', '自營商買賣超股數_避險']
        
        # 第一次格式改制前
        if date < self.twse_first_reform_date:
            CrawlerTools.move_col(twse_df, "自營商買賣超股數", "自營商賣出股數")
        # 第一次格式改制後，第二次格式改制前
        elif self.twse_first_reform_date <= date < self.twse_second_reform_date:
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
        twse_df.to_csv(os.path.join(CHIP_DOWNLOADS_PATH, f"twse_{date.strftime('%Y%m%d')}.csv"), index=False)
        
        return twse_df
    

    def crawl_tpex_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ TPEX 三大法人單日爬蟲 """
        
        date_str: str = date.strftime("%Y/%m/%d")
        print("* Start crawling TPEX institutional investors data...")
        print(date_str)
        
        tpex_url: str = URLManager.get_chip_url("TPEX_CHIP_URL", date=date_str)
        headers: Dict[str, str] = CrawlerTools.generate_random_header()
        tpex_response: requests.Response = requests.get(tpex_url, headers=headers)
        
        try:
            tpex_df: pd.DataFrame = pd.read_html(StringIO(tpex_response.text))[0]
        except Exception as e:
            print(f"Error crawling TPEX table: {e}")
            return None
        
        try:
            tpex_df.drop(index=tpex_df.index[0], columns=tpex_df.columns[-1], inplace=True)
        except Exception:
            print("TPEX table structure unexpected.")
            return None
    
        # 檢查是否為假日
        if tpex_df.empty:
            print("No data in TPEX table. Possibly not updated yet.")
            return None
        if tpex_df.shape[0] == 1:
            print("It's Holiday!")
            return None

        if isinstance(tpex_df.columns, pd.MultiIndex):
            tpex_df.columns = tpex_df.columns.droplevel(0)
            
        new_col_name: List[str] = [
            '證券代號', '證券名稱', '外資買進股數', '外資賣出股數', '外資買賣超股數',
            '投信買進股數', '投信賣出股數', '投信買賣超股數', '自營商買賣超股數',
            '自營商買進股數_自行買賣', '自營商賣出股數_自行買賣', '自營商買賣超股數_自行買賣',
            '自營商買進股數_避險', '自營商賣出股數_避險', '自營商買賣超股數_避險', '三大法人買賣超股數'
        ]
        
        # 格式改制前
        if date < self.tpex_first_reform_date:
            old_col_name: List[str] = [
                '代號', '名稱', '外資 及陸資 買股數', '外資 及陸資 賣股數', '外資 及陸資 淨買股數',
                '投信 買股數', '投信 賣股數', '投信 淨買股數', '自營商 淨買股數',
                '自營商 (自行買賣) 買股數', '自營商 (自行買賣) 賣股數', '自營商 (自行買賣) 淨買股數',
                '自營商 (避險) 買股數', '自營商 (避險) 賣股數', '自營商 (避險) 淨買股數', '三大法人 買賣超股數'
            ]
            
            tpex_df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)
        # 格式改制後
        else:
            new_tpex_df: pd.DataFrame = pd.DataFrame(columns=new_col_name)
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
        tpex_df.insert(0, '日期', date)
        CrawlerTools.move_col(tpex_df, "自營商買賣超股數", "自營商買賣超股數_避險")
        tpex_df = CrawlerTools.remove_redundant_col(tpex_df, '三大法人買賣超股數')
        tpex_df = CrawlerTools.fill_nan(tpex_df, 0)
        tpex_df.to_csv(os.path.join(CHIP_DOWNLOADS_PATH, f"tpex_{date.strftime('%Y%m%d')}.csv"), index=False)
        
        return tpex_df
    

    def crawl_twse_chip_range(
        self, 
        start_date: datetime.date, 
        end_date: datetime.date=datetime.date.today()
    ) -> None:
        """ TWSE 三大法人日期範圍爬蟲 """
        
        cur_date: datetime.date = start_date
        
        # if crawl_cnt == 100, then sleep
        crawl_cnt: int = 0

        print("* Start crawling TWSE institutional investors data...")
        while cur_date <= end_date:
            print(cur_date.strftime("%Y/%m/%d"))
            self.crawl_twse_chip(cur_date)
            cur_date += datetime.timedelta(days=1)
            crawl_cnt += 1
            
            if crawl_cnt == 100:
                print("Sleep 2 minutes...")
                crawl_cnt = 0
                time.sleep(120)
            else:
                delay = random.randint(1, 5)
                time.sleep(delay)
            
              
    def crawl_tpex_chip_range(
        self, 
        start_date: datetime.date, 
        end_date: datetime.date=datetime.date.today()
    ) -> None:
        """ TPEX 三大法人日期範圍爬蟲  """
        
        cur_date: datetime.date = start_date
        
        # if crawl_cnt == 100, then sleep
        crawl_cnt: int = 0
        
        print("* Start crawling TPEX institutional investors data...")
        while cur_date <= end_date:
            print(cur_date.strftime("%Y/%m/%d"))
            self.crawl_tpex_chip(cur_date)
            cur_date += datetime.timedelta(days=1)
            crawl_cnt += 1
        
            if crawl_cnt == 100:
                print("Sleep 2 minutes...")
                crawl_cnt = 0
                time.sleep(120)
            else:
                delay = random.randint(1, 5)
                time.sleep(delay)
        
    
    def update_table(self, dates: List[datetime.date]) -> None:
        """ Chip Database 資料更新 """
        
        print(f'* Start updating chip data')
                
        progress: Any = tqdm_notebook(dates)        
        crawl_cnt: int = 0
        
        # Crawl chip data
        for date in progress:
            print(f"Crawling {date}")
            
            progress.set_description(f"Crawl {CHIP_TABLE_NAME} {date}")

            # Crawl Chip Data
            twse_chip: Optional[pd.DataFrame] = self.crawl_twse_chip(date)
            tpex_chip: Optional[pd.DataFrame] = self.crawl_tpex_chip(date)
            
            if twse_chip is None and tpex_chip is None:
                print("No data found. It might be a holiday.")
         
            crawl_cnt += 1
            if crawl_cnt == 100:
                print("Sleep 2 minutes...")
                crawl_cnt = 0
                time.sleep(120)
            else:
                delay = random.randint(1, 5)
                time.sleep(delay)
        
        # Save chip data to database
        self.add_to_sql()

                    
    def widget(self) -> None:
        """ Chip Database 資料更新的 UI """
        
        # Set update date
        date_picker_from: widgets.DatePicker = widgets.DatePicker(description='from', disabled=False)
        date_picker_to: widgets.DatePicker = widgets.DatePicker(description='to', disabled=False)

        if SQLiteTools.check_table_exist(self.conn, CHIP_TABLE_NAME):
            date_picker_from.value = SQLiteTools.get_table_latest_date(self.conn, CHIP_TABLE_NAME, '日期') + datetime.timedelta(days=1)
        date_picker_to.value = datetime.datetime.now().date()
        
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
            
            print(f"Updating data for table '{CHIP_TABLE_NAME}' from {dates[0]} to {dates[-1]}...")
            self.update_table(dates)
            
        btn.on_click(onupdate)
        
        if SQLiteTools.check_table_exist(self.conn, CHIP_TABLE_NAME):
            label: widgets.Label = widgets.Label(f""" 
                                  {CHIP_TABLE_NAME} (from {SQLiteTools.get_table_earliest_date(self.conn, CHIP_TABLE_NAME, '日期').strftime('%Y-%m-%d')} to 
                                  {SQLiteTools.get_table_latest_date(self.conn, CHIP_TABLE_NAME, '日期').strftime('%Y-%m-%d')})
                                  """)
        else:
            label: widgets.Label = widgets.Label(f"{CHIP_TABLE_NAME} (No table found)")
        
        items: List[widgets.Widget] = [date_picker_from, date_picker_to, btn]
        display(widgets.VBox([label, widgets.HBox(items)]))

    
    def create_chip_db(self) -> None:
        """ 創建三大法人盤後籌碼db """
        
        cursor: sqlite3.Cursor = self.conn.cursor()
        
        create_table_query: str = f""" 
        CREATE TABLE IF NOT EXISTS {CHIP_TABLE_NAME}(
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
        cursor.execute(f"PRAGMA table_info('{CHIP_TABLE_NAME}')")
        if cursor.fetchall():
            print(f"Table {CHIP_TABLE_NAME} create successfully!")
        else:
            print(f"Table {CHIP_TABLE_NAME} create unsuccessfully!")
        
        self.conn.commit()
        self.conn.close()

    
    def add_to_sql(self) -> None:
        """ 將資料夾中的所有 CSV 檔存入指定 SQLite 資料庫中的指定資料表。 """
        
        file_cnt: int = 0
        for file_name in os.listdir(CHIP_DOWNLOADS_PATH):
            # Skip non-CSV files
            if not file_name.endswith('.csv'):
                continue
            df: pd.DataFrame = pd.read_csv(os.path.join(CHIP_DOWNLOADS_PATH, file_name))
            df.to_sql(CHIP_TABLE_NAME, self.conn, if_exists='append', index=False)
            print(f"Save {file_name} into database.")
            file_cnt += 1
        self.conn.close()
        shutil.rmtree(CHIP_DOWNLOADS_PATH)
        print(f"Total file: {file_cnt}")