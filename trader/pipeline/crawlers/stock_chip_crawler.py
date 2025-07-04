import os
import random
import sqlite3
import datetime
import time
from typing import List, Dict, Optional, Any
from io import StringIO

import pandas as pd
import requests

from trader.pipeline.crawlers import BaseCrawler
from trader.pipeline.utils import CrawlerUtils, URLManager
from trader.config import (
    CHIP_DOWNLOADS_PATH,
    CHIP_DB_PATH,
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


class StockChipCrawler(BaseCrawler):
    """ 爬取上市、上櫃股票三大法人盤後籌碼 """

    def __init__(self):
        super().__init__()

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


    def crawl(self, date: datetime.date) -> None:
        """ Crawl TWSE & TPEX Chip Data """

        self.crawl_twse_chip(date)
        self.crawl_tpex_chip(date)


    def crawl_twse_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ TWSE 三大法人單日爬蟲 """

        date_str: str = date.strftime("%Y%m%d")
        readable_date: str = date.strftime("%Y/%m/%d")
        print("* Start crawling TWSE institutional investors data...")
        print(readable_date)

        twse_url: str = URLManager.get_url("TWSE_CHIP_URL", date=date_str)
        headers: Dict[str, str] = CrawlerUtils.generate_random_header()
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
            CrawlerUtils.move_col(twse_df, "自營商買賣超股數", "自營商賣出股數")
        # 第一次格式改制後，第二次格式改制前
        elif self.twse_first_reform_date <= date < self.twse_second_reform_date:
            CrawlerUtils.move_col(twse_df, "自營商買賣超股數", "自營商買賣超股數(避險)")
            twse_df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)
        # 第二次格式改制後
        else:
            twse_df['外資買進股數'] = twse_df['外陸資買進股數(不含外資自營商)'] + twse_df['外資自營商買進股數']
            twse_df['外資賣出股數'] = twse_df['外陸資賣出股數(不含外資自營商)'] + twse_df['外資自營商賣出股數']
            twse_df['外資買賣超股數'] = twse_df['外陸資買賣超股數(不含外資自營商)'] + twse_df['外資自營商買賣超股數']
            twse_df.drop(columns=['外陸資買進股數(不含外資自營商)', '外陸資賣出股數(不含外資自營商)', '外陸資買賣超股數(不含外資自營商)',
                                '外資自營商買進股數', '外資自營商賣出股數', '外資自營商買賣超股數'], inplace=True)
            CrawlerUtils.move_col(twse_df, '外資買進股數', '證券名稱')
            CrawlerUtils.move_col(twse_df, '外資賣出股數', '外資買進股數')
            CrawlerUtils.move_col(twse_df, '外資買賣超股數', '外資賣出股數')
            CrawlerUtils.move_col(twse_df, "自營商買賣超股數", "自營商買賣超股數(避險)")
            twse_df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)

        twse_df = CrawlerUtils.remove_redundant_col(twse_df, '三大法人買賣超股數')
        twse_df = CrawlerUtils.fill_nan(twse_df, 0)
        twse_df.to_csv(os.path.join(CHIP_DOWNLOADS_PATH, f"twse_{date.strftime('%Y%m%d')}.csv"), index=False)

        return twse_df


    def crawl_tpex_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ TPEX 三大法人單日爬蟲 """

        date_str: str = date.strftime("%Y/%m/%d")
        print("* Start crawling TPEX institutional investors data...")
        print(date_str)

        tpex_url: str = URLManager.get_url("TPEX_CHIP_URL", date=date_str)
        headers: Dict[str, str] = CrawlerUtils.generate_random_header()
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
        CrawlerUtils.move_col(tpex_df, "自營商買賣超股數", "自營商買賣超股數_避險")
        tpex_df = CrawlerUtils.remove_redundant_col(tpex_df, '三大法人買賣超股數')
        tpex_df = CrawlerUtils.fill_nan(tpex_df, 0)
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