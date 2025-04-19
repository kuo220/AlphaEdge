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

crawler_path = Path.cwd().parents[0]
sys.path.append(str(crawler_path))

from utils import Crawler
from utils import Data


    
    
if __name__ == '__main__':
    db_path = os.path.join('..', 'Data', 'chip.db')
    dir_name = '三大法人盤後籌碼'
    dir_path = os.path.join('..', 'Downloads', dir_name)
    table_name = '三大法人盤後籌碼'
    
    crawler = Crawler().FromHTML
    crawler.create_chip_db(db_path)
    crawler.add_to_sql(db_path, dir_path, table_name)
    