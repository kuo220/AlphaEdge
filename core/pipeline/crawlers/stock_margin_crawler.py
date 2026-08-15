import datetime
from io import StringIO
from typing import Optional

import pandas as pd
import requests
from loguru import logger

from core.pipeline.crawlers.base import BaseDataCrawler
from core.pipeline.crawlers.utils.request_utils import RequestUtils
from core.pipeline.utils.url_manager import URLManager
from core.utils import TimeUtils

"""
信用交易（融資融券餘額）爬蟲資料時間表：
1. TWSE
    - 來源：MI_MARGN（selectType=ALL，含股票、ETF、TDR、受益證券）
    - 資料自民國 90 年 01 月 01 日（2001/01/01）起提供
    - 回傳兩張表格：第一張為信用交易統計彙總，最後一張才是個股明細
2. TPEX
    - 來源：上櫃融資融券餘額（該端點本身即涵蓋全部上櫃標的，含 ETF）
    - 資料自民國 96 年 01 月（2007/01）起提供

**版面穩定性（2026-08-15 逐年實測，2013~2026 每年抽一個交易日）**：
上市固定 16 欄、上櫃固定 20 欄，且**表頭序列逐年完全相同**，故 cleaner
依「欄位位置」對應是安全的，不需要改制日期分流。

> 對照組：櫃買中心的**除權除息**表於 2016 年改制（2013~2015 多一欄
> `員工紅利轉增資`），`stock_dividend_cleaner` 因此改為依「欄位名稱」對應。
> 兩者的差異是刻意的，修改前請先重跑一次逐年掃描確認版面仍未改制。
"""


class StockMarginCrawler(BaseDataCrawler):
    """爬取上市、上櫃股票每日信用交易（融資融券餘額）"""

    def __init__(self):
        super().__init__()

    def setup(self) -> None:
        """Set Up the Config of Crawler"""
        pass

    def crawl(self, date: datetime.date) -> None:
        """Crawl TWSE & TPEX Margin Trading Data"""

        self.crawl_twse_margin(date)
        self.crawl_tpex_margin(date)

    def crawl_twse_margin(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """TWSE 融資融券餘額單日爬蟲"""

        logger.info(f"* Start crawling TWSE margin: {date}")

        date_str: str = TimeUtils.format_date(date, sep="")
        twse_url: str = URLManager.get_url("TWSE_MARGIN_ALL_URL", date=date_str)

        twse_response: Optional[requests.Response] = RequestUtils.requests_get(twse_url)

        if twse_response is None:
            return None

        # 檢查是否為假日 or 單純網站還未更新
        try:
            # selectType=ALL 會多回傳一張信用交易統計彙總表，個股明細固定在最後一張
            # 證券代號含合計列會被推斷為 float，以 converters 保留原始字串
            twse_df: pd.DataFrame = pd.read_html(
                StringIO(twse_response.text), converters={0: str}
            )[-1]
            if twse_df.empty:
                logger.warning("No data in table. Possibly not yet updated")
                return None
        except Exception:
            logger.info(f"{date} is a Holiday!")
            return None

        return twse_df

    def crawl_tpex_margin(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """TPEX 融資融券餘額單日爬蟲"""

        logger.info(f"* Start crawling TPEX margin: {date}")

        date_str: str = TimeUtils.format_date(date, sep="/")
        tpex_url: str = URLManager.get_url("TPEX_MARGIN_ALL_URL", date=date_str)

        tpex_response: Optional[requests.Response] = RequestUtils.requests_get(tpex_url)

        if tpex_response is None:
            return None

        try:
            tpex_df: pd.DataFrame = pd.read_html(
                StringIO(tpex_response.text), converters={0: str}
            )[0]
            if tpex_df.empty:
                logger.warning("No data in table. Possibly not yet updated")
                return None
        except Exception:
            logger.info(f"{date} is a Holiday!")
            return None

        return tpex_df
