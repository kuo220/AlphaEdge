import datetime
from io import StringIO
from loguru import logger
from pathlib import Path
from typing import List, Optional
import pandas as pd
import requests

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils import URLManager, MarketType, FileEncoding
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import MONTHLY_REVENUE_REPORT_PATH


class MonthlyRevenueReporterCleaner(BaseDataCleaner):
    """TWSE & TPEX Monthly Revenue Report Crawler"""

    def __init__(self):
        # Downloads Directory
        self.mrr_dir: Path = MONTHLY_REVENUE_REPORT_PATH

    def setup(self):
        """Set Up the Config of Cleaner"""
        # Create the tick downloads directory
        self.mrr_dir.mkdir(parents=True, exist_ok=True)

    def clean_monthly_revenue(self, df_list: List[pd.DataFrame], date: datetime.date):
        """Clean TWSE Monthly Revenue Report"""
        """
        資料格式
        上市: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
        """

        new_df_list: List[pd.DataFrame] = []
        for df in df_list:
            if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
                df.columns = df.columns.droplevel(0)
                new_df_list.append(df)
