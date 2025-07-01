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

from ..utils.crawler_tools import CrawlerTools
from ..managers.url_manager import URLManager
from trader.data import SQLiteTools
from trader.config import (
    CHIP_DOWNLOADS_PATH,
    CHIP_DB_PATH,
    CHIP_TABLE_NAME
)


class StockChipHandler:
    """ 將爬取後的上市、上櫃股票三大法人盤後籌碼資料存入 Database """

    def __init__(self):
        # SQLite Connection
        self.conn: sqlite3.Connection = sqlite3.connect(CHIP_DB_PATH)


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