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
        
    }
    
    
    @classmethod
    def get_code_url(cls, url_name: str) -> str:
        """ 取得上市櫃公司代號 URL """
        return cls.URLS[url_name]
    
    
    @classmethod
    def get_chip_url(cls, url_name: str, **kwargs: Any) -> str:
        """ 取得上市櫃公司籌碼 URL """
        
        if url_name not in cls.URLS:
            raise ValueError(f"URL key '{url_name}' not found in URLManager.")
        return cls.URLS[url_name].format(**kwargs)