import datetime
from pathlib import Path
from typing import List, Dict
import numpy as np
import pandas as pd
from dateutil.rrule import DAILY, MONTHLY, rrule
from fake_useragent import UserAgent


class CrawlerTools:
    """ Cralwer Tools """

    @staticmethod
    def generate_random_header() -> Dict[str, str]:
        """ 產生隨機 headers 避免爬蟲被鎖 """

        ua: UserAgent = UserAgent()
        user_agent: str = ua.random
        headers: Dict[str, str] = {'Accept': '*/*', 'Connection': 'keep-alive',
                'User-Agent': user_agent}
        return headers


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