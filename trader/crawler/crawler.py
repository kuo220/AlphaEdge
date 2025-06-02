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

from .chip_crawler import CrawlStockChip
from .tick_crawler import CrawlStockTick
from .html_crawler import CrawlHTML
from .qx_crawler import CrawlQuantX
from .shioaji_crawler import CrawlShioaji
from .crawler_tools import CrawlerTools


class Crawler:
    """
    Unified crawler interface for all data sources.

    Integrates multiple crawlers:
    - CrawlStockChip: Fetches institutional trading data (TWSE, TPEX).
    - CrawlHTML: Retrieves static HTML-based data such as stock lists.
    - CrawlShioaji: Gathers real-time tick data via Shioaji API.

    Provides centralized access to trigger updates or batch crawling across sources.
    Useful for pipeline automation or scheduled tasks.
    """

    def __init__(self):
        self.chip = CrawlStockChip()
        self.tick = CrawlStockTick()
        self.html = CrawlHTML()
        self.quantx = CrawlQuantX()
        self.shioaji = CrawlShioaji()
