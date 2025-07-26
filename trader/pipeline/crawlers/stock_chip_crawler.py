import datetime
import random
import time
import requests
from loguru import logger
import pandas as pd
from io import StringIO
from typing import Optional

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils.url_manager import URLManager
from trader.utils import TimeUtils


"""
三大法人爬蟲資料時間表：
1. TWSE
    - TWSE: 2012/5/2 開始提供（這邊從 2014/12/1 開始爬）
    - TWSE 改制時間: 2014/12/1, 2017/12/18
2. TPEX
    - TPEX: 2007/4/20 開始提供 (這邊從 2014/12/1 開始爬)
    - TPEX 改制時間: 2018/1/15
"""


class StockChipCrawler(BaseDataCrawler):
    """爬取上市、上櫃股票三大法人盤後籌碼"""

    def __init__(self):
        super().__init__()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Crawler"""
        pass

    def crawl(self, date: datetime.date) -> None:
        """Crawl TWSE & TPEX Chip Data"""

        self.crawl_twse_chip(date)
        self.crawl_tpex_chip(date)

    def crawl_twse_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """TWSE 三大法人單日爬蟲"""

        date_str: str = TimeUtils.format_date(date)
        readable_date: str = TimeUtils.format_date(date, sep="/")
        logger.info("* Start crawling TWSE institutional investors data...")
        logger.info(readable_date)

        twse_url: str = URLManager.get_url("TWSE_CHIP_URL", date=date_str)
        twse_response: requests.Response = RequestUtils.requests_get(twse_url)

        # 檢查是否為假日 or 單純網站還未更新
        try:
            twse_df: pd.DataFrame = pd.read_html(StringIO(twse_response.text))[0]
            if twse_df.empty:
                logger.info("No data in table. Possibly not yet updated.")
                return None
        except Exception as e:
            logger.info(f"{date} is a Holiday!")
            return None

        return twse_df

    def crawl_tpex_chip(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """TPEX 三大法人單日爬蟲"""

        date_str: str = TimeUtils.format_date(date, sep="/")
        logger.info("* Start crawling TPEX institutional investors data...")
        logger.info(date_str)

        tpex_url: str = URLManager.get_url("TPEX_CHIP_URL", date=date_str)
        logger.info(tpex_url)
        tpex_response: requests.Response = RequestUtils.requests_get(tpex_url)

        try:
            tpex_df: pd.DataFrame = pd.read_html(StringIO(tpex_response.text))[0]
        except Exception as e:
            logger.info(f"{date} is a Holiday!")
            return None

        try:
            tpex_df.drop(
                index=tpex_df.index[0], columns=tpex_df.columns[-1], inplace=True
            )
        except Exception:
            logger.info("TPEX table structure unexpected.")
            return None

        # 檢查是否為假日
        if tpex_df.empty:
            logger.info("No data in TPEX table. Possibly not updated yet.")
            return None
        if tpex_df.shape[0] == 1:
            logger.info(f"{date} is a Holiday!")
            return None

        return tpex_df