import time
import random
import datetime
from io import StringIO
from loguru import logger
from pathlib import Path
from typing import List, Optional
import pandas as pd
import requests

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils import URLManager, DataType, MarketType, FileEncoding
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import (
    MONTHLY_REVENUE_REPORT_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
)


class MonthlyRevenueReportCrawler(BaseDataCrawler):
    """TWSE & TPEX Monthly Revenue Report Crawler"""

    def __init__(self):
        # Downloads Directory
        self.mrr_dir: Path = MONTHLY_REVENUE_REPORT_PATH

        # Market Type
        self.twse_market_types: List[MarketType] = [MarketType.SII0, MarketType.SII1]
        self.tpex_market_types: List[MarketType] = [MarketType.OTC0, MarketType.OTC1]

    def crawl(self, date: datetime.date) -> Optional[List[pd.DataFrame]]:
        """Crawl Data"""

        twse_df: List[pd.DataFrame] = self.crawl_twse_monthly_revenue(date)
        tpex_df: List[pd.DataFrame] = self.crawl_tpex_monthly_revenue(date)

        return twse_df + tpex_df

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Crawler"""

        # Create the tick downloads directory
        self.mrr_dir.mkdir(parents=True, exist_ok=True)

    def crawl_twse_monthly_revenue(
        self, year: int, month: int
    ) -> Optional[List[pd.DataFrame]]:
        """Crawl TWSE Monthly Revenue Report"""
        """
        資料格式
        上市: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
        """

        df_list: List[pd.DataFrame] = []

        for market_type in self.twse_market_types:
            url: str = URLManager.get_url(
                "TWSE_MONTHLY_REVENUE_REPORT_URL",
                roc_year=TimeUtils.convert_ad_to_roc_year(year),
                month=month,
                market_type=market_type.value,
            )

            try:
                res: requests.Response = RequestUtils.requests_get(url)
                res.encoding = FileEncoding.BIG5.value
            except Exception as e:
                logger.info(
                    f"* WARN: Cannot get TWSE Monthly Revenue Report at {year}/{month}"
                )
                logger.info(e)
                return None

            dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
            df_list.extend(dfs)

        return df_list

    def crawl_tpex_monthly_revenue(
        self, year: int, month: int
    ) -> Optional[List[pd.DataFrame]]:
        """Crawl TPEX Monthly Revenue Report"""
        """
        資料格式
        上櫃: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
        """

        df_list: List[pd.DataFrame] = []

        for market_type in self.tpex_market_types:
            url: str = URLManager.get_url(
                "TPEX_MONTHLY_REVENUE_REPORT_URL",
                roc_year=TimeUtils.convert_ad_to_roc_year(year),
                month=month,
                market_type=market_type.value,
            )

            try:
                res: requests.Response = RequestUtils.requests_get(url)
                res.encoding = FileEncoding.BIG5.value
            except Exception as e:
                logger.info(
                    f"* WARN: Cannot get TWSE Monthly Revenue Report at {year}/{month}"
                )
                logger.info(e)
                return None

            dfs: List[pd.DataFrame] = pd.read_html(StringIO(res.text))
            df_list.extend(dfs)

        return df_list

    def get_all_mrr_columns(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> List[str]:
        """取得所有月營收財報的 Columns Name"""

        year_list: List[int] = list(range(start_date.year, end_date.year + 1))
        month_list: List[int] = list(range(start_date.month, end_date.month + 1))
        all_columns: List[str] = []

        for year in year_list:
            for month in month_list:
                twse_df_list: List[pd.DataFrame] = self.crawl_twse_monthly_revenue(
                    year=year, month=month
                )
                tpex_df_list: List[pd.DataFrame] = self.crawl_tpex_monthly_revenue(
                    year=year, month=month
                )

                if twse_df_list:
                    for df in twse_df_list:
                        if (
                            isinstance(df.columns, pd.MultiIndex)
                            and df.columns.nlevels > 1
                        ):
                            df.columns = df.columns.droplevel(0)
                            all_columns.extend(df.columns)

                if tpex_df_list:
                    for df in tpex_df_list:
                        if (
                            isinstance(df.columns, pd.MultiIndex)
                            and df.columns.nlevels > 1
                        ):
                            df.columns = df.columns.droplevel(0)
                            all_columns.extend(df.columns)
            time.sleep(random.uniform(1, 3))

        # 去除重複欄位並保留順序
        unique_columns: List[str] = list(dict.fromkeys(all_columns))

        # Save all columns list as .json in pipeline/downloads/meta/monthly_revenue_report
        dir_path: Path = MONTHLY_REVENUE_REPORT_META_DIR_PATH
        dir_path.mkdir(parents=True, exist_ok=True)

        file_path: Path = dir_path / f"{DataType.MRR.lower()}_all_columns.json"
        DataUtils.save_json(data=unique_columns, file_path=file_path)

        return unique_columns
