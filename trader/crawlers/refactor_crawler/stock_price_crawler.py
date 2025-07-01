import datetime
import pandas as pd
from io import StringIO
import requests
import logging
from typing import List, Optional

from trader.crawlers.utils.url_manager import URLManager
from trader.crawlers.utils.crawler_tools import CrawlerTools


class StockPriceCrawler:
    """ 爬取上市、上櫃公司的股票收盤行情（OHLC、成交量） """

    def __init__(self):
        pass


    def crawl_twse_price(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ 爬取上市公司股票收盤行情 """

        date_str: str = date.strftime('%Y%m%d')
        url: str = URLManager.get_url("TWSE_CLOSING_QUOTE_URL", date=date_str)

        try:
            r: Optional[requests.Response] = CrawlerTools.requests_get(url)
            logging.info(f"上市 URL: {url}")
        except Exception as e:
            logging.info(f"* WARN: Cannot get stock price at {date_str}")
            logging.info(e)
            return None

        content: str = r.text.replace('=', '')
        lines: List[str] = content.split('\n')
        lines = list(filter(lambda l: len(l.split('",')) > 10, lines))
        content = "\n".join(lines)

        if content == "":
            return None

        df: pd.DataFrame = pd.read_csv(StringIO(content))
        df = df.astype(str)
        df = df.apply(lambda s: s.str.replace(',', ''))
        df['date'] = pd.to_datetime(date)
        df = df.rename(columns={'證券代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])

        for col in df.columns:
            if col != "證券名稱":
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        return df


    def crawl_tpex_price(self, date: datetime.date) -> Optional[pd.DataFrame]:
        """ 爬取上櫃公司股票收盤行情 """

        """
        1. 上櫃資料從96/7/2以後才提供
        2. 109/4/30以後csv檔的column不一樣
        """

        date_str: str = date.strftime('%Y%m%d')
        url: str = URLManager.get_url(
            "TPEX_CLOSING_QUOTE_URL",
            roc_year = str(date.year - 1911),
            month=date_str[4:6],
            day=date_str[6:]
        )

        try:
            r: Optional[requests.Response] = CrawlerTools.requests_get(url)
            logging.info(f"上櫃 URL: {url}")
        except Exception as e:
            logging.info(f"* WARN: Cannot get stock price at {date_str}")
            logging.info(e)
            return None

        content = r.text.replace('=', '')

        lines = content.split('\n')
        lines = list(filter(lambda l: len(l.split('",')) > 10, lines))
        content = "\n".join(lines)

        if content == "":
            return None

        df = pd.read_csv(StringIO(content), header=None)
        df = df.astype(str)
        df = df.apply(lambda s: s.str.replace(',', ''))

        if date_str >= str(20200430):
            df.drop(
                df.columns[[14, 15, 16]],
                axis=1,
                inplace=True
            )
            # 證券名稱是修改過的，原本是證卷名稱
            df.columns = ["stock_id", "證券名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "成交股數",
                          "成交金額", "成交筆數", "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量"]
        else:
            df.drop(
                df.columns[[12, 13, 14]],
                axis=1,
                inplace=True
            )
            df.columns = ["stock_id", "證券名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "成交股數",
                          "成交金額", "成交筆數", "最後揭示買價", "最後揭示賣價"]

        df['date'] = pd.to_datetime(date)
        df = df.set_index(['stock_id', 'date'])

        for col in df.columns:
            if col != "證券名稱":
                df[col] = pd.to_numeric(df[col], errors='coerce')

        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        return df