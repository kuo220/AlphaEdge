from typing import Dict, Any


class URLManager:
    """ URL Manager """

    URLS: Dict[str, str] = {
        # 台灣證券交易所首頁 URL
        "TWSE_URL": "https://www.twse.com.tw/zh/",

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

        # 上市信用交易統計（Summary）
        "TWSE_MARGIN_SUMMARY_URL": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=MS&response=html",

        # 上市信用交易統計（封閉式基金 Fund）
        "TWSE_MARGIN_FUND_URL": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=0049&response=html",

        # 上市信用交易統計（ETF）
        "TWSE_MARGIN_ETF_URL": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=0099P&response=html",

        # 上市信用交易統計（存託憑證 TDR）
        "TWSE_MARGIN_TDR_URL": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=9299&response=html",

        # 上市信用交易統計（股票）
        "TWSE_MARGIN_STOCK_URL": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=STOCK&response=html",

        # 上櫃信用交易統計（Summary）
        "TPEX_MARGIN_SUMMARY_URL": "https://www.tpex.org.tw/web/stock/margin_trading/margin_balance/margin_bal_result.php?l=zh-tw&o=htm&d={roc_year}/{month}/{day}&s=0,asc",

        # 上市收盤行情
        "TWSE_CLOSING_QUOTE_URL": "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=html",

        # 上櫃收盤行情
        "TPEX_CLOSING_QUOTE_URL": "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?date={year}%2F{month}%2F{day}&type=EW&id=&response=html&order=0&sort=asc",

        # 上市月營收財報（month: m, market_type: {0: 國內上市, 1: 國外上市}）
        "TWSE_MONTHLY_REVENUE_REPORT_URL": "https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{roc_year}_{month}_{market_type}.html",

        # 上櫃月營收財報（month: m, market_type: {0: 國內上櫃, 1: 國外上櫃}）
        "TPEX_MONTHLY_REVENUE_REPORT_URL": "https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_{roc_year}_{month}_{market_type}.html",

        # 上市上櫃財報（四大報表）爬蟲網站（新方式）
        # 資產負債表
        "BALANCE_SHEET_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t163sb05",
        # 綜合損益表
        "INCOME_STATEMENT_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04",
        # 現金流量表
        "CASH_FLOW_STATEMENT_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t163sb20",
        # 權益變動表
        "EQUITY_CHANGE_STATEMENT_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t164sb06",
    }


    @classmethod
    def get_url(cls, url_name: str, **kwargs: Any) -> str:
        """ 取得指定 URL，若提供 kwargs 則進行格式化 """

        if url_name not in cls.URLS:
            raise ValueError(f"URL key '{url_name}' not found in URLManager.")

        url = cls.URLS[url_name]
        return url.format(**kwargs) if kwargs else url
