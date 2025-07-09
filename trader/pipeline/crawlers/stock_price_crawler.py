import datetime
import pandas as pd
from io import StringIO
import requests
from pathlib import Path
from loguru import logger
from typing import List, Optional

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.utils import URLManager
from trader.pipeline.utils.crawler_utils import CrawlerUtils
from trader.config import PRICE_DOWNLOADS_PATH


class StockPriceCrawler(BaseDataCrawler):
    """ 爬取上市、上櫃公司的股票收盤行情（OHLC、成交量） """

    def __init__(self):
        super().__init__()

        self.price_dir: Path = PRICE_DOWNLOADS_PATH
        self.setup()


    def crawl(self, date: datetime.date) -> None:
        """ Crawl Price Data """

        twse_price_df: pd.DataFrame = self.crawl_twse_price(date)
        tpex_price_df: pd.DataFrame = self.crawl_tpex_price(date)


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Crawler """

        self.price_dir.mkdir(parents=True, exist_ok=True)


    def crawl_twse_price(self, date: datetime.date) -> pd.DataFrame:
        """ 爬取上市公司股票收盤行情 """
        """
        TWSE 網站提供資料日期：
        1. 2004/2/11 ~ present
        """

        url: str = URLManager.get_url("TWSE_CLOSING_QUOTE_URL", date=date)

        try:
            res: Optional[requests.Response] = CrawlerUtils.requests_get(url)
            logger.info(f"上市 URL: {url}")
        except Exception as e:
            logger.info(f"* WARN: Cannot get stock price at {date}")
            logger.info(e)
            return None

        df: pd.DataFrame = pd.read_html(res.text)[-1]

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(0)

        df.drop(
            columns=["漲跌(+/-)"],
            axis=1,
            inplace=True
        )
        df.insert(0, "date", date)
        df = df.rename(columns={"證券代號": "stock_id"})
        df = df.astype(str)
        CrawlerUtils.move_col(df, "成交股數", "漲跌價差")
        CrawlerUtils.move_col(df, "成交金額", "成交股數")
        CrawlerUtils.move_col(df, "成交筆數", "成交金額")
        CrawlerUtils.convert_col_to_numeric(df, ["date", "stock_id", "證券名稱"])
        df.to_csv(f"{self.price_dir}/twse_{date}.csv", index=False)

        return df


    def crawl_tpex_price(self, date: datetime.date) -> pd.DataFrame:
        """ 爬取上櫃公司股票收盤行情 """

        """
        1. 上櫃資料從 96/7/2 以後才提供
        2. 從 109/4/30 開始後 csv 檔的 column 不一樣
        """

        table_change_date: datetime.date = datetime.date(2020, 4, 30)

        url: str = URLManager.get_url(
            "TPEX_CLOSING_QUOTE_URL",
            year=date.year,
            month=CrawlerUtils.pad2(date.month),
            day=CrawlerUtils.pad2(date.day)
        )

        try:
            res: Optional[requests.Response] = CrawlerUtils.requests_get(url)
            logger.info(f"上櫃 URL: {url}")
        except Exception as e:
            logger.info(f"* WARN: Cannot get stock price at {date}")
            logger.info(e)
            return None

        df: pd.DataFrame = pd.read_html(res.text)[0]

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(0)

        df.drop(
            columns=["次日漲停價", "次日跌停價"],
            axis=1,
            inplace=True
        )
        df.insert(0, "date", date)
        df = df.astype(str)

        if date >= table_change_date:
            df.columns = [
                "date",
                "stock_id",
                "證券名稱",
                "收盤價",
                "漲跌價差",
                "開盤價",
                "最高價",
                "最低價",
                "成交股數",
                "成交金額",
                "成交筆數",
                "最後揭示買價",
                "最後揭示買量",
                "最後揭示賣價",
                "最後揭示賣量",
                "發行股數",
            ]
        else:
            df.columns = [
                "date",
                "stock_id",
                "證券名稱",
                "收盤價",
                "漲跌價差",
                "開盤價",
                "最高價",
                "最低價",
                "成交股數",
                "成交金額",
                "成交筆數",
                "最後揭示買價",
                "最後揭示賣價",
                "發行股數"
            ]
        CrawlerUtils.move_col(df, "收盤價", "最低價")
        CrawlerUtils.move_col(df, "漲跌價差", "收盤價")
        CrawlerUtils.convert_col_to_numeric(df, ["date", "stock_id", "證券名稱"])
        df.to_csv(f"{self.price_dir}/tpex_{date}.csv", index=False)

        return df