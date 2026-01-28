import datetime
import json
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import pandas as pd
from loguru import logger

from trader.config import (
    BROKER_TRADING_METADATA_PATH,
    DB_PATH,
    FINMIND_DOWNLOADS_PATH,
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
- update_broker_trading_daily_report_batch(start_date, end_date) - 批量更新券商分點統計（loop 券商、股票，一次性查詢整個日期範圍）
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

        # Broker trading metadata 文件路徑（記錄每個 broker_id 和 stock_id 的日期範圍）
        self.broker_trading_metadata_path: Path = BROKER_TRADING_METADATA_PATH

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
        skip_processed_check: bool = False,
    ) -> UpdateStatus:
        """
        更新當日券商分點統計表資料

        Args:
            start_date: 起始日期
            end_date: 結束日期
            stock_id: 股票代碼（可選，不提供則返回所有股票）
            securities_trader_id: 券商代碼（可選，不提供則返回所有券商）
            skip_processed_check: 是否跳過已處理項目的檢查（預設 False）
                                當從 batch 方法調用時應設為 True，避免重複檢查

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

        # 如果沒有跳過檢查，且提供了 stock_id 和 securities_trader_id，檢查是否已處理過
        # 特別處理單個日期的情況（start_date == end_date）
        if (
            not skip_processed_check
            and stock_id
            and securities_trader_id
            and start_date
            and end_date
        ):
            # 標準化日期格式以便比較
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

            # 如果是單個日期，檢查是否已處理（從 metadata 檢查）
            if start_date_obj == end_date_obj:
                date_str: str = start_date_obj.strftime("%Y-%m-%d")

                # 從 metadata 檢查日期是否在範圍內
                if self._check_date_exists_in_metadata(
                    securities_trader_id=securities_trader_id,
                    stock_id=stock_id,
                    date=start_date_obj,
                ):
                    logger.info(
                        f"Date {date_str} for trader={securities_trader_id}, stock={stock_id} "
                        f"already exists in metadata. Skipping."
                    )
                    return UpdateStatus.ALREADY_UP_TO_DATE

        # 取得要開始更新的日期（從資料庫最新日期+1天開始，或使用提供的 start_date）
        actual_start_date: Union[datetime.date, str] = (
            self.get_actual_update_start_date(default_date=start_date)
        )

        # 如果實際開始日期已經超過結束日期，則不需要更新
        # 統一轉換為 datetime.date 進行比較
        if isinstance(actual_start_date, str):
            actual_start_date_obj: datetime.date = datetime.datetime.strptime(
                actual_start_date, "%Y-%m-%d"
            ).date()
        else:
            actual_start_date_obj: datetime.date = actual_start_date

        if isinstance(end_date, str):
            end_date_obj: datetime.date = datetime.datetime.strptime(
                end_date, "%Y-%m-%d"
            ).date()
        else:
            end_date_obj: datetime.date = end_date

        if actual_start_date_obj > end_date_obj:
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

            # Step 3: Load - 將資料保存到資料庫
            # 確保 loader 有連接
            if self.loader.conn is None:
                self.loader.connect()

            # 確保資料表存在
            self.loader.create_missing_tables()

            # 將清理後的資料保存到資料庫
            # 注意：cleaned_df 已經按 (securities_trader_id, stock_id) 分組並保存到 CSV
            # 現在需要將這些資料也寫入資料庫
            # 檢查資料庫中已存在的資料，避免重複插入
            existing_query: str = f"""
            SELECT DISTINCT stock_id, date, securities_trader_id
            FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
            """
            try:
                existing_df: pd.DataFrame = pd.read_sql_query(existing_query, self.conn)

                if not existing_df.empty:
                    # 建立已存在的鍵集合
                    existing_keys: Set[Tuple[str, str, str]] = set(
                        zip(
                            existing_df["stock_id"].astype(str),
                            existing_df["date"].astype(str),
                            existing_df["securities_trader_id"].astype(str),
                        )
                    )

                    # 過濾出新資料
                    cleaned_df["_key"] = list(
                        zip(
                            cleaned_df["stock_id"].astype(str),
                            cleaned_df["date"].astype(str),
                            cleaned_df["securities_trader_id"].astype(str),
                        )
                    )
                    mask: pd.Series = ~cleaned_df["_key"].isin(existing_keys)
                    new_df: pd.DataFrame = cleaned_df[mask].drop(columns=["_key"])
                else:
                    new_df: pd.DataFrame = cleaned_df

                # 只插入新資料
                if not new_df.empty:
                    # 確保欄位順序正確
                    column_order: List[str] = [
                        "securities_trader",
                        "securities_trader_id",
                        "stock_id",
                        "date",
                        "buy_volume",
                        "sell_volume",
                        "buy_price",
                        "sell_price",
                    ]
                    available_columns: List[str] = [
                        col for col in column_order if col in new_df.columns
                    ]
                    new_df = new_df[available_columns]

                    new_df.to_sql(
                        STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
                        self.conn,
                        if_exists="append",
                        index=False,
                    )
                    self.conn.commit()
                    logger.info(
                        f"✅ Saved {len(new_df)} new records to database "
                        f"({len(cleaned_df) - len(new_df)} duplicates skipped)"
                    )
                else:
                    logger.debug("All data already exists in database, skipping insert")

            except Exception as e:
                logger.warning(
                    f"Error checking existing data: {e}. Will insert all data."
                )
                # 如果檢查失敗，嘗試直接插入（可能會因為重複鍵而失敗，但至少嘗試）
                column_order: List[str] = [
                    "securities_trader",
                    "securities_trader_id",
                    "stock_id",
                    "date",
                    "buy_volume",
                    "sell_volume",
                    "buy_price",
                    "sell_price",
                ]
                available_columns: List[str] = [
                    col for col in column_order if col in cleaned_df.columns
                ]
                try:
                    cleaned_df[available_columns].to_sql(
                        STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
                        self.conn,
                        if_exists="append",
                        index=False,
                    )
                    self.conn.commit()
                    logger.info(f"✅ Saved {len(cleaned_df)} records to database")
                except Exception as insert_error:
                    logger.error(f"Error inserting data to database: {insert_error}")

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
        批量更新當日券商分點統計表資料（loop 券商、股票）

        此方法會：
        1. Loop 所有券商 ID
        2. Loop 所有股票 ID
        3. 對每個 (券商, 股票) 組合，一次性查詢整個日期範圍

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

        # 初始化時更新 metadata（從資料庫讀取）
        logger.info("Initializing broker trading metadata from database...")
        self._update_broker_trading_metadata_from_database()

        total_combinations: int = len(trader_list) * len(stock_list)
        logger.info(
            f"Total update combinations: {len(trader_list)} traders × {len(stock_list)} stocks = {total_combinations}"
        )
        logger.info(
            f"Date range: {actual_start_date.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')}"
        )

        # Loop: 券商 -> 股票
        combination_count: int = 0
        quota_exhausted: bool = False

        # 統計各種狀態
        stats: Dict[str, int] = {
            UpdateStatus.SUCCESS.value: 0,
            UpdateStatus.NO_DATA.value: 0,
            UpdateStatus.ALREADY_UP_TO_DATE.value: 0,
            UpdateStatus.ERROR.value: 0,
        }

        # 定期更新 metadata 的頻率（每處理 N 個項目後更新一次）
        update_metadata_interval: int = 100

        for securities_trader_id in trader_list:
            for stock_id in stock_list:
                # 檢查是否需要更新（檢查 metadata 中是否已包含所有日期）
                existing_dates: Set[str] = self._get_existing_dates_from_metadata(
                    securities_trader_id=securities_trader_id,
                    stock_id=stock_id,
                )

                # 產生目標日期範圍的所有日期
                target_dates: List[datetime.date] = TimeUtils.generate_date_range(
                    actual_start_date, end_date_obj
                )
                target_date_strs: Set[str] = {
                    d.strftime("%Y-%m-%d") for d in target_dates
                }

                # 檢查是否所有日期都已存在
                missing_dates: Set[str] = target_date_strs - existing_dates

                if not missing_dates:
                    # 所有日期都已存在，跳過此組合
                    stats[UpdateStatus.ALREADY_UP_TO_DATE.value] += 1
                    continue

                # 在每次 API 調用前檢查 quota
                if not self._check_and_update_api_quota():
                    # 自動等待 quota 重置（每隔 10 分鐘查詢一次 API usage）
                    logger.warning(
                        f"⚠️ API quota exhausted! Used {self.api_call_count}/{self.api_quota_limit} calls. "
                        f"Progress: {combination_count}/{total_combinations} combinations processed. "
                        f"Last processed: trader={securities_trader_id}, stock={stock_id}"
                    )
                    # 更新 metadata（從資料庫讀取）
                    logger.info(
                        "Updating broker trading metadata before waiting for quota reset..."
                    )
                    self._update_broker_trading_metadata_from_database()

                    # 等待 quota 重置（每隔 10 分鐘查詢一次，最多等待 2 小時）
                    quota_restored: bool = self._wait_for_quota_reset(
                        check_interval_minutes=10,
                        max_wait_minutes=120,  # 最多等待 2 小時
                    )

                    if not quota_restored:
                        quota_exhausted = True
                        logger.error(
                            f"❌ Failed to restore API quota within maximum wait time. "
                            f"Please check API status and restart manually."
                        )
                        break
                    else:
                        # Quota 已恢復，繼續處理
                        logger.info(
                            f"🔄 Resuming update from trader={securities_trader_id}, stock={stock_id}"
                        )
                        # 不 break，繼續當前循環

                combination_count += 1
                if combination_count % 50 == 0:
                    logger.info(
                        f"Progress: {combination_count}/{total_combinations} combinations processed "
                        f"(API calls: {self.api_call_count}/{self.api_quota_limit}) | "
                        f"Stats: success={stats[UpdateStatus.SUCCESS.value]}, no_data={stats[UpdateStatus.NO_DATA.value]}, "
                        f"error={stats[UpdateStatus.ERROR.value]}, already_up_to_date={stats[UpdateStatus.ALREADY_UP_TO_DATE.value]}"
                    )

                try:
                    # 對單一券商、單一股票，一次性查詢整個日期範圍
                    # 設置 skip_processed_check=True，因為 batch 方法已經檢查過了
                    status: UpdateStatus = self.update_broker_trading_daily_report(
                        stock_id=stock_id,
                        securities_trader_id=securities_trader_id,
                        start_date=actual_start_date,
                        end_date=end_date_obj,
                        skip_processed_check=True,  # 避免重複檢查
                    )

                    if status == UpdateStatus.NO_DATA:
                        logger.debug(
                            f"No data for trader={securities_trader_id}, stock={stock_id} "
                            f"(date range: {actual_start_date} to {end_date_obj})"
                        )

                    # 統計狀態
                    if status.value in stats:
                        stats[status.value] += 1
                    else:
                        logger.warning(f"Unknown status returned: {status}")
                        stats[UpdateStatus.ERROR.value] += 1

                    # 定期更新 metadata（避免程式意外中斷時遺失進度）
                    if combination_count % update_metadata_interval == 0:
                        logger.debug(
                            f"Periodically updating metadata at {combination_count} combinations..."
                        )
                        self._update_broker_trading_metadata_from_database()
                except Exception as e:
                    stats[UpdateStatus.ERROR.value] += 1
                    logger.error(
                        f"Error updating broker trading daily report for trader={securities_trader_id}, stock={stock_id}: {e}",
                        exc_info=True,
                    )
                    # 繼續處理下一個組合
                    continue

            if quota_exhausted:
                break

        # 更新 metadata（無論是否完成）
        logger.info("Updating broker trading metadata after batch update...")
        self._update_broker_trading_metadata_from_database()

        # 如果 quota 用完，記錄狀態
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

        # 檢查是否接近或超過 quota 限制（保留 50 次作為緩衝）
        remaining_quota: int = self.api_quota_limit - self.api_call_count
        if remaining_quota <= 50:
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

    def _get_api_remaining_quota_from_api(self) -> Optional[int]:
        """
        從 FinMind API 查詢剩餘的 API quota（如果 API 支援）

        Returns:
            Optional[int]: 剩餘的 API 調用次數，如果無法查詢則返回 None
        """
        try:
            if not self.crawler.api:
                return None

            api = self.crawler.api

            # FinMind API: api.api_usage_limit 回傳剩餘次數
            if hasattr(api, "api_usage_limit"):
                remaining = api.api_usage_limit
                if isinstance(remaining, int) and remaining >= 0:
                    return remaining

        except Exception as e:
            logger.debug(f"Could not query API remaining quota from FinMind API: {e}")
        return None

    def _wait_for_quota_reset(
        self,
        check_interval_minutes: int = 10,
        max_wait_minutes: Optional[int] = None,
    ) -> bool:
        """
        等待 API quota 重置，每隔指定時間查詢一次 API usage

        Args:
            check_interval_minutes: 每隔幾分鐘查詢一次 API usage（預設 10 分鐘）
            max_wait_minutes: 最大等待時間（分鐘），如果為 None 則不限制

        Returns:
            bool: True 表示 quota 已恢復，False 表示達到最大等待時間或發生錯誤
        """
        check_interval_seconds: int = check_interval_minutes * 60
        max_wait_seconds: Optional[int] = (
            max_wait_minutes * 60 if max_wait_minutes else None
        )
        start_wait_time: float = time.time()

        logger.info(
            f"⏳ Waiting for API quota reset. Checking every {check_interval_minutes} minutes..."
        )

        while True:
            # 檢查是否超過最大等待時間
            if max_wait_seconds:
                elapsed: float = time.time() - start_wait_time
                if elapsed >= max_wait_seconds:
                    logger.warning(
                        f"⚠️ Maximum wait time ({max_wait_minutes} minutes) reached. Stopping wait."
                    )
                    return False

            # 嘗試從 API 查詢剩餘 quota
            remaining: Optional[int] = self._get_api_remaining_quota_from_api()

            if remaining is not None:
                # 如果能夠查詢到剩餘 quota，檢查是否已重置
                current_usage: int = self.api_quota_limit - remaining
                logger.info(
                    f"📊 Current API usage: {current_usage}/{self.api_quota_limit} calls. "
                    f"Remaining: {remaining} calls."
                )

                if remaining > 50:  # 有足夠的 quota（保留 50 次緩衝）
                    # 重置本地計數器
                    self.api_call_count = 0
                    self.quota_reset_time = time.time() + 3600
                    logger.info(
                        f"✅ API quota has been reset! Resuming update. "
                        f"Remaining quota: {remaining} calls."
                    )
                    return True
            else:
                # 如果無法查詢 API usage，使用時間判斷
                current_time: float = time.time()
                if current_time >= self.quota_reset_time:
                    # 已經超過重置時間，重置計數器
                    self.api_call_count = 0
                    self.quota_reset_time = current_time + 3600
                    logger.info(f"✅ API quota reset time reached. Resuming update.")
                    return True

            # 計算已等待時間
            elapsed: float = time.time() - start_wait_time

            logger.info(
                f"⏳ Quota not yet reset. Next check in {check_interval_minutes} minutes. "
                f"(Elapsed: {elapsed / 60:.1f} minutes)"
            )

            # 等待指定時間
            time.sleep(check_interval_seconds)

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

    def _load_broker_trading_metadata(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        從 metadata 文件讀取 broker trading 的日期範圍資訊

        Returns:
            Dict[str, Dict[str, Dict[str, str]]]: metadata 結構
                {
                    "broker_id": {
                        "stock_id": {
                            "earliest_date": "2021-01-01",
                            "latest_date": "2023-12-31"
                        }
                    }
                }
        """
        if not self.broker_trading_metadata_path.exists():
            return {}

        try:
            with open(self.broker_trading_metadata_path, "r", encoding="utf-8") as f:
                metadata: Dict[str, Dict[str, Dict[str, str]]] = json.load(f)
                return metadata
        except Exception as e:
            logger.warning(f"Error reading broker trading metadata: {e}")
            return {}

    def _update_broker_trading_metadata_from_database(self) -> None:
        """
        從資料庫讀取數據並更新 broker_trading_metadata.json
        記錄每個 (broker_id, stock_id) 組合的 earliest_date 和 latest_date

        此方法從資料庫的實際數據來更新 metadata，不依賴 CSV 檔案
        """
        metadata: Dict[str, Dict[str, Dict[str, str]]] = (
            self._load_broker_trading_metadata()
        )

        # 確保資料庫連接存在
        if self.conn is None:
            logger.error("Database connection is not available")
            return

        updated_count: int = 0
        try:
            # 從資料庫查詢每個 (securities_trader_id, stock_id) 組合的日期範圍
            query: str = f"""
            SELECT 
                securities_trader_id,
                stock_id,
                MIN(date) as earliest_date,
                MAX(date) as latest_date
            FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
            GROUP BY securities_trader_id, stock_id
            ORDER BY securities_trader_id, stock_id
            """

            df: pd.DataFrame = pd.read_sql_query(query, self.conn)

            if df.empty:
                logger.info("No broker trading data found in database")
                # 如果資料庫沒有資料，清空所有 metadata
                metadata = {}
            else:
                # 建立一個集合來記錄資料庫中實際存在的組合
                existing_combinations: Set[Tuple[str, str]] = set()

                for _, row in df.iterrows():
                    securities_trader_id: str = str(row["securities_trader_id"])
                    stock_id: str = str(row["stock_id"])
                    earliest_date_str: str = str(row["earliest_date"])
                    latest_date_str: str = str(row["latest_date"])

                    existing_combinations.add((securities_trader_id, stock_id))

                    try:
                        # 解析日期
                        earliest_date: datetime.date = datetime.datetime.strptime(
                            earliest_date_str, "%Y-%m-%d"
                        ).date()
                        latest_date: datetime.date = datetime.datetime.strptime(
                            latest_date_str, "%Y-%m-%d"
                        ).date()

                        # 初始化 broker_id 如果不存在
                        if securities_trader_id not in metadata:
                            metadata[securities_trader_id] = {}

                        # 更新 metadata
                        if stock_id not in metadata[securities_trader_id]:
                            # 新項目，直接設置日期範圍
                            metadata[securities_trader_id][stock_id] = {
                                "earliest_date": earliest_date.strftime("%Y-%m-%d"),
                                "latest_date": latest_date.strftime("%Y-%m-%d"),
                            }
                            updated_count += 1
                        else:
                            # 如果已存在，比較並更新日期範圍
                            existing_earliest: Optional[datetime.date] = None
                            existing_latest: Optional[datetime.date] = None

                            if (
                                "earliest_date"
                                in metadata[securities_trader_id][stock_id]
                            ):
                                existing_earliest = datetime.datetime.strptime(
                                    metadata[securities_trader_id][stock_id][
                                        "earliest_date"
                                    ],
                                    "%Y-%m-%d",
                                ).date()
                            if (
                                "latest_date"
                                in metadata[securities_trader_id][stock_id]
                            ):
                                existing_latest = datetime.datetime.strptime(
                                    metadata[securities_trader_id][stock_id][
                                        "latest_date"
                                    ],
                                    "%Y-%m-%d",
                                ).date()

                            # 更新最早日期
                            if (
                                existing_earliest is None
                                or earliest_date < existing_earliest
                            ):
                                metadata[securities_trader_id][stock_id][
                                    "earliest_date"
                                ] = earliest_date.strftime("%Y-%m-%d")
                                updated_count += 1

                            # 更新最晚日期
                            if existing_latest is None or latest_date > existing_latest:
                                metadata[securities_trader_id][stock_id][
                                    "latest_date"
                                ] = latest_date.strftime("%Y-%m-%d")
                                updated_count += 1

                    except (ValueError, KeyError) as e:
                        logger.debug(
                            f"Error processing metadata for {securities_trader_id}/{stock_id}: {e}"
                        )
                        continue

                # 清理 metadata 中資料庫不存在的記錄
                removed_count: int = 0
                brokers_to_remove: List[str] = []

                for broker_id, stocks in metadata.items():
                    stocks_to_remove: List[str] = []

                    for stock_id in stocks.keys():
                        if (broker_id, stock_id) not in existing_combinations:
                            # 資料庫中不存在此組合，移除 metadata 中的記錄
                            stocks_to_remove.append(stock_id)
                            removed_count += 1

                    # 移除不存在的 stock_id
                    for stock_id in stocks_to_remove:
                        del metadata[broker_id][stock_id]

                    # 如果該 broker 下沒有任何 stock，標記為待移除
                    if not metadata[broker_id]:
                        brokers_to_remove.append(broker_id)

                # 移除空的 broker
                for broker_id in brokers_to_remove:
                    del metadata[broker_id]

                if removed_count > 0:
                    logger.info(
                        f"🧹 Cleaned {removed_count} metadata entries for non-existent database records"
                    )

                if updated_count > 0:
                    logger.info(
                        f"✅ Updated broker trading metadata: {updated_count} entries updated from database"
                    )

        except Exception as e:
            logger.error(
                f"Error updating broker trading metadata from database: {e}",
                exc_info=True,
            )

        # 保存 metadata
        self.broker_trading_metadata_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.broker_trading_metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, indent=2, ensure_ascii=False)

    def _check_date_exists_in_metadata(
        self,
        securities_trader_id: str,
        stock_id: str,
        date: Union[datetime.date, str],
    ) -> bool:
        """
        檢查指定日期是否已存在於 metadata 記錄的日期範圍內

        Args:
            securities_trader_id: 券商代碼
            stock_id: 股票代碼
            date: 要檢查的日期

        Returns:
            bool: True 表示日期在範圍內，False 表示不在範圍內或沒有記錄
        """
        # 轉換日期格式
        if isinstance(date, datetime.date):
            date_obj: datetime.date = date
        else:
            date_obj = datetime.datetime.strptime(str(date), "%Y-%m-%d").date()

        # 從 metadata 讀取日期範圍
        metadata: Dict[str, Dict[str, Dict[str, str]]] = (
            self._load_broker_trading_metadata()
        )

        if (
            securities_trader_id not in metadata
            or stock_id not in metadata[securities_trader_id]
        ):
            return False

        stock_info: Dict[str, str] = metadata[securities_trader_id][stock_id]

        if "earliest_date" not in stock_info or "latest_date" not in stock_info:
            return False

        try:
            earliest_date: datetime.date = datetime.datetime.strptime(
                stock_info["earliest_date"], "%Y-%m-%d"
            ).date()
            latest_date: datetime.date = datetime.datetime.strptime(
                stock_info["latest_date"], "%Y-%m-%d"
            ).date()

            # 檢查日期是否在範圍內
            return earliest_date <= date_obj <= latest_date
        except (ValueError, KeyError) as e:
            logger.debug(f"Error checking date in metadata: {e}")
            return False

    def _get_existing_dates_from_metadata(
        self,
        securities_trader_id: str,
        stock_id: str,
    ) -> Set[str]:
        """
        從 metadata 取得已存在的日期範圍，並生成所有日期

        Args:
            securities_trader_id: 券商代碼
            stock_id: 股票代碼

        Returns:
            Set[str]: 已存在的日期集合（格式為 "YYYY-MM-DD"）
        """
        # 從 metadata 讀取日期範圍
        metadata: Dict[str, Dict[str, Dict[str, str]]] = (
            self._load_broker_trading_metadata()
        )

        if (
            securities_trader_id not in metadata
            or stock_id not in metadata[securities_trader_id]
        ):
            return set()

        stock_info: Dict[str, str] = metadata[securities_trader_id][stock_id]

        if "earliest_date" not in stock_info or "latest_date" not in stock_info:
            return set()

        try:
            earliest_date: datetime.date = datetime.datetime.strptime(
                stock_info["earliest_date"], "%Y-%m-%d"
            ).date()
            latest_date: datetime.date = datetime.datetime.strptime(
                stock_info["latest_date"], "%Y-%m-%d"
            ).date()

            # 生成日期範圍內的所有日期
            date_range: List[datetime.date] = TimeUtils.generate_date_range(
                earliest_date, latest_date
            )
            existing_dates: Set[str] = {d.strftime("%Y-%m-%d") for d in date_range}
            return existing_dates
        except (ValueError, KeyError) as e:
            logger.debug(f"Error getting dates from metadata: {e}")
            return set()
