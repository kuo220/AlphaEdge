from io import StringIO
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.pipeline.shared.base_crawler import BaseDataCrawler
from core.pipeline.shared.request_utils import FetchResult, RequestUtils
from core.pipeline.utils import URLManager
from core.pipeline.utils.exceptions import PipelineError

"""
上市櫃基本資料爬蟲

**回傳值一律是「拿到資料」或「拋例外」，沒有中間態**：股票清單是
`broker_trading` 等下游流程的輸入，靜靜回一份殘缺的清單，會讓下游少更新幾百檔股票
卻不留任何錯誤紀錄。
"""


class StockInfoCrawler(BaseDataCrawler):
    """
    Crawls basic information of Taiwanese stocks (e.g., ticker, name, industry category), excluding price and financial data
    """

    def __init__(self):
        super().__init__()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Crawler"""
        pass

    def crawl(self, *args, **kwargs) -> None:
        """Crawl Data"""
        pass

    @staticmethod
    def fetch_html(url: str, label: str) -> str:
        """
        - Description:
            取得頁面內容；非 HTTP 2xx 一律拋出，不把錯誤頁交給 `pd.read_html()`

            舊寫法直接讀 `response.text`，`requests_get()` 回 `None` 時會撞
            `AttributeError`，站方回 404 錯誤頁時則會被 `read_html` 解析成
            一張看起來很正常、實際上完全錯誤的表。
        - Parameters:
            - url: str
                目標網址
            - label: str
                來源名稱，用於錯誤訊息
        - Return:
            - str
                頁面內容
        - Raise:
            - PipelineError
                請求未成功
        """

        result: FetchResult = RequestUtils.fetch(url)
        if not result.ok:
            raise PipelineError(
                f"取得 {label} 失敗：status={result.status.value}, "
                f"http={result.status_code}, error={result.error}"
            )
        return result.text

    @staticmethod
    def crawl_twse_stock_info() -> pd.DataFrame:
        """爬取上市公司的基本股票資訊（股票代號、上市日期、產業類別等）"""

        html: str = StockInfoCrawler.fetch_html(
            URLManager.get_url("TWSE_CODE_URL"), "TWSE stock info"
        )
        twse_df: pd.DataFrame = pd.read_html(StringIO(html))[0]

        twse_df.columns = twse_df.iloc[0]
        twse_df = twse_df.drop(index=[0, 1])
        twse_df = twse_df.reset_index(drop=True)

        # 找出第一個出現「上市認購(售)權證」的列索引，作為判斷權證區塊起始的位置並裁切權證及權證以下的資料
        warrant_idx: Optional[int] = twse_df[
            twse_df.iloc[:, 0]
            .astype(str)
            .str.contains("上市認購(售)權證", na=False, regex=False)
        ].index.min()
        if pd.notna(warrant_idx):
            twse_df = twse_df.loc[: warrant_idx - 1].reset_index(drop=True)

        # 拆成兩欄：證券代號、證券名稱
        twse_df[["證券代號", "證券名稱"]] = twse_df["有價證券代號及名稱"].str.extract(
            r"(\d+)\s+(.+)"
        )
        twse_df = twse_df.drop(columns=["有價證券代號及名稱"])

        # 重排欄位順序
        cols: List[str] = ["證券代號", "證券名稱"] + [
            col for col in twse_df.columns if col not in ["證券代號", "證券名稱"]
        ]
        twse_df = twse_df[cols]

        return twse_df

    @staticmethod
    def crawl_tpex_stock_info() -> pd.DataFrame:
        """爬取上櫃公司的基本股票資訊（股票代號、上櫃日期、產業類別等）"""

        html: str = StockInfoCrawler.fetch_html(
            URLManager.get_url("TPEX_CODE_URL"), "TPEX stock info"
        )
        tpex_df: pd.DataFrame = pd.read_html(StringIO(html))[0]

        tpex_df.columns = tpex_df.iloc[0]
        tpex_df = tpex_df.drop(index=[0, 1])
        tpex_df = tpex_df.reset_index(drop=True)

        # Step 1: 先找出「股票」的起始位置
        stock_idx: Optional[int] = tpex_df[
            tpex_df.iloc[:, 0].astype(str).str.contains("股票", na=False, regex=False)
        ].index.min()

        # Step 2: 找出「特別股」的起始位置
        preferred_idx: Optional[int] = tpex_df[
            tpex_df.iloc[:, 0].astype(str).str.contains("特別股", na=False, regex=False)
        ].index.min()

        # Step 3: 根據 index 切出「股票 ~ 特別股」的資料
        if pd.notna(stock_idx) and pd.notna(preferred_idx):
            tpex_df = tpex_df.loc[stock_idx + 1 : preferred_idx - 1].reset_index(
                drop=True
            )
        else:
            raise ValueError(
                "Unable to locate '股票' or '特別股' section header. Please check the original data format."
            )

        # 拆成兩欄：代號（第一段）、名稱（第二段）
        tpex_df[["證券代號", "證券名稱"]] = tpex_df["有價證券代號及名稱"].str.extract(
            r"(\d+)\s+(.+)"
        )
        tpex_df = tpex_df.drop(columns=["有價證券代號及名稱"])

        # 重排欄位順序
        cols: List[str] = ["證券代號", "證券名稱"] + [
            col for col in tpex_df.columns if col not in ["證券代號", "證券名稱"]
        ]
        tpex_df = tpex_df[cols]

        return tpex_df

    @staticmethod
    def crawl_stock_list() -> List[str]:
        """爬取上市櫃公司的股票代號"""

        # 取得上市公司代號
        twse_df: pd.DataFrame = StockInfoCrawler.crawl_twse_stock_info()
        twse_stock_list: List[str] = twse_df["證券代號"].to_list()
        logger.info(f"* TWSE stocks: {len(twse_stock_list)}")

        # 取得上櫃公司代號
        tpex_df: pd.DataFrame = StockInfoCrawler.crawl_tpex_stock_info()
        tpex_stock_list: List[str] = tpex_df["證券代號"].to_list()
        logger.info(f"* TPEX stocks: {len(tpex_stock_list)}")

        stock_list: List[str] = twse_stock_list + tpex_stock_list
        logger.info(f"* Total stocks: {len(stock_list)}")

        return stock_list
