import datetime
import os
import pickle
import random
import re
import shutil
import sqlite3
import sys
import time
import urllib.request
import warnings
import zipfile
from io import StringIO
from pathlib import Path
from typing import List, Optional, Any

import ipywidgets as widgets
import numpy as np
import pandas as pd
import requests
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from dateutil.rrule import DAILY, MONTHLY, rrule
from fake_useragent import UserAgent
from IPython.display import display
from requests.exceptions import ConnectionError, ReadTimeout
from tqdm import tqdm, tnrange, tqdm_notebook

from ..utils.crawler_utils import CrawlerUtils
from ..utils.url_manager import URLManager
from trader.config import (
    CRAWLER_DOWNLOADS_PATH,
    FINANCIAL_REPORT_PATH,
    QUANTX_DB_PATH,
    CERTS_FILE_PATH
)


class QuantXCrawler:
    """ QuantX Crawler """

    def __init__(self):
        self.table_without_stockid: List[str] = ["tw_total_pmi", "tw_total_nmi", "tw_business_indicator", "benchmark_return", "margin_balance"]
        self.ses: Any = None
        warnings.simplefilter(action='ignore', category=FutureWarning)


    def find_best_session(self) -> None:
        for i in range(10):
            try:
                print('獲取新的Session 第', i, '回合')
                headers = CrawlerUtils.generate_random_header()
                self.ses = requests.Session()
                self.ses.get('https://www.twse.com.tw/zh/', headers=headers, timeout=10)
                self.ses.headers.update(headers)
                print('成功！')
                return self.ses
            except (ConnectionError, ReadTimeout) as error:
                print(error)
                print('失敗，10秒後重試')
                time.sleep(10)

        print('您的網頁IP已經被證交所封鎖，請更新IP來獲取解鎖')
        print("　手機：開啟飛航模式，再關閉，即可獲得新的IP")
        print("數據機：關閉然後重新打開數據機的電源")


    def requests_get(self, *args1, **args2):
        # get current session
        if self.ses == None:
            self.ses = self.find_best_session()

        # download data
        i = 3
        while i >= 0:
            try:
                return self.ses.get(*args1, timeout=10, **args2)
            except (ConnectionError, ReadTimeout) as error:
                print(error)
                print('retry one more time after 60s', i, 'times left')
                time.sleep(60)
                self.ses = self.find_best_session()

            i -= 1
        # return pd.DataFrame()
        return None


    def requests_post(self, *args1, **args2):
        # get current session
        if self.ses == None:
            self.ses = self.find_best_session()

        # download data
        i = 3
        while i >= 0:
            try:
                return self.ses.post(*args1, timeout=10, **args2)
            except (ConnectionError, ReadTimeout) as error:
                print(error)
                print('retry one more time after 60s', i, 'times left')
                time.sleep(60)
                self.ses = self.find_best_session()

            i -= 1
        return pd.DataFrame()


    def crawl_benchmark_return(self, date) -> pd.DataFrame:
        date_str: str = date.strftime("%Y%m")
        url: str = URLManager.get_url("TAIEX_RETURN_INDEX", date=date_str)
        print("發行量加權股價報酬指數", url)

        # 偽瀏覽器
        headers = CrawlerUtils.generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        r = self.requests_get(url, headers=headers, verify=CERTS_FILE_PATH)
        if r is None:
            print('**WARRN: requests cannot get html')
            return None
        r.encoding = "UTF-8"
        try:
            html_df = pd.read_html(StringIO(r.text))
        except:
            print("**WARRN: Pandas cannot find any table in the HTML file")
            return None

        # 處理一下資料
        df = html_df[0].copy()
        df = df.set_axis(["date", "發行量加權股價報酬指數"], axis=1)
        # 民國年轉西元年
        df["date"] = df["date"].apply(
            lambda x: pd.to_datetime(str(int(x.split("/")[0]) + 1911) + "/" + x.split("/")[1] + "/" + x.split("/")[2]),
            format("%Y/%m/%d"))
        df["發行量加權股價報酬指數"] = df["發行量加權股價報酬指數"].apply(lambda x: round(x, 2))
        df.set_index(['date'], inplace=True)
        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]

        return df


    def crawl_tpex_margin_balance(self, date) -> pd.DataFrame:
        date_str: str = date.strftime('%Y%m%d')

        url: str = URLManager.get_url(
            "TPEX_MARGIN_SUMMARY_URL",
            roc_year=str(date.year - 1911),
            month=date_str[4:6],
            day=date_str[6:]
        )
        print("上櫃", url)

        # 偽瀏覽器
        headers = CrawlerUtils.generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        r = self.requests_get(url, headers=headers, verify=CERTS_FILE_PATH)
        if r is None:
            print('**WARRN: requests cannot get html')
            return None
        r.encoding = "UTF-8"
        try:
            html_df = pd.read_html(StringIO(r.text))
        except:
            print('**WARRN: Pandas cannot find any table in the HTML file')
            return None

        # 處理一下資料
        index = pd.to_datetime(date)

        columns_name = ["上櫃融資交易金額", "上櫃融資買進金額", "上櫃融資賣出金額", "上櫃融資現償金額", "上櫃融資餘額",
                        "上櫃融券餘額", "上櫃融資買進", "上櫃融資賣出", "上櫃融資現償", "上櫃融券買進", "上櫃融券賣出",
                        "上櫃融券券償", "date"]

        df = pd.DataFrame(index=[index], columns=columns_name)
        html_df = html_df[0].copy()
        df["date"] = index
        df.set_index(['date'], inplace=True)
        df["上櫃融資交易金額"] = float(html_df.iloc[-2, 6]) * 1000
        df["上櫃融資買進金額"] = float(html_df.iloc[-2, 3]) * 1000
        df["上櫃融資賣出金額"] = float(html_df.iloc[-2, 4]) * 1000
        df["上櫃融資現償金額"] = float(html_df.iloc[-2, 5]) * 1000
        df["上櫃融資餘額"] = html_df.iloc[-3, 6]
        df["上櫃融券餘額"] = html_df.iloc[-3, 14]
        df["上櫃融資買進"] = html_df.iloc[-3, 3]
        df["上櫃融券買進"] = html_df.iloc[-3, 12]
        df["上櫃融資賣出"] = html_df.iloc[-3, 4]
        df["上櫃融券賣出"] = html_df.iloc[-3, 11]
        df["上櫃融資現償"] = html_df.iloc[-3, 5]
        df["上櫃融券券償"] = html_df.iloc[-3, 13]
        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]

        return df


    def crawl_margin_balance(self, date):
        # 上櫃資料從102/1/2以後才提供，所以融資融券先以102/1/2以後為主
        date_str: str = date.strftime('%Y%m%d')

        url: str = URLManager.get_url("TWSE_MARGIN_SUMMARY_URL", date=date_str)
        print("上市", url)

        # 偽瀏覽器
        headers = CrawlerUtils.generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        r = self.requests_get(url, headers=headers, verify=CERTS_FILE_PATH)
        if r is None:
            print('**WARRN: requests cannot get html')
            return None
        r.encoding = 'UTF-8'
        try:
            html_df = pd.read_html(StringIO(r.text))
        except:
            print('**WARRN: Pandas cannot find any table in the HTML file')
            return None

        # 處理一下資料
        index = pd.to_datetime(date)
        columns_name = ["上市融資交易金額", "上市融資買進金額", "上市融資賣出金額", "上市融資現償金額", "上市融資餘額",
                        "上市融券餘額", "上市融資買進", "上市融資賣出", "上市融資現償", "上市融券買進", "上市融券賣出",
                        "上市融券券償", "date"]

        df = pd.DataFrame(index=[index], columns=columns_name)
        html_df = html_df[0].copy()
        df["date"] = index
        df.set_index(['date'], inplace=True)
        df["上市融資交易金額"] = float(html_df.iloc[2, 5]) * 1000
        df["上市融資買進金額"] = float(html_df.iloc[2, 1]) * 1000
        df["上市融資賣出金額"] = float(html_df.iloc[2, 2]) * 1000
        df["上市融資現償金額"] = float(html_df.iloc[2, 3]) * 1000
        df["上市融資餘額"] = html_df.iloc[0, 5]
        df["上市融券餘額"] = html_df.iloc[1, 5]
        df["上市融資買進"] = html_df.iloc[0, 1]
        df["上市融券買進"] = html_df.iloc[1, 1]
        df["上市融資賣出"] = html_df.iloc[0, 2]
        df["上市融券賣出"] = html_df.iloc[1, 2]
        df["上市融資現償"] = html_df.iloc[0, 3]
        df["上市融券券償"] = html_df.iloc[1, 3]
        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df_otc = self.crawl_tpex_margin_balance(date)
        df = pd.concat([df, df_otc], axis=1)

        return df


    def crawl_tpex_margin_transactions(self, date):
        date_str: str = date.strftime('%Y%m%d')

        url: str = URLManager.get_url(
            "TPEX_MARGIN_SUMMARY_URL",
            roc_year=str(date.year - 1911),
            month=date_str[4:6],
            day=date_str[6:]
        )
        print("上櫃", url)

        # 偽瀏覽器
        headers = CrawlerUtils.generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        r = self.requests_get(url, headers=headers, verify=CERTS_FILE_PATH)
        if r is None:
            print('**WARRN: requests cannot get html')
            return None
        r.encoding = 'UTF-8'

        try:
            html_df = pd.read_html(StringIO(r.text), converters={0: str})
        except:
            print('**WARRN: Pandas cannot find any table in the HTML file')
            return None

        # 處理一下資料
        html_df = html_df[0].copy()
        html_df = html_df.iloc[:-3, :-5]
        html_df = html_df.drop(columns=[html_df.columns[1], html_df.columns[2], html_df.columns[7], html_df.columns[8],
                                        html_df.columns[9], html_df.columns[10]])
        html_df.columns = ["stock_id", "融資買進", "融資賣出", "融資現償", "融資餘額", "融券賣出", "融券買進", "融券券償",
                        "融券餘額"]
        html_df["date"] = pd.to_datetime(date)
        html_df.set_index(['stock_id', 'date'], inplace=True)
        html_df = html_df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        html_df = html_df[html_df.columns[html_df.isnull().all() == False]]

        return html_df


    def crawl_margin_transactions(self, date) -> pd.DataFrame:
        # 上櫃資料從102/1/2以後才提供，所以融資融券先以102/1/2以後為主
        date_str: str = date.strftime('%Y%m%d')

        # 上市分成4個網站爬取: 封閉式基金、ETF、存託憑證、股票
        # 封閉式基金 => 0049
        # ETF => 0099P
        # 存託憑證 => 9299
        # 股票 => STOCK

        url_names: List[str] = ["TWSE_MARGIN_FUND_URL", "TWSE_MARGIN_ETF_URL", "TWSE_MARGIN_TDR_URL", "TWSE_MARGIN_STOCK_URL"]
        url_list: List[str] = [URLManager.get_url(url_name, date=date_str) for url_name in url_names]
        c = 0
        df = None
        for url in url_list:
            print("上市", url)

            # 偽瀏覽器
            headers = CrawlerUtils.generate_random_header()

            # 下載該年月的網站，並用pandas轉換成 dataframe
            try:
                r = self.requests_get(url, headers=headers, verify=CERTS_FILE_PATH)
                r.encoding = 'UTF-8'
            except:
                print('**WARRN: requests cannot get html')
                continue

            try:
                html_df = pd.read_html(StringIO(r.text), converters={0: str})
            except:
                print('**WARRN: Pandas cannot find any table in the HTML file')
                continue

            # 處理一下資料
            html_df = html_df[0].copy()
            html_df = html_df.iloc[1:, :-1]
            html_df = html_df.drop(columns=[html_df.columns[1], html_df.columns[5], html_df.columns[7], html_df.columns[11],
                                            html_df.columns[13], html_df.columns[14]])
            html_df.columns = ["stock_id", "融資買進", "融資賣出", "融資現償", "融資餘額", "融券買進", "融券賣出",
                            "融券券償",
                            "融券餘額"]
            html_df["date"] = pd.to_datetime(date)
            html_df.set_index(['stock_id', 'date'], inplace=True)
            html_df = html_df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
            html_df = html_df[html_df.columns[html_df.isnull().all() == False]]
            if c == 0:
                df = html_df.copy()
            else:
                df = pd.concat([df, html_df], axis=0)
            c += 1

        df_otc = self.crawl_tpex_margin_transactions(date)
        if df_otc is not None and df is not None:
            df = pd.concat([df, df_otc], axis=0)
        elif df is None and df_otc is not None:
            return df_otc
        elif df is not None and df_otc is None:
            return df
        else:
            return None
        return df


    def crawl_tpex_price(self, date) -> Optional[pd.DataFrame]:
        # 上櫃資料從96/7/2以後才提供
        # 109/4/30以後csv檔的column不一樣
        date_str: str = date.strftime('%Y%m%d')

        url: str = URLManager.get_url(
            "TPEX_CLOSING_QUOTE_URL",
            roc_year=str(date.year - 1911),
            month=date_str[4:6],
            day=date_str[6:]
        )
        print("上櫃", url)
        r = self.requests_post(url)

        if r is None:
            print('**WARRN: cannot get stock price at', date_str)
            return None

        content = r.text.replace('=', '')

        lines = content.split('\n')
        lines = list(filter(lambda l: len(l.split('",')) > 10, lines))
        content = "\n".join(lines)

        if content == '':
            return None

        df = pd.read_csv(StringIO(content))
        df = df.astype(str)
        df = df.apply(lambda s: s.str.replace(',', ''))
        if date_str >= str(20200430):
            df.drop(df.columns[[14, 15, 16]],
                    axis=1,
                    inplace=True)
            df.columns = ["stock_id", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "成交股數",
                        "成交金額", "成交筆數", "最後揭示買價", "最後揭示買量", "最後揭示賣價", "最後揭示賣量"]
        else:
            df.drop(df.columns[[12, 13, 14]],
                    axis=1,
                    inplace=True)
            df.columns = ["stock_id", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "成交股數",
                        "成交金額", "成交筆數", "最後揭示買價", "最後揭示賣價"]

        df['date'] = pd.to_datetime(date)

        df = df.set_index(['stock_id', 'date'])

        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        return df


    def crawl_price(self, date) -> Optional[pd.DataFrame]:
        date_str: str = date.strftime('%Y%m%d')

        url: str = URLManager.get_url("TWSE_CLOSING_QUOTE_URL", date=date_str)
        print("上市", url)
        r = self.requests_post(url)

        if r is None:
            print('**WARRN: cannot get stock price at', date_str)
            return None

        content = r.text.replace('=', '')

        lines = content.split('\n')
        lines = list(filter(lambda l: len(l.split('",')) > 10, lines))
        content = "\n".join(lines)

        if content == '':
            return None

        df = pd.read_csv(StringIO(content))
        df = df.astype(str)
        df = df.apply(lambda s: s.str.replace(',', ''))
        df['date'] = pd.to_datetime(date)
        df = df.rename(columns={'證券代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])

        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        df1 = self.crawl_tpex_price(date)

        df = df.append(df1)

        return df


    def crawl_tpex_price_old_1(self, date) -> Optional[pd.DataFrame]:
        # For year == 2005 or year == 2006
        date_str: str = date.strftime('%Y%m%d')
        date_str = str(int(date_str[0:4]) - 1911) + date_str[4:]

        url: str = URLManager.get_url("TPEX_CLOSING_QUOTE_OLD_1_URL", date=date_str)

        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # 找到表格元素
        table = soup.find('table')
        # rows = table.find_all('tr')

        if table == None:
            return None

        # 初始化一個列表來存儲數據
        columns = ["股票代號", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "均價", "成交股數",
                "成交金額", "成交筆數", "最後揭示買價", "最後揭示賣價", "發行股數", "次日參考價", "次日漲停價",
                "次日跌停價"]

        # df.columns = ["stock_id", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "成交股數", "成交金額", "成交筆數", "最後揭示買價", "最後揭示賣價"]

        df = pd.DataFrame(columns=columns)
        index = [0, 1, 3, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18]

        # 遍歷表格行
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) > 17:  # 根據你提供的數據結構，確保列數正確
                # data = {columns[i]: cells[i].text.strip() for i in range(len(columns))}
                data = {columns[idx]: cells[i].text.strip() for idx, i in enumerate(index)}
                df = df.append(data, ignore_index=True)

        df = df.apply(lambda s: s.str.replace(',', ''))
        df['date'] = pd.to_datetime(date)
        df = df.rename(columns={'股票代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])

        df.drop(df.columns[[6, 12, 13, 14, 15]],
                axis=1,
                inplace=True)

        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        return df


    # For date 2007/01/02 - 2007/04/20
    def crawl_tpex_price_old_2(self, date) -> Optional[pd.DataFrame]:
        datestr = date.strftime('%Y%m%d')
        datestr = str(int(datestr[0:4]) - 1911) + '/' + datestr[2:4] + '/' + datestr[4:6]

        # 目標網址（網址已經壞了）
        url: str = URLManager.get_url("TPEX_CLOSING_QUOTE_OLD_2_URL")
        print(url)

        # 設置 payload 參數，只包含日期
        payload = {"ajax": "true", "input_date": datestr}  # 修改為你需要的日期

        headers = CrawlerUtils.generate_random_header()
        # 發送 POST 請求
        response = requests.post(url, data=payload, headers=headers)

        # 使用 BeautifulSoup 解析頁面源代碼
        soup = BeautifulSoup(response.text, "html.parser")

        # 找到包含數據的<table>標籤
        table = soup.find("table", {"id": "contentTable"})

        data_list = []

        if table:
            rows = table.find_all("tr")

            for row in rows:
                columns = row.find_all("td")
                if columns:
                    data = [col.get_text(strip=True) for col in columns]
                    data_list.append(data)
        else:
            # print("未找到表格數據")
            return None

        columns = ["股票代號", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "均價", "成交股數",
                "成交金額", "成交筆數", "最後揭示買價", "最後揭示賣價", "發行股數", "次日參考價", "次日漲停價",
                "次日跌停價"]

        # 創建 DataFrame
        df = pd.DataFrame(data_list, columns=columns)

        df = df.apply(lambda s: s.str.replace(',', ''))

        df['date'] = pd.to_datetime(date)
        df = df.rename(columns={'股票代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])

        df.drop(df.columns[[6, 12, 13, 14, 15]],
                axis=1,
                inplace=True)

        # 這個判斷會刪掉一些資料
        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))

        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        return df


    # For date 2007/04/20 - 2007/06/29
    def crawl_tpex_price_old_3(self, date) -> Optional[pd.DataFrame]:
        date_str: str = date.strftime('%Y%m%d')
        date_str = str(int(date_str[0:4]) - 1911) + date_str[4:]

        url: str = URLManager.get_url(
            "TPEX_CLOSING_QUOTE_OLD_3_URL",
            roc_year=date_str[0:2],
            month=date_str[2:4],
            day=date_str[4:6]
        )
        print("上櫃", url)

        response = requests.get(url)
        soup = BeautifulSoup(response.content, 'html.parser')

        # 找到表格元素
        table = soup.find('table')
        # rows = table.find_all('tr')

        if table == None:
            return None

        # 初始化一個列表來存儲數據
        columns = ["股票代號", "證卷名稱", "收盤價", "漲跌價差", "開盤價", "最高價", "最低價", "均價", "成交股數",
                "成交金額", "成交筆數", "最後揭示買價", "最後揭示賣價", "發行股數", "次日參考價", "次日漲停價",
                "次日跌停價"]

        df = pd.DataFrame(columns=columns)

        # 遍歷表格行
        for row in table.find_all("tr"):
            cells = row.find_all("td")
            if len(cells) >= 17:  # 根據你提供的數據結構，確保列數正確
                data = {columns[i]: cells[i].text.strip() for i in range(len(columns))}
                df = df.append(data, ignore_index=True)

        df = df.apply(lambda s: s.str.replace(',', ''))
        df['date'] = pd.to_datetime(date)
        df = df.rename(columns={'股票代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])

        df.drop(df.columns[[6, 12, 13, 14, 15]],
                axis=1,
                inplace=True)

        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        return df


    # 爬上市公司的股價 For year = 2005 ~ 2007
    def crawl_old_price(self, date) -> Optional[pd.DataFrame]:
        date_str: str = date.strftime('%Y%m%d')

        try:
            r = self.requests_post(URLManager.get_url("TWSE_CLOSING_QUOTE_URL", date=date_str))
        except Exception as e:
            print('**WARRN: cannot get stock price at', date_str)
            print(e)
            return None

        content = r.text.replace('=', '')

        lines = content.split('\n')
        lines = list(filter(lambda l: len(l.split('",')) > 10, lines))
        content = "\n".join(lines)

        if content == '':
            return None

        df = pd.read_csv(StringIO(content))
        df = df.astype(str)
        df = df.apply(lambda s: s.str.replace(',', ''))
        df['date'] = pd.to_datetime(date)
        df = df.rename(columns={'證券代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])

        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]
        df = df[~df['收盤價'].isnull()]

        # 上櫃公司的部分
        if date.year == 2005 or date.year == 2006:
            df1 = self.crawl_tpex_price_old_1(date)
        elif date.year == 2007:
            if date.month == 4:
                if date.day <= 20:
                    df1 = self.crawl_price_tpex_2(date)
                else:
                    df1 = self.crawl_tpex_price_old_3(date)
            elif date.month < 4:
                df1 = self.crawl_price_tpex_2(date)
            else:
                df1 = self.crawl_tpex_price_old_3(date)

        df = df.append(df1)

        return df


    def crawl_tpex_monthly_report(self, date):
        url: str = URLManager.get_url(
            "TPEX_MONTHLY_REVENUE_REPORT_URL",
            roc_year=(date.year - 1911),
            month=date.month
        )
        print("上櫃：", url)

        # 偽瀏覽器
        headers = CrawlerUtils.generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        try:
            r = self.requests_get(url, headers=headers, verify=CERTS_FILE_PATH)
            r.encoding = 'big5'
        except:
            print('**WARRN: requests cannot get html')
            return None

        try:
            html_df = pd.read_html(StringIO(r.text))
        except:
            print('**WARRN: Pandas cannot find any table in the HTML file')
            return None

        # 處理一下資料
        if html_df[0].shape[0] > 500:
            df = html_df[0].copy()
        else:
            df = pd.concat([df for df in html_df if df.shape[1] <= 11 and df.shape[1] > 5])
        # 超靠北公司代號陷阱
        try:
            df.rename(columns={'公司 代號': '公司代號'}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={'上月比較 增減(%)': '上月比較增減(%)'}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={'去年同月 增減(%)': '去年同月增減(%)'}, inplace=True)
        except:
            pass
        try:
            df.rename(columns={'前期比較 增減(%)': '前期比較增減(%)'}, inplace=True)
        except:
            pass
        if 'levels' in dir(df.columns):
            df.columns = df.columns.get_level_values(1)
        else:
            df = df[list(range(0, 10))]
            column_index = df.index[(df[0] == '公司代號')][0]
            df.columns = df.iloc[column_index]

        df['當月營收'] = pd.to_numeric(df['當月營收'], 'coerce')
        df = df[~df['當月營收'].isnull()]
        df = df[df['公司代號'] != '合計']
        df = df[df['公司代號'] != '總計']

        next_month = datetime.date(date.year + int(date.month / 12), ((date.month % 12) + 1), 10)
        df['date'] = pd.to_datetime(next_month)

        df = df.rename(columns={'公司代號': 'stock_id'})
        df = df.set_index(['stock_id', 'date'])
        df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
        df = df[df.columns[df.isnull().all() == False]]

        return df


    def crawl_monthly_report(self, date) -> Optional[pd.DataFrame]:
        x = [datetime.date(2011, 2, 10), datetime.date(2012, 1, 10)]
        if date in x:
            df1 = self.crawl_tpex_monthly_report(date)
            return df1
        else:
            url: str = URLManager.get_url(
                "TWSE_MONTHLY_REVENUE_REPORT_URL",
                roc_year=(date.year - 1911),
                month=date.month
            )
            print("上市", url)

            # 偽瀏覽器
            headers = CrawlerUtils.generate_random_header()

            # 下載該年月的網站，並用pandas轉換成 dataframe
            try:
                r = self.requests_get(url, headers=headers, verify=CERTS_FILE_PATH)
                r.encoding = 'big5'
            except:
                print('**WARRN: requests cannot get html')
                return None

            try:
                html_df = pd.read_html(StringIO(r.text))
            except:
                print('**WARRN: Pandas cannot find any table in the HTML file')
                return None

            # 處理一下資料
            if html_df[0].shape[0] > 500:
                df = html_df[0].copy()
            else:
                df = pd.concat([df for df in html_df if df.shape[1] <= 11 and df.shape[1] > 5])
            # 超靠北公司代號陷阱
            try:
                df.rename(columns={'公司 代號': '公司代號'}, inplace=True)
            except:
                pass
            try:
                df.rename(columns={'上月比較 增減(%)': '上月比較增減(%)'}, inplace=True)
            except:
                pass
            try:
                df.rename(columns={'去年同月 增減(%)': '去年同月增減(%)'}, inplace=True)
            except:
                pass
            try:
                df.rename(columns={'前期比較 增減(%)': '前期比較增減(%)'}, inplace=True)
            except:
                pass

            if 'levels' in dir(df.columns):
                df.columns = df.columns.get_level_values(1)
            else:
                df = df[list(range(0, 10))]
                column_index = df.index[(df[0] == '公司代號')][0]
                df.columns = df.iloc[column_index]

            df['當月營收'] = pd.to_numeric(df['當月營收'], 'coerce')
            df = df[~df['當月營收'].isnull()]
            df = df[df['公司代號'] != '合計']
            df = df[df['公司代號'] != '總計']

            next_month = datetime.date(date.year + int(date.month / 12), ((date.month % 12) + 1), 10)
            df['date'] = pd.to_datetime(next_month)

            df = df.rename(columns={'公司代號': 'stock_id'})
            df = df.set_index(['stock_id', 'date'])
            df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
            df = df[df.columns[df.isnull().all() == False]]

            df1 = self.crawl_tpex_monthly_report(date)

            df = df.append(df1)

            return df


    def crawl_finance_statement2019(self, year, season):
        def ifrs_url(year, season):
            url: str = URLManager.get_url(
                "IFRS_URL",
                year=year,
                season=season
            )
            print(url)
            return url

        headers = CrawlerUtils.generate_random_header()

        print('start download')

        class DownloadProgressBar(tqdm):
            def update_to(self, b=1, bsize=1, tsize=None):
                if tsize is not None:
                    self.total = tsize
                self.update(b * bsize - self.n)

        def download_url(url, output_path):
            with DownloadProgressBar(unit='B', unit_scale=True,
                                    miniters=1, desc=url.split('/')[-1]) as t:
                urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)

        url = ifrs_url(year, season)
        download_url(url, 'temp.zip')

        print('finish download')

        path: Path = (CRAWLER_DOWNLOADS_PATH / f"financial_statement{year}{season}").resolve()

        if path.is_dir():
            shutil.rmtree(path)

        print('create new dir')

        zipfiles = zipfile.ZipFile(open('temp.zip', 'rb'))
        zipfiles.extractall(path=path)

        print('extract all files')

        fnames = [f for f in os.listdir(path) if f[-5:] == '.html']
        fnames = sorted(fnames)

        newfnames = [f.split("-")[5] + '.html' for f in fnames]

        for fold, fnew in zip(fnames, newfnames):
            if len(fnew) != 9:
                print('remove strange code id', fnew)
                os.remove(os.path.join(path, fold))
                continue

            if not os.path.exists(os.path.join(path, fnew)):
                os.rename(os.path.join(path, fold), os.path.join(path, fnew))
            else:
                os.remove(os.path.join(path, fold))

    # TODO:需要 Refactor（目前有 bug）
    def crawl_finance_statement(self, year, season, stock_ids):
        if not FINANCIAL_REPORT_PATH.is_dir():
            FINANCIAL_REPORT_PATH.mkdir(parents=True, exist_ok=True)

        def download_html(year, season, stock_ids, report_type='C'):

            headers = {
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3''Accept-Encoding: gzip, deflate',
                'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
                'Cache-Control': 'max-age=0',
                'Connection': 'keep-alive',
                'Host': 'mops.twse.com.tw',
                'Upgrade-Insecure-Requests': '1',
                'User-Agent': CrawlerUtils.generate_random_header()["User-Agent"]
            }
            pbar = tqdm(stock_ids)
            for i in pbar:

                # check if the html is already parsed
                file = os.path.join(FINANCIAL_REPORT_PATH, str(i) + '.html')
                if os.path.exists(file) and os.stat(file).st_size > 20000:
                    continue

                pbar.set_description('parse htmls %d season %d stock %s' % (year, season, str(i)))

                # start parsing
                if year >= 2019:
                    ty = {"C": "cr", "B": "er", "C": "ir"}
                    url: str = URLManager.get_url(
                        "FINANCE_REPORT_2019_URL",
                        type=ty[report_type],
                        id=i,
                        year=year,
                        season=season
                    )
                else:
                    url: str = URLManager.get_url(
                        "FINANCE_REPORT_URL",
                        id=i,
                        year=year,
                        season=season,
                        type=report_type
                    )
                print(url)
                try:
                    r = self.requests_get(url, headers=headers, timeout=30, verify=CERTS_FILE_PATH)
                except:
                    print('**WARRN: requests cannot get stock', i, '.html')
                    time.sleep(25 + random.uniform(0, 10))
                    continue

                r.encoding = 'big5'

                # write files
                f = open(file, 'w', encoding='utf-8')

                f.write('<meta charset="UTF-8">\n')
                f.write(r.text)
                f.close()

                # finish
                # print(percentage, i, 'end')

                # sleep a while
                time.sleep(10)

        if year < 2019:
            download_html(year, season, stock_ids, 'C')
            download_html(year, season, stock_ids, 'A')
            download_html(year, season, stock_ids, 'B')
            download_html(year, season, stock_ids, 'C')
            download_html(year, season, stock_ids, 'A')
            download_html(year, season, stock_ids, 'B')
        else:
            download_html(year, season, stock_ids, 'C')


    def crawl_finance_statement_by_date(self, date):
        FDH = FinanceDataHandler()

        year = date.year
        if date.month == 3:
            season = 4
            year = year - 1
            month = 11
        elif date.month == 5:
            season = 1
            month = 2
        elif date.month == 8:
            season = 2
            month = 5
        elif date.month == 11:
            season = 3
            month = 8
        else:
            return None

        if year >= 2019:
            self.crawl_finance_statement2019(year, season)
        else:
            df = self.crawl_monthly_report(datetime.datetime(year, month, 1))
            self.crawl_finance_statement(year, season, df.index.levels[0])
        FDH.html2db(date)
        return {}


    def date_range(self, start_date, end_date):
        return [dt.date() for dt in rrule(DAILY, dtstart=start_date, until=end_date)]


    def month_range(self, start_date, end_date):
        return [dt.date() for dt in rrule(MONTHLY, dtstart=start_date, until=end_date)]


    def season_range(self, start_date, end_date):
        if isinstance(start_date, datetime.datetime):
            start_date = start_date.date()

        if isinstance(end_date, datetime.datetime):
            end_date = end_date.date()

        ret = []
        for year in range(start_date.year - 1, end_date.year + 1):
            ret += [datetime.date(year, 5, 15),
                    datetime.date(year, 8, 14),
                    datetime.date(year, 11, 14),
                    datetime.date(year + 1, 3, 31)]
        ret = [r for r in ret if start_date < r < end_date]

        return ret


    def table_exist(self, conn, table):
        return list(conn.execute(
            "select count(*) from sqlite_master where type='table' and name='" + table + "'"))[0][0] == 1


    def table_latest_date(self, conn, table):
        cursor = conn.execute('SELECT date FROM ' + table + ' ORDER BY date DESC LIMIT 1;')
        return datetime.datetime.strptime(list(cursor)[0][0], '%Y-%m-%d %H:%M:%S')


    def table_earliest_date(self, conn, table):
        cursor = conn.execute('SELECT date FROM ' + table + ' ORDER BY date ASC LIMIT 1;')
        return datetime.datetime.strptime(list(cursor)[0][0], '%Y-%m-%d %H:%M:%S')


    def add_to_sql(self, conn, name, df):
        # get the existing dataframe in sqlite3
        exist = self.table_exist(conn, name)
        ret = pd.read_sql('select * from ' + name, conn, index_col=['stock_id', 'date']) if exist else pd.DataFrame()

        # add new df to the dataframe
        ret = ret.append(df)
        ret.reset_index(inplace=True)
        ret['stock_id'] = ret['stock_id'].astype(str)
        ret['date'] = pd.to_datetime(ret['date'])
        ret = ret.drop_duplicates(['stock_id', 'date'], keep='last')
        ret = ret.sort_values(['stock_id', 'date']).set_index(['stock_id', 'date'])

        # add the combined table
        ret.to_csv('backup.csv')

        try:
            ret.to_sql(name, conn, if_exists='replace')
        except:
            ret = pd.read_csv('backup.csv', parse_dates=['date'], dtype={'stock_id': str})
            ret['stock_id'] = ret['stock_id'].astype(str)
            ret.set_index(['stock_id', 'date'], inplace=True)
            ret.to_sql(name, conn, if_exists='replace')


    def add_to_sql_without_stock_id_index(self, conn, name, df):
        exist = self.table_exist(conn, name)
        ret = pd.read_sql('select * from ' + name, conn, index_col=['date']) if exist else pd.DataFrame()

        # add new df to the dateframe
        ret = ret.append(df)
        ret.reset_index(inplace=True)
        ret["date"] = pd.to_datetime(ret["date"])
        ret = ret.drop_duplicates(subset=['date'], keep='last')
        ret = ret.sort_values(['date']).set_index(['date'])

        ret.to_csv('backup.csv')

        try:
            ret.to_sql(name, conn, if_exists='replace')
        except:
            ret = pd.read_csv('backup.csv', parse_dates=['date'])
            ret.set_index(['date'], inplace=True)
            ret.to_sql(name, conn, if_exists='replace')


    def update_table(self, conn, table_name, crawl_function, dates):
        print('start crawl ' + table_name + ' from ', dates[0], 'to', dates[-1])

        df = pd.DataFrame()
        dfs = {}

        progress = tqdm_notebook(dates, )

        for d in progress:

            print('crawling', d)
            progress.set_description('crawl' + table_name + str(d))

            # 呼叫crawl_function return df
            data = crawl_function(d)

            if data is None:
                print('fail, check if it is a holiday')

            # update multiple dataframes
            elif isinstance(data, dict):
                if len(dfs) == 0:
                    dfs = {i: pd.DataFrame() for i in data.keys()}

                for i, d in data.items():
                    dfs[i] = dfs[i].append(d)

            # update single dataframe
            else:
                df = df.append(data)
                print('success')

            if len(df) > 50000:
                if table_name in self.table_without_stockid:
                    self.add_to_sql_without_stock_id_index(conn, table_name, df)
                else:
                    self.add_to_sql(conn, table_name, df)
                print('save', len(df))
                df = pd.DataFrame()

            time.sleep(15)

        if df is not None and len(df) != 0:
            if table_name in self.table_without_stockid:
                self.add_to_sql_without_stock_id_index(conn, table_name, df)
            else:
                self.add_to_sql(conn, table_name, df)
            print('df save successfully')

        if len(dfs) != 0:
            for i, d in dfs.items():
                print('saving df', d.head(), len(d))
                if len(d) != 0:
                    self.add_to_sql(conn, i, d)
                    print('df save successfully', d.head())


    def update_table_from_tej(self, conn, table_name, get_function, progress):
        print('start crawl ')

        df = pd.DataFrame()
        dfs = {}

        for d in progress:

            print('crawling', d)

            # 呼叫crawl_function return df
            data = get_function(d)

            if data is None:
                print('fail, check if it is a holiday')

            # update multiple dataframes
            elif isinstance(data, dict):
                if len(dfs) == 0:
                    dfs = {i: pd.DataFrame() for i in data.keys()}

                for i, d in data.items():
                    dfs[i] = dfs[i].append(d)

            # update single dataframe
            else:
                df = df.append(data)
                print('success')

            if len(df) > 50000:
                if table_name in self.table_without_stockid:
                    self.add_to_sql_without_stock_id_index(conn, table_name, df)
                else:
                    self.add_to_sql(conn, table_name, df)
                print('save', len(df))
                df = pd.DataFrame()

            time.sleep(15)

        if df is not None and len(df) != 0:
            if table_name in self.table_without_stockid:
                self.add_to_sql_without_stock_id_index(conn, table_name, df)
            else:
                self.add_to_sql(conn, table_name, df)
            print('df save successfully')

        if len(dfs) != 0:
            for i, d in dfs.items():
                print('saving df', d.head(), len(d))
                if len(d) != 0:
                    self.add_to_sql(conn, i, d)
                    print('df save successfully', d.head())


    def widget(self, conn, table_name, crawl_func, range_date):
        date_picker_from = widgets.DatePicker(
            description='from',
            disabled=False,
        )

        if self.table_exist(conn, table_name):
            date_picker_from.value = self.table_latest_date(conn, table_name)

        date_picker_to = widgets.DatePicker(
            description='to',
            disabled=False,
        )

        date_picker_to.value = datetime.datetime.now().date()

        btn = widgets.Button(description='update ')

        def onupdate(x):
            dates = range_date(date_picker_from.value, date_picker_to.value)

            if len(dates) == 0:
                print('no data to parse')

            # update_table 這邊呼叫更新table func
            self.update_table(conn, table_name, crawl_func, dates)

        btn.on_click(onupdate)

        if self.table_exist(conn, table_name):
            label = widgets.Label(table_name +
                                ' (from ' + self.table_earliest_date(conn, table_name).strftime('%Y-%m-%d') +
                                ' to ' + self.table_latest_date(conn, table_name).strftime('%Y-%m-%d') + ')')
        else:
            label = widgets.Label(table_name + ' (No table found)(對於finance_statement是正常情況)')

        items = [date_picker_from, date_picker_to, btn]
        display(widgets.VBox([label, widgets.HBox(items)]))



class FinanceDataHandler:
    """ 從 HTML 檔案中提取財務報表數據，清理、組合並將它們儲存到資料庫中 """

    def __init__(self):
        pass

    def afterIFRS(self, year, season):
        season2date = [
            datetime.datetime(year, 5, 15),
            datetime.datetime(year, 8, 14),
            datetime.datetime(year, 11, 14),
            datetime.datetime(year+1, 3, 31)
        ]

        return pd.to_datetime(season2date[season-1].date())


    def clean(self, year, season, balance_sheet):

        if len(balance_sheet) == 0:
            print('**WARRN: no data to parse')
            return balance_sheet
        balance_sheet = balance_sheet.transpose().reset_index().rename(columns={'index':'stock_id'})

        if '會計項目' in balance_sheet:
            s = balance_sheet['會計項目']
            balance_sheet = balance_sheet.drop('會計項目', axis=1).apply(pd.to_numeric)
            balance_sheet['會計項目'] = s.astype(str)

        balance_sheet['date'] = self.afterIFRS(year, season)

        balance_sheet['stock_id'] = balance_sheet['stock_id'].astype(str)
        balance = balance_sheet.set_index(['stock_id', 'date'])
        return balance

    def remove_english(self, s):
        result = re.sub(r'[a-zA-Z()]', "", s)
        return result


    def patch2019(self, df):
        df = df.copy()
        dfname = df.columns.levels[0][0]

        df = df.iloc[:,1:].rename(columns={'會計項目Accounting Title':'會計項目'})


        refined_name = df[(dfname,'會計項目')].str.split(" ").str[0].str.replace("　", "").apply(self.remove_english)

        subdf = df[dfname].copy()
        subdf['會計項目'] = refined_name
        df[dfname] = subdf

        df.columns = pd.MultiIndex(levels=[df.columns.levels[1], df.columns.levels[0]],codes=[df.columns.codes[1], df.columns.codes[0]])

        def neg(s):

            if isinstance(s, float):
                return s

            if str(s) == 'nan':
                return np.nan

            s = s.replace(",", "")
            if s[0] == '(':
                return -float(s[1:-1])
            else:
                return float(s)

        df.iloc[:,1:] = df.iloc[:,1:].applymap(neg)
        return df


    def read_html2019(self, file):
        dfs = pd.read_html(file)
        return [pd.DataFrame(), self.patch2019(dfs[0]), self.patch2019(dfs[1]), self.patch2019(dfs[2])]


    def pack_htmls(self, year, season, directory):
        balance_sheet = {}
        income_sheet = {}
        cash_flows = {}
        income_sheet_cumulate = {}
        pbar = tqdm(os.listdir(directory))

        for i in pbar:

            # 將檔案路徑建立好
            file = os.path.join(directory, i) 

            # 假如檔案不是html結尾，或是太小，代表不是正常的檔案，略過
            if file[-4:] != 'html' or os.stat(file).st_size < 10000:
                continue

            # 顯示目前運行的狀況
            stock_id = i.split('.')[0]
            pbar.set_description('parse htmls %d season %d stock %s' % (year, season, stock_id))

            # 讀取html
            if year < 2019:
                dfs = pd.read_html(file)
            else:
                try:
                    dfs = self.read_html2019(file)
                except:
                    print("ERROR** cannot parse", file)
                    continue

            # 處理pandas0.24.1以上，會把columns parse好的問題
            for df in dfs:
                if 'levels' in dir(df.columns):
                    df.columns = list(range(df.values.shape[1]))#list(range(max_col))

            # 假如html不完整，則略過
            if len(dfs) < 4:
                print('**WARRN html file broken', year, season, i)
                continue

            # 取得 balance sheet
            df = dfs[1].copy().drop_duplicates(subset=0, keep='last')
            df = df.set_index(0)
            balance_sheet[stock_id] = df[1].dropna()
            #balance_sheet = self.combine(balance_sheet, df[1].dropna(), stock_id)

            # 取得 income statement
            df = dfs[2].copy().drop_duplicates(subset=0, keep='last')
            df = df.set_index(0)

            # 假如有4個columns，則第1與第3條column是單季跟累計的income statement
            if len(df.columns) == 4:
                income_sheet[stock_id] = df[1].dropna()
                income_sheet_cumulate[stock_id] = df[3].dropna()
            # 假如有2個columns，則代表第3條column為累計的income statement，單季的從缺
            elif len(df.columns) == 2:
                income_sheet_cumulate[stock_id] = df[1].dropna()

                # 假如是第一季財報 累計 跟單季 的數值是一樣的
                if season == 1:
                    income_sheet[stock_id] = df[1].dropna()

            # 取得 cash_flows
            df = dfs[3].copy().drop_duplicates(subset=0, keep='last')
            df = df.set_index(0)
            cash_flows[stock_id] = df[1].dropna()

        # 將dictionary整理成dataframe
        balance_sheet = pd.DataFrame(balance_sheet)
        income_sheet = pd.DataFrame(income_sheet)
        income_sheet_cumulate = pd.DataFrame(income_sheet_cumulate)
        cash_flows = pd.DataFrame(cash_flows)

        # 做清理
        ret = {'balance_sheet': self.clean(year, season, balance_sheet), 'income_sheet': self.clean(year, season, income_sheet),
                'income_sheet_cumulate': self.clean(year, season, income_sheet_cumulate), 'cash_flows': self.clean(year, season, cash_flows)}

        # 假如是第一季的話，則 單季 跟 累計 是一樣的
        if season == 1:
            ret['income_sheet'] = ret['income_sheet_cumulate'].copy()

        ret['income_sheet_cumulate'].columns = '累計' + ret['income_sheet_cumulate'].columns

        pickle.dump(ret, open('data/financial_statement/pack' + str(year) + str(season) + '.pickle', 'wb'))

        return ret


    def get_all_pickles(self, directory):
        ret = {}
        for i in os.listdir(directory):
            if i[:4] != 'pack':
                continue
            ret[i[4:9]] = pd.read_pickle(os.path.join(directory, i))
        return ret


    def combine(self, d):

        tnames = ['balance_sheet',
                'cash_flows',
                'income_sheet',
                'income_sheet_cumulate']

        tbs = {t:pd.DataFrame() for t in tnames}

        for i, dfs in d.items():
            for tname in tnames:
                tbs[tname] = tbs[tname].append(dfs[tname])
        return tbs


    def fill_season4(self, tbs):
        # copy income sheet (will modify it later)
        income_sheet = tbs['income_sheet'].copy()

        # calculate the overlap columns
        c1 = set(tbs['income_sheet'].columns)
        c2 = set(tbs['income_sheet_cumulate'].columns)

        overlap_columns = []
        for i in c1:
            if '累計' + i in c2:
                overlap_columns.append('累計' + i)

        # get all years
        years = set(tbs['income_sheet_cumulate'].index.levels[1].year)

        for y in years:

            # get rows of the dataframe that is season 4
            ys = tbs['income_sheet_cumulate'].reset_index('stock_id').index.year == y
            ds4 = tbs['income_sheet_cumulate'].reset_index('stock_id').index.month == 3
            df4 = tbs['income_sheet_cumulate'][ds4 & ys].apply(lambda s: pd.to_numeric(s, errors='coerce')).reset_index('date')

            # get rows of the dataframe that is season 3
            yps = tbs['income_sheet_cumulate'].reset_index('stock_id').index.year == y - 1
            ds3 = tbs['income_sheet_cumulate'].reset_index('stock_id').index.month == 11
            df3 = tbs['income_sheet_cumulate'][ds3 & yps].apply(lambda s: pd.to_numeric(s, errors='coerce')).reset_index('date')

            if len(df3) == 0:
                print('skip ', y)
                continue

            # calculate the differences of income_sheet_cumulate to get income_sheet single season
            diff = df4 - df3
            diff = diff.drop(['date'], axis=1)[overlap_columns]

            # remove 累計
            diff.columns = diff.columns.str[2:]

            # 加上第四季的日期
            diff['date'] = pd.to_datetime(str(y) + '-03-31')
            diff = diff[list(c1) + ['date']].reset_index().set_index(['stock_id','date'])

            diff = diff.dropna(how="all")

            # 新增資料於income_sheet尾部
            income_sheet = income_sheet.append(diff)


        # 排序好並更新tbs
        income_sheet = income_sheet.reset_index().sort_values(['stock_id', 'date']).set_index(['stock_id', 'date'])
        tbs['income_sheet'] = income_sheet


    def to_db(self, tbs):
        print('save table to db')
        conn = sqlite3.connect(QUANTX_DB_PATH)
        for i, df in tbs.items():
            print('  ', i)
            df = df.reset_index().sort_values(['stock_id', 'date']).drop_duplicates(['stock_id', 'date']).set_index(['stock_id', 'date'])
            df[df.count().nlargest(900).index].to_sql(i, conn, if_exists='replace')


    def html2db(self, date):
        year = date.year
        if date.month == 3:
            season = 4
            year = year - 1
            month = 11
        elif date.month == 5:
            season = 1
            month = 2
        elif date.month == 8:
            season = 2
            month = 5
        elif date.month == 11:
            season = 3
            month = 8
        else:
            return None

        self.pack_htmls(year, season, os.path.join('data', 'financial_statement', str(year) + str(season)))
        d = self.get_all_pickles(os.path.join('data', 'financial_statement'))
        tbs = self.combine(d)
        self.fill_season4(tbs)
        self.to_db(tbs)
        return {}
