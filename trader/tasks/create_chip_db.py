import sys
import os
from pathlib import Path
import sqlite3
import requests
import datetime
import pandas as pd
from io import StringIO
from fake_useragent import UserAgent
import time
from loguru import logger
import random
sys.path.append(str(Path(__file__).resolve().parents[1]))
from crawler import CrawStockChip
    
    
if __name__ == '__main__':
    db_path = Path(__file__).resolve().parents[1] / 'database' / 'chip.db'
    dir_name = 'chip'
    dir_path = Path(__file__).resolve().parents[1] / 'crawler' / 'downloads' / dir_name
    table_name = 'chip'
    
    crawler = CrawStockChip()
    crawler.create_chip_db(db_path)
    crawler.add_to_sql(db_path, dir_path, table_name)
    