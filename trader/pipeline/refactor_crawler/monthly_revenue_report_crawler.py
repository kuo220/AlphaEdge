import datetime
import os
import pickle
import random
import re
import shutil
import sqlite3
import sys
import time
import urllib.request
import warnings
import zipfile
from io import StringIO
from pathlib import Path
from typing import List, Optional, Any

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

from trader.pipeline.crawlers import BaseCrawler
from trader.pipeline.utils import URLManager
from trader.pipeline.utils.crawler_utils import CrawlerUtils
from trader.config import (
    CRAWLER_DOWNLOADS_PATH,
    FINANCIAL_REPORT_PATH,
    QUANTX_DB_PATH,
    CERTS_FILE_PATH
)


class MonthlyRevenueReportCrawler(BaseCrawler):
    """ TWSE & TPEX Monthly Revenue Report Crawler """

    def __init__(self):
        pass