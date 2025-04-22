import os
import shutil
import numpy as np
import pandas as pd
import datetime
import time
import re
import random
import requests
from pathlib import Path
from requests.exceptions import ReadTimeout
from requests.exceptions import ConnectionError
import shutil
import zipfile
import pickle
import warnings
import sqlite3
from bs4 import BeautifulSoup
from io import StringIO
from typing import List
import urllib.request
import ipywidgets as widgets
from IPython.display import display
from fake_useragent import UserAgent
from tqdm import tqdm
from tqdm import tnrange, tqdm_notebook
from dateutil.rrule import rrule, DAILY, MONTHLY
from dateutil.relativedelta import relativedelta


class CrawlHTML:
    """ HTML Crawler """
        
    def crawl_stock_list(self) -> List[str]:
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