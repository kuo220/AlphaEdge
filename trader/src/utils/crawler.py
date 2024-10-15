import pandas as pd
from io import StringIO
import requests
from typing import List


def stock_list_crawler() -> List[str]:
    """ 爬取上市櫃公司的股票代號 """
    
    # 取得上市公司代號
    twse_url = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=1&industry_code=&Page=1&chklike=Y"

    response = requests.get(twse_url)
    twse_list = pd.read_html(StringIO(response.text))[0]
    twse_list.columns = twse_list.iloc[0, :]
    twse_list = twse_list.iloc[1:]['有價證券代號'].tolist()

    print(f"* Len of listed company in TWSE: {len(twse_list)}")

    # 取得上櫃公司代號
    otc_url = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=2&issuetype=4&industry_code=&Page=1&chklike=Y"

    response = requests.get(otc_url)
    otc_list = pd.read_html(StringIO(response.text))[0]
    otc_list.columns = otc_list.iloc[0, :]
    otc_list = otc_list.iloc[1:]['有價證券代號'].tolist()

    print(f"* Len of listed company in OTC: {len(otc_list)}")

    # Combine two list and sort
    stock_list = sorted(twse_list + otc_list)
    
    print(f"* Len of listed company in market: {len(stock_list)}")
    return stock_list
    

class CrawlShioaji:
    pass


class CrawlHTML:
    pass