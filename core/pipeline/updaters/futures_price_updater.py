import datetime
import random
import sqlite3
import time
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import (
    DB_PATH,
    DEFAULT_FUTURES_START_DATE,
    FUTURES_DB_PATH,
    FUTURES_PRICE_DAILY_TABLE_NAME,
    FUTURES_TARGET_PRODUCTS,
    PRICE_TABLE_NAME,
)
from core.pipeline.cleaners.futures_price_cleaner import FuturesPriceCleaner
from core.pipeline.crawlers.futures_price_crawler import FuturesPriceCrawler
from core.pipeline.loaders.futures_price_loader import FuturesPriceLoader
from core.pipeline.updaters.base import BaseDataUpdater
from core.utils import FuturesSession, TimeUtils
from core.utils.log_manager import LogManager

"""
台期貨每日行情 Updater

1. **逐商品迴圈，不是逐日期迴圈**
   各商品的上市日不同（TX 1998-07、MTX 2001、TMF 2022 之後），且會陸續加入
   `FUTURES_TARGET_PRODUCTS`。若以「全表最新日」當續跑起點，新加的商品會被
   既有商品的進度擋住而整段歷史都補不到，故 resume 一律以 (product) 為單位。

2. 每個交易日要打兩次（日盤、夜盤）
   兩者是獨立行情，見 `futures_price_crawler` 的說明。

3. 分批入庫
   TX 全段約 6,900 個交易日、13,800 次請求，數小時起跳。整段跑完才入庫的話
   中斷等於前功盡棄，故每 `LOAD_BATCH_SIZE` 天就入庫一次。
"""


# 週六的 weekday() 值；用於判斷是否為週末
SATURDAY: int = 5


class FuturesPriceUpdater(BaseDataUpdater):
    """Futures Price Updater"""

    # 每爬幾天就入庫一次；中斷最多只損失最後一批
    LOAD_BATCH_SIZE: int = 100
    BATCH_SLEEP_EVERY_N_FILES: int = 100
    BATCH_SLEEP_DURATION_SECONDS: int = 120
    BATCH_RANDOM_DELAY_MIN: int = 1
    BATCH_RANDOM_DELAY_MAX: int = 3

    def __init__(self):
        super().__init__()

        # SQLite Connection（futures.db）
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: FuturesPriceCrawler = FuturesPriceCrawler()
        self.cleaner: FuturesPriceCleaner = FuturesPriceCleaner()
        self.loader: FuturesPriceLoader = FuturesPriceLoader()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            FUTURES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn: sqlite3.Connection = sqlite3.connect(FUTURES_DB_PATH)
        LogManager.setup_logger("update_futures_price.log")

    def get_actual_update_start_date(
        self,
        product: str,
        default_date: datetime.date,
    ) -> datetime.date:
        """
        - Description:
            取得該商品實際要開始更新的日期（表內該商品最新日 +1）

            **以 product 為單位而非全表**：新加入的商品在表內沒有任何資料，
            用全表最新日當起點會讓它的歷史整段補不到，且不會有任何錯誤訊息。
        - Parameters:
            - product: str
                商品代碼
            - default_date: datetime.date
                表內無該商品資料時的起始日
        - Return:
            - datetime.date
        """

        try:
            row = self.conn.execute(
                f"SELECT MAX(date) FROM {FUTURES_PRICE_DAILY_TABLE_NAME} "
                f"WHERE product = ?",
                (product,),
            ).fetchone()
        except sqlite3.Error as error:
            logger.warning(f"查詢 {product} 最新日期失敗，改用預設起日：{error}")
            return default_date

        latest: Optional[str] = row[0] if row else None
        if not latest:
            return default_date

        return TimeUtils.to_date(latest) + datetime.timedelta(days=1)

    def get_traded_weekend_dates(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> Set[datetime.date]:
        """
        - Description:
            取得區間內實際開市的週末（補行交易日）

            期貨與現貨共用同一份行事曆，故直接以 `stock.db` 的 `price` 表判斷，
            不另建期貨日曆（那是 Phase2-3 的事）。

            **已知限制**：`price` 表自 2013 起才有資料，故 **2013 年之前的補行
            交易日無法偵測**，那幾天的期貨資料會缺。補救方式是日後以明確日期
            重跑；不影響絕大多數區間。
        - Parameters:
            - start_date / end_date: datetime.date
                查詢區間
        - Return:
            - Set[datetime.date]
                區間內開市的週末日期
        """

        try:
            with sqlite3.connect(DB_PATH) as stock_conn:
                df: pd.DataFrame = pd.read_sql_query(
                    f"SELECT DISTINCT date FROM {PRICE_TABLE_NAME} "
                    f"WHERE date BETWEEN ? AND ?",
                    stock_conn,
                    params=(start_date, end_date),
                )
        except Exception as error:
            logger.warning(
                f"無法讀取 price 表判斷補行交易日，本次一律跳過週末：{error}"
            )
            return set()

        if df.empty:
            return set()

        dates = pd.to_datetime(df["date"]).dt.date
        return {date for date in dates if date.weekday() >= SATURDAY}

    def get_candidate_dates(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> List[datetime.date]:
        """
        - Description:
            決定要送出請求的日期清單

            平日一律照爬（國定假日無法純靠日曆判斷，交給回應判定）；
            週末原則上跳過，但補行交易日例外（見 `get_traded_weekend_dates`）。
        - Parameters:
            - start_date / end_date: datetime.date
                更新區間
        - Return:
            - List[datetime.date]
        """

        traded_weekends: Set[datetime.date] = self.get_traded_weekend_dates(
            start_date, end_date
        )
        if traded_weekends:
            logger.info(
                f"區間內有 {len(traded_weekends)} 個補行交易日，一併納入更新："
                f"{sorted(traded_weekends)}"
            )

        return [
            date
            for date in TimeUtils.generate_date_range(start_date, end_date)
            if date.weekday() < SATURDAY or date in traded_weekends
        ]

    def load_batch(self, batch_dates: List[str]) -> None:
        """入庫本批爬取的日期；只載入本批檔案，避免每批重掃整個 downloads 目錄"""

        logger.info(
            f"* Loading batch: {len(batch_dates)} 天"
            f"（{batch_dates[0]} ~ {batch_dates[-1]}）"
        )
        self.loader.add_to_db(remove_files=False, only_dates=set(batch_dates))

    def update(
        self,
        start_date: datetime.date = DEFAULT_FUTURES_START_DATE,
        end_date: datetime.date = datetime.date.today(),
        products: Optional[List[str]] = None,
    ) -> None:
        """
        - Description:
            更新台期貨每日行情

            未指定 `products` 時取用 `FUTURES_TARGET_PRODUCTS`。
        - Parameters:
            - start_date: datetime.date
                起日；實際起點仍會被該商品在表內的最新日覆蓋（續跑）
            - end_date: datetime.date
                迄日
            - products: Optional[List[str]]
                要更新的商品；None 表示取設定檔
        """

        target_products: List[str] = products or FUTURES_TARGET_PRODUCTS

        # 商品代碼拼錯會讓整段回補安靜地全部查無資料，看似「一直都是假日」，
        # 故在送出任何請求之前先全部檢查一遍
        for product in target_products:
            self.crawler.validate_product(product)

        logger.info(f"* Start Updating TAIFEX Futures Price: {target_products}")

        for product in target_products:
            self.update_product(product, start_date, end_date)

        self.log_summary(target_products)

    def update_product(
        self,
        product: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> None:
        """單一商品的爬取 → 清洗 → 分批入庫"""

        actual_start: datetime.date = self.get_actual_update_start_date(
            product, default_date=start_date
        )
        if actual_start > end_date:
            logger.info(f"* {product} 已是最新（起點 {actual_start} 晚於 {end_date}）")
            return

        dates: List[datetime.date] = self.get_candidate_dates(actual_start, end_date)
        logger.info(f"* {product}: {actual_start} ~ {end_date}，共 {len(dates)} 天")

        file_cnt: int = 0
        batch_dates: List[str] = []

        for date in dates:
            crawled: bool = False

            for session in FuturesSession:
                raw_df: Optional[pd.DataFrame] = self.crawler.crawl_futures_price(
                    date, product, session
                )
                if raw_df is None or raw_df.empty:
                    continue

                cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_futures_price(
                    raw_df, date, product, session
                )
                if cleaned_df is None or cleaned_df.empty:
                    logger.warning(
                        f"Cleaned dataframe empty on {date} {product} {session.value}"
                    )
                    continue
                crawled = True

            if crawled:
                batch_dates.append(TimeUtils.format_date(date))

            file_cnt += 1

            if len(batch_dates) >= self.LOAD_BATCH_SIZE:
                self.load_batch(batch_dates)
                batch_dates = []

            if file_cnt >= self.BATCH_SLEEP_EVERY_N_FILES:
                logger.info("Sleep 2 minutes...")
                file_cnt = 0
                time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
            else:
                time.sleep(
                    random.randint(
                        self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                    )
                )

        # 收尾：載入最後一批未達批量的日期
        if batch_dates:
            self.load_batch(batch_dates)

    def log_summary(self, products: List[str]) -> None:
        """更新後逐商品回報最新日期與列數，讓「有沒有真的補到」一眼可見"""

        for product in products:
            row = self.conn.execute(
                f"SELECT COUNT(*), MIN(date), MAX(date) "
                f"FROM {FUTURES_PRICE_DAILY_TABLE_NAME} WHERE product = ?",
                (product,),
            ).fetchone()

            if not row or not row[0]:
                logger.warning(f"{product}: 表內仍無資料")
                continue

            logger.info(f"{product}: {row[0]} 列，{row[1]} ~ {row[2]}")
