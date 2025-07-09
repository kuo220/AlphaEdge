import os
import random
import sqlite3
import datetime
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from io import StringIO

import pandas as pd
import requests

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.utils.crawler_utils import CrawlerUtils, URLManager
from trader.config import (
    CHIP_DOWNLOADS_PATH,
    CHIP_DB_PATH,
)


class StockChipCleaner(BaseDataCleaner):
    """ Stock Chip Cleaner (Transform) """

    def __init__(self):
        super().__init__()

        # The date that TWSE chip data format was reformed
        self.twse_first_reform_date: datetime.date = datetime.date(2014, 12, 1)
        self.twse_second_reform_date: datetime.date = datetime.date(2017, 12, 18)

        # The date that TPEX chip data format was reformed
        self.tpex_first_reform_date: datetime.date = datetime.date(2018, 1, 15)


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Cleaner """
        pass


    def clean_twse_chip(
        self,
        df: pd.DataFrame,
        date: datetime.date
    ) -> pd.DataFrame:
        """ Clean TWSE Stock Chip Data """

        df.columns = df.columns.droplevel(0)

        df.insert(0, '日期', date)

        old_col_name: List[str] = ['自營商買進股數(自行買賣)', '自營商賣出股數(自行買賣)', '自營商買賣超股數(自行買賣)',
                        '自營商買進股數(避險)', '自營商賣出股數(避險)', '自營商買賣超股數(避險)']

        new_col_name: List[str] = ['自營商買進股數_自行買賣', '自營商賣出股數_自行買賣', '自營商買賣超股數_自行買賣',
                            '自營商買進股數_避險', '自營商賣出股數_避險', '自營商買賣超股數_避險']

        # 第一次格式改制前
        if date < self.twse_first_reform_date:
            CrawlerUtils.move_col(df, "自營商買賣超股數", "自營商賣出股數")
        # 第一次格式改制後，第二次格式改制前
        elif self.twse_first_reform_date <= date < self.twse_second_reform_date:
            CrawlerUtils.move_col(df, "自營商買賣超股數", "自營商買賣超股數(避險)")
            df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)
        # 第二次格式改制後
        else:
            df['外資買進股數'] = df['外陸資買進股數(不含外資自營商)'] + df['外資自營商買進股數']
            df['外資賣出股數'] = df['外陸資賣出股數(不含外資自營商)'] + df['外資自營商賣出股數']
            df['外資買賣超股數'] = df['外陸資買賣超股數(不含外資自營商)'] + df['外資自營商買賣超股數']
            df.drop(columns=['外陸資買進股數(不含外資自營商)', '外陸資賣出股數(不含外資自營商)', '外陸資買賣超股數(不含外資自營商)',
                                '外資自營商買進股數', '外資自營商賣出股數', '外資自營商買賣超股數'], inplace=True)
            CrawlerUtils.move_col(df, '外資買進股數', '證券名稱')
            CrawlerUtils.move_col(df, '外資賣出股數', '外資買進股數')
            CrawlerUtils.move_col(df, '外資買賣超股數', '外資賣出股數')
            CrawlerUtils.move_col(df, "自營商買賣超股數", "自營商買賣超股數(避險)")
            df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)

        df = CrawlerUtils.remove_redundant_col(df, '三大法人買賣超股數')
        df = CrawlerUtils.fill_nan(df, 0)
        df.to_csv(os.path.join(CHIP_DOWNLOADS_PATH, f"twse_{CrawlerUtils.format_date(date)}.csv"), index=False)

        return df


    def clean_tpex_chip(
        self,
        df: pd.DataFrame,
        date: datetime.date
    ) -> pd.DataFrame:
        """ Clean TPEX Stock Chip Data """

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(0)

        new_col_name: List[str] = [
            '證券代號', '證券名稱', '外資買進股數', '外資賣出股數', '外資買賣超股數',
            '投信買進股數', '投信賣出股數', '投信買賣超股數', '自營商買賣超股數',
            '自營商買進股數_自行買賣', '自營商賣出股數_自行買賣', '自營商買賣超股數_自行買賣',
            '自營商買進股數_避險', '自營商賣出股數_避險', '自營商買賣超股數_避險', '三大法人買賣超股數'
        ]

        # 格式改制前
        if date < self.tpex_first_reform_date:
            old_col_name: List[str] = [
                '代號', '名稱', '外資 及陸資 買股數', '外資 及陸資 賣股數', '外資 及陸資 淨買股數',
                '投信 買股數', '投信 賣股數', '投信 淨買股數', '自營商 淨買股數',
                '自營商 (自行買賣) 買股數', '自營商 (自行買賣) 賣股數', '自營商 (自行買賣) 淨買股數',
                '自營商 (避險) 買股數', '自營商 (避險) 賣股數', '自營商 (避險) 淨買股數', '三大法人 買賣超股數'
            ]

            df.rename(columns=dict(zip(old_col_name, new_col_name)), inplace=True)
        # 格式改制後
        else:
            new_df: pd.DataFrame = pd.DataFrame(columns=new_col_name)
            new_df['證券代號'] = df.loc[:, ('代號', '代號')]
            new_df['證券名稱'] = df.loc[:, ('名稱', '名稱')]
            new_df['外資買進股數'] = df.loc[:, ('外資及陸資', '買進股數')]
            new_df['外資賣出股數'] = df.loc[:, ('外資及陸資', '賣出股數')]
            new_df['外資買賣超股數'] = df.loc[:, ('外資及陸資', '買賣超股數')]
            new_df['投信買進股數'] = df.loc[:, ('投信', '買進股數')]
            new_df['投信賣出股數'] = df.loc[:, ('投信', '賣出股數')]
            new_df['投信買賣超股數'] = df.loc[:, ('投信', '買賣超股數')]
            new_df['自營商買賣超股數'] = df.loc[:, ('自營商', '買賣超股數')]
            new_df['自營商買進股數_自行買賣'] = df.loc[:, ('自營商(自行買賣)', '買進股數')]
            new_df['自營商賣出股數_自行買賣'] = df.loc[:, ('自營商(自行買賣)', '賣出股數')]
            new_df['自營商買賣超股數_自行買賣'] = df.loc[:, ('自營商(自行買賣)', '買賣超股數')]
            new_df['自營商買進股數_避險'] = df.loc[:, ('自營商(避險)', '買進股數')]
            new_df['自營商賣出股數_避險'] = df.loc[:, ('自營商(避險)', '賣出股數')]
            new_df['自營商買賣超股數_避險'] = df.loc[:, ('自營商(避險)', '買賣超股數')]
            new_df['三大法人買賣超股數'] = df.loc[:, ('三大法人買賣超 股數合計', '三大法人買賣超 股數合計')]
            df = new_df

        df = df.iloc[:-1] # 刪掉最後一個 row
        df.insert(0, '日期', date)
        CrawlerUtils.move_col(df, "自營商買賣超股數", "自營商買賣超股數_避險")
        df = CrawlerUtils.remove_redundant_col(df, '三大法人買賣超股數')
        df = CrawlerUtils.fill_nan(df, 0)
        df.to_csv(os.path.join(CHIP_DOWNLOADS_PATH, f"tpex_{CrawlerUtils.format_date(date)}.csv"), index=False)

        return df