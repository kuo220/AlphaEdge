import datetime
import time
from concurrent.futures import Future, ThreadPoolExecutor
from pathlib import Path
from threading import Lock
from typing import Any, Dict, List, Optional

import pandas as pd
import shioaji as sj
from loguru import logger

from trader.config import LOGS_DIR_PATH, TICK_DOWNLOADS_PATH
from trader.pipeline.cleaners.stock_tick_cleaner import StockTickCleaner
from trader.pipeline.crawlers.stock_info_crawler import StockInfoCrawler
from trader.pipeline.crawlers.stock_tick_crawler import StockTickCrawler
from trader.pipeline.loaders.stock_tick_loader import StockTickLoader
from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.utils.stock_tick_utils import StockTickUtils
from trader.utils import ShioajiAccount, ShioajiAPI, TimeUtils

"""
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today

目前資料庫資料時間：
From 2020/04/01 ~ 2024/05/10
"""


class StockTickUpdater(BaseDataUpdater):
    """Stock Tick Updater"""

    def __init__(self):

        super().__init__()

        # ETL
        self.crawler: StockTickCrawler = StockTickCrawler()
        self.cleaner: StockTickCleaner = StockTickCleaner()
        self.loader: StockTickLoader = StockTickLoader()

        # Crawler Setting
        # Shioaji API List
        self.api_list: List[sj.Shioaji] = []

        # 爬取所有上市櫃股票清單
        self.all_stock_list: List[str] = StockInfoCrawler.crawl_stock_list()

        # 可用的 API 數量 = 可開的 thread 數
        self.num_threads: int = 0

        # 股票清單分組（後續給多線程用）
        self.split_stock_list: List[List[str]] = []

        # 目前 tickDB 最新資料日期
        self.table_latest_date: Optional[datetime.date] = None
        self.table_latest_date_lock: Lock = Lock()
        self.tick_dir: Path = TICK_DOWNLOADS_PATH

        # 全局統計信息
        self.global_stats: Dict[str, Any] = {
            "start_time": 0.0,
            "total_stocks_processed": 0,
            "successful_stocks": 0,
            "failed_stocks": 0,
            "skipped_stocks": 0,
            "total_dates_processed": 0,
            "successful_dates": 0,
            "failed_dates": 0,
            "skipped_dates": 0,
        }

        self.setup()

    def setup(self):
        """Set Up the Config of Updater"""

        # Setup Shioaji APIs
        API_LIST: List[ShioajiAPI] = StockTickUtils.setup_shioaji_apis()
        for sj_api in API_LIST:
            api_instance: Optional[sj.Shioaji] = ShioajiAccount.API_login(
                sj.Shioaji(), sj_api.api_key, sj_api.api_secret_key
            )
            if api_instance is not None:
                self.api_list.append(api_instance)

        # Set up number of threads
        self.num_threads = len(self.api_list)

        # Generate tick_metadata backup
        StockTickUtils.generate_tick_metadata_backup()

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_tick.log")

    def update(
        self,
        start_date: datetime.date,
        end_date: datetime.date = datetime.date.today(),
    ):
        """Update the Database"""

        # 重置全局統計信息
        self.global_stats = {
            "start_time": time.time(),
            "total_stocks_processed": 0,
            "successful_stocks": 0,
            "failed_stocks": 0,
            "skipped_stocks": 0,
            "total_dates_processed": 0,
            "successful_dates": 0,
            "failed_dates": 0,
            "skipped_dates": 0,
        }

        try:
            # 改進 CSV 文件刪除策略：只刪除臨時文件，保留已確認的 CSV
            # 檢查是否有臨時文件（以股票代號開頭但包含臨時標記的文件）
            temp_files: List[Path] = [
                f
                for f in self.tick_dir.glob("*.csv")
                if "_" in f.stem and f.stem.split("_")[0].isdigit()
            ]
            if temp_files:
                logger.info(f"Found {len(temp_files)} temporary CSV files, deleting...")
                for temp_file in temp_files:
                    try:
                        temp_file.unlink()
                        logger.debug(f"Deleted temporary file: {temp_file.name}")
                    except Exception as e:
                        logger.warning(
                            f"Failed to delete temporary file {temp_file.name}: {e}"
                        )

            # 檢查是否有正常的 CSV 文件（這些應該是已存入資料庫的）
            normal_csv_files: List[Path] = [
                f
                for f in self.tick_dir.glob("*.csv")
                if f.stem.isdigit() and f not in temp_files
            ]
            if normal_csv_files:
                logger.info(
                    f"Found {len(normal_csv_files)} existing CSV files. "
                    f"These will be preserved (assuming they are already in database)."
                )

            # 取得最近更新的日期（從 tick_metadata.json 讀取）
            start_date = self.get_actual_update_start_date(default_date=start_date)
            logger.info(f"Latest data date in database: {start_date}")

            # Set Up Update Period
            dates: List[datetime.date] = TimeUtils.generate_date_range(
                start_date, end_date
            )

            # Step 1: Crawl + Clean（會使用 tick_metadata.json 來跳過已存在的日期）
            logger.info("=" * 80)
            logger.info("Starting multi-threaded update process...")
            logger.info("=" * 80)

            self.update_multithreaded(dates)

            # Step 2: Load - 存入資料庫
            logger.info("=" * 80)
            logger.info("Starting database loading process...")
            logger.info("=" * 80)

            try:
                self.loader.add_to_db(remove_files=False)
                logger.info("Database loading completed successfully")
            except Exception as e:
                logger.error(f"Database loading failed: {e}", exc_info=True)
                raise

            # Step 3: 確定都存完後，掃描 tick 資料夾內所有的 .csv 以更新 tick_metadata.json
            logger.info("Scanning CSV files and updating tick metadata...")
            try:
                StockTickUtils.update_tick_metadata_from_csv()
                logger.info("Tick metadata updated successfully")
            except Exception as e:
                logger.error(f"Failed to update tick metadata: {e}", exc_info=True)
                # 不中斷流程，因為 metadata 更新失敗不影響數據本身

            # 更新後重新取得最新日期並記錄
            if self.table_latest_date:
                logger.info(
                    f"* Tick data updated. Latest available date: {self.table_latest_date}"
                )
                # 如果最新日期小於目標結束日期，記錄警告
                if self.table_latest_date < end_date:
                    logger.warning(
                        f"* Warning: Latest date ({self.table_latest_date}) is before target end_date ({end_date}). "
                        f"Some dates may have no data (non-trading days or API issues)."
                    )
            else:
                logger.warning("* No new stock tick data was updated")

            # 輸出完整的統計報告
            self._print_update_summary(self.global_stats, start_date, end_date)
        except Exception as e:
            logger.error(f"Update process failed with exception: {e}", exc_info=True)
            self._print_update_summary(self.global_stats, start_date, end_date)
            raise
        finally:
            # Step 4: Cleanup - 確保登出所有 API 連接（即使發生異常也會執行）
            self.cleanup()

    def update_thread(
        self,
        api: sj.Shioaji,
        dates: List[datetime.date],
        stock_list: List[str],
    ) -> None:
        """
        - Description:
            單一 thread 任務：爬 + 清洗

        - Parameters:
            - api: sj.Shioaji
                Shioaji API
            - dates: List[datetime.date]
                日期 List
            - stock_list: List[str]
                Stock List

        - Return: List[pd.DataFrame]
            - 每個 df 是一檔股票日期區間內的所有 tick
        """

        latest_date: Optional[datetime.date] = None
        # 統計信息
        stats: Dict[str, Any] = {
            "total_stocks": len(stock_list),
            "successful_stocks": 0,
            "failed_stocks": 0,
            "skipped_stocks": 0,
        }

        # Crawl
        for stock_id in stock_list:
            # 判斷 api 用量（統一檢查，避免重複）
            try:
                remaining_mb: float = api.usage().remaining_bytes / 1024**2
                if remaining_mb < 20:
                    logger.warning(
                        f"API quota low ({remaining_mb:.2f} MB remaining) for {api}. "
                        f"Stopped crawling at stock {stock_id}."
                    )
                    break
            except Exception as e:
                logger.warning(f"Failed to check API quota: {e}. Continuing...")

            logger.info(f"Start crawling stock: {stock_id}")

            df_list: List[pd.DataFrame] = []
            stock_successful_dates: List[datetime.date] = (
                []
            )  # 追蹤當前股票成功爬取的日期
            skipped_dates: List[datetime.date] = []  # 追蹤被跳過的日期
            failed_dates: List[datetime.date] = []  # 追蹤爬取失敗的日期

            for date in dates:
                # 檢查是否已經存在該日期的資料，如果存在則跳過
                if StockTickUtils.should_skip_crawl(stock_id, date):
                    skipped_dates.append(date)
                    logger.debug(
                        f"Skipping {stock_id} on {date.isoformat()} (data already exists in CSV)"
                    )
                    continue

                # 統一 API 配額檢查（在每次爬取前檢查，因為配額是動態變化的）
                try:
                    remaining_mb: float = api.usage().remaining_bytes / 1024**2
                    if remaining_mb < 20:
                        logger.warning(
                            f"API quota low ({remaining_mb:.2f} MB remaining) for {api}. "
                            f"Stopped crawling {stock_id} at date {date.isoformat()}."
                        )
                        break  # 跳出日期循環，繼續下一個股票
                except Exception as e:
                    logger.warning(
                        f"Failed to check API quota before crawling {stock_id} on {date}: {e}. "
                        f"Continuing..."
                    )

                try:
                    df: Optional[pd.DataFrame] = self.crawler.crawl_stock_tick(
                        api, date, stock_id
                    )

                    if df is None or df.empty:
                        skipped_dates.append(date)
                        logger.debug(
                            f"No tick data for {stock_id} on {date.isoformat()} "
                            f"(may be non-trading day or no data)"
                        )
                        continue

                    df_list.append(df)
                    stock_successful_dates.append(date)  # 記錄成功爬取的日期

                except Exception as e:
                    failed_dates.append(date)
                    logger.warning(
                        f"Failed to crawl {stock_id} on {date.isoformat()}: {e}"
                    )
                    continue

            # 改進邏輯：即使部分日期失敗，也保存成功的數據
            if not df_list:
                if skipped_dates:
                    logger.info(
                        f"Stock {stock_id}: All dates skipped (already exist or no data). "
                        f"Total skipped: {len(skipped_dates)}"
                    )
                    stats["skipped_stocks"] += 1
                else:
                    logger.warning(
                        f"No tick data found for stock {stock_id} from {dates[0]} to {dates[-1]}. "
                        f"Failed dates: {len(failed_dates)}"
                    )
                    stats["failed_stocks"] += 1
                continue

            # 記錄詳細的日期統計
            logger.info(
                f"Stock {stock_id}: Successfully crawled {len(stock_successful_dates)} dates, "
                f"skipped {len(skipped_dates)} dates, failed {len(failed_dates)} dates"
            )
            if stock_successful_dates:
                logger.debug(
                    f"Stock {stock_id}: Successful date range: "
                    f"{min(stock_successful_dates).isoformat()} ~ {max(stock_successful_dates).isoformat()}"
                )
            if failed_dates:
                logger.warning(
                    f"Stock {stock_id}: Failed dates: "
                    f"{min(failed_dates).isoformat()} ~ {max(failed_dates).isoformat()}"
                )

            # 合併所有成功的數據
            try:
                merged_df: pd.DataFrame = pd.concat(df_list, ignore_index=True)
                logger.debug(
                    f"Stock {stock_id}: Merged {len(df_list)} dataframes, "
                    f"total rows: {len(merged_df)}"
                )
            except Exception as e:
                logger.error(
                    f"Stock {stock_id}: Error merging dataframes: {e}", exc_info=True
                )
                stats["failed_stocks"] += 1
                continue

            # Clean
            try:
                cleaned_df: pd.DataFrame = self.cleaner.clean_stock_tick(
                    merged_df, stock_id
                )

                if cleaned_df is None or cleaned_df.empty:
                    logger.warning(
                        f"Stock {stock_id}: Cleaned dataframe is empty after processing"
                    )
                    stats["failed_stocks"] += 1
                else:
                    # 更新 latest_date 為成功處理的日期中的最大值
                    if stock_successful_dates:
                        stock_max_date: datetime.date = max(stock_successful_dates)
                        latest_date = (
                            stock_max_date
                            if latest_date is None
                            else max(latest_date, stock_max_date)
                        )
                    stats["successful_stocks"] += 1
                    logger.info(
                        f"Stock {stock_id}: Successfully processed and saved "
                        f"({len(cleaned_df)} rows)"
                    )

            except Exception as e:
                logger.error(
                    f"Stock {stock_id}: Error cleaning tick data: {e}", exc_info=True
                )
                stats["failed_stocks"] += 1

        # 記錄線程統計信息
        logger.info(
            f"Thread completed. Stats: {stats['successful_stocks']} successful, "
            f"{stats['failed_stocks']} failed, {stats['skipped_stocks']} skipped "
            f"out of {stats['total_stocks']} stocks"
        )

        # 返回統計信息供匯總
        return stats

        # 更新 table 最新日期（thread-safe）
        if latest_date:
            with self.table_latest_date_lock:
                self.table_latest_date = max(
                    self.table_latest_date or latest_date, latest_date
                )

    def update_multithreaded(self, dates: List[datetime.date]) -> None:
        """使用 Multi-threading 的方式 Update Tick Data"""

        logger.info(
            f"Start multi-thread Updating. Total stocks: {len(self.all_stock_list)}, "
            f"Total dates: {len(dates)}, Threads: {self.num_threads}"
        )
        start_time: float = time.time()  # 開始計時

        # 將 Stock list 均分給各個 thread 進行爬蟲
        self.split_stock_list: List[List[str]] = self.split_list(
            self.all_stock_list, self.num_threads
        )

        # Multi-threading
        futures: List[Future] = []
        thread_results: List[Dict[str, Any]] = []  # 收集每個線程的統計信息

        with ThreadPoolExecutor(max_workers=self.num_threads) as executor:
            for api, stock_list in zip(self.api_list, self.split_stock_list):
                futures.append(
                    executor.submit(
                        self.update_thread,
                        api=api,
                        dates=dates,
                        stock_list=stock_list,
                    )
                )

            # 等待所有 thread 結束並收集結果
            for i, future in enumerate(futures):
                try:
                    thread_stats: Optional[Dict[str, Any]] = (
                        future.result()
                    )  # 若有 exception 會在這邊被 raise 出來
                    if thread_stats:
                        thread_results.append(thread_stats)
                except Exception as e:
                    logger.error(
                        f"Thread {i + 1} task failed with exception: {e}", exc_info=True
                    )
                    # 記錄失敗的線程統計
                    thread_results.append(
                        {
                            "successful_stocks": 0,
                            "failed_stocks": (
                                len(self.split_stock_list[i])
                                if i < len(self.split_stock_list)
                                else 0
                            ),
                            "skipped_stocks": 0,
                        }
                    )

        # 匯總所有線程的統計信息
        for thread_stat in thread_results:
            self.global_stats["successful_stocks"] += thread_stat.get(
                "successful_stocks", 0
            )
            self.global_stats["failed_stocks"] += thread_stat.get("failed_stocks", 0)
            self.global_stats["skipped_stocks"] += thread_stat.get("skipped_stocks", 0)
            self.global_stats["total_stocks_processed"] += thread_stat.get(
                "total_stocks", 0
            )

        total_time: float = time.time() - start_time
        total_file: int = len(list(TICK_DOWNLOADS_PATH.glob("*.csv")))
        logger.info(
            f"All crawling tasks completed. Total CSV files: {total_file}, "
            f"Total time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)"
        )

    def split_list(
        self,
        target_list: List[Any],
        n_parts: int,
    ) -> List[List[str]]:
        """將 list 均分成 n 個 list"""

        num_list: int
        rem: int
        num_list, rem = divmod(len(target_list), n_parts)
        return [
            target_list[
                i * num_list + min(i, rem) : (i + 1) * num_list + min(i + 1, rem)
            ]
            for i in range(n_parts)
        ]

    def get_actual_update_start_date(
        self, default_date: datetime.date
    ) -> datetime.date:
        """Get the actual start date for updating (1 day after latest date in table, or default_date)"""

        self.table_latest_date = StockTickUtils.get_table_latest_date()
        if self.table_latest_date:
            return self.table_latest_date + datetime.timedelta(days=1)
        else:
            return default_date

    def cleanup(self) -> None:
        """清理資源：登出所有 Shioaji API 連接"""
        from trader.utils import ShioajiAccount

        if not self.api_list:
            return

        logger.info("Cleaning up API connections...")
        for api in self.api_list:
            try:
                ShioajiAccount.API_logout(api)
            except (TimeoutError, Exception) as e:
                # 如果登出失敗（例如連接已關閉或超時），記錄警告但不中斷程序
                # 這些錯誤通常在程序結束時發生，可以安全忽略
                logger.debug(f"API logout warning (can be safely ignored): {e}")

        # 清空 API 列表
        self.api_list.clear()
        logger.info("All API connections closed")

    def _print_update_summary(
        self, stats: Dict[str, Any], start_date: datetime.date, end_date: datetime.date
    ) -> None:
        """打印更新過程的完整統計報告"""

        total_time: float = time.time() - stats["start_time"]

        logger.info("=" * 80)
        logger.info("UPDATE SUMMARY")
        logger.info("=" * 80)
        logger.info(f"Date Range: {start_date.isoformat()} ~ {end_date.isoformat()}")
        logger.info(
            f"Total Time: {total_time:.2f} seconds ({total_time/60:.2f} minutes)"
        )
        logger.info("")
        logger.info("Stock Statistics:")
        logger.info(f"  - Total Processed: {stats['total_stocks_processed']}")
        logger.info(f"  - Successful: {stats['successful_stocks']}")
        logger.info(f"  - Failed: {stats['failed_stocks']}")
        logger.info(f"  - Skipped: {stats['skipped_stocks']}")
        logger.info("")
        if stats["total_stocks_processed"] > 0:
            success_rate: float = (
                stats["successful_stocks"] / stats["total_stocks_processed"]
            ) * 100
            logger.info(f"Success Rate: {success_rate:.2f}%")
        logger.info("=" * 80)
