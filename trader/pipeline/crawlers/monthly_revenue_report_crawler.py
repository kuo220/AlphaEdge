import datetime
from io import StringIO
from loguru import logger
from pathlib import Path
from typing import List, Optional
import pandas as pd
import requests

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils import (
    URLManager,
    MarketType,
    FileEncoding
)
from trader.pipeline.utils.data_utils import DataUtils
from trader.config import MONTHLY_REVENUE_REPORT_PATH


class MonthlyRevenueReportCrawler(BaseDataCrawler):
    """ TWSE & TPEX Monthly Revenue Report Crawler """

    def __init__(self):

        # Downloads Directory
        self.mrr_dir: Path = MONTHLY_REVENUE_REPORT_PATH

        # Market Type
        self.twse_market_types: List[MarketType] = [MarketType.SII0, MarketType.SII1]
        self.tpex_market_types: List[MarketType] = [MarketType.OTC0, MarketType.OTC1]


    def crawl(self, date: datetime.date) -> Optional[List[pd.DataFrame]]:
        """ Crawl Data """

        twse_df: List[pd.DataFrame] = self.crawl_twse_monthly_revenue(date)
        tpex_df: List[pd.DataFrame] = self.crawl_tpex_monthly_revenue(date)

        return twse_df + tpex_df


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Crawler """

        # Create the tick downloads directory
        self.mrr_dir.mkdir(parents=True, exist_ok=True)


    def crawl_twse_monthly_revenue(self, date: datetime.date) -> Optional[List[pd.DataFrame]]:
        """ Crawl TWSE Monthly Revenue Report """

        df_list: List[pd.DataFrame] = []

        for market_type in self.twse_market_types:
            url: str = URLManager.get_url(
                "TWSE_MONTHLY_REVENUE_REPORT_URL",
                roc_year=DataUtils.convert_ad_to_roc_year(date.year),
                month=date.month,
                market_type=market_type.value
            )

            try:
                res: requests.Response = RequestUtils.requests_get(url)
                res.encoding = FileEncoding.BIG5.value
            except Exception as e:
                logger.info(f"* WARN: Cannot get TWSE Monthly Revenue Report at {date}")
                logger.info(e)
                return None

            dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
            df_list.extend(dfs)

        return df_list


    def crawl_tpex_monthly_revenue(self, date: datetime.date) -> Optional[List[pd.DataFrame]]:
        """ Crawl TPEX Monthly Revenue Report """

        df_list: List[pd.DataFrame] = []

        for market_type in self.tpex_market_types:
            url: str = URLManager.get_url(
                "TPEX_MONTHLY_REVENUE_REPORT_URL",
                roc_year=DataUtils.convert_ad_to_roc_year(date.year),
                month=date.month,
                market_type=market_type.value
            )

            try:
                res: requests.Response = RequestUtils.requests_get(url)
                res.encoding = FileEncoding.BIG5.value
            except Exception as e:
                logger.info(f"* WARN: Cannot get TWSE Monthly Revenue Report at {date}")
                logger.info(e)
                return None

            dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
            df_list.extend(dfs)

        return df_list
