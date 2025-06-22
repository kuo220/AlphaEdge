from typing import List, Dict, Any


class URLManager:
    """ URL Manager """
    
    URLS: Dict[str, str] = {
        # 上市公司代號 URL
        "TWSE_CODE_URL": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",
        
        # 上櫃公司代號 URL
        "TPEX_CODE_URL": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4",
        
        # 上市公司籌碼 URL
        "TWSE_CHIP_URL": "https://www.twse.com.tw/rwd/zh/fund/T86?date={date}&selectType=ALLBUT0999&response=html",
        
        # 上櫃公司籌碼 URL
        "TPEX_CHIP_URL": "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={date}&id=&response=html",
        
        # 發行量加權股價報酬指數
        "TAIEX_RETURN_INDEX": "https://www.twse.com.tw/rwd/zh/TAIEX/MFI94U?date={date}01&response=html",
        
        # 上市信用交易餘額查詢
        "TWSE_MARGIN_BALANCE_URL": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=MS&response=html",
        
        # 上櫃信用交易餘額查詢
        "TPEX_MARGIN_BALANCE_URL": "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=htm&d={roc_year}/{month}/{day}&s=0,asc",
        
    }
    
    
    @classmethod
    def get_url(cls, url_name: str, **kwargs: Any) -> str:
        """ 取得指定 URL，若提供 kwargs 則進行格式化 """
        
        if url_name not in cls.URLS:
            raise ValueError(f"URL key '{url_name}' not found in URLManager.")
        
        url = cls.URLS[url_name]
        return url.format(**kwargs) if kwargs else url
    
