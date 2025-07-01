import sys
from pathlib import Path
import os
import sqlite3
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")

import ipywidgets as widgets
from IPython.display import display
from tqdm import tqdm
from tqdm import tnrange, tqdm_notebook
from dateutil.rrule import rrule, DAILY, MONTHLY
from dateutil.relativedelta import relativedelta

from trader.utils import ShioajiAccount
from trader.data import (Data, SQLiteTools, TickDBTools, TickDBManager)
from trader.crawler import (Crawler, StockChipCrawler, StockTickCrawler, QuantXCrawler)
from trader.config import QUANTX_DB_PATH


"""
This script is used to update the Chip, Tick, and QuantX databases all at once.
"""

# TODO: 設定各資料庫更新的日期區間

if __name__ == "__main__":
    crawler = Crawler()
    
    chip_crawler = crawler.chip
    tick_crawler = crawler.tick
    qx_crawler = crawler.quantx