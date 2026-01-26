import datetime
import os
from typing import Dict, Optional, Union

import pandas as pd
from FinMind.data import DataLoader
from loguru import logger

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.utils.log_manager import LogManager

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
        # Set logger
        LogManager.setup_logger("crawl_finmind.log")

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
        pass

    def crawl_stock_info_with_warrant(self) -> Optional[pd.DataFrame]:
        """爬取台股總覽(含權證) (TaiwanStockInfoWithWarrant)
        資料欄位說明：
            - industry_category: str         # 產業別
            - stock_id: str                  # 股票代碼
            - stock_name: str                # 股票名稱
            - type: str                      # 市場別
            - date: str                      # 更新日期

        回傳值：
            pd.DataFrame 或 None
        """

        logger.info("* Start crawling Taiwan Stock Info With Warrant")

        try:
            # 直接使用 API 專用方法
            df: pd.DataFrame = self.api.taiwan_stock_info_with_warrant()

            if df is None or df.empty:
                logger.warning("No data available for Taiwan Stock Info With Warrant")
                return None

            logger.info(f"Successfully crawled {len(df)} records")
            return df

        except Exception as e:
            logger.error(f"Error crawling Taiwan Stock Info With Warrant: {e}")
            return None

    def crawl_broker_info(self) -> Optional[pd.DataFrame]:
        """
        爬取證券商資訊表 (TaiwanSecuritiesTraderInfo)
        資料欄位說明：
            - securities_trader_id: str      # 券商代碼 (FinMind API 原始欄位名稱)
            - securities_trader: str         # 券商名稱 (FinMind API 原始欄位名稱)
            - date: str                      # 開業日
            - address: str                   # 地址
            - phone: str                     # 電話

        回傳值：
            pd.DataFrame 或 None
        """

        logger.info("* Start crawling Broker Info")

        try:
            # 直接使用 API 專用方法
            df: pd.DataFrame = self.api.taiwan_securities_trader_info()

            if df is None or df.empty:
                logger.warning("No data available for Broker Info")
                return None

            logger.info(f"Successfully crawled {len(df)} records")
            return df

        except Exception as e:
            logger.error(f"Error crawling Broker Info: {e}")
            return None

    def crawl_broker_trading_daily_report(
        self,
        stock_id: Optional[str] = None,
        securities_trader_id: Optional[str] = None,
        start_date: Optional[Union[datetime.date, str]] = None,
        end_date: Optional[Union[datetime.date, str]] = None,
    ) -> Optional[pd.DataFrame]:
        """
        爬取「當日券商分點統計表」（TaiwanStockTradingDailyReportSecIdAgg）

        參數：
            - stock_id: Optional[str]                # 股票代碼（可選，不提供則返回所有股票）
            - securities_trader_id: Optional[str]    # 券商代碼（可選，不提供則返回所有券商）
            - start_date: Optional[datetime.date | str]    # 起始日期（可以是 datetime.date 或 "YYYY-MM-DD" 格式的字符串）
            - end_date: Optional[datetime.date | str]      # 結束日期（可以是 datetime.date 或 "YYYY-MM-DD" 格式的字符串）

        API 調用方式：
            使用 self.api.taiwan_stock_trading_daily_report_secid_agg() 方法，
            直接傳遞參數：stock_id, securities_trader_id, start_date, end_date
            注意：API 需要所有參數都有值才能取得資料

        資料欄位說明：
            - securities_trader: str         # 券商名稱 (FinMind API 原始欄位名稱)
            - securities_trader_id: str      # 券商代碼 (FinMind API 原始欄位名稱)
            - stock_id: str                  # 股票代碼
            - date: str                      # 日期（YYYY-MM-DD）
            - buy_volume: int                # 買進總股數
            - sell_volume: int               # 賣出總股數
            - buy_price: float               # 買進均價
            - sell_price: float              # 賣出均價

        回傳值：
            pd.DataFrame 或 None
        """

        logger.info(
            f"* Start crawling Broker Trading Daily Report: {start_date} to {end_date}"
        )

        try:
            # 處理 start_date：如果是字符串則直接使用，如果是 datetime.date 則轉換為字符串
            if isinstance(start_date, str):
                start_date_str: str = start_date
            elif isinstance(start_date, datetime.date):
                start_date_str: str = start_date.strftime("%Y-%m-%d")
            else:
                raise ValueError(
                    f"start_date must be str or datetime.date, got {type(start_date)}"
                )

            # 處理 end_date：如果是字符串則直接使用，如果是 datetime.date 則轉換為字符串
            if isinstance(end_date, str):
                end_date_str: str = end_date
            elif isinstance(end_date, datetime.date):
                end_date_str: str = end_date.strftime("%Y-%m-%d")
            else:
                raise ValueError(
                    f"end_date must be str or datetime.date, got {type(end_date)}"
                )

            # 直接使用 API 方法，傳遞所有參數
            df: pd.DataFrame = self.api.taiwan_stock_trading_daily_report_secid_agg(
                stock_id=stock_id,
                securities_trader_id=securities_trader_id,
                start_date=start_date_str,
                end_date=end_date_str,
            )

            if df is None or df.empty:
                logger.warning(f"No data available for {start_date} to {end_date}")
                return None

            logger.info(f"Successfully crawled {len(df)} records")
            return df

        except Exception as e:
            logger.error(
                f"Error crawling broker trading daily report from {start_date} to {end_date}: {e}"
            )
            return None
