import datetime
import pandas as pd
import requests
from io import StringIO
from pathlib import Path
import json
from loguru import logger
from dateutil.relativedelta import relativedelta
from typing import List, Dict, Set, Optional

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.crawlers.utils.payload import Payload
from trader.pipeline.utils import (
    URLManager,
    MarketType,
    FinancialStatementType
)
from trader.pipeline.utils.data_utils import DataUtils
from trader.config import (
    FINANCIAL_STATEMENT_PATH,
    DOWNLOADS_METADATA_DIR_PATH
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
        date: datetime.date = kwargs.get("date")
        season: int = kwargs.get("season")

        if date is None or season is None:
            raise ValueError("Missing required parameters: 'date', or 'season'")

        df_dict: Dict[str, List[pd.DataFrame]] = {
            "balance_sheet": [],
            "comprehensive_income": [],
            "cash_flow": [],
            "equity_changes": []
        }

        df_dict["balance_sheet"].extend(self.crawl_balance_sheet(date, season))
        df_dict["comprehensive_income"].extend(self.crawl_comprehensive_income(date, season))
        df_dict["cash_flow"].extend(self.crawl_cash_flow(date, season))
        df_dict["equity_changes"].extend(self.crawl_equity_changes(date, season, stock_code))

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
        date: datetime.date,
        season: int
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Balance Sheet (資產負債表) """
        """
        資料區間
        上市: 民國 79 (1990) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        roc_year: str = DataUtils.convert_to_roc_year(date.year)

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
                logger.info(f"* WARN: Cannot get balance sheet at {date}")
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
        date: datetime.date,
        season: int
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Statement of Comprehensive Income (綜合損益表) """
        """
        資料區間
        上市: 民國 77 (1988) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        roc_year: str = DataUtils.convert_to_roc_year(date.year)

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
                logger.info(f"* WARN: Cannot get statement of comprehensive income at {date}")

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
        date: datetime.date,
        season: int
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Cash Flow Statement (現金流量表) """
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """

        roc_year: str = DataUtils.convert_to_roc_year(date.year)

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
                logger.info(f"* WARN: Cannot get cash flow statement at {date}")

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
        date: datetime.date,
        season: int,
        stock_code: str,
    ) -> Optional[List[pd.DataFrame]]:
        """ Crawl Statement of Changes in Equity (權益變動表) """
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """

        roc_year: str = DataUtils.convert_to_roc_year(date.year)

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
            logger.info(f"* WARN: Cannot get equity changes statement at {date}")

        try:
            df_list: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
        except Exception as e:
            logger.info("No tables found")
            logger.info(e)
            return None

        return df_list


    def get_all_report_columns(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
        seasons: List[int] = [1, 2, 3, 4],
        stock_code: str="2330",
        report_type: FinancialStatementType=FinancialStatementType.BALANCE_SHEET
    ) -> List[str]:
        """ 取得財報的從網站提供日期至今所有不重複的 columns name """

        current_date: datetime.date = start_date
        all_df_list: List[pd.DataFrame] = []
        all_columns: Set[str] = set()

        while current_date <= end_date:
            for season in seasons:
                if report_type == FinancialStatementType.BALANCE_SHEET:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_balance_sheet(current_date, season)
                elif report_type == FinancialStatementType.COMPREHENSIVE_INCOME:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_comprehensive_income(current_date, season)
                elif report_type == FinancialStatementType.CASH_FLOW:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_cash_flow(current_date, season)
                elif report_type == FinancialStatementType.EQUITY_CHANGE:
                    df_list: Optional[List[pd.DataFrame]] = self.crawl_equity_changes(current_date, season, stock_code)

                if df_list is not None:
                    all_df_list.extend(df_list)

            current_date += relativedelta(months=1)

        for df in all_df_list:
            df.columns = (
                df.columns
                .map(str)
                .str.replace(r"\s+", "", regex=True)        # 刪除空白
                .str.replace("（", "(")                     # 全形左括號轉半形
                .str.replace("）", ")")                     # 全形右括號轉半形
                .str.replace("－", "")                      # 全形減號 → 刪除
            )
            all_columns.update(df.columns)  # 將所有欄位名稱加入 set（自動去除重複）

        # Save all columns list as .json
        DOWNLOADS_METADATA_DIR_PATH.mkdir(parents=True, exist_ok=True)
        output_file = DOWNLOADS_METADATA_DIR_PATH / f"{report_type.value.lower()}_columns.json"

        with open(output_file, "w", encoding="big5") as f:
            json.dump(sorted(all_columns), f, ensure_ascii=False, indent=2)

        return list(all_columns)