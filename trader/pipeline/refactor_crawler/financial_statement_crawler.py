import datetime
import pandas as pd
import requests
import random
import shutil
from io import StringIO
from pathlib import Path
import logging
from dataclasses import dataclass, asdict
from typing import List, Dict, Optional, Any

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.utils import URLManager
from trader.pipeline.utils import MarketType
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


class FinancialStatementCrawler(BaseDataCrawler):
    """ Crawler for quarterly financial reports """
    """
    目前公開資訊觀測站（mopsov.twse.com）提供的財務報表格式有更改
    1. 舊制：2013 ~ 2018
    2. 新制：2019 ~ present
    """

    def __init__(self):
        super().__init__()

        # Financial Statement Directories Set Up
        self.fr_dir: Path = FINANCIAL_STATEMENT_PATH
        self.balance_sheet_dir: Path = self.fr_dir / "balance_sheet"
        self.income_statement_dir: Path = self.fr_dir / "income_statement"
        self.cash_flow_statement_dir: Path = self.fr_dir / "cash_flow_statement"
        self.equity_changes_statement_dir: Path = self.fr_dir / "equity_changes_statement"

        # Payload For HTTP Requests
        self.payload: FinancialStatementPayload = None
        self.market_types: List[MarketType] = [MarketType.SII, MarketType.OTC]

        self.setup()


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

        # Set Up Payload
        self.payload = FinancialStatementPayload(
            firstin="1",
            TYPEK="sii",
            year="102",
            season="1",
            co_id=None
        )


    def crawl_balance_sheet(self, date: datetime.date, season: int) -> Optional[List[pd.DataFrame]]:
        """ Crawl Balance Sheet (資產負債表) """
        """
        資料區間
        上市: 民國 79 (1990) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        roc_year: str = CrawlerUtils.convert_to_roc_year(date.year)
        self.payload.year = roc_year
        self.payload.season=season

        balance_sheet_url: str = URLManager.get_url("BALANCE_SHEET_URL")
        df_list: List[pd.DataFrame] = []

        for market_type in self.market_types:
            self.payload.TYPEK = market_type.value

            try:
                res: Optional[requests.Response] = requests.post(balance_sheet_url, data=self.payload.convert_to_clean_dict())
                logging.info(f"上市 URL: {balance_sheet_url}")
            except Exception as e:
                logging.info(f"* WARN: Cannot get balance sheet at {date}")
                logging.info(e)

            try:
                dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
                df_list.extend(dfs)
            except Exception as e:
                logging.info("No tables found")
                logging.info(e)
                return None

        return df_list


    def crawl_comprehensive_income(self, date: datetime.date, season: int) -> Optional[List[pd.DataFrame]]:
        """ Crawl Statement of Comprehensive Income (綜合損益表) """
        """
        資料區間
        上市: 民國 77 (1988) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        roc_year: str = CrawlerUtils.convert_to_roc_year(date.year)


    def crawl_cash_flow(self):
        """ Crawl Cash Flow Statement (現金流量表) """
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """
        pass


    def crawl_equity_changes(self):
        """ Crawl Statement of Changes in Equity (權益變動表) """
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """
        pass