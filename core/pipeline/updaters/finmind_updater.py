import datetime
import sqlite3
import time
from pathlib import Path
from typing import Dict, List, Optional, Set, Tuple, Union

import pandas as pd
from loguru import logger

from core.config import (
    BROKER_TRADING_METADATA_PATH,
    DB_PATH,
    SECURITIES_TRADER_INFO_TABLE_NAME,
    STOCK_INFO_TABLE_NAME,
    STOCK_INFO_WITH_WARRANT_TABLE_NAME,
    STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
)
from core.pipeline.cleaners.finmind_cleaner import FinMindCleaner
from core.pipeline.crawlers.finmind_crawler import FinMindCrawler
from core.pipeline.loaders.finmind_loader import FinMindLoader
from core.pipeline.updaters.base import BaseDataUpdater
from core.pipeline.utils import (
    FinMindDataType,
    FinMindQuotaExhaustedError,
    UpdateStatus,
)
from core.pipeline.utils.data_utils import DataUtils
from core.utils import TimeUtils
from core.utils.instrument import StockUtils
from core.utils.log_manager import LogManager

"""FinMind data updater: stock info with warrant, broker info, broker trading daily report"""


class FinMindUpdater(BaseDataUpdater):
    """FinMind Updater"""

    # API Quota 相關常數（供 _wait_for_quota_reset 使用）
    QUOTA_RESET_INTERVAL_SECONDS: int = (
        3600  # 配額重置間隔（秒），用於 fallback 推算下次重置時間
    )
    MIN_REMAINING_QUOTA_TO_RESUME: int = (
        3000  # 剩餘 quota 至少達此值才視為已恢復、繼續更新
    )
    DEFAULT_API_QUOTA_LIMIT: int = (
        20000  # 每小時最大 API 調用次數（無法從 API 取得時使用）
    )
    SECONDS_PER_MINUTE: int = 60  # 分鐘轉秒（用於配額輪詢間隔等）

    # 配額用盡後等待恢復的預設參數
    QUOTA_CHECK_INTERVAL_MINUTES: int = 10  # 每隔幾分鐘查詢一次 API usage
    QUOTA_MAX_WAIT_MINUTES: int = 120  # 最大等待時間（分鐘）

    # 券商分點批量更新：進度記錄、metadata 更新、commit 間隔
    BATCH_LOG_PROGRESS_INTERVAL: int = 50  # 每處理 N 筆記錄一次進度
    BATCH_UPDATE_METADATA_INTERVAL: int = 500  # 每處理 N 筆更新一次 metadata
    BATCH_COMMIT_INTERVAL: int = 50  # 每處理 N 筆 commit 一次

    # 預設日期（update_all 時 broker_trading 若未給 start_date）
    DEFAULT_BROKER_TRADING_START_DATE: datetime.date = datetime.date(2021, 6, 30)

    # API 剩餘配額查詢：有效值下界（usage 與 limit 的合法性檢查）
    MIN_VALID_API_USAGE: int = 0
    MIN_VALID_API_LIMIT: int = 1

    def __init__(self):
        super().__init__()

        # SQLite Connection（用於讀取：股票/券商列表、metadata 從 DB 查詢）
        # 寫入由 self.loader.conn 負責（broker trading 等）；兩者皆指向同一 DB_PATH
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: FinMindCrawler = FinMindCrawler()
        self.cleaner: FinMindCleaner = FinMindCleaner()
        self.loader: FinMindLoader = FinMindLoader()

        # API Quota（供 _wait_for_quota_reset 查詢與 fallback 用；配額用盡由 FinMindQuotaExhaustedError 處理）
        self.api_quota_limit: int = self.DEFAULT_API_QUOTA_LIMIT
        self.quota_reset_time: float = (
            time.time() + self.QUOTA_RESET_INTERVAL_SECONDS
        )  # 下次重置時間（無法從 API 取得剩餘時用）

        # Broker trading metadata 文件路徑（記錄每個 broker_id 和 stock_id 的日期範圍）
        self.broker_trading_metadata_path: Path = BROKER_TRADING_METADATA_PATH
        # Metadata 快取（雙層迴圈內只讀快取，減少重複讀取 JSON；僅在 _update_broker_trading_metadata_from_database 寫入後更新）
        self._metadata_cache: Optional[Dict[str, Dict[str, Dict[str, str]]]] = None

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
        LogManager.setup_logger("update_finmind.log")

        # 動態獲取 API quota 限制
        try:
            if self.crawler.api and hasattr(self.crawler.api, "api_usage_limit"):
                self.api_quota_limit: int = self.crawler.api.api_usage_limit
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
        **kwargs,
    ) -> None:
        """
        通用更新方法

        Args:
            data_type: 資料類型，可選值：
                - FinMindDataType.STOCK_INFO 或 "stock_info": 更新台股總覽（不含權證）
                - FinMindDataType.STOCK_INFO_WITH_WARRANT 或 "stock_info_with_warrant": 更新台股總覽（含權證）
                - FinMindDataType.BROKER_INFO 或 "broker_info": 更新證券商資訊
                - FinMindDataType.BROKER_TRADING 或 "broker_trading": 更新券商分點統計
                - "all" 或 None: 更新所有資料
            start_date: 起始日期（僅用於 BROKER_TRADING）
            end_date: 結束日期（僅用於 BROKER_TRADING）
        """
        # 處理 "all" 或 None 的情況
        if data_type is None or (
            isinstance(data_type, str) and data_type.lower() == "all"
        ):
            self.update_all(
                start_date=start_date,
                end_date=end_date,
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
            self.update_stock_info()
        elif data_type == FinMindDataType.STOCK_INFO_WITH_WARRANT:
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
            )
        else:
            raise ValueError(
                f"Unknown data_type: {data_type}. "
                f"Supported types: {[dt.name for dt in FinMindDataType]}, 'all'"
            )

    def update_stock_info(self) -> None:
        """更新台股總覽資料（不含權證）"""

        logger.info("* Start Updating Taiwan Stock Info...")

        # Step 1: Crawl
        try:
            df: Optional[pd.DataFrame] = self.crawler.crawl_stock_info()
        except FinMindQuotaExhaustedError as e:
            logger.error(
                "⚠️ FinMind API quota exhausted. Please wait for quota reset and retry later. %s",
                e,
            )
            return
        if df is None or df.empty:
            logger.warning("No stock info data to update")
            return

        # Step 2: Clean
        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_stock_info(df)
        if cleaned_df is None or cleaned_df.empty:
            logger.warning("Cleaned stock info data is empty")
            return

        # Step 3: Load
        # 確保 loader 有連接
        if self.loader.conn is None:
            self.loader.connect()
        self.loader.load_stock_info()
        if self.loader.conn:
            self.loader.conn.commit()

        logger.info("✅ Taiwan Stock Info updated successfully")

    def update_stock_info_with_warrant(self) -> None:
        """更新台股總覽(含權證)資料"""

        logger.info("* Start Updating Taiwan Stock Info With Warrant...")

        # Step 1: Crawl
        try:
            df: Optional[pd.DataFrame] = self.crawler.crawl_stock_info_with_warrant()
        except FinMindQuotaExhaustedError as e:
            logger.error(
                "⚠️ FinMind API quota exhausted. Please wait for quota reset and retry later. %s",
                e,
            )
            return
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
        self.loader.load_stock_info_with_warrant()
        if self.loader.conn:
            self.loader.conn.commit()

        logger.info("✅ Taiwan Stock Info With Warrant updated successfully")

    def update_broker_info(self) -> None:
        """更新證券商資訊表資料"""

        logger.info("* Start Updating Broker Info...")

        # Step 1: Crawl
        try:
            df: Optional[pd.DataFrame] = self.crawler.crawl_broker_info()
        except FinMindQuotaExhaustedError as e:
            logger.error(
                "⚠️ FinMind API quota exhausted. Please wait for quota reset and retry later. %s",
                e,
            )
            return
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
        self.loader.load_broker_info()
        if self.loader.conn:
            self.loader.conn.commit()

        logger.info("✅ Broker Info updated successfully")

    def update_broker_trading_daily_report(
        self,
        start_date: Union[datetime.date, str],
        end_date: Union[datetime.date, str],
    ) -> None:
        """
        批量更新當日券商分點統計表資料

        此方法會：
        1. Loop 所有券商 ID 和股票 ID，批量更新所有組合
        2. 對每個 (券商, 股票) 組合，使用 metadata 判斷需要更新的日期範圍

        Args:
            start_date: 起始日期
            end_date: 結束日期
        """
        logger.info(
            f"* Start Updating Broker Trading Daily Report: {start_date} to {end_date}"
        )

        def _to_date(value: Union[datetime.date, str]) -> datetime.date:
            """將 date 或字串轉為 datetime.date；字串須為 YYYY-MM-DD 格式。"""
            if isinstance(value, datetime.date):
                return value
            try:
                return datetime.datetime.strptime(value, "%Y-%m-%d").date()
            except (ValueError, TypeError) as e:
                raise ValueError(
                    f"Invalid date format: expected datetime.date or 'YYYY-MM-DD' string, got {type(value).__name__!r}"
                ) from e

        start_date_obj: datetime.date = _to_date(start_date)
        end_date_obj: datetime.date = _to_date(end_date)

        # 取得股票列表和券商列表
        stock_list: List[str] = self._get_stock_list()
        securities_trader_list: List[str] = self._get_securities_trader_list()

        logger.info(
            f"Retrieved stock list: {len(stock_list)} stocks, "
            f"securities trader list: {len(securities_trader_list)} traders"
        )

        if not stock_list:
            logger.warning(
                "No stocks found in database. Please update stock info first."
            )
            return

        # 過濾出一般股票（排除 ETF、權證等）
        stock_list: List[str] = StockUtils.filter_common_stocks(stock_list)
        logger.info(
            f"Filtered to {len(stock_list)} common stocks (excluding ETFs, warrants, etc.)"
        )

        if not stock_list:
            logger.warning(
                "No common stocks found after filtering. Please check stock info data."
            )
            return

        if not securities_trader_list:
            logger.warning(
                "No securities traders found in database. Please update broker info first."
            )
            return

        # 初始化時更新 metadata（從資料庫讀取）
        logger.info("Initializing broker trading metadata from database...")
        self._update_broker_trading_metadata_from_database()

        total_combinations: int = len(securities_trader_list) * len(stock_list)
        logger.info(
            f"Total update combinations: {len(securities_trader_list)} traders × {len(stock_list)} stocks = {total_combinations}"
        )
        logger.info(
            f"Requested date range: {start_date_obj.strftime('%Y-%m-%d')} to {end_date_obj.strftime('%Y-%m-%d')} "
            f"(each combination will use its own start date based on metadata)"
        )

        # Loop: 券商 -> 股票
        processed_count: int = 0
        quota_exhausted: bool = False

        # 統計各種狀態
        stats: Dict[str, int] = {
            UpdateStatus.SUCCESS.value: 0,
            UpdateStatus.NO_DATA.value: 0,
            UpdateStatus.ALREADY_UP_TO_DATE.value: 0,
            UpdateStatus.ERROR.value: 0,
        }

        # 輔助函數：記錄進度並定期更新 metadata
        def log_progress_and_update_metadata():
            """記錄處理進度並在需要時更新 metadata（避免程式意外中斷時遺失進度）"""
            if processed_count % self.BATCH_LOG_PROGRESS_INTERVAL == 0:
                logger.info(
                    f"Progress: {processed_count}/{total_combinations} combinations processed | "
                    f"Stats: success={stats[UpdateStatus.SUCCESS.value]}, no_data={stats[UpdateStatus.NO_DATA.value]}, "
                    f"error={stats[UpdateStatus.ERROR.value]}, already_up_to_date={stats[UpdateStatus.ALREADY_UP_TO_DATE.value]}"
                )
            # 定期更新 metadata（避免程式意外中斷時遺失進度）
            if processed_count % self.BATCH_UPDATE_METADATA_INTERVAL == 0:
                logger.debug(
                    f"Periodically updating metadata at {processed_count} combinations..."
                )
                # 先 commit loader 未提交寫入，避免 self.conn 的 SELECT 被 self.loader.conn 鎖住
                if self.loader.conn is not None:
                    self.loader.conn.commit()
                self._update_broker_trading_metadata_from_database()

        for securities_trader_id in securities_trader_list:
            for stock_id in stock_list:
                # 每個組合開始處理時就增加計數（無論是否跳過都會被計入）
                processed_count += 1

                # 記錄正在處理的券商和股票（改為 debug 減少 I/O，進度已由 log_progress_and_update_metadata 每 50 筆 log 一次）
                logger.debug(
                    f"Processing: trader_id={securities_trader_id}, stock_id={stock_id}"
                )

                # 為每個組合決定起始日期（基於該組合的 metadata，而非整個表）
                # 從 metadata 取得該組合的最新日期
                metadata: Dict[str, Dict[str, Dict[str, str]]] = (
                    self._load_broker_trading_metadata()
                )

                # 檢查該組合是否在 metadata 中
                has_metadata: bool = (
                    securities_trader_id in metadata
                    and stock_id in metadata[securities_trader_id]
                    and "latest_date" in metadata[securities_trader_id][stock_id]
                )

                update_start_date: datetime.date = start_date_obj

                if has_metadata:
                    try:
                        # 如果 metadata 中有該組合的資料，從最新日期+1開始
                        latest_date_str: str = metadata[securities_trader_id][stock_id][
                            "latest_date"
                        ]
                        latest_date: datetime.date = datetime.datetime.strptime(
                            latest_date_str, "%Y-%m-%d"
                        ).date()
                        update_start_date = latest_date + datetime.timedelta(days=1)
                    except (ValueError, KeyError) as e:
                        logger.debug(
                            f"Error parsing latest_date from metadata for {securities_trader_id}/{stock_id}: {e}"
                        )
                        update_start_date = start_date_obj

                update_start_date = max(update_start_date, start_date_obj)

                # 起始日期已超過結束日期：已是最新或日期範圍無效，跳過
                if update_start_date > end_date_obj:
                    if not has_metadata:
                        logger.warning(
                            f"Invalid date range for new combination {securities_trader_id}/{stock_id}: "
                            f"start_date={update_start_date} > end_date={end_date_obj}. Skipping."
                        )
                    stats[UpdateStatus.ALREADY_UP_TO_DATE.value] += 1
                    log_progress_and_update_metadata()
                    continue

                # 檢查是否需要更新（檢查 metadata 中是否已包含所有日期）
                existing_dates: Set[str] = self._get_existing_dates_from_metadata(
                    securities_trader_id=securities_trader_id,
                    stock_id=stock_id,
                )

                # 產生目標日期範圍的所有日期
                target_dates: List[datetime.date] = TimeUtils.generate_date_range(
                    update_start_date, end_date_obj
                )

                # 如果日期範圍為空（例如 start_date > end_date），跳過
                if not target_dates:
                    logger.warning(
                        f"Empty date range for {securities_trader_id}/{stock_id}: "
                        f"start_date={update_start_date}, end_date={end_date_obj}. Skipping."
                    )
                    stats[UpdateStatus.ALREADY_UP_TO_DATE.value] += 1
                    log_progress_and_update_metadata()
                    continue

                target_date_strs: Set[str] = {
                    d.strftime("%Y-%m-%d") for d in target_dates
                }

                # 檢查是否所有日期都已存在
                missing_dates: Set[str] = target_date_strs - existing_dates

                if not missing_dates:
                    # 所有日期都已存在，跳過此組合
                    # 但如果是新組合（不在 metadata 中），這不應該發生，記錄警告
                    if not has_metadata:
                        logger.warning(
                            f"Unexpected: combination {securities_trader_id}/{stock_id} not in metadata "
                            f"but all dates {target_date_strs} appear to exist. This may indicate a logic error."
                        )
                    stats[UpdateStatus.ALREADY_UP_TO_DATE.value] += 1
                    log_progress_and_update_metadata()
                    continue

                # 配額用盡時會等待恢復並重試「本組合」，成功或未恢復才往下一組合
                while True:
                    try:
                        status: UpdateStatus = self._update_broker_trading_daily_report(
                            stock_id=stock_id,
                            securities_trader_id=securities_trader_id,
                            start_date=update_start_date,
                            end_date=end_date_obj,
                            do_commit=False,
                        )
                        if status == UpdateStatus.NO_DATA:
                            logger.debug(
                                f"No data for trader={securities_trader_id}, stock={stock_id} "
                                f"(date range: {update_start_date} to {end_date_obj})"
                            )
                        if status.value in stats:
                            stats[status.value] += 1
                        else:
                            logger.warning(f"Unknown status returned: {status}")
                            stats[UpdateStatus.ERROR.value] += 1
                        break
                    except FinMindQuotaExhaustedError as e:
                        logger.warning(
                            f"⚠️ FinMind API quota exhausted. "
                            f"Progress: {processed_count}/{total_combinations}. "
                            f"Current: trader={securities_trader_id}, stock={stock_id}. {e}"
                        )
                        self._update_broker_trading_metadata_from_database()
                        quota_restored: bool = self._wait_for_quota_reset()
                        if not quota_restored:
                            quota_exhausted = True
                            logger.error(
                                "❌ API quota not restored within max wait time. Please check API and restart later."
                            )
                            break
                        logger.info(
                            f"🔄 Quota restored. Retrying current combination: trader={securities_trader_id}, stock={stock_id}"
                        )
                    except Exception as e:
                        stats[UpdateStatus.ERROR.value] += 1
                        logger.error(
                            f"Error updating broker trading daily report for trader={securities_trader_id}, stock={stock_id}: {e}",
                            exc_info=True,
                        )
                        break

                if quota_exhausted:
                    break

                log_progress_and_update_metadata()
                if (
                    processed_count % self.BATCH_COMMIT_INTERVAL == 0
                    and self.loader.conn
                ):
                    self.loader.conn.commit()

            if quota_exhausted:
                break

        # 將尚未 commit 的寫入一次提交，再更新 metadata
        if self.loader.conn:
            self.loader.conn.commit()
        # 更新 metadata（無論是否完成）
        logger.info("Updating broker trading metadata after batch update...")
        self._update_broker_trading_metadata_from_database()

        # 如果 quota 用完，記錄狀態
        if quota_exhausted:
            logger.warning(
                f"⚠️ Batch update paused due to API quota exhaustion. "
                f"Processed {processed_count}/{total_combinations} combinations. "
                f"Please wait for quota reset and resume from where it stopped."
            )
        else:
            logger.info(
                f"✅ Batch update completed. Processed {processed_count} combinations"
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
    ) -> None:
        """
        更新所有 FinMind 資料

        Args:
            start_date: 起始日期（僅用於 broker_trading_daily_report）
            end_date: 結束日期（僅用於 broker_trading_daily_report）
        """

        logger.info("* Start Updating All FinMind Data...")

        # 更新台股總覽（不含權證）
        self.update_stock_info()

        # 更新台股總覽（含權證）
        self.update_stock_info_with_warrant()

        # 更新證券商資訊
        self.update_broker_info()

        # 更新券商分點統計（需要日期範圍）
        if start_date is None:
            start_date = self.DEFAULT_BROKER_TRADING_START_DATE
        if end_date is None:
            end_date = datetime.date.today()

        # 批量更新所有券商和股票組合
        self.update_broker_trading_daily_report(
            start_date=start_date,
            end_date=end_date,
        )

        logger.info("✅ All FinMind Data updated successfully")

    # ============================================================================
    # Private Methods - Core Update Methods
    # ============================================================================

    def _update_broker_trading_daily_report(
        self,
        stock_id: str,
        securities_trader_id: str,
        start_date: Union[datetime.date, str],
        end_date: Union[datetime.date, str],
        do_commit: bool = True,
    ) -> UpdateStatus:
        """
        核心方法：更新券商分點統計表資料（給定股票、券商與日期區間，不包含時間判斷邏輯）

        Args:
            stock_id: 股票代碼
            securities_trader_id: 券商代碼
            start_date: 起始日期
            end_date: 結束日期
            do_commit: 是否在寫入後立即 commit；批次更新時由呼叫端傳 False 並定期 commit

        Returns:
            UpdateStatus: 更新狀態
                - UpdateStatus.SUCCESS: 成功更新（含 API 有回傳但本批皆為重複、saved_count==0 之情況）
                - UpdateStatus.NO_DATA: 沒有資料（API 返回空結果）
                - UpdateStatus.ERROR: 發生錯誤
        """
        logger.info(
            f"Crawling and saving broker trading daily report: "
            f"trader={securities_trader_id}, stock={stock_id}, "
            f"date={start_date} to {end_date}"
        )

        try:
            # Step 1: Crawl（配額用盡時由上層迴圈捕捉並等待重置）
            df: Optional[pd.DataFrame] = self.crawler.crawl_broker_trading_daily_report(
                stock_id=stock_id,
                securities_trader_id=securities_trader_id,
                start_date=start_date,
                end_date=end_date,
            )
            if df is None or df.empty:
                logger.debug(
                    f"No broker trading daily report data for stock_id={stock_id}, "
                    f"securities_trader_id={securities_trader_id}, "
                    f"date={start_date} to {end_date}"
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
            # 使用 loader 的方法來載入資料（do_commit=False 時由批次迴圈定期 commit）
            saved_count: int = self.loader.load_broker_trading_daily_report(
                df=cleaned_df, commit=do_commit
            )

            if saved_count == 0:
                # API 有回傳且已清洗，但本批無新寫入（例如皆為重複）；視為成功、不報錯
                logger.debug("No new data was saved to database")
                return UpdateStatus.SUCCESS

            # 成功後用當次 DataFrame 的 date 最大值 log，避免額外查詢 DB
            if "date" in cleaned_df.columns and not cleaned_df.empty:
                latest_date_from_df: str = str(cleaned_df["date"].max())
                logger.info(
                    f"✅ Broker trading daily report updated successfully. Latest date in batch: {latest_date_from_df}"
                )
            else:
                logger.info("✅ Broker trading daily report updated successfully.")
            return UpdateStatus.SUCCESS

        except FinMindQuotaExhaustedError:
            # 配額用盡：不在此處處理，向上拋出由批次迴圈統一等待／中斷
            raise
        except Exception as e:
            logger.error(
                f"Error updating broker trading daily report: {e}",
                exc_info=True,
            )
            return UpdateStatus.ERROR

    # ============================================================================
    # Private Methods - API Quota Management
    # ============================================================================

    def _get_api_remaining_quota_from_api(self) -> Optional[int]:
        """
        從 FinMind API 查詢剩餘的 API quota。

        FinMind DataLoader 提供：
        - api_usage: 目前已經使用的次數
        - api_usage_limit: 每小時可以使用的總次數
        剩餘次數 = api_usage_limit - api_usage。

        Returns:
            Optional[int]: 剩餘的 API 調用次數，若無法查詢則返回 None
        """
        try:
            if not self.crawler.api:
                return None
            if not hasattr(self.crawler.api, "api_usage") or not hasattr(
                self.crawler.api, "api_usage_limit"
            ):
                return None
            usage: int = self.crawler.api.api_usage
            limit: int = self.crawler.api.api_usage_limit
            if not (
                isinstance(usage, int)
                and isinstance(limit, int)
                and usage >= self.MIN_VALID_API_USAGE
                and limit >= self.MIN_VALID_API_LIMIT
            ):
                return None
            remaining: int = max(self.MIN_VALID_API_USAGE, limit - usage)
            logger.info(f"📊 目前使用次數 / 總次數: {usage} / {limit}")
            return remaining
        except Exception as e:
            logger.debug(f"Could not query API remaining quota from FinMind API: {e}")
        return None

    def _wait_for_quota_reset(self) -> bool:
        """
        等待 API quota 重置，每隔指定時間查詢一次 API usage。

        使用類別常數 QUOTA_CHECK_INTERVAL_MINUTES、QUOTA_MAX_WAIT_MINUTES。

        Returns:
            bool: True 表示 quota 已恢復，False 表示達到最大等待時間或發生錯誤
        """
        check_interval_seconds: int = (
            self.QUOTA_CHECK_INTERVAL_MINUTES * self.SECONDS_PER_MINUTE
        )
        max_wait_seconds: int = self.QUOTA_MAX_WAIT_MINUTES * self.SECONDS_PER_MINUTE
        start_wait_time: float = time.time()

        logger.info(
            f"⏳ Waiting for API quota reset. Checking every {self.QUOTA_CHECK_INTERVAL_MINUTES} minutes..."
        )

        while True:
            # 檢查是否超過最大等待時間
            elapsed: float = time.time() - start_wait_time
            if elapsed >= max_wait_seconds:
                logger.warning(
                    f"⚠️ Maximum wait time ({self.QUOTA_MAX_WAIT_MINUTES} minutes) reached. Stopping wait."
                )
                return False

            # 嘗試從 API 查詢剩餘 quota
            remaining: Optional[int] = self._get_api_remaining_quota_from_api()

            if remaining is not None:
                if remaining >= self.MIN_REMAINING_QUOTA_TO_RESUME:
                    self.quota_reset_time = (
                        time.time() + self.QUOTA_RESET_INTERVAL_SECONDS
                    )
                    logger.info(
                        f"✅ API quota has been reset! Resuming update. "
                        f"Remaining quota: {remaining} calls."
                    )
                    return True
            else:
                # 如果無法查詢 API usage，使用時間判斷（fallback）
                current_time: float = time.time()
                if current_time >= self.quota_reset_time:
                    self.quota_reset_time = (
                        current_time + self.QUOTA_RESET_INTERVAL_SECONDS
                    )
                    logger.info("✅ API quota reset time reached. Resuming update.")
                    return True

            logger.info(
                f"⏳ Quota not yet reset. Next check in {self.QUOTA_CHECK_INTERVAL_MINUTES} minutes. "
                f"(Elapsed: {elapsed / self.SECONDS_PER_MINUTE:.1f} minutes)"
            )

            # 等待指定時間
            time.sleep(check_interval_seconds)

    # ============================================================================
    # Private Methods - Data Retrieval
    # ============================================================================

    def _get_stock_list(self) -> List[str]:
        """
        從資料庫取得所有股票代碼列表（使用 stock_info，不含權證）

        Returns:
            List[str]: 股票代碼列表
        """
        try:
            query: str = (
                f"SELECT DISTINCT stock_id FROM {STOCK_INFO_TABLE_NAME} ORDER BY stock_id"
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
            securities_trader_list: List[str] = (
                df["securities_trader_id"].astype(str).tolist()
            )
            logger.info(
                f"Retrieved {len(securities_trader_list)} securities traders from database"
            )
            return securities_trader_list
        except Exception as e:
            logger.error(f"Error retrieving securities trader list: {e}")
            return []

    # ============================================================================
    # Private Methods - Metadata Management
    # ============================================================================

    def _load_broker_trading_metadata(self) -> Dict[str, Dict[str, Dict[str, str]]]:
        """
        從 metadata 文件讀取 broker trading 的日期範圍資訊。
        若有快取（_metadata_cache）則直接回傳，減少重複 I/O；快取僅在
        _update_broker_trading_metadata_from_database 成功寫入後更新。

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
        if self._metadata_cache is not None:
            return self._metadata_cache

        if not self.broker_trading_metadata_path.exists():
            return {}

        try:
            metadata: Dict[str, Dict[str, Dict[str, str]]] = DataUtils.load_json(
                self.broker_trading_metadata_path
            )
            return metadata if metadata is not None else {}
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
                            # 情況 A：DB 已有此組合但 metadata 遺漏，直接寫入查到的日期範圍
                            metadata[securities_trader_id][stock_id] = {
                                "earliest_date": earliest_date.strftime("%Y-%m-%d"),
                                "latest_date": latest_date.strftime("%Y-%m-%d"),
                            }
                            updated_count += 1
                        else:
                            # 情況 B：metadata 已有此組合，比較並擴展 earliest/latest 日期範圍
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
        DataUtils.save_json(
            metadata,
            self.broker_trading_metadata_path,
            ensure_ascii=False,
        )
        # 寫入成功後更新快取，迴圈內後續 _load 只讀快取
        self._metadata_cache = metadata

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
