from typing import List, Dict, Any


class URLManager:
    """ URL Manager """
    
    # 取得上市公司代號
    TWSE_CODE_URL: str = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2"
    
    # 取得上櫃公司代號
    TPEX_CODE_URL: str = "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4"