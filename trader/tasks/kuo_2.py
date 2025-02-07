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


def generate_random_header():
    ua = UserAgent()
    user_agent = ua.random
    headers = {'Accept': '*/*', 'Connection': 'keep-alive',
            'User-Agent': user_agent}
    return headers


def move_col(df: pd.DataFrame, col_name: str, ref_col_name: str):
    """ 移動 columns 位置"""
    col_data = df.pop(col_name)
    df.insert(df.columns.get_loc(ref_col_name) + 1, col_name, col_data)
    
    
if __name__ == '__main__':
    dir_path = Path(__file__).resolve().parent.parent / 'Downloads' / 'tmp'
    print(dir_path)
    
    for file in os.listdir(dir_path):
        file_path = dir_path / file
        
        df = pd.read_csv(file_path)
        move_col(df, "自營商買賣超股數", "自營商買賣超股數(避險)")
        df.to_csv(file_path, index=False)