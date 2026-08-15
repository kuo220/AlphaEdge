import datetime
from io import StringIO
from typing import Any, Dict, List, Optional

import pandas as pd
import requests
from loguru import logger

from core.pipeline.crawlers.base import BaseDataCrawler
from core.pipeline.crawlers.utils.request_utils import RequestUtils
from core.pipeline.utils.url_manager import URLManager
from core.utils import TimeUtils

"""
除權除息計算結果表爬蟲資料時間表：
1. TWSE（上市）
    - 來源：TWT49U（除權除息計算結果表），支援 startDate／endDate 區間查詢
    - **一次可取整年**（2024 全年 1184 筆／單一請求），故不採逐日爬取
    - 民國 90 年起提供；本專案實測 2013 年起表格結構未再改制
2. TPEX（上櫃）
    - 來源：櫃買中心「除權除息計算結果表」（`bulletin/exDailyQ`），同樣支援區間查詢
    - **一次可取整年**（2024 全年 1060 筆／單一請求）；官方頁面標示資料自 2008/01/02 起
    - 欄位比證交所更細：`權值`／`息值`／`現金股利`／`每仟股無償配股` 皆分開提供
    - **版面曾於 2016 年改制**：2013~2015 為 22 欄（多一欄 `員工紅利轉增資`），
      2016 起為 21 欄。cleaner 依**欄位名稱**對應而非位置，兩種版面皆可正確清洗
      （已實測 2013／2015／2016 逐年清洗零筆遺漏）

兩個來源皆為交易所官方，不需要第三方資料源。

實測涵蓋（2026-08-15，逐年掃描 2013~2026）：
- 上市每年皆為 15 欄，無改制
- 上櫃 2013~2015 為 22 欄、2016 起 21 欄，`totalCount` 與實際筆數逐年相符
"""


class StockDividendCrawler(BaseDataCrawler):
    """爬取上市、上櫃股票除權除息計算結果表"""

    def __init__(self):
        super().__init__()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Crawler"""
        pass

    def crawl(self, start_date: datetime.date, end_date: datetime.date) -> None:
        """Crawl TWSE & TPEX Ex-Rights/Ex-Dividend Data"""

        self.crawl_twse_dividend(start_date, end_date)
        self.crawl_tpex_dividend(start_date, end_date)

    def crawl_twse_dividend(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Optional[pd.DataFrame]:
        """
        - Description:
            TWSE 除權除息計算結果表區間爬蟲

            與其他 TWSE 爬蟲不同，本端點支援日期區間，呼叫端應以「年」為單位切分，
            不要退化成逐日呼叫（一年 250 次請求 vs 1 次）

        - Parameters:
            - start_date: datetime.date
                查詢起日
            - end_date: datetime.date
                查詢迄日

        - Return:
            - Optional[pd.DataFrame]
                原始表格；查無資料或版面異常時回傳 None
        """

        logger.info(f"* Start crawling TWSE dividend: {start_date} ~ {end_date}")

        twse_url: str = URLManager.get_url(
            "TWSE_EX_RIGHT_URL",
            start_date=TimeUtils.format_date(start_date, sep=""),
            end_date=TimeUtils.format_date(end_date, sep=""),
        )

        twse_response: Optional[requests.Response] = RequestUtils.requests_get(twse_url)

        if twse_response is None:
            return None

        try:
            # 股票代號含 ETF（00xxx）會被推斷為 int 而丟失前導 0，以 converters 保留原始字串
            twse_df: pd.DataFrame = pd.read_html(
                StringIO(twse_response.text), converters={1: str}
            )[0]
            if twse_df.empty:
                logger.warning("No data in table. Possibly no ex-dividend in period")
                return None
        except Exception:
            logger.info(f"No TWSE dividend data between {start_date} and {end_date}")
            return None

        return twse_df

    def crawl_tpex_dividend(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Optional[pd.DataFrame]:
        """
        - Description:
            TPEX（櫃買中心）除權除息計算結果表區間爬蟲

            回傳格式為 `{"tables": [{"fields": [...], "data": [[...], ...]}]}`，
            本方法組回帶欄名的 DataFrame 再交給 cleaner。

            **日期必須用斜線格式**：傳 `20240101` 不會報錯，而是靜默退回「近三日」的
            預設區間。因此這裡會比對回傳的 `date` 欄位是否等於送出的區間，
            不符時直接中止——寧可沒有資料，也不要把三天的資料當成一整年入庫。

        - Parameters:
            - start_date: datetime.date
                查詢起日
            - end_date: datetime.date
                查詢迄日

        - Return:
            - Optional[pd.DataFrame]
                原始表格（欄名為官方中文欄位）；查無資料或區間不符時回傳 None
        """

        logger.info(f"* Start crawling TPEX dividend: {start_date} ~ {end_date}")

        tpex_url: str = URLManager.get_url(
            "TPEX_EX_RIGHT_URL",
            start_date=TimeUtils.format_date(start_date, sep="/"),
            end_date=TimeUtils.format_date(end_date, sep="/"),
        )

        tpex_response: Optional[requests.Response] = RequestUtils.requests_get(tpex_url)

        if tpex_response is None:
            return None

        try:
            payload: Dict[str, Any] = tpex_response.json()
        except Exception as e:
            logger.warning(f"Failed to parse TPEX dividend response: {e}")
            return None

        if not self.check_tpex_date_range(payload, start_date, end_date):
            return None

        tables: List[Dict[str, Any]] = payload.get("tables") or []
        if not tables:
            logger.warning("No table in TPEX dividend response")
            return None

        fields: List[str] = tables[0].get("fields") or []
        rows: List[List[Any]] = tables[0].get("data") or []

        if not fields or not rows:
            logger.info(f"No TPEX dividend data between {start_date} and {end_date}")
            return None

        return pd.DataFrame(rows, columns=fields)

    @staticmethod
    def check_tpex_date_range(
        payload: Dict[str, Any],
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> bool:
        """
        - Description:
            確認 TPEX 回傳的區間與送出的區間一致

            日期格式錯誤時該端點會**靜默**回傳預設的「近三日」而非報錯，
            不擋下來會讓三天的資料被當成整年入庫，且不會有任何錯誤訊息

        - Parameters:
            - payload: Dict[str, Any]
                端點回傳的 JSON
            - start_date: datetime.date
                送出的查詢起日
            - end_date: datetime.date
                送出的查詢迄日

        - Return:
            - bool
                區間相符為 True
        """

        expected: str = (
            f"{TimeUtils.format_date(start_date)}~{TimeUtils.format_date(end_date)}"
        )
        actual: str = str(payload.get("date", ""))

        if actual != expected:
            logger.warning(
                f"TPEX dividend date range mismatch: requested {expected}, got {actual}. "
                f"Aborting to avoid ingesting the wrong period"
            )
            return False

        return True
