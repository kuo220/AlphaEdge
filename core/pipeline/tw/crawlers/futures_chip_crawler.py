import datetime
from typing import Dict, Optional

import requests
from loguru import logger

from core.pipeline.shared.base_crawler import BaseDataCrawler
from core.pipeline.shared.request_utils import RequestUtils
from core.pipeline.utils.url_manager import URLManager
from core.utils import FileEncoding

"""
台期貨籌碼爬蟲（三大法人、大額交易人、選擇權 PCR）

**三個資料集共用同一種請求形態**：POST ＋ 日期區間，回 big5 CSV。
故合成一支 crawler，而不是三支只差網址的檔案。

1. **一次請求涵蓋所有商品**
    與 `futures_price_crawler` 的「逐商品 × 逐時段 × 逐日」完全不同——
    這三個端點一天只要一次請求就拿到全市場（大額交易人一天約 80KB）。
    **不要為了「只要 TX」而逐商品打**，那只會讓請求數乘上商品數。

2. **編碼是 big5**
    與保證金 crawler 同一個處境：`requests` 猜的編碼不可信，故本層一律回傳
    **解碼後的字串**，解碼點只有這裡一處。

3. **盤後才有資料**
    三者都在收盤後公布。當日盤中查會拿到空表（只有表頭），那是正常狀態，
    不是失敗——回測要用的本來就是前一交易日的籌碼（見 `FuturesChipAPI`）。

4. **查不到一律回 None 而不拋錯**
    站方改版、假日、暫時無回應在此層分不出來，交由 updater 判斷。
"""


class FuturesChipCrawler(BaseDataCrawler):
    """爬取 TAIFEX 的三大法人、大額交易人與選擇權 PCR"""

    # 三個端點的日期參數名不同，統一在此對照
    DATE_PARAM_KEYS: Dict[str, tuple] = {
        "TAIFEX_FUTURES_INSTITUTIONAL_URL": ("queryStartDate", "queryEndDate"),
        "TAIFEX_FUTURES_LARGE_TRADER_URL": ("queryStartDate", "queryEndDate"),
        "TAIFEX_FUTURES_PCR_URL": ("queryStartDate", "queryEndDate"),
    }

    # 只有表頭沒有資料列時的行數門檻（表頭一行 ＋ 可能的空行）
    MIN_DATA_LINES: int = 2

    # CSV 表頭的識別字：三個端點的第一欄都是「日期」。
    #
    # ⚠️ **非交易日回的是 HTTP 200 ＋ 一整頁 HTML**（不是空 CSV、也不是 404）。
    # 2026-09-02 實測：查週日拿到 19 行的 HTML，行數檢查完全擋不住它，
    # 下游 `csv` 解析出來會是一堆亂七八糟的「欄位」而不會報錯。
    # 故一律檢查第一行是不是真的 CSV 表頭——這是本端點最容易靜默寫錯資料的地方。
    CSV_HEADER_KEYWORD: str = "日期"

    def __init__(self):
        super().__init__()

    def setup(self) -> None:
        """Set Up the Config of Crawler"""
        pass

    def crawl(self, date: datetime.date) -> Optional[str]:
        """預設路徑：爬三大法人（其餘兩個資料集各有專屬方法）"""

        return self.crawl_institutional(date)

    def crawl_institutional(self, date: datetime.date) -> Optional[str]:
        """三大法人（自營商／投信／外資）的逐商品多空口數與未平倉"""

        return self.fetch_csv("TAIFEX_FUTURES_INSTITUTIONAL_URL", date, "三大法人")

    def crawl_large_trader(self, date: datetime.date) -> Optional[str]:
        """大額交易人：前五大／前十大的買賣方部位，含特定法人拆分"""

        return self.fetch_csv("TAIFEX_FUTURES_LARGE_TRADER_URL", date, "大額交易人")

    def crawl_put_call_ratio(self, date: datetime.date) -> Optional[str]:
        """選擇權 Put/Call Ratio：一天一列"""

        return self.fetch_csv("TAIFEX_FUTURES_PCR_URL", date, "PCR")

    def fetch_csv(
        self, url_name: str, date: datetime.date, label: str
    ) -> Optional[str]:
        """
        - Description:
            以單日區間查詢並取回 CSV 原文（big5 解碼）

            **起訖日都給同一天**：這些端點支援區間查詢，但逐日抓才能做到
            「一天一個中繼檔、可續跑、可重跑」，與本專案其他 ETL 一致。
        - Parameters:
            - url_name: str
                `URLManager` 的 key
            - date: datetime.date
                查詢日
            - label: str
                log 用的資料集名稱
        - Return:
            - Optional[str]
                CSV 原文；取得失敗或當日無資料時為 None
        """

        logger.info(f"* Start crawling TAIFEX futures chip: {label} {date}")

        url: str = URLManager.get_url(url_name)
        start_key, end_key = self.DATE_PARAM_KEYS[url_name]
        query_date: str = date.strftime("%Y/%m/%d")

        response: Optional[requests.Response] = RequestUtils.requests_post(
            url, data={start_key: query_date, end_key: query_date}
        )
        if response is None:
            logger.warning(f"[Futures Chip] 取得{label}失敗：{date}")
            return None

        text: str = response.content.decode(FileEncoding.BIG5.value, errors="replace")

        lines: list = [line for line in text.splitlines() if line.strip()]

        # 非交易日回的是 HTML 而不是 CSV（見 `CSV_HEADER_KEYWORD`）
        if not lines or self.CSV_HEADER_KEYWORD not in lines[0] or "," not in lines[0]:
            logger.info(f"{date} {label}: no data（非交易日或尚未公布）")
            return None

        # 只有表頭代表當日無資料（盤後尚未公布），不是失敗
        if len(lines) < self.MIN_DATA_LINES:
            logger.info(f"{date} {label}: no data")
            return None

        return text
