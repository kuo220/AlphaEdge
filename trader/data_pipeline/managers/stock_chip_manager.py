import os
import shutil
import random
import sqlite3
import datetime
import time
from typing import List, Dict, Optional, Any

import pandas as pd
import ipywidgets as widgets
from IPython.display import display
from tqdm import tqdm_notebook

from trader.data_pipeline.managers.base import BaseDatabaseManager
from trader.data_pipeline.crawlers.chip_crawler import StockChipCrawler
from trader.data_pipeline.utils.crawler_utils import CrawlerUtils
from trader.data_pipeline.utils.sqlite_utils import SQLiteUtils
from trader.config import (
    CHIP_DB_PATH,
    CHIP_TABLE_NAME,
    CHIP_DOWNLOADS_PATH
)


class StockChipManager(BaseDatabaseManager):
    """ 管理上市與上櫃股票的三大法人籌碼資料，整合爬取、清洗與寫入資料庫等流程 """

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None
        self.connect()

        # Chip Crawler
        self.crawler: StockChipCrawler = StockChipCrawler()


    def connect(self) -> None:
        """ Connect to the Database """

        if self.conn is None:
            self.conn = sqlite3.connect(CHIP_DB_PATH)


    def disconnect(self) -> None:
        """ Disconnect the Database """

        if self.conn:
            self.conn.close()
            self.conn = None


    def create_db(self) -> None:
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
        self.disconnect()


    def add_to_db(self) -> None:
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
        self.disconnect()
        shutil.rmtree(CHIP_DOWNLOADS_PATH)
        print(f"Total file: {file_cnt}")


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
        self.add_to_db()


    def widget(self) -> None:
        """ Chip Database 資料更新的 UI """

        # Set update date
        date_picker_from: widgets.DatePicker = widgets.DatePicker(description='from', disabled=False)
        date_picker_to: widgets.DatePicker = widgets.DatePicker(description='to', disabled=False)

        if SQLiteUtils.check_table_exist(self.conn, CHIP_TABLE_NAME):
            date_picker_from.value = SQLiteUtils.get_table_latest_date(self.conn, CHIP_TABLE_NAME, '日期') + datetime.timedelta(days=1)
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

            dates: List[datetime.date] = CrawlerUtils.generate_date_range(start_date, end_date)

            if not dates:
                print("Date range is empty. Please check if the start date is earlier than the end date.")
                return

            print(f"Updating data for table '{CHIP_TABLE_NAME}' from {dates[0]} to {dates[-1]}...")
            self.update_table(dates)

        btn.on_click(onupdate)

        if SQLiteUtils.check_table_exist(self.conn, CHIP_TABLE_NAME):
            label: widgets.Label = widgets.Label(
                f"""
                {CHIP_TABLE_NAME} (from {SQLiteUtils.get_table_earliest_date(self.conn, CHIP_TABLE_NAME, '日期').strftime('%Y-%m-%d')} to
                {SQLiteUtils.get_table_latest_date(self.conn, CHIP_TABLE_NAME, '日期').strftime('%Y-%m-%d')})
                """
            )
        else:
            label: widgets.Label = widgets.Label(f"{CHIP_TABLE_NAME} (No table found)")

        items: List[widgets.Widget] = [date_picker_from, date_picker_to, btn]
        display(widgets.VBox([label, widgets.HBox(items)]))