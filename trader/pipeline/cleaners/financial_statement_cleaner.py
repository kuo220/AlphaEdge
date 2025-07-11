import datetime
import pandas as pd
import requests
from io import StringIO
from pathlib import Path
from loguru import logger
from typing import List, Dict, Optional

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.crawlers.utils.payload import Payload
from trader.pipeline.utils import URLManager, MarketType
from trader.pipeline.utils.data_utils import DataUtils
from trader.config import FINANCIAL_STATEMENT_PATH


class FinancialStatementCleaner(BaseDataCleaner):
    """ Cleaner for quarterly financial Statement """

    def __init__(self):
        super().__init__()

        # Financial Statement Directories Set Up
        self.fs_dir: Path = FINANCIAL_STATEMENT_PATH
        self.balance_sheet_dir: Path = self.fs_dir / "balance_sheet"
        self.income_statement_dir: Path = self.fs_dir / "income_statement"
        self.cash_flow_statement_dir: Path = self.fs_dir / "cash_flow_statement"
        self.equity_changes_statement_dir: Path = self.fs_dir / "equity_changes_statement"


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Cleaner """

        # Create Downloads Directory For Financial Reports
        self.fs_dir.mkdir(parents=True, exist_ok=True)
        self.balance_sheet_dir.mkdir(parents=True, exist_ok=True)
        self.income_statement_dir.mkdir(parents=True, exist_ok=True)
        self.cash_flow_statement_dir.mkdir(parents=True, exist_ok=True)
        self.equity_changes_statement_dir.mkdir(parents=True, exist_ok=True)


    def clean_balance_sheet(
        self,
        df_list: List[pd.DataFrame],
        date: datetime.date,
        season: int
    ) -> pd.DataFrame:
        """ Cleaner Balance Sheet (資產負債表) """
        """
        資料區間
        上市: 民國 79 (1990) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

