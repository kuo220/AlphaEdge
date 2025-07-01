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

from ..chip_crawler import StockChipCrawler
from ..handlers import StockChipHandler
from ..utils.crawler_tools import CrawlerTools
from ..managers.url_manager import URLManager
from trader.data import SQLiteTools
from trader.config import (
    CHIP_DOWNLOADS_PATH,
    CHIP_DB_PATH,
    CHIP_TABLE_NAME
)


class StockChipManager:
    """ 管理上市與上櫃股票的三大法人籌碼資料，整合爬取、清洗與寫入資料庫等流程 """

    def __init__(self):
        # SQLite Connection
        self.conn: sqlite3.Connection = sqlite3.connect(CHIP_DB_PATH)

        # Chip Crawler
        self.crawler: StockChipCrawler = StockChipCrawler()

        # Chip Handler
        self.handler: StockChipHandler = StockChipHandler()


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
            twse_chip: Optional[pd.DataFrame] = self.crawler.crawl_twse_chip(date)
            tpex_chip: Optional[pd.DataFrame] = self.crawler.crawl_tpex_chip(date)

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
        self.handler.add_to_sql()


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