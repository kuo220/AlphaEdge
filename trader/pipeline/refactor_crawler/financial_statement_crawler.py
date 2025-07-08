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
from typing import List, Dict, Optional, Any
from dataclasses import dataclass, asdict

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

from trader.pipeline.crawlers.base import BaseCrawler
from trader.pipeline.utils import URLManager
from trader.pipeline.utils.crawler_utils import CrawlerUtils
from trader.config import (
    CRAWLER_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_PATH,
    QUANTX_DB_PATH,
    CERTS_FILE_PATH
)


@dataclass
class FinancialStatementPayload:
    """ 財報查詢用 payload 結構 """

    firstin: Optional[str] = None               # default: 1
    TYPEK: Optional[str] = None                 # {sii: 上市, otc: 上櫃, all: 全部}
    year: Optional[str] = None                  # ROC year
    season: Optional[str] = None                # Season
    co_id: Optional[str] = None                 # Stock code


    def convert_to_clean_dict(self) -> Dict[str, str]:
        """ Return a dict with all non-None fields """
        return {key: value for key, value in asdict(self).items() if value is not None}


class FinancialStatementCrawler(BaseCrawler):
    """ Crawler for quarterly financial reports """
    """
    目前公開資訊觀測站（mopsov.twse.com）提供的財務報表格式有更改
    1. 舊制：2013 ~ 2018
    2. 新制：2019 ~ present
    """

    def __init__(self):
        super().__init__()

        # Payload For HTTP Requests
        self.payload: FinancialStatementPayload = None

        # Financial Statement Directories Set Up
        self.fr_dir: Path = FINANCIAL_STATEMENT_PATH
        self.balance_sheet_dir: Path = self.fr_dir / "balance_sheet"
        self.income_statement_dir: Path = self.fr_dir / "income_statement"
        self.cash_flow_statement_dir: Path = self.fr_dir / "cash_flow_statement"
        self.equity_changes_statement_dir: Path = self.fr_dir / "equity_changes_statement"


    def crawl(self, *args, **kwargs) -> None:
        """ Crawl Financial Report (Include 4 reports) """
        pass


    def setup(self, *args, **kwargs):
        """ Set Up the Config of Crawler """

        # Create Downloads Directory For Financial Reports
        self.fr_dir.mkdir(parents=True, exist_ok=True)
        self.balance_sheet_dir.mkdir(parents=True, exist_ok=True)
        self.income_statement_dir.mkdir(parents=True, exist_ok=True)
        self.cash_flow_statement_dir.mkdir(parents=True, exist_ok=True)
        self.equity_changes_statement_dir.mkdir(parents=True, exist_ok=True)


    def crawl_balance_sheet(self):
        """ Crawl Balance Sheet (資產負債表) """
        pass


    def crawl_comprehensive_income(self):
        """ Crawl Statement of Comprehensive Income (綜合損益表) """
        pass


    def crawl_cash_flow(self):
        """ Crawl Cash Flow Statement (現金流量表) """
        pass


    def crawl_equity_changes(self):
        """ Crawl Statement of Changes in Equity (權益變動表) """
        pass