import time
import random
import pandas as pd
import requests
from io import StringIO
from pathlib import Path
import json
from loguru import logger
from typing import List, Dict, Set, Optional

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.crawlers.utils.payload import Payload
from trader.pipeline.utils import (
    URLManager,
    MarketType,
    FinancialStatementType,
    FileEncoding
)
from trader.pipeline.utils.data_utils import DataUtils
from trader.config import (
    FINANCIAL_STATEMENT_PATH,
    DOWNLOADS_METADATA_DIR_PATH,
    FINANCIAL_STATEMENT_META_DIR_PATH
)


class FinancialStatementCrawler(BaseDataCrawler):
    """ Crawler for quarterly financial Statement """

    def __init__(self):
        super().__init__()

        # Financial Statement Directories Set Up
        self.fs_dir: Path = FINANCIAL_STATEMENT_PATH

        # Payload For HTTP Requests
        self.payload: Payload = None
        self.market_types: List[MarketType] = [MarketType.SII, MarketType.OTC]

        self.setup()


    def crawl(self, *args, **kwargs) -> Dict[str, List[pd.DataFrame]]:
        """ Crawl Financial Report (Include 4 reports) """
        """
        General usage:
        **kwargs = {
            "stock_code": str,
            "date": datetime.date,
            "season": int
        }
        """

        stock_code: str = kwargs.get("stock_code")
        year: int = kwargs.get("year")
        season: int = kwargs.get("season")

        if year is None or season is None:
            raise ValueError("Missing required parameters: 'date', or 'season'")

        df_dict: Dict[str, List[pd.DataFrame]] = {
            "balance_sheet": [],
            "comprehensive_income": [],
            "cash_flow": [],
            "equity_changes": []
        }

        df_dict["balance_sheet"].extend(self.crawl_balance_sheet(year, season))
        df_dict["comprehensive_income"].extend(self.crawl_comprehensive_income(year, season))
        df_dict["cash_flow"].extend(self.crawl_cash_flow(year, season))
        df_dict["equity_changes"].extend(self.crawl_equity_changes(year, season, stock_code))

        return df_dict


    def setup(self, *args, **kwargs):
        """ Set Up the Config of Crawler """

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


    def crawl_balance_sheet(
        self,
        year: int,
        season: int
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Balance Sheet (資產負債表) """
        """
        資料區間（但是只有 102 年以後才可以爬）
        上市: 民國 78 (1989) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        roc_year: str = DataUtils.convert_ad_to_roc_year(year)

        self.payload.year = roc_year
        self.payload.season = season

        balance_sheet_url: str = URLManager.get_url("BALANCE_SHEET_URL")
        df_list: List[pd.DataFrame] = []

        for market_type in self.market_types:
            self.payload.TYPEK = market_type.value

            try:
                res: Optional[requests.Response] = RequestUtils.requests_post(
                    balance_sheet_url,
                    data=self.payload.convert_to_clean_dict()
                )
                logger.info(f"{market_type} Balance Sheet URL: {balance_sheet_url}")
            except Exception as e:
                logger.info(f"* WARN: Cannot get balance sheet at {year}Q{season}")
                logger.info(e)

            try:
                dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
                df_list.extend(dfs)
            except Exception as e:
                logger.info("No tables found")
                logger.info(e)
                continue

        return df_list


    def crawl_comprehensive_income(
        self,
        year: int,
        season: int
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Statement of Comprehensive Income (綜合損益表) """
        """
        資料區間（但是只有 102 年以後才可以爬）
        上市: 民國 77 (1988) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        roc_year: str = DataUtils.convert_ad_to_roc_year(year)

        self.payload.year = roc_year
        self.payload.season = season

        income_url: str = URLManager.get_url("INCOME_STATEMENT_URL")
        df_list: List[pd.DataFrame] = []

        for market_type in self.market_types:
            self.payload.TYPEK = market_type.value

            try:
                res: Optional[requests.Response] = RequestUtils.requests_post(
                    income_url,
                    data=self.payload.convert_to_clean_dict()
                )
                logger.info(f"{market_type} Statement of Comprehensive Income URL: {income_url}")
            except Exception as e:
                logger.info(f"* WARN: Cannot get statement of comprehensive income at {year}Q{season}")

            try:
                dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
                df_list.extend(dfs)
            except Exception as e:
                logger.info("No tables found")
                logger.info(e)
                continue

        return df_list


    def crawl_cash_flow(
        self,
        year: int,
        season: int
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Cash Flow Statement (現金流量表) """
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """

        roc_year: str = DataUtils.convert_ad_to_roc_year(year)

        self.payload.year = roc_year
        self.payload.season = season

        cash_flow_url: str = URLManager.get_url("CASH_FLOW_STATEMENT_URL")
        df_list: List[pd.DataFrame] = []

        for market_type in self.market_types:
            self.payload.TYPEK = market_type.value

            try:
                res: Optional[requests.Response] = RequestUtils.requests_post(
                    cash_flow_url,
                    data=self.payload.convert_to_clean_dict()
                )
                logger.info(f"{market_type} Statement of Cash Flow URL: {cash_flow_url}")
            except Exception as e:
                logger.info(f"* WARN: Cannot get cash flow statement at {year}Q{season}")

            try:
                dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
                df_list.extend(dfs)
            except Exception as e:
                logger.info("No tables found")
                logger.info(e)
                continue

        return df_list


    def crawl_equity_changes(
        self,
        year: int,
        season: int,
        stock_code: str,
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Statement of Changes in Equity (權益變動表) """
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """

        roc_year: str = DataUtils.convert_ad_to_roc_year(year)

        self.payload.TYPEK = None
        self.payload.co_id = stock_code
        self.payload.year = roc_year
        self.payload.season = season

        equity_changes_url: str = URLManager.get_url("EQUITY_CHANGE_STATEMENT_URL")

        try:
            res: Optional[requests.Response] = RequestUtils.requests_post(
                equity_changes_url,
                data=self.payload.convert_to_clean_dict()
            )
            logger.info(f"{equity_changes_url} Statement of Equity Changes URL: {equity_changes_url}")
        except Exception as e:
            logger.info(f"* WARN: Cannot get equity changes statement at {year}Q{season}")

        try:
            df_list: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
        except Exception as e:
            logger.info("No tables found")
            logger.info(e)
            return None

        return df_list


    def get_all_report_columns(
        self,
        start_year: int=2013,
        end_year: int=2025,
        seasons: List[int]=[1, 2, 3, 4],
        stock_code: str="2330",
        report_type: FinancialStatementType=FinancialStatementType.BALANCE_SHEET
    ) -> List[str]:
        """ 取得所有財報的 Columns Name """
        """
        目前能爬取的資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """

        year_list: List[int] = list(range(start_year, end_year + 1))
        all_df_list: List[pd.DataFrame] = []
        all_columns: Set[str] = set()

        for year in year_list:
            for season in seasons:
                if report_type == FinancialStatementType.BALANCE_SHEET:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_balance_sheet(year, season)
                elif report_type == FinancialStatementType.COMPREHENSIVE_INCOME:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_comprehensive_income(year, season)
                elif report_type == FinancialStatementType.CASH_FLOW:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_cash_flow(year, season)
                elif report_type == FinancialStatementType.EQUITY_CHANGE:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_equity_changes(year, season, stock_code)

                if df_list is not None:
                    all_df_list.extend(df_list)
            time.sleep(random.uniform(1, 3))

        for df in all_df_list:
            all_columns.update(df.columns)  # 將所有欄位名稱加入 set（自動去除重複）

        # Save all columns list as .json in pipeline/downloads/meta/financial_statement
        dir_path: Path = FINANCIAL_STATEMENT_META_DIR_PATH / report_type.lower()
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path: Path = dir_path / f"{report_type.lower()}_all_columns.json"
        with open(file_path, "w", encoding=FileEncoding.UTF8.value) as f:
            json.dump(list(all_columns), f, ensure_ascii=False, indent=2)

        return list(all_columns)