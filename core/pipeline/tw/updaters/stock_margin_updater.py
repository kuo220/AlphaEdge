import datetime
import random
import sqlite3
import time
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import MARGIN_TABLE_NAME, PRICE_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.shared.base_updater import BaseDataUpdater
from core.pipeline.tw.cleaners.stock_margin_cleaner import StockMarginCleaner
from core.pipeline.tw.crawlers.stock_margin_crawler import StockMarginCrawler
from core.pipeline.tw.loaders.stock_margin_loader import StockMarginLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils
from core.utils import TimeUtils
from core.utils.log_manager import LogManager

"""
信用交易（融資融券餘額）爬蟲資料時間表：
1. TWSE
    - MI_MARGN（selectType=ALL）：官方自民國 90/01/01（2001/01/01）起提供，
      本專案實測 2013/1/1 起可取得且表格結構未再改制
2. TPEX
    - 上櫃融資融券餘額：官方自民國 96/01（2007/01）起提供，
      本專案實測 2013/1/1 起可取得且表格結構未再改制
"""


# 週六的 weekday() 值；用於判斷是否為週末
SATURDAY: int = 5


class StockMarginUpdater(BaseDataUpdater):
    """Stock Margin Updater"""

    # 每爬幾天就入庫一次。整段爬完才入庫的話，中斷等於前功盡棄——
    # 2013 起的回補有 3,300 個交易日、數小時，中途失敗要全部重來。
    # 分批之後最多只損失最後一批（未入庫的部分），重跑會自動接續。
    LOAD_BATCH_SIZE: int = 100
    BATCH_SLEEP_EVERY_N_FILES: int = 100
    BATCH_SLEEP_DURATION_SECONDS: int = 120
    BATCH_RANDOM_DELAY_MIN: int = 1
    BATCH_RANDOM_DELAY_MAX: int = 5

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: StockMarginCrawler = StockMarginCrawler()
        self.cleaner: StockMarginCleaner = StockMarginCleaner()
        self.loader: StockMarginLoader = StockMarginLoader()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)
        LogManager.setup_logger("update_margin.log")

    def get_traded_weekend_dates(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> Set[datetime.date]:
        """
        - Description:
            取得區間內「週末但實際有開市」的日期，資料來源為 price 表

            台股有**補行交易日**（補班補上課的週六照常開市），2013 起就有 11 天。
            這些日子必須照爬，否則 margin 會缺整天的資料。
        - Parameters:
            - start_date: datetime.date
                查詢起日
            - end_date: datetime.date
                查詢迄日
        - Return:
            - Set[datetime.date]
                週末且 price 表有資料的日期
        """

        rows = self.conn.execute(
            f"SELECT DISTINCT date FROM {PRICE_TABLE_NAME} WHERE date BETWEEN ? AND ?",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

        traded: Set[datetime.date] = set()
        for (raw,) in rows:
            date: datetime.date = datetime.date.fromisoformat(str(raw)[:10])
            if date.weekday() >= SATURDAY:
                traded.add(date)
        return traded

    def get_candidate_dates(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> List[datetime.date]:
        """
        - Description:
            決定要送出請求的日期清單

            **平日一律照爬**：國定假日無法純靠日曆判斷，維持「送出請求後由回應判定」。

            **週末原則上跳過**：台股週六日多半不開市，送出請求只會換回
            「is a Holiday」，卻一樣要付兩次 HTTP ＋ 節流時間；2013 起的回補約
            4,975 個日曆天中有 1,420 天是週末，跳過可省下約三成執行時間。

            **但補行交易日例外**：以 price 表實際有資料的週末為準，不用「非週末」
            近似。原本的寫法漏掉了 2013 年以來的 11 個補行交易日（皆為週六），
            那幾天的 margin 資料整天缺失。

            price 表落後於 margin 時，該區間的補行交易日會被漏掉——實務上
            price 一律先於 margin 更新，故此風險極低；真的缺漏時重跑即可補上。
        - Parameters:
            - start_date: datetime.date
                更新起日
            - end_date: datetime.date
                更新迄日
        - Return:
            - List[datetime.date]
                要送出請求的日期
        """

        traded_weekends: Set[datetime.date] = self.get_traded_weekend_dates(
            start_date, end_date
        )
        if traded_weekends:
            logger.info(
                f"區間內有 {len(traded_weekends)} 個補行交易日（週末開市），一併納入更新："
                f"{sorted(traded_weekends)}"
            )

        return [
            date
            for date in TimeUtils.generate_date_range(start_date, end_date)
            if date.weekday() < SATURDAY or date in traded_weekends
        ]

    def load_batch(self, batch_dates: List[str]) -> None:
        """
        - Description:
            入庫本批爬取的日期

            **只載入本批的檔案**：loader 預設會掃整個 downloads 目錄，若每批都全掃，
            13 年的回補會變成「數十批 × 數千檔」的重複讀取。
        - Parameters:
            - batch_dates: List[str]
                本批的日期字串（`YYYYMMDD`），對應 downloads 內的檔名後綴
        """

        logger.info(
            f"* Loading batch: {len(batch_dates)} 天（{batch_dates[0]} ~ {batch_dates[-1]}）"
        )
        self.loader.add_to_db(remove_files=False, only_dates=set(batch_dates))

    def update(
        self,
        start_date: datetime.date,
        end_date: datetime.date = datetime.date.today(),
    ) -> None:
        """Update the Database"""

        logger.info("* Start Updating TWSE & TPEX Margin Data...")

        # Step 1: Crawl
        # 取得要開始更新的日期
        start_date: datetime.date = self.get_actual_update_start_date(
            default_date=start_date
        )
        logger.info(f"Latest data date in database: {start_date}")
        # Set Up Update Period
        dates: List[datetime.date] = self.get_candidate_dates(start_date, end_date)
        file_cnt: int = 0
        batch_dates: List[str] = []

        for date in dates:
            logger.info(date.strftime("%Y/%m/%d"))
            twse_df: Optional[pd.DataFrame] = self.crawler.crawl_twse_margin(date)
            tpex_df: Optional[pd.DataFrame] = self.crawler.crawl_tpex_margin(date)

            # Step 2: Clean
            if twse_df is not None and not twse_df.empty:
                cleaned_twse_df: Optional[pd.DataFrame] = (
                    self.cleaner.clean_twse_margin(twse_df, date)
                )
                if cleaned_twse_df is None or cleaned_twse_df.empty:
                    logger.warning(f"Cleaned TWSE dataframe empty on {date}")

            if tpex_df is not None and not tpex_df.empty:
                cleaned_tpex_df: Optional[pd.DataFrame] = (
                    self.cleaner.clean_tpex_margin(tpex_df, date)
                )
                if cleaned_tpex_df is None or cleaned_tpex_df.empty:
                    logger.warning(f"Cleaned TPEX dataframe empty on {date}")

            file_cnt += 1
            batch_dates.append(date.strftime("%Y%m%d"))

            # Step 3: Load（分批）
            if len(batch_dates) >= self.LOAD_BATCH_SIZE:
                self.load_batch(batch_dates)
                batch_dates = []

            if file_cnt == self.BATCH_SLEEP_EVERY_N_FILES:
                logger.info("Sleep 2 minutes...")
                file_cnt = 0
                time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
            else:
                delay: int = random.randint(
                    self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                )
                time.sleep(delay)

        # 收尾：載入最後一批未達批量的日期
        if batch_dates:
            self.load_batch(batch_dates)

        # 更新後重新取得Table最新的日期
        table_latest_date: str = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=MARGIN_TABLE_NAME,
            col_name="date",
        )
        if table_latest_date:
            logger.info(
                f"Stock margin data updated. Latest available date: {table_latest_date}"
            )
        else:
            logger.warning("No new stock margin data was updated")

    def get_actual_update_start_date(
        self, default_date: datetime.date
    ) -> datetime.date:
        """Get the actual start date for updating (1 day after latest date in table, or default_date)"""

        latest_date: Optional[str] = SQLiteUtils.get_table_latest_value(
            conn=self.conn,
            table_name=MARGIN_TABLE_NAME,
            col_name="date",
        )

        if latest_date is not None:
            table_latest_date: datetime.date = datetime.datetime.strptime(
                latest_date,
                "%Y-%m-%d",
            ).date()
            return table_latest_date + datetime.timedelta(days=1)
        else:
            return default_date
