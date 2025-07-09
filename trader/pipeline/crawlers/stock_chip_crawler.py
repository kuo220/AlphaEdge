import os
import random
import sqlite3
import datetime
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from io import StringIO

import pandas as pd
import requests

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.utils.crawler_utils import CrawlerUtils, URLManager
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


class StockChipCrawler(BaseDataCrawler):
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
        self.chip_dir: Path = CHIP_DOWNLOADS_PATH
        self.setup()


    def crawl(self, date: datetime.date) -> None:
        """ Crawl TWSE & TPEX Chip Data """

        self.crawl_twse_chip(date)
        self.crawl_tpex_chip(date)


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Crawler """

        # Generate downloads directory
        self.chip_dir.mkdir(parents=True, exist_ok=True)


    def crawl_twse_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ TWSE 三大法人單日爬蟲 """

        date_str: str = CrawlerUtils.format_date(date)
        readable_date: str = CrawlerUtils.format_date(date, sep="/")
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

        return twse_df


    def crawl_tpex_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ TPEX 三大法人單日爬蟲 """

        date_str: str = CrawlerUtils.format_date(date, sep="/")
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

        return tpex_df


    # TODO: Refactor 成 ETL 架構後無法使用以下兩個 methods
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