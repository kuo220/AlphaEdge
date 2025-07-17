import time
import urllib
import requests
import logging as L
import pandas as pd
from tqdm import tqdm
from datetime import date
from dataclasses import dataclass
from fake_useragent import UserAgent
from requests.exceptions import ReadTimeout

ses = None


def generate_random_header():
    ua = UserAgent()
    user_agent = ua.random
    headers = {"Accept": "*/*", "Connection": "keep-alive", "User-Agent": user_agent}
    return headers


def find_best_session():
    for i in range(10):
        try:
            L.info("獲取新的Session 第", i, "回合")
            headers = generate_random_header()
            ses = requests.Session()
            ses.get("https://www.twse.com.tw/zh/", headers=headers, timeout=10)
            ses.headers.update(headers)
            L.info("成功！")
            return ses
        except (ConnectionError, ReadTimeout) as error:
            L.info(error)
            L.info("失敗,10秒後重試")
            time.sleep(10)

    L.info("您的網頁IP已經被證交所封鎖,請更新IP來獲取解鎖")
    L.info(" 手機:開啟飛航模式,再關閉,即可獲得新的IP")
    L.info("數據機：關閉然後重新打開數據機的電源")


def requests_post(*args1, **args2):
    # get current session
    global ses
    if ses == None:
        ses = find_best_session()

    # download data
    i = 3
    while i >= 0:
        try:
            return ses.post(*args1, timeout=10, **args2)
        except (ConnectionError, ReadTimeout) as error:
            L.info(error)
            L.info("retry one more time after 60s", i, "times left")
            time.sleep(60)
            ses = find_best_session()

        i -= 1
    return pd.DataFrame()


def requests_get(*args1, **args2):
    # get current session
    global ses
    if ses == None:
        ses = find_best_session()

    # download data
    i = 3
    while i >= 0:
        try:
            return ses.get(*args1, timeout=10, **args2)
        except (ConnectionError, ReadTimeout) as error:
            L.error(error)
            L.info("retry one more time after 60s", i, "times left")
            time.sleep(60)
            ses = find_best_session()

        i -= 1
    return pd.DataFrame()


class DownloadProgressBar(tqdm):
    def update_to(self, b=1, bsize=1, tsize=None):
        if tsize is not None:
            self.total = tsize
        self.update(b * bsize - self.n)


def download_url(url, output_path):
    with DownloadProgressBar(
        unit="B", unit_scale=True, miniters=1, desc=url.split("/")[-1]
    ) as t:
        urllib.request.urlretrieve(url, filename=output_path, reporthook=t.update_to)


@dataclass
class FiscalDate:
    year: int
    month: int
    quarter: int

    def __eq__(self, other):
        if not isinstance(other, FiscalDate):
            return NotImplemented
        return (
            (self.year == other.year)
            and (self.month, other.month)
            and (self.quarter == other.quarter)
        )


def to_fiscal_date(date: date) -> FiscalDate:
    """
    Convert a given date to the corresponding fiscal year, quarter, and reference month.

    Args:
        date (datetime.date): The input date.

    Returns:
        Tuple[int, int, int] | None: A tuple (fiscal_year, fiscal_quarter, reference_month),
        or None if the date does not correspond to a fiscal quarter.
    """
    quarter_mapping = {
        3: (4, -1, 11),  # Q4, previous year
        5: (1, 0, 2),  # Q1, same year
        8: (2, 0, 5),  # Q2, same year
        11: (3, 0, 8),  # Q3, same year
    }

    if date.month not in quarter_mapping:
        return None  # Not a quarter month

    quarter, year_offset, month = quarter_mapping[date.month]
    fiscal_year = date.year + year_offset
    fiscal_date = FiscalDate(fiscal_year, month, quarter)

    return fiscal_date
