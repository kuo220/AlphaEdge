import datetime
from io import StringIO
from pathlib import Path
from typing import Optional

import pandas as pd
import requests
from loguru import logger

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils import URLManager
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils

"""
TWSE 網站提供資料日期：
1. 2004/2/11 ~ present

TPEX 網站提供資料日期：
1. 上櫃資料從 96/7/2 以後才提供
2. 從 109/4/30 開始後 csv 檔的 column 不一樣
"""


class StockPriceCrawler(BaseDataCrawler):
    """爬取上市、上櫃公司的股票收盤行情（OHLC、成交量）"""

    def __init__(self):
        super().__init__()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Crawler"""
        pass

    def crawl(self, date: datetime.date) -> None:
        """Crawl Price Data"""

        twse_price_df: pd.DataFrame = self.crawl_twse_price(date)
        tpex_price_df: pd.DataFrame = self.crawl_tpex_price(date)

    def crawl_twse_price(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """爬取上市公司股票收盤行情"""
        """
        TWSE 網站提供資料日期：
        1. 2004/2/11 ~ present
        """

        logger.info(f"* Start crawling TWSE Price: {date}")

        date_str: str = TimeUtils.format_date(date, sep="")
        url: str = URLManager.get_url(
            "TWSE_CLOSING_QUOTE_URL",
            date=date_str,
        )

        try:
            res: Optional[requests.Response] = RequestUtils.requests_get(url)
        except Exception as e:
            logger.warning(f"Cannot get stock price at {date}")
            logger.info(e)
            return None

        # 檢查是否為假日
        try:
            df: pd.DataFrame = pd.read_html(StringIO(res.text))[-1]
        except Exception as e:
            logger.info(f"{date} is a Holiday!")
            return None

        return df

    def crawl_tpex_price(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """爬取上櫃公司股票收盤行情"""

        """
        1. 上櫃資料從 96/7/2 以後才提供
        2. 從 109/4/30 開始後 csv 檔的 column 不一樣
        """

        logger.info(f"* Start crawling TPEX Price: {date}")

        date_str: str = TimeUtils.format_date(date, sep="/")
        url: str = URLManager.get_url(
            "TPEX_CLOSING_QUOTE_URL",
            date=date_str,
        )

        try:
            res: Optional[requests.Response] = RequestUtils.requests_get(url)
        except Exception as e:
            logger.warning(f"Cannot get stock price at {date}")
            logger.info(e)
            return None

        # 檢查是否為假日
        try:
            df: pd.DataFrame = pd.read_html(StringIO(res.text))[0]
        except Exception as e:
            logger.info(f"{date} is a Holiday!")
            return None

        return df
