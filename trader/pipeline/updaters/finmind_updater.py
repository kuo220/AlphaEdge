import datetime
import sqlite3
from typing import Dict, Optional, Union

import pandas as pd
from loguru import logger

from trader.config import (
    DB_PATH,
    SECURITIES_TRADER_INFO_TABLE_NAME,
    STOCK_INFO_WITH_WARRANT_TABLE_NAME,
    STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
)
from trader.pipeline.cleaners.finmind_cleaner import FinMindCleaner
from trader.pipeline.crawlers.finmind_crawler import FinMindCrawler
from trader.pipeline.loaders.finmind_loader import FinMindLoader
from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.utils import FinMindDataType
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils.log_manager import LogManager

"""
FinMind 資料更新器

支援更新以下三種資料：
1. 台股總覽(含權證) (TaiwanStockInfoWithWarrant) - 一次性更新全部資料
2. 證券商資訊表 (TaiwanSecuritiesTraderInfo) - 一次性更新全部資料
3. 當日券商分點統計表 (TaiwanStockTradingDailyReportSecIdAgg) - 需要指定日期範圍

更新方法：
- update_stock_info_with_warrant() - 更新台股總覽
- update_broker_info() - 更新證券商資訊
- update_broker_trading_daily_report(start_date, end_date, stock_id, securities_trader_id) - 更新券商分點統計
- update_all() - 更新所有 FinMind 資料
- update(data_type, **kwargs) - 通用更新方法，可指定資料類型
"""


class FinMindUpdater(BaseDataUpdater):
    """FinMind Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: FinMindCrawler = FinMindCrawler()
        self.cleaner: FinMindCleaner = FinMindCleaner()
        self.loader: FinMindLoader = FinMindLoader()

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        LogManager.setup_logger("update_finmind.log")

    def update(
        self,
        data_type: Optional[Union[str, FinMindDataType]] = None,
        start_date: Optional[Union[datetime.date, str]] = None,
        end_date: Optional[Union[datetime.date, str]] = None,
        stock_id: Optional[str] = None,
        securities_trader_id: Optional[str] = None,
        **kwargs,
    ) -> None:
        """
        通用更新方法

        Args:
            data_type: 資料類型，可選值：
                - FinMindDataType.STOCK_INFO 或 "stock_info": 更新台股總覽
                - FinMindDataType.BROKER_INFO 或 "broker_info": 更新證券商資訊
                - FinMindDataType.BROKER_TRADING 或 "broker_trading": 更新券商分點統計
                - "all" 或 None: 更新所有資料
            start_date: 起始日期（僅用於 BROKER_TRADING）
            end_date: 結束日期（僅用於 BROKER_TRADING）
            stock_id: 股票代碼（可選，僅用於 BROKER_TRADING）
            securities_trader_id: 券商代碼（可選，僅用於 BROKER_TRADING）
        """
        # 處理 "all" 或 None 的情況
        if data_type is None or (isinstance(data_type, str) and data_type.lower() == "all"):
            self.update_all(
                start_date=start_date,
                end_date=end_date,
                stock_id=stock_id,
                securities_trader_id=securities_trader_id,
            )
            return

        # 將字串轉換為 Enum（向後兼容）
        if isinstance(data_type, str):
            data_type_str: str = data_type.upper()
            try:
                data_type = FinMindDataType(data_type_str)
            except ValueError:
                # 嘗試小寫形式（更友好的用戶輸入）
                data_type_str_lower: str = data_type.lower()
                type_mapping: Dict[str, FinMindDataType] = {
                    dt.value.lower(): dt for dt in FinMindDataType
                }
                if data_type_str_lower in type_mapping:
                    data_type = type_mapping[data_type_str_lower]
                else:
                    raise ValueError(
                        f"Unknown data_type string: {data_type}. "
                        f"Supported strings: {[dt.value.lower() for dt in FinMindDataType]}, 'all'"
                    )

        if data_type == FinMindDataType.STOCK_INFO:
            self.update_stock_info_with_warrant()
        elif data_type == FinMindDataType.BROKER_INFO:
            self.update_broker_info()
        elif data_type == FinMindDataType.BROKER_TRADING:
            if start_date is None or end_date is None:
                raise ValueError(
                    "start_date and end_date are required for BROKER_TRADING"
                )
            self.update_broker_trading_daily_report(
                start_date=start_date,
                end_date=end_date,
                stock_id=stock_id,
                securities_trader_id=securities_trader_id,
            )
        else:
            raise ValueError(
                f"Unknown data_type: {data_type}. "
                f"Supported types: {[dt.name for dt in FinMindDataType]}, 'all'"
            )

    def update_stock_info_with_warrant(self) -> None:
        """更新台股總覽(含權證)資料"""

        logger.info("* Start Updating Taiwan Stock Info With Warrant...")

        # Step 1: Crawl
        df: Optional[pd.DataFrame] = self.crawler.crawl_stock_info_with_warrant()
        if df is None or df.empty:
            logger.warning("No stock info with warrant data to update")
            return

        # Step 2: Clean
        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_stock_info_with_warrant(df)
        if cleaned_df is None or cleaned_df.empty:
            logger.warning("Cleaned stock info with warrant data is empty")
            return

        # Step 3: Load
        # 確保 loader 有連接
        if self.loader.conn is None:
            self.loader.connect()
        self.loader._load_stock_info_with_warrant()
        if self.loader.conn:
            self.loader.conn.commit()

        logger.info("✅ Taiwan Stock Info With Warrant updated successfully")

    def update_broker_info(self) -> None:
        """更新證券商資訊表資料"""

        logger.info("* Start Updating Broker Info...")

        # Step 1: Crawl
        df: Optional[pd.DataFrame] = self.crawler.crawl_broker_info()
        if df is None or df.empty:
            logger.warning("No broker info data to update")
            return

        # Step 2: Clean
        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_broker_info(df)
        if cleaned_df is None or cleaned_df.empty:
            logger.warning("Cleaned broker info data is empty")
            return

        # Step 3: Load
        # 確保 loader 有連接
        if self.loader.conn is None:
            self.loader.connect()
        self.loader._load_broker_info()
        if self.loader.conn:
            self.loader.conn.commit()

        logger.info("✅ Broker Info updated successfully")

    def update_broker_trading_daily_report(
        self,
        stock_id: Optional[str] = None,
        securities_trader_id: Optional[str] = None,
        start_date: Union[datetime.date, str] = None,
        end_date: Union[datetime.date, str] = None,
    ) -> None:
        """
        更新當日券商分點統計表資料

        Args:
            start_date: 起始日期
            end_date: 結束日期
            stock_id: 股票代碼（可選，不提供則返回所有股票）
            securities_trader_id: 券商代碼（可選，不提供則返回所有券商）
        """

        logger.info(
            f"* Start Updating Broker Trading Daily Report: {start_date} to {end_date}"
        )

        # 取得要開始更新的日期（從資料庫最新日期+1天開始，或使用提供的 start_date）
        actual_start_date: Union[datetime.date, str] = self.get_actual_update_start_date(default_date=start_date)

        # 如果實際開始日期已經超過結束日期，則不需要更新
        if isinstance(actual_start_date, datetime.date) and isinstance(
            end_date, datetime.date
        ):
            if actual_start_date > end_date:
                logger.info(
                    f"No new data to update. Latest date in database is already up to date."
                )
                return
        elif isinstance(actual_start_date, str) and isinstance(end_date, str):
            if actual_start_date > end_date:
                logger.info(
                    f"No new data to update. Latest date in database is already up to date."
                )
                return

        logger.info(f"Updating from {actual_start_date} to {end_date}")

        # Step 1: Crawl
        df: Optional[pd.DataFrame] = self.crawler.crawl_broker_trading_daily_report(
            stock_id=stock_id,
            securities_trader_id=securities_trader_id,
            start_date=actual_start_date,
            end_date=end_date,
        )
        if df is None or df.empty:
            logger.warning(
                f"No broker trading daily report data to update from {actual_start_date} to {end_date}"
            )
            return

        # Step 2: Clean
        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_broker_trading_daily_report(df)
        if cleaned_df is None or cleaned_df.empty:
            logger.warning("Cleaned broker trading daily report data is empty")
            return

        # Step 3: Load
        # 確保 loader 有連接
        if self.loader.conn is None:
            self.loader.connect()
        self.loader._load_broker_trading_daily_report()
        if self.loader.conn:
            self.loader.conn.commit()

        # 更新後重新取得 Table 最新的日期
        table_latest_date: str = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
            col_name="date",
        )
        if table_latest_date:
            logger.info(
                f"✅ Broker trading daily report updated successfully. Latest available date: {table_latest_date}"
            )
        else:
            logger.warning("No new broker trading daily report data was updated")

    def update_all(
        self,
        start_date: Optional[Union[datetime.date, str]] = None,
        end_date: Optional[Union[datetime.date, str]] = None,
        stock_id: Optional[str] = None,
        securities_trader_id: Optional[str] = None,
    ) -> None:
        """
        更新所有 FinMind 資料

        Args:
            start_date: 起始日期（僅用於 broker_trading_daily_report）
            end_date: 結束日期（僅用於 broker_trading_daily_report）
            stock_id: 股票代碼（可選，僅用於 broker_trading_daily_report）
            securities_trader_id: 券商代碼（可選，僅用於 broker_trading_daily_report）
        """

        logger.info("* Start Updating All FinMind Data...")

        # 更新台股總覽
        self.update_stock_info_with_warrant()

        # 更新證券商資訊
        self.update_broker_info()

        # 更新券商分點統計（需要日期範圍）
        if start_date is None:
            # 預設從 2013/1/1 開始
            start_date = datetime.date(2021, 6, 30)
        if end_date is None:
            end_date = datetime.date.today()

        self.update_broker_trading_daily_report(
            start_date=start_date,
            end_date=end_date,
            stock_id=stock_id,
            securities_trader_id=securities_trader_id,
        )

        logger.info("✅ All FinMind Data updated successfully")

    def get_actual_update_start_date(
        self,
        default_date: Union[datetime.date, str],
    ) -> Union[datetime.date, str]:
        """
        取得實際的更新起始日期（資料庫最新日期+1天，或使用 default_date）

        Args:
            default_date: 預設起始日期（同時用於決定返回值的類型）

        Returns:
            實際的起始日期，類型與 default_date 相同
        """

        latest_date: Optional[str] = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
            col_name="date",
        )

        if latest_date is not None:
            # 將資料庫中的日期字串轉換為 datetime.date
            table_latest_date: datetime.date = datetime.datetime.strptime(
                latest_date, "%Y-%m-%d"
            ).date()

            # 加一天作為新的起始日期
            next_date: datetime.date = table_latest_date + datetime.timedelta(days=1)

            # 根據 default_date 的類型決定返回格式
            if isinstance(default_date, str):
                return next_date.strftime("%Y-%m-%d")
            else:
                return next_date
        else:
            # 如果資料庫中沒有資料，使用 default_date
            return default_date
