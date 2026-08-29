from typing import Any, Dict


class URLManager:
    """URL Manager"""

    # fmt: off
    # 本表刻意以空行分隔每一條 URL，維護時一眼就看得出邊界；
    # ruff-format 會移除 dict 內的空行，故以 fmt: off／on 圈住這一段。
    # **例外僅限這個 dict**，其餘程式碼一律交給 formatter（見 CLAUDE.md §2.10）
    URLS: Dict[str, str] = {
        # 台灣證券交易所首頁 URL
        "TWSE_URL": "https://www.twse.com.tw/zh/",

        # 上市公司代號 URL
        "TWSE_CODE_URL": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=2",

        # 上櫃公司代號 URL
        "TPEX_CODE_URL": "https://isin.twse.com.tw/isin/C_public.jsp?strMode=4",

        # 上市公司籌碼 URL
        "TWSE_CHIP_URL": "https://www.twse.com.tw/rwd/zh/fund/T86?date={date}&selectType=ALLBUT0999&response=html",

        # 上櫃公司籌碼 URL (URL1: 2007/4/21 ~ 2014/11/30, URL2: 2014/12/1 ~ present)
        "TPEX_CHIP_URL_1": "https://www.tpex.org.tw/www/zh-tw/insti/dailyTradeHis?type=Daily&cate=EW&date={date}&id=&response=html",
        "TPEX_CHIP_URL_2": "https://www.tpex.org.tw/www/zh-tw/insti/dailyTrade?type=Daily&sect=EW&date={date}&id=&response=html",

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

        # 上市信用交易統計（全部，含股票／ETF／TDR／受益證券，Ex: date = 20260731）
        "TWSE_MARGIN_ALL_URL": "https://www.twse.com.tw/rwd/zh/marginTrading/MI_MARGN?date={date}&selectType=ALL&response=html",

        # 上櫃信用交易統計（全部，Ex: date = 2026/07/31）
        "TPEX_MARGIN_ALL_URL": "https://www.tpex.org.tw/www/zh-tw/margin/balance?date={date}&id=&response=html",

        # 上市除權除息計算結果表（支援日期區間，一次可取整年，Ex: 20240101 / 20241231）
        "TWSE_EX_RIGHT_URL": "https://www.twse.com.tw/rwd/zh/exRight/TWT49U?startDate={start_date}&endDate={end_date}&response=html",

        # 上櫃除權除息計算結果表（支援日期區間，一次可取整年，Ex: 2024/01/01 ~ 2024/12/31）
        # 日期**必須**用斜線格式：傳 20240101 不會報錯，會靜默退回「近三日」的預設區間
        "TPEX_EX_RIGHT_URL": "https://www.tpex.org.tw/www/zh-tw/bulletin/exDailyQ?startDate={start_date}&endDate={end_date}&response=json",

        # 上市收盤行情（Ex: date = 20250801）
        "TWSE_CLOSING_QUOTE_URL": "https://www.twse.com.tw/rwd/zh/afterTrading/MI_INDEX?date={date}&type=ALLBUT0999&response=html",

        # 上櫃收盤行情（Ex: date = 2025/08/01）
        "TPEX_CLOSING_QUOTE_URL": "https://www.tpex.org.tw/www/zh-tw/afterTrading/otc?date={date}&type=EW&id=&response=html&order=0&sort=asc",

        # 上市月營收財報（month: m, market_type: {0: 國內上市, 1: 國外上市}）
        "TWSE_MONTHLY_REVENUE_REPORT_URL": "https://mopsov.twse.com.tw/nas/t21/sii/t21sc03_{roc_year}_{month}_{market_type}.html",

        # 上櫃月營收財報（month: m, market_type: {0: 國內上櫃, 1: 國外上櫃}）
        "TPEX_MONTHLY_REVENUE_REPORT_URL": "https://mopsov.twse.com.tw/nas/t21/otc/t21sc03_{roc_year}_{month}_{market_type}.html",

        # === 上市上櫃財報（四大報表）爬蟲網站（新方式）===
        # 資產負債表
        "BALANCE_SHEET_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t163sb05",

        # 綜合損益表
        "INCOME_STATEMENT_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t163sb04",

        # 現金流量表
        "CASH_FLOW_STATEMENT_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t163sb20",

        # 權益變動表
        "EQUITY_CHANGE_STATEMENT_URL": "https://mopsov.twse.com.tw/mops/web/ajax_t164sb06",

        # 台期貨每日交易行情（TAIFEX）
        # **與本表其他 URL 不同：這是 POST 端點，參數走 form data 而非 query string**，
        # 因此沒有 {} 佔位符——對它呼叫 get_url(..., date=...) 既不會報錯也不會生效
        # 必要的 form 欄位：
        #   queryDate: 查詢日（yyyy/MM/dd）
        #   commodity_id / commodity_idt: 商品代碼，兩者須帶相同值
        #     （Ex: TX 臺股期貨、MTX 小型臺指、TMF 微型臺指；股票期貨如台積電期為 CDF）
        #   MarketCode / marketCode: 0 一般交易時段（日盤）、1 盤後交易時段（夜盤）
        # 兩個時段的**欄位結構不同**（日盤 17 欄、夜盤 15 欄且無結算價與未沖銷契約量），
        # 且各自是獨立行情，須分別查詢後以 session 區分入庫
        # 一次僅能查一個商品；非交易日回傳的頁面無表格（`pd.read_html` 會拋 ValueError）
        "TAIFEX_FUTURES_PRICE_URL": "https://www.taifex.com.tw/cht/3/futDailyMarketReport",
    }
    # fmt: on

    @classmethod
    def get_url(cls, url_name: str, **kwargs: Any) -> str:
        """取得指定 URL，若提供 kwargs 則進行格式化"""

        if url_name not in cls.URLS:
            raise ValueError(f"URL key '{url_name}' not found in URLManager")

        url: str = cls.URLS[url_name]
        return url.format(**kwargs) if kwargs else url
