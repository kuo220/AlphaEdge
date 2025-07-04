import datetime
from pathlib import Path
from typing import List, Dict, Optional
import numpy as np
import pandas as pd
import time
import requests
import logging as L
from dateutil.rrule import DAILY, MONTHLY, rrule
from fake_useragent import UserAgent
from requests.exceptions import ReadTimeout

from trader.pipeline.utils import URLManager


class CrawlerUtils:
    """ Cralwer Tools """

    ses: Optional[requests.Session] = None    # Session

    @staticmethod
    def generate_random_header() -> Dict[str, str]:
        """ 產生隨機 headers 避免爬蟲被鎖 """

        ua: UserAgent = UserAgent()
        user_agent: str = ua.random
        headers: Dict[str, str] = {'Accept': '*/*', 'Connection': 'keep-alive',
                'User-Agent': user_agent}
        return headers


    @classmethod
    def find_best_session(cls) -> Optional[requests.Session]:
        """ 嘗試建立可用的 requests.Session 連線 """

        for i in range(10):
            try:
                L.info('獲取新的Session 第', i, '回合')
                headers = cls.generate_random_header()
                ses = requests.Session()
                ses.get(URLManager.get_url('TWSE_URL'), headers=headers, timeout=10)
                ses.headers.update(headers)
                L.info('成功！')
                cls.ses = ses

                return ses
            except (ConnectionError, ReadTimeout) as error:
                L.info(error)
                L.info('失敗,10秒後重試')
                time.sleep(10)

        L.info('您的網頁IP已經被證交所封鎖,請更新IP來獲取解鎖')
        L.info(" 手機:開啟飛航模式,再關閉,即可獲得新的IP")
        L.info("數據機：關閉然後重新打開數據機的電源")


    @classmethod
    def requests_get(cls, *args1, **args2) -> Optional[requests.Response]:
        """ 使用共用 session 發送 POST 請求，內建重試機制 """

        if cls.ses is None:
            cls.find_best_session()

        # download data
        for i in range(3):
            try:
                return cls.ses.get(*args1, timeout=10, **args2)
            except (ConnectionError, ReadTimeout) as error:
                L.info(error)
                L.info(f"retry one more time after 60s {2 - i} times left")
                time.sleep(60)
                cls.find_best_session()
        return None


    @staticmethod
    def move_col(df: pd.DataFrame, col_name: str, ref_col_name: str) -> None:
        """ 移動 columns 位置"""

        col_data: pd.Series = df.pop(col_name)
        df.insert(df.columns.get_loc(ref_col_name) + 1, col_name, col_data)


    @staticmethod
    def remove_redundant_col(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
        """ 刪除 DataFrame 中指定欄位後面的所有欄位 """

        if col_name in df.columns:
            last_col_loc: int = df.columns.get_loc(col_name)
            df = df.iloc[:, :last_col_loc + 1]
        return df


    @staticmethod
    def fill_nan(df: pd.DataFrame, value: int=0) -> pd.DataFrame:
        """ 檢查 DataFrame 是否有 NaN 值，若有則將所有 NaN 值填補為指定值 """

        if df.isnull().values.any():
            df.fillna(value, inplace=True)
        return df


    @staticmethod
    def generate_date_range(start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
        """ 產生從 start_date 到 end_date 的每日日期清單 """
        return [dt.date() for dt in rrule(DAILY, dtstart=start_date, until=end_date)]


    @staticmethod
    def generate_month_range(start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
        """ 產生從 start_date 到 end_date 的每月清單（取每月的起始日） """
        return [dt.date() for dt in rrule(MONTHLY, dtstart=start_date, until=end_date)]