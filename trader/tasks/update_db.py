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
sys.path.append(str(Path(__file__).resolve().parents[1]))
from utils import ShioajiAccount
from data import (Data, SQLiteTools, TickDBManager)
from crawler import (Crawler, CrawlStockChip, CrawlStockTick, CrawlQuantX)
from config import QUANTX_DB_PATH


""" 
This script is used to update the Chip, Tick, and QuantX databases all at once. 
"""
if __name__ == "__main__":
    crawler = Crawler()
