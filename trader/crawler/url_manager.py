from typing import List, Dict, Any


class URLManager:
    """ URL Manager """
    
    # 取得上市公司代號
    twse_code_url: str = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=1&issuetype=1&industry_code=&Page=1&chklike=Y"
    
    # 取得上櫃公司代號
    tpex_code_url: str = "https://isin.twse.com.tw/isin/class_main.jsp?owncode=&stockname=&isincode=&market=2&issuetype=4&industry_code=&Page=1&chklike=Y"