import datetime
import random
import time
from io import StringIO
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
import requests
from loguru import logger

from core.config import (
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_META_DIR_PATH,
)
from core.pipeline.crawlers.base import BaseDataCrawler
from core.pipeline.crawlers.utils.payload import Payload
from core.pipeline.crawlers.utils.request_utils import RequestUtils
from core.pipeline.utils import FinancialStatementType, MarketType, URLManager
from core.pipeline.utils.data_utils import DataUtils
from core.utils import TimeUtils


class FinancialStatementCrawler(BaseDataCrawler):
    """Crawler for quarterly financial Statement"""

    # 起始年份為資料源下界（MOPS 只供得出民國 102 年以後），故寫死；
    # 結束年份不設常數，改由呼叫端取當年——MOPS 一路供到當季，寫死會逐年落後
    DEFAULT_START_YEAR: int = 2013
    CRAWL_DELAY_MIN: float = 1.0
    CRAWL_DELAY_MAX: float = 3.0

    # 權益變動表專用（其餘三張報表不適用，故不放共用常數）
    # MOPS 的 ajax_t164sb06 要 step=2 才會直接回報表：step=1 對金控這類多實體公司
    # 只回子公司選單頁（實測 2891 中信金），step=2 則各類公司一律直接得到報表
    EQUITY_CHANGE_STEP: str = "2"
    # 站方過載時會回 HTTP 200，內容卻只有 "Unreachable Server"。這與「查無資料」
    # 必須分開處理，否則逐檔回補會把暫時性失敗記成「這檔沒有權益變動表」而永久略過
    EQUITY_CHANGE_UNREACHABLE_MARKER: str = "Unreachable Server"
    EQUITY_CHANGE_NO_DATA_MARKER: str = "查無資料"
    EQUITY_CHANGE_MAX_RETRIES: int = 3
    EQUITY_CHANGE_RETRY_DELAY_SECONDS: int = 30

    def __init__(self):
        super().__init__()

        # Financial Statement Directories Set Up
        self.fs_dir: Path = FINANCIAL_STATEMENT_DOWNLOADS_PATH

        # Payload For HTTP Requests
        self.payload: Optional[Payload] = None
        self.market_types: List[MarketType] = [MarketType.SII, MarketType.OTC]

        self.setup()

    def setup(self, *args, **kwargs):
        """Set Up the Config of Crawler"""

        # Create Downloads Directory For Financial Reports
        self.fs_dir.mkdir(parents=True, exist_ok=True)

        # Set Up Payload
        self.payload = Payload(
            firstin="1",
            step="1",
            TYPEK="sii",
            co_id=None,
            year="102",
            season="1",
        )

    def crawl(self, *args, **kwargs) -> Dict[str, List[pd.DataFrame]]:
        """Crawl Financial Report (Include 4 reports)"""
        """
        General usage:
        **kwargs = {
            "stock_id": str,
            "date": datetime.date,
            "season": int
        }
        """

        stock_id: Optional[str] = kwargs.get("stock_id")
        year: Optional[int] = kwargs.get("year")
        season: Optional[int] = kwargs.get("season")

        if year is None or season is None:
            raise ValueError("Missing required parameters: 'date', or 'season'")

        df_dict: Dict[str, List[pd.DataFrame]] = {
            "balance_sheet": [],
            "comprehensive_income": [],
            "cash_flow": [],
            "equity_changes": [],
        }

        df_dict["balance_sheet"].extend(self.crawl_balance_sheet(year, season))
        df_dict["comprehensive_income"].extend(
            self.crawl_comprehensive_income(year, season)
        )
        df_dict["cash_flow"].extend(self.crawl_cash_flow(year, season))
        # 權益變動表查無資料或站方過載時會回 None，不能直接 extend
        equity_changes: Optional[List[pd.DataFrame]] = self.crawl_equity_changes(
            year, season, stock_id
        )
        df_dict["equity_changes"].extend(equity_changes or [])

        return df_dict

    def crawl_balance_sheet(
        self,
        year: int,
        season: int,
    ) -> Optional[List[pd.DataFrame]]:
        """Crawl Balance Sheet (資產負債表)"""
        """
        資料區間（但是只有 102 年以後才可以爬）
        上市: 民國 78 (1989) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        logger.info(f"* Start crawling balance sheet: {year}/Q{season}")

        roc_year: str = TimeUtils.convert_ad_to_roc_year(year)

        self.payload.year = roc_year
        self.payload.season = season

        balance_sheet_url: str = URLManager.get_url("BALANCE_SHEET_URL")
        df_list: List[pd.DataFrame] = []

        for market_type in self.market_types:
            self.payload.TYPEK = market_type.value

            try:
                res: Optional[requests.Response] = RequestUtils.requests_post(
                    balance_sheet_url, data=self.payload.convert_to_clean_dict()
                )
            except Exception:
                logger.warning(f"Cannot get balance sheet at {year}Q{season}")
                continue

            try:
                dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
                df_list.extend(dfs)
            except Exception:
                logger.warning("No tables found")
                continue

        return df_list

    def crawl_comprehensive_income(
        self,
        year: int,
        season: int,
    ) -> Optional[List[pd.DataFrame]]:
        """Crawl Statement of Comprehensive Income (綜合損益表)"""
        """
        資料區間（但是只有 102 年以後才可以爬）
        上市: 民國 77 (1988) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        logger.info(f"* Start crawling comprehensive income: {year}/Q{season}")

        roc_year: str = TimeUtils.convert_ad_to_roc_year(year)

        self.payload.year = roc_year
        self.payload.season = season

        income_url: str = URLManager.get_url("INCOME_STATEMENT_URL")
        df_list: List[pd.DataFrame] = []

        for market_type in self.market_types:
            self.payload.TYPEK = market_type.value

            try:
                res: Optional[requests.Response] = RequestUtils.requests_post(
                    income_url, data=self.payload.convert_to_clean_dict()
                )
            except Exception:
                logger.warning(
                    f"Cannot get statement of comprehensive income at {year}Q{season}"
                )
                continue

            try:
                dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
                df_list.extend(dfs)
            except Exception:
                logger.warning("No tables found")
                continue

        return df_list

    def crawl_cash_flow(
        self,
        year: int,
        season: int,
    ) -> Optional[List[pd.DataFrame]]:
        """Crawl Cash Flow Statement (現金流量表)"""
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """

        logger.info(f"* Start crawling cash flow: {year}/Q{season}")

        roc_year: str = TimeUtils.convert_ad_to_roc_year(year)

        self.payload.year = roc_year
        self.payload.season = season

        cash_flow_url: str = URLManager.get_url("CASH_FLOW_STATEMENT_URL")
        df_list: List[pd.DataFrame] = []

        for market_type in self.market_types:
            self.payload.TYPEK = market_type.value

            try:
                res: Optional[requests.Response] = RequestUtils.requests_post(
                    cash_flow_url, data=self.payload.convert_to_clean_dict()
                )
            except Exception:
                logger.warning(f"Cannot get cash flow statement at {year}Q{season}")
                continue

            try:
                dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
                df_list.extend(dfs)
            except Exception:
                logger.warning("No tables found")
                continue

        return df_list

    def crawl_equity_changes(
        self,
        year: int,
        season: int,
        stock_id: str,
    ) -> Optional[List[pd.DataFrame]]:
        """Crawl Statement of Changes in Equity (權益變動表)"""
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present

        與其他三張報表不同，本端點是「逐檔查詢」（一次一檔股票），
        故回傳值要能分辨三種結果，讓逐檔回補的呼叫端決定要不要重試：
        - None: 暫時性失敗（站方過載或連線失敗），本檔尚未確認有無資料，應留待重跑
        - []:   查無資料（例如 ETF、當季未申報），重跑也不會有結果
        - 非空 list: 正常取得，內容為該頁的所有表格
        """

        logger.debug(f"* Start crawling equity changes: {stock_id} {year}/Q{season}")

        roc_year: str = TimeUtils.convert_ad_to_roc_year(year)

        # step 與 co_id 只在本方法生效，離開前一律還原：payload 由四張報表共用，
        # 其餘三張是「全市場一次查完」，被殘留的 co_id 縮成單一公司會靜默少資料
        original_step: Optional[str] = self.payload.step
        self.payload.step = self.EQUITY_CHANGE_STEP
        self.payload.TYPEK = None
        self.payload.co_id = stock_id
        self.payload.year = roc_year
        self.payload.season = season

        equity_changes_url: str = URLManager.get_url("EQUITY_CHANGE_STATEMENT_URL")

        try:
            return self._request_equity_changes(
                url=equity_changes_url,
                payload=self.payload.convert_to_clean_dict(),
                year=year,
                season=season,
                stock_id=stock_id,
            )
        finally:
            self.payload.step = original_step
            self.payload.co_id = None

    def _request_equity_changes(
        self,
        url: str,
        payload: Dict[str, str],
        year: int,
        season: int,
        stock_id: str,
    ) -> Optional[List[pd.DataFrame]]:
        """送出權益變動表請求，暫時性失敗就地重試；回傳語意見 crawl_equity_changes"""

        for attempt in range(self.EQUITY_CHANGE_MAX_RETRIES):
            res: Optional[requests.Response] = None
            try:
                res = RequestUtils.requests_post(url, data=payload)
            except Exception as error:
                logger.warning(
                    f"Request failed on equity changes {stock_id} {year}Q{season}: {error}"
                )

            if res is not None:
                if self.EQUITY_CHANGE_NO_DATA_MARKER in res.text:
                    logger.debug(f"No equity changes data: {stock_id} {year}Q{season}")
                    return []

                if self.EQUITY_CHANGE_UNREACHABLE_MARKER not in res.text:
                    try:
                        return pd.read_html(StringIO(res.text))
                    except ValueError:
                        # 既非「查無資料」也非過載，卻解不出表格：版面可能已改制
                        logger.warning(
                            f"No tables found on equity changes {stock_id} {year}Q{season}"
                        )
                        return []

            # 走到這裡代表站方過載或連線失敗，等一下再試同一檔
            if attempt < self.EQUITY_CHANGE_MAX_RETRIES - 1:
                time.sleep(self.EQUITY_CHANGE_RETRY_DELAY_SECONDS)

        logger.warning(
            f"Equity changes unreachable after {self.EQUITY_CHANGE_MAX_RETRIES} "
            f"retries: {stock_id} {year}Q{season}"
        )
        return None

    def get_all_report_columns(
        self,
        start_year: Optional[int] = None,
        end_year: Optional[int] = None,
        seasons: List[int] = [
            1,
            2,
            3,
            4,
        ],
        stock_id: str = "2330",
        report_type: FinancialStatementType = FinancialStatementType.BALANCE_SHEET,
    ) -> List[str]:
        """取得所有財報的 Columns Name"""
        """
        目前能爬取的資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """
        _start_year: int = (
            start_year if start_year is not None else self.DEFAULT_START_YEAR
        )
        _end_year: int = (
            end_year if end_year is not None else datetime.date.today().year
        )

        year_list: List[int] = list(range(_start_year, _end_year + 1))
        all_columns: List[str] = []

        for year in year_list:
            for season in seasons:
                if report_type == FinancialStatementType.BALANCE_SHEET:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_balance_sheet(
                        year, season
                    )
                elif report_type == FinancialStatementType.COMPREHENSIVE_INCOME:
                    df_list: Optional[List[pd.DataFrame]] = (
                        self.crawl_comprehensive_income(year, season)
                    )
                elif report_type == FinancialStatementType.CASH_FLOW:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_cash_flow(
                        year, season
                    )
                elif report_type == FinancialStatementType.EQUITY_CHANGE:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_equity_changes(
                        year, season, stock_id
                    )
                else:
                    df_list: Optional[List[pd.DataFrame]] = None

                if df_list:
                    for df in df_list:
                        all_columns.extend(df.columns)
            time.sleep(random.uniform(self.CRAWL_DELAY_MIN, self.CRAWL_DELAY_MAX))

        # 去除重複欄位並保留順序
        unique_columns: List[str] = list(dict.fromkeys(all_columns))

        # Save all columns list as .json in pipeline/downloads/meta/financial_statement
        dir_path: Path = FINANCIAL_STATEMENT_META_DIR_PATH / report_type.lower()
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path: Path = dir_path / f"{report_type.lower()}_all_columns.json"
        DataUtils.save_json(data=unique_columns, file_path=file_path)

        return unique_columns
