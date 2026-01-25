import datetime
import os
from typing import Optional

import pandas as pd
from FinMind.data import DataLoader
from loguru import logger

from trader.pipeline.crawlers.base import BaseDataCrawler

"""
FinMind 資料爬蟲
負責爬取以下資料：
1. 當日卷商分點統計表 (TaiwanStockTradingDailyReportSecIdAgg)
2. 台股總覽(含權證) (TaiwanStockInfoWithWarrant)
3. 證券商資訊表 (TaiwanSecuritiesTraderInfo)
"""


class FinMindCrawler(BaseDataCrawler):
    """爬取 FinMind 提供的台股相關資料"""

    def __init__(self):
        super().__init__()
        self.api: Optional[DataLoader] = None
        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Crawler"""
        # 從環境變數取得 FinMind API Token
        api_token: Optional[str] = os.getenv("FINMIND_API_TOKEN")
        if not api_token:
            raise ValueError(
                "FINMIND_API_TOKEN is missing. Please set it in your .env file."
            )

        # 初始化 FinMind DataLoader
        self.api = DataLoader()
        self.api.login_by_token(api_token=api_token)
        logger.info("FinMind API initialized successfully")

    def crawl(self, *args, **kwargs):
        """Crawl Data"""
        """
        根據 kwargs 中的參數決定要爬取哪些資料：
        - date: datetime.date - 爬取當日卷商分點統計表
        - crawl_stock_info: bool - 是否爬取台股總覽(含權證)
        - crawl_broker_info: bool - 是否爬取證券商資訊表
        
        返回爬取的資料，如果爬取多種資料則返回字典，單一資料則返回 DataFrame
        """
        date: Optional[datetime.date] = kwargs.get("date")
        crawl_stock_info: bool = kwargs.get("crawl_stock_info", False)
        crawl_broker_info: bool = kwargs.get("crawl_broker_info", False)

        results = {}

        if date:
            results["broker_trading_daily_report"] = (
                self.crawl_broker_trading_daily_report(date)
            )

        if crawl_stock_info:
            results["stock_info_with_warrant"] = self.crawl_stock_info_with_warrant()

        if crawl_broker_info:
            results["securities_trader_info"] = self.crawl_securities_trader_info()

        # 如果只有一種資料，直接返回 DataFrame，否則返回字典
        if len(results) == 1:
            return list(results.values())[0]
        elif len(results) > 1:
            return results
        else:
            return None

    def crawl_broker_trading_daily_report(
        self, date: datetime.date
    ) -> Optional[pd.DataFrame]:
        """爬取當日卷商分點統計表 (TaiwanStockTradingDailyReportSecIdAgg)"""

        logger.info(f"* Start crawling Broker Trading Daily Report: {date}")

        try:
            date_str: str = date.strftime("%Y-%m-%d")
            # 使用 get_data 方法，傳入 dataset 名稱和日期參數
            # FinMind API 通常使用 start_date 和 end_date 參數
            df: pd.DataFrame = self.api.get_data(
                dataset="TaiwanStockTradingDailyReportSecIdAgg",
                start_date=date_str,
                end_date=date_str,
            )

            if df is None or df.empty:
                logger.warning(f"No data available for {date}")
                return None

            logger.info(f"Successfully crawled {len(df)} records")
            return df

        except Exception as e:
            logger.error(f"Error crawling broker trading daily report at {date}: {e}")
            return None

    def crawl_stock_info_with_warrant(self) -> Optional[pd.DataFrame]:
        """爬取台股總覽(含權證) (TaiwanStockInfoWithWarrant)"""

        logger.info("* Start crawling Taiwan Stock Info With Warrant")

        try:
            # 嘗試使用專用方法，如果不存在則使用 get_data
            if hasattr(self.api, "taiwan_stock_info_with_warrant"):
                df: pd.DataFrame = self.api.taiwan_stock_info_with_warrant()
            else:
                df: pd.DataFrame = self.api.get_data(
                    dataset="TaiwanStockInfoWithWarrant"
                )

            if df is None or df.empty:
                logger.warning("No data available for Taiwan Stock Info With Warrant")
                return None

            logger.info(f"Successfully crawled {len(df)} records")
            return df

        except Exception as e:
            logger.error(f"Error crawling Taiwan Stock Info With Warrant: {e}")
            return None

    def crawl_securities_trader_info(self) -> Optional[pd.DataFrame]:
        """爬取證券商資訊表 (TaiwanSecuritiesTraderInfo)"""

        logger.info("* Start crawling Taiwan Securities Trader Info")

        try:
            # 嘗試使用專用方法，如果不存在則使用 get_data
            if hasattr(self.api, "taiwan_securities_trader_info"):
                df: pd.DataFrame = self.api.taiwan_securities_trader_info()
            else:
                df: pd.DataFrame = self.api.get_data(
                    dataset="TaiwanSecuritiesTraderInfo"
                )

            if df is None or df.empty:
                logger.warning("No data available for Taiwan Securities Trader Info")
                return None

            logger.info(f"Successfully crawled {len(df)} records")
            return df

        except Exception as e:
            logger.error(f"Error crawling Taiwan Securities Trader Info: {e}")
            return None
