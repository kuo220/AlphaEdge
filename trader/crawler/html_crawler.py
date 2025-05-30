# Standard library imports
import datetime
import os
import pickle
import random
import re
import shutil
import sqlite3
import time
import urllib.request
from io import StringIO
from pathlib import Path
from typing import List

# Third party imports
import ipywidgets as widgets
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, rrule
from fake_useragent import UserAgent
from IPython.display import display
from requests.exceptions import ConnectionError, ReadTimeout
from tqdm import tqdm, tnrange, tqdm_notebook
import warnings
import zipfile


class CrawlHTML:
    """ HTML Crawler """
    
    @staticmethod
    def crawl_stock_list() -> List[str]:
        """ 爬取上市櫃公司的股票代號 """
        
        # 取得上市公司代號
        twse_code_url = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=1&industry_code=&Page=1&chklike=Y"
        response = requests.get(twse_code_url)
        twse_list = pd.read_html(StringIO(response.text))[0]
        twse_list.columns = twse_list.iloc[0, :]
        twse_list = twse_list.iloc[1:]['有價證券代號'].tolist()

        print(f"* Len of listed company in TWSE: {len(twse_list)}")

        # 取得上櫃公司代號
        tpex_code_url = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=2&issuetype=4&industry_code=&Page=1&chklike=Y"

        response = requests.get(tpex_code_url)
        tpex_list = pd.read_html(StringIO(response.text))[0]
        tpex_list.columns = tpex_list.iloc[0, :]
        tpex_list = tpex_list.iloc[1:]['有價證券代號'].tolist()

        print(f"* Len of listed company in OTC: {len(tpex_list)}")

        # Combine two list and sort
        stock_list = sorted(twse_list + tpex_list)
        
        print(f"* Len of listed company in market: {len(stock_list)}")
        return stock_list