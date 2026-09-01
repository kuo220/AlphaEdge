from typing import Optional

import requests
from loguru import logger

from core.pipeline.shared.base_crawler import BaseDataCrawler
from core.pipeline.shared.request_utils import RequestUtils
from core.pipeline.utils.url_manager import URLManager
from core.utils import FileEncoding

"""
台期貨保證金爬蟲（TAIFEX 保證金一覽表）

**與本目錄其他 crawler 最大的差別：回的是 CSV 純文字，不是 HTML**。
`pd.read_html` 在這裡完全用不上，一律走 `csv` 模組（解析交給 cleaner）。

1. **編碼是 big5，不是 UTF-8**
    `requests` 猜到的編碼不可信，故本層一律回傳**解碼後的字串**而不是 `Response`，
    解碼點只有這裡一處，下游不必再操心編碼。

2. **來源只給「現在這一組」，沒有歷史**
    與 `futures_stock_universe_crawler` 同一個處境：靠快照序列累積變動歷史。
    2020/03 之後的歷史另有調整公告可補（本文件 S4），本層不負責。

3. **第一行不是表頭**
    指數類的第一行是 `更新日期:YYYY/MM/DD`（＝這組保證金的生效日），
    股票類前面還有兩行標題文字。生效日的解析在 cleaner，本層原樣回傳。

4. **兩支端點的格式語意不同**
    指數類給「每口固定金額」、股票類給「適用比例 ＋ 級距」，
    因此下游是兩條清洗與入庫路徑（見 `backlog/台期貨保證金ETL.md` §一）。
"""


class FuturesMarginCrawler(BaseDataCrawler):
    """爬取 TAIFEX 保證金一覽表（指數類與股票類）"""

    def __init__(self):
        super().__init__()

    def setup(self) -> None:
        """Set Up the Config of Crawler"""
        pass

    def crawl(self) -> Optional[str]:
        """爬取指數類保證金一覽表（預設路徑）"""

        return self.crawl_index_margin()

    def crawl_index_margin(self) -> Optional[str]:
        """
        - Description:
            取得股價指數類的現行保證金一覽表（CSV 原文）

            **查不到一律回傳 None 而不拋錯**，與本目錄其他 crawler 一致：
            站方改版、暫時無回應等成因在此層分不出來，交由 updater 判斷。
        - Return:
            - Optional[str]
                big5 解碼後的 CSV 原文；取得失敗時為 None
        """

        return self.fetch_csv("TAIFEX_INDEX_MARGIN_URL", "指數類")

    def crawl_stock_margin(self) -> Optional[str]:
        """取得股票類的現行保證金一覽表（CSV 原文）；語意同 `crawl_index_margin()`"""

        return self.fetch_csv("TAIFEX_STOCK_MARGIN_URL", "股票類")

    @staticmethod
    def fetch_csv(url_name: str, label: str) -> Optional[str]:
        """
        - Description:
            取回 CSV 並以 big5 解碼

            **`errors="replace"` 是刻意的**：整份表因為一個罕見字就整批取不到，
            比留下一個問號字元糟得多；真正要用的欄位（金額、比例、代碼）都是
            ASCII，受影響的只有中文簡稱。
        - Parameters:
            - url_name: str
                `URLManager` 的 key
            - label: str
                log 用的類別名稱（指數類／股票類）
        - Return:
            - Optional[str]
                CSV 原文；取得失敗時為 None
        """

        logger.info(f"* Start crawling TAIFEX futures margin: {label}")

        url: str = URLManager.get_url(url_name)
        response: Optional[requests.Response] = RequestUtils.requests_get(url)

        if response is None:
            logger.warning(f"[Futures Margin] 取得{label}保證金一覽表失敗")
            return None

        text: str = response.content.decode(FileEncoding.BIG5.value, errors="replace")

        if not text.strip():
            logger.warning(f"[Futures Margin] {label}保證金一覽表為空")
            return None

        return text
