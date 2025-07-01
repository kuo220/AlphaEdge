import datetime
import os
import pickle
import random
import re
import shutil
import sqlite3
import time
import urllib.request
import warnings
from io import StringIO
from pathlib import Path
from typing import List
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, rrule
from fake_useragent import UserAgent
from IPython.display import display
import ipywidgets as widgets
from requests.exceptions import ConnectionError, ReadTimeout
from tqdm import tqdm, tnrange, tqdm_notebook
import zipfile

from .chip_crawler import StockChipCrawler
from .tick_crawler import StockTickCrawler
from .stock_info_crawler import StockInfoCrawler
from .qx_crawler import QuantXCrawler
from .shioaji_crawler import ShioajiCrawler
from .utils.crawler_tools import CrawlerTools


class Crawler:
    """
    Unified crawler interface for all data sources.

    Integrates multiple crawlers:
    - StockChipCrawler: Fetches institutional trading data (TWSE, TPEX).
    - StockInfoCrawler: Retrieves static HTML-based data such as stock lists.
    - ShioajiCrawler: Gathers real-time tick data via Shioaji API.

    Provides centralized access to trigger updates or batch crawling across sources.
    Useful for pipeline automation or scheduled tasks.
    """

    def __init__(self):
        self.chip: StockChipCrawler = StockChipCrawler()
        self.tick: StockTickCrawler = StockTickCrawler()
        self.html: StockInfoCrawler = StockInfoCrawler()
        self.quantx: QuantXCrawler = QuantXCrawler()
        self.shioaji: ShioajiCrawler = ShioajiCrawler()
