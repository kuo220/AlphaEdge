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
from .chip_crawler import CrawlStockChip
from .html_crawler import CrawlHTML
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
        self.html = CrawlHTML()
        self.shioaji = CrawlShioaji()
