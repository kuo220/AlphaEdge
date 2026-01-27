import datetime
import sqlite3
import time
from typing import Dict, List, Optional, Union

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
from trader.pipeline.utils import FinMindDataType, UpdateStatus
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils.log_manager import LogManager
from trader.utils import TimeUtils

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
- update_broker_trading_daily_report_batch(start_date, end_date) - 批量更新券商分點統計（loop 日期、券商、股票）
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

        # API Quota 追蹤（初始值，會在 setup 中動態獲取）
        self.api_quota_limit: int = 20000  # 每小時最大 API 調用次數（預設值）
        self.api_call_count: int = 0  # 當前小時的 API 調用次數
        self.quota_reset_time: float = time.time() + 3600  # 下次重置時間（1小時後）

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        LogManager.setup_logger("update_finmind.log")

        # 動態獲取 API quota 限制
        try:
            if self.crawler.api and hasattr(self.crawler.api, "api_usage_limit"):
                self.api_quota_limit = self.crawler.api.api_usage_limit
                logger.info(
                    f"FinMind API quota limit retrieved: {self.api_quota_limit} calls per hour"
                )
            else:
                logger.warning(
                    f"Could not retrieve API quota limit from FinMind API. Using default: {self.api_quota_limit}"
                )
        except Exception as e:
            logger.warning(
                f"Error retrieving API quota limit: {e}. Using default: {self.api_quota_limit}"
            )

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
        if data_type is None or (
            isinstance(data_type, str) and data_type.lower() == "all"
        ):
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
        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_stock_info_with_warrant(
            df
        )
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
    ) -> UpdateStatus:
        """
        更新當日券商分點統計表資料

        Args:
            start_date: 起始日期
            end_date: 結束日期
            stock_id: 股票代碼（可選，不提供則返回所有股票）
            securities_trader_id: 券商代碼（可選，不提供則返回所有券商）

        Returns:
            UpdateStatus: 更新狀態
                - UpdateStatus.SUCCESS: 成功更新
                - UpdateStatus.NO_DATA: 沒有資料（API 返回空結果）
                - UpdateStatus.ALREADY_UP_TO_DATE: 資料庫已是最新
                - UpdateStatus.ERROR: 發生錯誤
        """

        logger.info(
            f"* Start Updating Broker Trading Daily Report: {start_date} to {end_date}"
        )

        # 取得要開始更新的日期（從資料庫最新日期+1天開始，或使用提供的 start_date）
        actual_start_date: Union[datetime.date, str] = (
            self.get_actual_update_start_date(default_date=start_date)
        )

        # 如果實際開始日期已經超過結束日期，則不需要更新
        if isinstance(actual_start_date, datetime.date) and isinstance(
            end_date, datetime.date
        ):
            if actual_start_date > end_date:
                logger.info(
                    f"No new data to update. Latest date in database is already up to date."
                )
                return UpdateStatus.ALREADY_UP_TO_DATE
        elif isinstance(actual_start_date, str) and isinstance(end_date, str):
            if actual_start_date > end_date:
                logger.info(
                    f"No new data to update. Latest date in database is already up to date."
                )
                return UpdateStatus.ALREADY_UP_TO_DATE

        logger.info(f"Updating from {actual_start_date} to {end_date}")

        try:
            # Step 1: Crawl
            df: Optional[pd.DataFrame] = self.crawler.crawl_broker_trading_daily_report(
                stock_id=stock_id,
                securities_trader_id=securities_trader_id,
                start_date=actual_start_date,
                end_date=end_date,
            )
            if df is None or df.empty:
                # 記錄更詳細的資訊，包含 stock_id 和 securities_trader_id
                if stock_id and securities_trader_id:
                    logger.debug(
                        f"No broker trading daily report data for stock_id={stock_id}, "
                        f"securities_trader_id={securities_trader_id}, "
                        f"date={actual_start_date} to {end_date}"
                    )
                else:
                    logger.warning(
                        f"No broker trading daily report data to update from {actual_start_date} to {end_date}"
                    )
                return UpdateStatus.NO_DATA

            # Step 2: Clean
            cleaned_df: Optional[pd.DataFrame] = (
                self.cleaner.clean_broker_trading_daily_report(df)
            )
            if cleaned_df is None or cleaned_df.empty:
                logger.warning("Cleaned broker trading daily report data is empty")
                return UpdateStatus.NO_DATA

            # Step 3: Load - 暫時取消資料庫存儲
            # 確保 loader 有連接
            # if self.loader.conn is None:
            #     self.loader.connect()
            # self.loader._load_broker_trading_daily_report()
            # if self.loader.conn:
            #     self.loader.conn.commit()

            # 更新後重新取得 Table 最新的日期
            # table_latest_date: str = SQLiteUtils.get_table_latest_value(
            #     conn=self.conn,
            #     table_name=STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
            #     col_name="date",
            # )
            # if table_latest_date:
            #     logger.info(
            #         f"✅ Broker trading daily report updated successfully. Latest available date: {table_latest_date}"
            #     )
            # else:
            #     logger.warning("No new broker trading daily report data was updated")

            logger.info(
                f"✅ Broker trading daily report crawled and cleaned successfully (database storage disabled)"
            )
            return UpdateStatus.SUCCESS

        except Exception as e:
            logger.error(
                f"Error updating broker trading daily report: {e}",
                exc_info=True,
            )
            return UpdateStatus.ERROR

    def update_broker_trading_daily_report_batch(
        self,
        start_date: Union[datetime.date, str],
        end_date: Union[datetime.date, str],
    ) -> None:
        """
        批量更新當日券商分點統計表資料（loop 日期、券商、股票）

        此方法會：
        1. Loop 日期區間（從 start_date 到 end_date）
        2. Loop 所有券商 ID
        3. Loop 所有股票 ID
        4. 對每個組合呼叫 update_broker_trading_daily_report

        Args:
            start_date: 起始日期
            end_date: 結束日期
        """
        logger.info(
            f"* Start Batch Updating Broker Trading Daily Report: {start_date} to {end_date}"
        )

        # 轉換日期格式
        if isinstance(start_date, str):
            start_date_obj: datetime.date = datetime.datetime.strptime(
                start_date, "%Y-%m-%d"
            ).date()
        else:
            start_date_obj: datetime.date = start_date

        if isinstance(end_date, str):
            end_date_obj: datetime.date = datetime.datetime.strptime(
                end_date, "%Y-%m-%d"
            ).date()
        else:
            end_date_obj: datetime.date = end_date

        # 取得要開始更新的日期（從資料庫最新日期+1天開始，或使用提供的 start_date）
        actual_start_date: datetime.date = self.get_actual_update_start_date(
            default_date=start_date_obj
        )
        if isinstance(actual_start_date, str):
            actual_start_date = datetime.datetime.strptime(
                actual_start_date, "%Y-%m-%d"
            ).date()

        # 如果實際開始日期已經超過結束日期，則不需要更新
        if actual_start_date > end_date_obj:
            logger.info(
                f"No new data to update. Latest date in database is already up to date."
            )
            return

        # 產生日期列表
        dates: List[datetime.date] = TimeUtils.generate_date_range(
            actual_start_date, end_date_obj
        )
        logger.info(f"Will update {len(dates)} dates")

        # 取得股票列表和券商列表
        stock_list: List[str] = self._get_stock_list()
        trader_list: List[str] = self._get_securities_trader_list()

        if not stock_list:
            logger.warning(
                "No stocks found in database. Please update stock info first."
            )
            return

        if not trader_list:
            logger.warning(
                "No securities traders found in database. Please update broker info first."
            )
            return

        total_combinations: int = len(dates) * len(trader_list) * len(stock_list)
        logger.info(
            f"Total update combinations: {len(dates)} dates × {len(trader_list)} traders × {len(stock_list)} stocks = {total_combinations}"
        )

        # Loop: 日期 -> 券商 -> 股票
        combination_count: int = 0
        quota_exhausted: bool = False

        # 統計各種狀態
        stats: Dict[str, int] = {
            UpdateStatus.SUCCESS.value: 0,
            UpdateStatus.NO_DATA.value: 0,
            UpdateStatus.ALREADY_UP_TO_DATE.value: 0,
            UpdateStatus.ERROR.value: 0,
        }

        for date in dates:
            logger.info(f"Processing date: {date.strftime('%Y-%m-%d')}")
            for securities_trader_id in trader_list:
                for stock_id in stock_list:
                    # 在每次 API 調用前檢查 quota
                    if not self._check_and_update_api_quota():
                        quota_exhausted = True
                        logger.warning(
                            f"⚠️ Stopping update due to API quota exhaustion. "
                            f"Progress: {combination_count}/{total_combinations} combinations processed. "
                            f"Last processed: date={date.strftime('%Y-%m-%d')}, "
                            f"trader={securities_trader_id}, stock={stock_id}"
                        )
                        break

                    combination_count += 1
                    if combination_count % 100 == 0:
                        logger.info(
                            f"Progress: {combination_count}/{total_combinations} combinations processed "
                            f"(API calls: {self.api_call_count}/{self.api_quota_limit}) | "
                            f"Stats: success={stats[UpdateStatus.SUCCESS.value]}, no_data={stats[UpdateStatus.NO_DATA.value]}, "
                            f"error={stats[UpdateStatus.ERROR.value]}, already_up_to_date={stats[UpdateStatus.ALREADY_UP_TO_DATE.value]}"
                        )

                    try:
                        # 對單一日期、單一券商、單一股票進行更新
                        status: UpdateStatus = self.update_broker_trading_daily_report(
                            stock_id=stock_id,
                            securities_trader_id=securities_trader_id,
                            start_date=date,
                            end_date=date,
                        )
                        # 統計狀態
                        if status.value in stats:
                            stats[status.value] += 1
                        else:
                            logger.warning(f"Unknown status returned: {status}")
                            stats[UpdateStatus.ERROR.value] += 1
                    except Exception as e:
                        stats[UpdateStatus.ERROR.value] += 1
                        logger.error(
                            f"Error updating broker trading daily report for date={date}, trader={securities_trader_id}, stock={stock_id}: {e}",
                            exc_info=True,
                        )
                        # 繼續處理下一個組合
                        continue

                if quota_exhausted:
                    break

            if quota_exhausted:
                break

        # 輸出最終統計
        if quota_exhausted:
            logger.warning(
                f"⚠️ Batch update paused due to API quota exhaustion. "
                f"Processed {combination_count}/{total_combinations} combinations. "
                f"Please wait for quota reset and resume from where it stopped."
            )
        else:
            logger.info(
                f"✅ Batch update completed. Processed {combination_count} combinations"
            )

        # 輸出詳細統計
        logger.info(
            f"📊 Update Statistics: "
            f"Success={stats[UpdateStatus.SUCCESS.value]}, "
            f"No Data={stats[UpdateStatus.NO_DATA.value]} (API returned empty result), "
            f"Already Up-to-date={stats[UpdateStatus.ALREADY_UP_TO_DATE.value]}, "
            f"Errors={stats[UpdateStatus.ERROR.value]}"
        )

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

    def _check_and_update_api_quota(self) -> bool:
        """
        檢查 API quota 是否足夠，並更新調用次數

        Returns:
            bool: True 表示 quota 足夠可以繼續調用，False 表示 quota 已用盡
        """
        current_time: float = time.time()

        # 如果已經超過重置時間，重置計數器
        if current_time >= self.quota_reset_time:
            logger.info(
                f"API quota reset. Previous hour used {self.api_call_count}/{self.api_quota_limit} calls"
            )
            self.api_call_count = 0
            self.quota_reset_time = current_time + 3600  # 重置為下一個小時

        # 檢查是否接近或超過 quota 限制（保留 100 次作為緩衝）
        remaining_quota: int = self.api_quota_limit - self.api_call_count
        if remaining_quota <= 100:
            wait_seconds: int = int(self.quota_reset_time - current_time) + 1
            logger.warning(
                f"⚠️ API quota nearly exhausted! Used {self.api_call_count}/{self.api_quota_limit} calls. "
                f"Remaining: {remaining_quota} calls. "
                f"Quota will reset in {wait_seconds} seconds ({wait_seconds // 60} minutes). "
                f"Stopping update to avoid quota exhaustion."
            )
            return False

        # 增加調用次數
        self.api_call_count += 1

        # 每 1000 次調用記錄一次狀態
        if self.api_call_count % 1000 == 0:
            remaining_quota = self.api_quota_limit - self.api_call_count
            logger.info(
                f"API quota status: {self.api_call_count}/{self.api_quota_limit} calls used, "
                f"{remaining_quota} remaining"
            )

        return True

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

    def _get_stock_list(self) -> List[str]:
        """
        從資料庫取得所有股票代碼列表

        Returns:
            List[str]: 股票代碼列表
        """
        try:
            query: str = (
                f"SELECT DISTINCT stock_id FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME} ORDER BY stock_id"
            )
            df: pd.DataFrame = pd.read_sql_query(query, self.conn)
            stock_list: List[str] = df["stock_id"].astype(str).tolist()
            logger.info(f"Retrieved {len(stock_list)} stocks from database")
            return stock_list
        except Exception as e:
            logger.error(f"Error retrieving stock list: {e}")
            return []

    def _get_securities_trader_list(self) -> List[str]:
        """
        從資料庫取得所有券商代碼列表

        Returns:
            List[str]: 券商代碼列表
        """
        try:
            query: str = (
                f"SELECT DISTINCT securities_trader_id FROM {SECURITIES_TRADER_INFO_TABLE_NAME} ORDER BY securities_trader_id"
            )
            df: pd.DataFrame = pd.read_sql_query(query, self.conn)
            trader_list: List[str] = df["securities_trader_id"].astype(str).tolist()
            logger.info(
                f"Retrieved {len(trader_list)} securities traders from database"
            )
            return trader_list
        except Exception as e:
            logger.error(f"Error retrieving securities trader list: {e}")
            return []
