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
import sqlite3
import shioaji as sj
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
from .crawler_tools import CrawlerTools


""" 
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today
"""

class CrawlStockTick:
    """ 爬取上市櫃股票 ticks """
    
    def __init__(self):
        pass