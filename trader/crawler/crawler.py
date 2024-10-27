import copy
import warnings
from io import StringIO
from financial_statement import html2db
from requests.exceptions import ReadTimeout
from requests.exceptions import ConnectionError
import datetime
import time
import os
import pandas as pd
from tqdm import tnrange, tqdm_notebook
from dateutil.rrule import rrule, DAILY, MONTHLY
import random
import requests
import shutil
import zipfile
import urllib.request
from tqdm import tqdm
import ipywidgets as widgets
from IPython.display import display
from fake_useragent import UserAgent
from pathlib import Path
from shared_list import table_without_stockid
from bs4 import BeautifulSoup
from dateutil.relativedelta import relativedelta
from typing import List


def generate_random_header():
    ua = UserAgent()
    user_agent = ua.random
    headers = {'Accept': '*/*', 'Connection': 'keep-alive',
               'User-Agent': user_agent}
    return headers


def find_best_session():
    for i in range(10):
        try:
            print('獲取新的Session 第', i, '回合')
            headers = generate_random_header()
            ses = requests.Session()
            ses.get('https://www.twse.com.tw/zh/', headers=headers, timeout=10)
            ses.headers.update(headers)
            print('成功！')
            return ses
        except (ConnectionError, ReadTimeout) as error:
            print(error)
            print('失敗，10秒後重試')
            time.sleep(10)

    print('您的網頁IP已經被證交所封鎖，請更新IP來獲取解鎖')
    print("　手機：開啟飛航模式，再關閉，即可獲得新的IP")
    print("數據機：關閉然後重新打開數據機的電源")


ses = None


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
            print(error)
            print('retry one more time after 60s', i, 'times left')
            time.sleep(60)
            ses = find_best_session()

        i -= 1
    return pd.DataFrame()


ses = None


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
            print(error)
            print('retry one more time after 60s', i, 'times left')
            time.sleep(60)
            ses = find_best_session()

        i -= 1
    return pd.DataFrame()


warnings.simplefilter(action='ignore', category=FutureWarning)


def add_tw_pmi_csv(conn, name):
    path = os.path.join('data', 'pmi.xlsx')
    df = pd.read_excel(path)
    df.drop(0, inplace=True)
    df.rename(columns={"Unnamed: 0": "date"}, inplace=True)
    dates = df["date"]
    new_dates = pd.to_datetime(dates) + pd.DateOffset(months=1)
    df["date"] = new_dates
    df.set_index(['date'], inplace=True)

    add_to_sql_without_stock_id_index(conn, name, df)

    print("df save successfully")


def add_tw_nmi_csv(conn, name):
    path = os.path.join('data', 'nmi.xlsx')
    df = pd.read_excel(path)
    df.drop(0, inplace=True)
    df.rename(columns={"Unnamed: 0": "date"}, inplace=True)
    dates = df["date"]
    new_dates = pd.to_datetime(dates) + pd.DateOffset(months=1)
    df["date"] = new_dates
    df.set_index(['date'], inplace=True)

    add_to_sql_without_stock_id_index(conn, name, df)

    print("df save successfully")


def add_tw_bi_csv(conn, name):
    path = os.path.join('data', 'tw_bi.xlsx')
    df = pd.read_excel(path)
    df.drop(0, inplace=True)
    df.rename(columns={"Unnamed: 0": "date"}, inplace=True)
    df.drop("景氣對策信號(燈號)", axis=1, inplace=True)
    dates = df["date"]
    new_dates = pd.to_datetime(dates) + pd.DateOffset(months=1, days=26)
    df["date"] = new_dates
    df.set_index(['date'], inplace=True)

    add_to_sql_without_stock_id_index(conn, name, df)

    print("df save successfully")


def crawl_tw_total_pmi(date):
    url = "https://index.ndc.gov.tw/n/excel/data/PMI/total?sy=" + str(date.year) + "&sm=" + str(
        date.month) + "&ey=" + str(date.year) + "&em=" + str(
        date.month) + "&id=59%2C60%2C61%2C62%2C63%2C64%2C65%2C66%2C279%2C280%2C281%2C282&sq=0,0,0&file_type=xlsx"
    print("TW Total PMI", url)

    path_xlsx = os.path.join('data', 'macro_economics', str(date.year) + "_" + str(date.month) + '_pmi.xlsx')
    try:
        urllib.request.urlretrieve(url, filename=path_xlsx)
    except:
        print("**WARRN: requests cannot download {} {} total_pmi.xls".format(date.year, date.month))
        return None

    print("finish download")

    df = pd.read_excel(path_xlsx)
    df.drop(0, inplace=True)
    df.rename(columns={"Unnamed: 0": "date"}, inplace=True)
    dates = df["date"]
    new_dates = pd.to_datetime(dates) + pd.DateOffset(months=1)
    df["date"] = new_dates
    df.set_index(['date'], inplace=True)
    df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
    df = df[df.columns[df.isnull().all() == False]]

    return df


def crawl_tw_total_nmi(date):
    url = "https://index.ndc.gov.tw/n/excel/data/NMI/total?sy=" + str(date.year) + "&sm=" + str(
        date.month) + "&ey=" + str(date.year) + "&em=" + str(
        date.month) + "&id=160%2C161%2C162%2C163%2C164%2C165%2C166%2C167%2C168%2C169%2C170%2C171%2C172&sq=0,0,0&file_type=xlsx"
    print("TW Total NMI", url)

    path_xlsx = os.path.join('data', 'macro_economics', str(date.year) + "_" + str(date.month) + '_nmi.xlsx')
    try:
        urllib.request.urlretrieve(url, filename=path_xlsx)
    except:
        print("**WARRN: requests cannot download {} {} total_nmi.xls".format(date.year, date.month))
        return None

    print("finish download")

    df = pd.read_excel(path_xlsx)
    df.drop(0, inplace=True)
    df.rename(columns={"Unnamed: 0": "date"}, inplace=True)
    dates = df["date"]
    new_dates = pd.to_datetime(dates) + pd.DateOffset(months=1)
    df["date"] = new_dates
    df.set_index(['date'], inplace=True)
    df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
    df = df[df.columns[df.isnull().all() == False]]

    return df


def crawl_tw_business_indicator(date):
    url = "https://index.ndc.gov.tw/n/excel/data/eco/indicators?sy=" + str(date.year) + "&sm=" + str(
        date.month) + "&ey=" + str(date.year) + "&em=" + str(
        date.month) + "&id=1%2C12%2C13%2C14%2C25%2C26%2C33%2C34&sq=0,0,0&file_type=xlsx"
    print("TW Business Indicator ", url)

    path_xlsx = os.path.join('data', 'macro_economics', str(date.year) + "_" + str(date.month) + '_bi.xlsx')
    try:
        urllib.request.urlretrieve(url, filename=path_xlsx)
    except:
        print("**WARRN: requests cannot download {} {} total_bi.xls".format(date.year, date.month))
        return None

    print("finish download")

    df = pd.read_excel(path_xlsx)
    df.drop(0, inplace=True)
    df.rename(columns={"Unnamed: 0": "date"}, inplace=True)
    dates = df["date"]
    new_dates = pd.to_datetime(dates) + pd.DateOffset(months=1, days=26)
    df["date"] = new_dates
    df.set_index(['date'], inplace=True)
    df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
    df = df[df.columns[df.isnull().all() == False]]

    return df


def crawl_benchmark_return(date):
    url = "https://www.twse.com.tw/rwd/zh/TAIEX/MFI94U?date=" + date.strftime("%Y%m") + "01&response=html"
    print("發行量加權股價報酬指數", url)

    # 偽瀏覽器
    headers = generate_random_header()

    # 下載該年月的網站，並用pandas轉換成 dataframe
    try:
        r = requests_get(url, headers=headers, verify='./certs.cer')
        r.encoding = "UTF-8"
    except:
        print("**WARRN: requests cannot get html")
        return None

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


# cttc 代表是爬取上櫃資料
def crawl_margin_balance_cttc(date):
    datestr = date.strftime('%Y%m%d')

    url = ('https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=htm&d=' +
           str(date.year - 1911) + "/" + datestr[4:6] + "/" + datestr[6:] + '&s=0,asc')
    print("上櫃", url)

    # 偽瀏覽器
    headers = generate_random_header()

    # 下載該年月的網站，並用pandas轉換成 dataframe
    try:
        r = requests_get(url, headers=headers, verify='./certs.cer')
        r.encoding = 'UTF-8'
    except:
        print('**WARRN: requests cannot get html')
        return None

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


def crawl_margin_balance(date):
    # 上櫃資料從102/1/2以後才提供，所以融資融券先以102/1/2以後為主
    datestr = date.strftime('%Y%m%d')

    url = 'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=' + datestr + '&selectType=MS&response=html'
    print("上市", url)

    # 偽瀏覽器
    headers = generate_random_header()

    # 下載該年月的網站，並用pandas轉換成 dataframe
    try:
        r = requests_get(url, headers=headers, verify='./certs.cer')
        r.encoding = 'UTF-8'
    except:
        print('**WARRN: requests cannot get html')
        return None

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
    df_otc = crawl_margin_balance_cttc(date)
    df = pd.concat([df, df_otc], axis=1)

    return df


def crawl_margin_transactions_cttc(date):
    datestr = date.strftime('%Y%m%d')

    url = ('https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=htm&d=' +
           str(date.year - 1911) + "/" + datestr[4:6] + "/" + datestr[6:] + '&s=0,asc')
    print("上櫃", url)

    # 偽瀏覽器
    headers = generate_random_header()

    # 下載該年月的網站，並用pandas轉換成 dataframe
    try:
        r = requests_get(url, headers=headers, verify='./certs.cer')
        r.encoding = 'UTF-8'
    except:
        print('**WARRN: requests cannot get html')
        return None

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


def crawl_margin_transactions(date):
    # 上櫃資料從102/1/2以後才提供，所以融資融券先以102/1/2以後為主
    datestr = date.strftime('%Y%m%d')

    # 上市分成4個網站爬取: 封閉式基金、ETF、存託憑證、股票
    # ETF
    url_list = ["&selectType=0049&response=html", "&selectType=0099P&response=html", "&selectType=9299&response=html",
                "&selectType=STOCK&response=html"]
    c = 0
    df = None
    for url in url_list:
        url = 'https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date=' + datestr + url
        print("上市", url)

        # 偽瀏覽器
        headers = generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        try:
            r = requests_get(url, headers=headers, verify='./certs.cer')
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

    df_otc = crawl_margin_transactions_cttc(date)
    if df_otc is not None and df is not None:
        df = pd.concat([df, df_otc], axis=0)
    elif df is None and df_otc is not None:
        return df_otc
    elif df is not None and df_otc is None:
        return df
    else:
        return None
    return df


def crawl_price_cttc(date):
    # 上櫃資料從96/7/2以後才提供
    # 109/4/30以後csv檔的column不一樣
    datestr = date.strftime('%Y%m%d')

    try:
        url = 'https://www.tpex.org.tw/web/stock/aftertrading/otc_quotes_no1430/stk_wn1430_result.php?l=zh-tw&o=csv&d=' + str(
            date.year - 1911) + "/" + datestr[4:6] + "/" + datestr[6:] + '&se=EW&s=0,asc,0'
        r = requests_post(url)
        print("上櫃", url)
    except Exception as e:
        print('**WARRN: cannot get stock price at', datestr)
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
    if datestr >= str(20200430):
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


def crawl_price(date):
    datestr = date.strftime('%Y%m%d')

    try:
        url = 'https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date=' + datestr + '&type=ALLBUT0999'
        r = requests_post(url)
        print("上市", url)
    except Exception as e:
        print('**WARRN: cannot get stock price at', datestr)
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

    df1 = crawl_price_cttc(date)

    df = df.append(df1)

    return df


def crawl_price_tpex_1(date):
    datestr = date.strftime('%Y%m%d')
    datestr = str(int(datestr[0:4]) - 1911) + datestr[4:]

    # url = "https://hist.tpex.org.tw/Hist/STOCK/AFTERTRADING/DAILY_CLOSE_QUOTES/RSTA3104_951201.HTML"
    url = "https://hist.tpex.org.tw/Hist/STOCK/AFTERTRADING/DAILY_CLOSE_QUOTES/RSTA3104_" + datestr + ".HTML"

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


# for date 2007/01/02 - 2007/04/20
def crawl_price_tpex_2(date):
    datestr = date.strftime('%Y%m%d')
    datestr = str(int(datestr[0:4]) - 1911) + '/' + datestr[2:4] + '/' + datestr[4:6]

    # 目標網址
    url = "https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotesB/stk_quote_result.php?timestamp=1693758523823"

    # 設置 payload 參數，只包含日期
    payload = {"ajax": "true", "input_date": datestr}  # 修改為你需要的日期

    headers = generate_random_header()
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

    # print(df)

    return df


# for date 2007/04/20 - 2007/06/29
def crawl_price_tpex_3(date):
    datestr = date.strftime('%Y%m%d')
    datestr = str(int(datestr[0:4]) - 1911) + datestr[4:]

    # url = 'https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=htm&d=96/04/23&s=0,asc,0'
    url = 'https://www.tpex.org.tw/web/stock/aftertrading/daily_close_quotes/stk_quote_result.php?l=zh-tw&o=htm&d=' + datestr[
                                                                                                                      0:2] + '/' + datestr[
                                                                                                                                   2:4] + '/' + datestr[
                                                                                                                                                4:6] + '&s=0,asc,0'

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


# 爬上市公司的股價
def crawl_old_price(date):
    datestr = date.strftime('%Y%m%d')

    try:
        r = requests_post(
            'https://www.twse.com.tw/exchangeReport/MI_INDEX?response=csv&date=' + datestr + '&type=ALLBUT0999')
    except Exception as e:
        print('**WARRN: cannot get stock price at', datestr)
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
        df1 = crawl_price_tpex_1(date)
    elif date.year == 2007:
        if date.month == 4:
            if date.day <= 20:
                df1 = crawl_price_tpex_2(date)
            else:
                df1 = crawl_price_tpex_3(date)
        elif date.month < 4:
            df1 = crawl_price_tpex_2(date)
        else:
            df1 = crawl_price_tpex_3(date)

    df = df.append(df1)

    return df


def crawl_monthly_report_cttc(date):
    url = 'https://mops.twse.com.tw/nas/t21/otc/t21sc03_' + str(date.year - 1911) + '_' + str(date.month) + '.html'
    print("上櫃：", url)

    # 偽瀏覽器
    headers = generate_random_header()

    # 下載該年月的網站，並用pandas轉換成 dataframe
    try:
        r = requests_get(url, headers=headers, verify='./certs.cer')
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


def crawl_monthly_report(date):
    x = [datetime.date(2011, 2, 10), datetime.date(2012, 1, 10)]
    if date in x:
        df1 = crawl_monthly_report_cttc(date)
        return df1
    else:
        url = 'https://mops.twse.com.tw/nas/t21/sii/t21sc03_' + str(date.year - 1911) + '_' + str(date.month) + '.html'
        print("上市", url)

        # 偽瀏覽器
        headers = generate_random_header()

        # 下載該年月的網站，並用pandas轉換成 dataframe
        try:
            r = requests_get(url, headers=headers, verify='./certs.cer')
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

        df1 = crawl_monthly_report_cttc(date)

        df = df.append(df1)

        return df


def crawl_finance_statement2019(year, season):
    def ifrs_url(year, season):
        url = "https://mops.twse.com.tw/server-java/FileDownLoad?step=9&fileName=tifrs-" + str(year) + "Q" + str(season) \
              + ".zip&filePath=/home/html/nas/ifrs/" + str(year) + "/"
        print(url)
        return url

    headers = generate_random_header()

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

    def ifrs_url(year, season):
        url = "https://mops.twse.com.tw/server-java/FileDownLoad?step=9&fileName=tifrs-" + str(year) + "Q" + str(season) \
              + ".zip&filePath=/home/html/nas/ifrs/" + str(year) + "/"
        print(url)
        return url

    url = ifrs_url(year, season)
    download_url(url, 'temp.zip')

    print('finish download')

    path = os.path.join('data', 'financial_statement', str(year) + str(season))

    if os.path.isdir(path):
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


def crawl_finance_statement(year, season, stock_ids):
    # directory = os.path.join('Data', 'financial_statement', str(year) + str(season))
    directory = str(Path(__file__).resolve().parents[1] / 'Data' / 'financial_statement')
    if not os.path.exists(directory):
        os.makedirs(directory)

    def download_html(year, season, stock_ids, report_type='C'):

        headers = {
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3''Accept-Encoding: gzip, deflate',
            'Accept-Language': 'zh-TW,zh;q=0.9,en-US;q=0.8,en;q=0.7',
            'Cache-Control': 'max-age=0',
            'Connection': 'keep-alive',
            'Host': 'mops.twse.com.tw',
            'Upgrade-Insecure-Requests': '1',
            'User-Agent': generate_random_header()["User-Agent"]
        }
        pbar = tqdm(stock_ids)
        for i in pbar:

            # check if the html is already parsed
            file = os.path.join(directory, str(i) + '.html')
            if os.path.exists(file) and os.stat(file).st_size > 20000:
                continue

            pbar.set_description('parse htmls %d season %d stock %s' % (year, season, str(i)))

            # start parsing
            if year >= 2019:
                ty = {"C": "cr", "B": "er", "C": "ir"}
                url = "https://mops.twse.com.tw/server-java/t164sb01?step=3&year=2019&file_name=tifrs-fr1-m1-ci-" + ty[
                    report_type] + "-" + i + "-" + str(year) + "Q" + str(season) + ".html"
            else:
                url = ('https://mops.twse.com.tw/server-java/t164sb01?step=1&CO_ID='
                       + i + '&SYEAR=' + str(year) + '&SSEASON=' + str(season) + '&REPORT_ID=' + str(report_type))

            print(url)
            try:
                r = requests_get(url, headers=headers, timeout=30, verify='./certs.cer')
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


def crawl_finance_statement_by_date(date):
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
        crawl_finance_statement2019(year, season)
    else:
        df = crawl_monthly_report(datetime.datetime(year, month, 1))
        crawl_finance_statement(year, season, df.index.levels[0])
    html2db(date)
    return {}


def date_range(start_date, end_date):
    return [dt.date() for dt in rrule(DAILY, dtstart=start_date, until=end_date)]


def month_range(start_date, end_date):
    return [dt.date() for dt in rrule(MONTHLY, dtstart=start_date, until=end_date)]


def season_range(start_date, end_date):
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


def table_exist(conn, table):
    return list(conn.execute(
        "select count(*) from sqlite_master where type='table' and name='" + table + "'"))[0][0] == 1


def table_latest_date(conn, table):
    cursor = conn.execute('SELECT date FROM ' + table + ' ORDER BY date DESC LIMIT 1;')
    return datetime.datetime.strptime(list(cursor)[0][0], '%Y-%m-%d %H:%M:%S')


def table_earliest_date(conn, table):
    cursor = conn.execute('SELECT date FROM ' + table + ' ORDER BY date ASC LIMIT 1;')
    return datetime.datetime.strptime(list(cursor)[0][0], '%Y-%m-%d %H:%M:%S')


def add_to_sql(conn, name, df):
    # get the existing dataframe in sqlite3
    exist = table_exist(conn, name)
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


def add_to_sql_without_stock_id_index(conn, name, df):
    exist = table_exist(conn, name)
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


def update_table(conn, table_name, crawl_function, dates):
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
            if table_name in table_without_stockid:
                add_to_sql_without_stock_id_index(conn, table_name, df)
            else:
                add_to_sql(conn, table_name, df)
            print('save', len(df))
            df = pd.DataFrame()

        time.sleep(15)

    if df is not None and len(df) != 0:
        if table_name in table_without_stockid:
            add_to_sql_without_stock_id_index(conn, table_name, df)
        else:
            add_to_sql(conn, table_name, df)
        print('df save successfully')

    if len(dfs) != 0:
        for i, d in dfs.items():
            print('saving df', d.head(), len(d))
            if len(d) != 0:
                add_to_sql(conn, i, d)
                print('df save successfully', d.head())


def update_table_from_tej(conn, table_name, get_function, progress):
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
            if table_name in table_without_stockid:
                add_to_sql_without_stock_id_index(conn, table_name, df)
            else:
                add_to_sql(conn, table_name, df)
            print('save', len(df))
            df = pd.DataFrame()

        time.sleep(15)

    if df is not None and len(df) != 0:
        if table_name in table_without_stockid:
            add_to_sql_without_stock_id_index(conn, table_name, df)
        else:
            add_to_sql(conn, table_name, df)
        print('df save successfully')

    if len(dfs) != 0:
        for i, d in dfs.items():
            print('saving df', d.head(), len(d))
            if len(d) != 0:
                add_to_sql(conn, i, d)
                print('df save successfully', d.head())


def get_old_capital_increment(file):
    df = pd.read_csv("./data/現金增資/" + file)
    df = df.astype(str)
    df = df.rename(columns={'代號': 'stock_id', '除權日': 'date'})
    df = df[["stock_id", "date", "現金增資(仟股)"]]
    df["現金增資(仟股)"] = df["現金增資(仟股)"].str.replace(',', '').astype(int)
    df["date"] = df["date"].apply(lambda x: x.replace("/", "-") + "-15")
    df["date"] = pd.to_datetime(df["date"])

    df = df.set_index(['stock_id', 'date'])

    df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
    df = df[df.columns[df.isnull().all() == False]]

    return df

def get_old_ds_chip(file):
    df = pd.read_excel("./data/董監持股/" + file)
    df = df.astype(str)
    df = df.rename(columns={'代號': 'stock_id', '年月日': 'date'})
    df = df[["stock_id", "date", "董監持股%"]]
    df["date"] = df["date"].apply(lambda x: x.replace("/", "-") + "-15")
    df["date"] = pd.to_datetime(df["date"])

    df = df.set_index(['stock_id', 'date'])

    df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
    df = df[df.columns[df.isnull().all() == False]]

    return df


def get_old_monthly_revenue(file):
    df = pd.read_excel("./data/月營收/" + file)
    df = df.astype(str)
    df = df.rename(columns={'證券代碼': 'stock_id', '年月': 'date', '單月營收(千元)': '當月營收',
                            '去年單月營收(千元)': '去年當月營收', '累計營收成長率％': '前期比較增減(%)',
                            '單月營收成長率％': '去年同月增減(%)', '單月營收與上月比％': '上月比較增減(%)',
                            '去年累計營收(千元)': '去年累計營收', '累計營收(千元)': '當月累計營收'})
    df = df[["stock_id", "date", '當月營收', '去年當月營收', '前期比較增減(%)', '去年同月增減(%)', '上月比較增減(%)',
             '去年累計營收', '當月累計營收']]
    df["stock_id"] = df["stock_id"].apply(lambda x: x.split(" ")[0])
    df['date'] = pd.to_datetime(df['date'], format='%Y%m')
    df['date'] = df['date'].apply(lambda x: x.replace(day=10, hour=0, minute=0, second=0) + relativedelta(months=1))

    df = df.set_index(['stock_id', 'date'])

    df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
    df = df[df.columns[df.isnull().all() == False]]

    return df


def get_old_statement(statement_name, file):
    df = pd.read_excel("./data/" + statement_name + "/" + file)
    df = df.astype(str)
    df = df.rename(columns={'證券代碼': 'stock_id', '年月': 'date'})
    df["stock_id"] = df["stock_id"].apply(lambda x: x.split(" ")[0])
    df['date'] = pd.to_datetime(df['date'], format='%Y%m')
    df['date'] = df['date'].apply(
        lambda x: x.replace(month=8, day=14, hour=0, minute=0, second=0) if x.month == 6 else (
            x.replace(year=x.year+1, month=3, day=31, hour=0, minute=0, second=0) if x.month == 12 else (
                x.replace(month=5, day=15, hour=0, minute=0, second=0) if x.month == 3 else x.replace(month=11, day=14,
                                                                                                      hour=0, minute=0,
                                                                                                      second=0))))
    df = df.set_index(['stock_id', 'date'])
    df.rename(columns=lambda x: x.replace(' ', ''), inplace=True)
    df = df.apply(lambda s: pd.to_numeric(s, errors='coerce'))
    df = df[df.columns[df.isnull().all() == False]]

    return df


def widget(conn, table_name, crawl_func, range_date):
    date_picker_from = widgets.DatePicker(
        description='from',
        disabled=False,
    )

    if table_exist(conn, table_name):
        date_picker_from.value = table_latest_date(conn, table_name)

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
        update_table(conn, table_name, crawl_func, dates)

    btn.on_click(onupdate)

    if table_exist(conn, table_name):
        label = widgets.Label(table_name +
                              ' (from ' + table_earliest_date(conn, table_name).strftime('%Y-%m-%d') +
                              ' to ' + table_latest_date(conn, table_name).strftime('%Y-%m-%d') + ')')
    else:
        label = widgets.Label(table_name + ' (No table found)(對於finance_statement是正常情況)')

    items = [date_picker_from, date_picker_to, btn]
    display(widgets.VBox([label, widgets.HBox(items)]))


# 測試用
def test():
    import sqlite3
    import os
    from dateutil.relativedelta import relativedelta
    #
    #     # 把垃圾國發會的xls檔轉成xlsx才能用
    #     transform_xls_to_xlsx(path = './data')
    #     print("transform xls to xlsx finished")
    conn = sqlite3.connect(os.path.join('data', "data.db"))
    dates = [datetime.datetime(2024, 3, 31)]
    # update price table
    update_table(conn, 'finance_statement', crawl_finance_statement_by_date, dates)


    #
    #     add_tw_pmi_csv(conn, "tw_total_pmi")
    #     add_tw_nmi_csv(conn, "tw_total_nmi")
    #     add_tw_bi_csv(conn, "tw_business_indicator")
    #
    #     fromd = table_latest_date(conn, "benchmark_return")
    #     fromd = fromd.replace(day=1)
    #     tod = datetime.datetime.now().date()
    #     dates = month_range(fromd, tod)
    #     update_table(conn, 'benchmark_return', crawl_benchmark_return, dates)
    #
    #     fromd = table_latest_date(conn, "tw_total_nmi")
    #     fromd = fromd - relativedelta(months=1)
    #     tod = datetime.datetime.now().date()
    #     dates = month_range(fromd, tod)
    #     update_table(conn, "tw_total_nmi", crawl_tw_total_nmi, dates)
    #
    #     fromd = table_latest_date(conn, "tw_business_indicator")
    #     fromd = fromd - relativedelta(months=1)
    #     tod = datetime.datetime.now().date()
    #     dates = month_range(fromd, tod)
    #     update_table(conn, "tw_business_indicator", crawl_tw_business_indicator, dates)
    #
    #     fromd = table_latest_date(conn, "margin_balance")
    #     tod = datetime.datetime(2023, 9, 1)
    #     dates = date_range(fromd, tod)
    #     update_table(conn, "margin_balance", crawl_margin_balance, dates)
    #
    #     fromd = datetime.datetime(2015, 1, 2)
    #     tod = datetime.datetime(2015, 1, 3)
    #     dates = date_range(fromd, tod)
    #     update_table(conn, "margin_transactions", crawl_margin_transactions, dates)
    #     fromd = datetime.datetime(2007, 6, 27)
    #     tod = datetime.datetime(2007, 6, 29)
    #     dates = date_range(fromd, tod)
    #     update_table(conn, "price", crawl_old_price, dates)
    #     progress = ["董監持股_2002_2003.xlsx", "董監持股_2004_2005.xlsx", "董監持股_2006_2007.xlsx", "董監持股_2008_2009.xlsx",
    #                 "董監持股_2010_2011.xlsx", "董監持股_2012_2013.xlsx", "董監持股_2014_2015.xlsx", "董監持股_2016_2017.xlsx",
    #                 "董監持股_2018_2019.xlsx", "董監持股_2020_2023.xlsx"]
    #     update_table_from_tej(conn, "director_supervisor_chip", get_old_ds_chip, progress)
    # progress = ["a.xlsx"]
    # statement_name = "資產負債表"
    # update_table_from_tej(conn, "tej_balance_sheet", statement_name, get_old_statement, progress)

    # progress = ["a.xlsx"]
    # statement_name = "損益表_單季"
    # update_table_from_tej(conn, "tej_income_sheet", statement_name, get_old_statement, progress)
    #
    # progress = ["a.xlsx"]
    # statement_name = "損益表_累積"
    # update_table_from_tej(conn, "tej_income_sheet_cumulate", statement_name, get_old_statement, progress)
    #
    # progress = ["a.xlsx"]
    # statement_name = "現金流量表"
    # update_table_from_tej(conn, "tej_cash_flows", statement_name, get_old_statement, progress)

def stocklist_crawler() -> List[str]:
    # 取得上市公司代號
    urlListed = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=1&industry_code=&Page=1&chklike=Y"

    response = requests.get(urlListed)
    listed = pd.read_html(response.text)[0]
    listed.columns = listed.iloc[0, :]
    listed = listed[["有價證券代號", "有價證券名稱", "市場別", "產業別", "公開發行/上市(櫃)/發行日"]]
    listed = listed.iloc[1:]

    stockListListed = listed["有價證券代號"]

    stockListListed  = stockListListed.tolist()
    print("* Len of listed company in TWSE:", len(stockListListed))

    # 取得上櫃公司代號
    urlOTC = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=2&issuetype=4&industry_code=&Page=1&chklike=Y"

    response = requests.get(urlOTC)
    listed = pd.read_html(response.text)[0]
    listed.columns = listed.iloc[0, :]
    listed = listed[["有價證券代號", "有價證券名稱", "市場別", "產業別", "公開發行/上市(櫃)/發行日"]]
    listed = listed.iloc[1:]

    stockListOTC = listed["有價證券代號"]

    stockListOTC  = stockListOTC.tolist()

    print("* Len of listed company in OTC:", len(stockListOTC))

    # Combine two list and sort
    stockList = stockListListed + stockListOTC
    stockList.sort()
    print("* Len of listed company in market:", len(stockList))

    return stockList
