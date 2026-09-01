import datetime
import random
import time
from typing import Callable, Dict, List, Optional, Tuple

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_INSTITUTIONAL_CHIP_TABLE_NAME,
    FUTURES_LARGE_TRADER_TABLE_NAME,
    FUTURES_PUT_CALL_RATIO_TABLE_NAME,
)
from core.pipeline.shared.base_updater import BaseDataUpdater
from core.pipeline.tw.cleaners.futures_chip_cleaner import FuturesChipCleaner
from core.pipeline.tw.crawlers.futures_chip_crawler import FuturesChipCrawler
from core.pipeline.tw.loaders.futures_chip_loader import FuturesChipLoader
from core.utils import TimeUtils
from core.utils.log_manager import LogManager

"""
台期貨籌碼 Updater：三大法人、大額交易人、選擇權 PCR

**一天三次請求就涵蓋全市場**（不逐商品打），故本 updater 的形態是
「逐日 × 三個資料集」，與 `futures_price_updater` 的「逐商品 × 逐時段 × 逐日」
完全不同——同樣的區間，請求數少一個數量級。

**續跑以各資料集自己的最新日為準**：三張表可能因為中斷而補到不同的日期，
用同一個起點會讓已經補到的那一張重爬一整段（雖然入庫會被 IGNORE，但請求
還是打出去了）。

⚠️ **籌碼是盤後公布**：當天盤中跑只會拿到「無資料」，那是正常狀態。
回測要用的本來就是前一交易日的籌碼（見 `FuturesChipAPI` 的前視偏差說明）。
"""


class FuturesChipUpdater(BaseDataUpdater):
    """更新 tw_futures.db 的三張籌碼表"""

    # 節流：與 `futures_price_updater` 同一組理由——TAIFEX 擋流量時回的是
    # HTTP 200 ＋ 一頁 HTML，看起來就像「當天沒資料」，被擋了也不會有錯誤
    MIN_DELAY_SECONDS: float = 1.0
    MAX_DELAY_SECONDS: float = 2.0
    BATCH_SIZE: int = 30  # 每 N 天多睡一次
    BATCH_REST_SECONDS: int = 10

    # 沒有指定起點時的預設回補起點：與行情一致（2015-01-01 起）
    DEFAULT_START_DATE: datetime.date = datetime.date(2015, 1, 1)

    def __init__(self):
        super().__init__()

        self.crawler: Optional[FuturesChipCrawler] = None
        self.cleaner: Optional[FuturesChipCleaner] = None
        self.loader: Optional[FuturesChipLoader] = None

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        LogManager.setup_logger("futures_chip_updater.log")
        self.crawler = FuturesChipCrawler()
        self.cleaner = FuturesChipCleaner()
        self.loader = FuturesChipLoader()

    def close(self) -> None:
        """關閉資料連線"""

        if self.loader is not None:
            self.loader.disconnect()

    def get_datasets(self) -> List[Tuple[str, str, Callable, Callable]]:
        """三個資料集的 (表名, 標籤, crawl, clean)"""

        return [
            (
                FUTURES_INSTITUTIONAL_CHIP_TABLE_NAME,
                "institutional",
                self.crawler.crawl_institutional,
                self.cleaner.clean_institutional,
            ),
            (
                FUTURES_LARGE_TRADER_TABLE_NAME,
                "large_trader",
                self.crawler.crawl_large_trader,
                self.cleaner.clean_large_trader,
            ),
            (
                FUTURES_PUT_CALL_RATIO_TABLE_NAME,
                "pcr",
                self.crawler.crawl_put_call_ratio,
                self.cleaner.clean_put_call_ratio,
            ),
        ]

    def update(
        self,
        start_date: Optional[datetime.date] = None,
        end_date: Optional[datetime.date] = None,
        resume: bool = True,
    ) -> None:
        """
        - Description:
            逐日更新三個籌碼資料集

            **每個資料集各自續跑**：以自己表內的最新日為起點，避免已補到的那一張
            重爬一整段。`resume=False` 則一律使用傳入的 `start_date`（歷史回補用）。
        - Parameters:
            - start_date / end_date: Optional[datetime.date]
                回補區間；None 分別取 `DEFAULT_START_DATE` 與今天
            - resume: bool
                是否從各表的最新日接續
        """

        end: datetime.date = end_date or datetime.date.today()

        for table, label, crawl, clean in self.get_datasets():
            start: datetime.date = self.resolve_start_date(
                table, start_date, resume=resume
            )
            self.update_dataset(table, label, crawl, clean, start, end)

    def resolve_start_date(
        self,
        table: str,
        start_date: Optional[datetime.date],
        resume: bool,
    ) -> datetime.date:
        """決定該資料集的起點：續跑時取表內最新日的次日"""

        if not resume:
            return start_date or self.DEFAULT_START_DATE

        latest: Optional[str] = self.loader.get_latest_date(table)
        if latest is None:
            return start_date or self.DEFAULT_START_DATE

        return datetime.date.fromisoformat(latest) + datetime.timedelta(days=1)

    def update_dataset(
        self,
        table: str,
        label: str,
        crawl: Callable,
        clean: Callable,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> int:
        """逐日爬取、清洗並入庫單一資料集；回傳新增列數"""

        if start_date > end_date:
            logger.info(f"[Futures Chip] {table} 已是最新（{start_date} > {end_date}）")
            return 0

        logger.info(f"* Updating {table}: {start_date} ~ {end_date}")

        dates: List[datetime.date] = TimeUtils.generate_date_range(start_date, end_date)
        inserted: int = 0

        for index, date in enumerate(dates, start=1):
            raw: Optional[str] = crawl(date)
            if raw is None:
                self.throttle(index)
                continue

            df: Optional[pd.DataFrame] = clean(raw, date)
            if df is None or df.empty:
                self.throttle(index)
                continue

            self.loader.save_csv(df, f"{label}_{date.strftime('%Y%m%d')}.csv")
            inserted += self.loader.add_to_db(table, df)
            self.throttle(index)

        logger.info(f"[Futures Chip] {table}：本次新增 {inserted} 列")
        return inserted

    def throttle(self, index: int) -> None:
        """逐日節流；每 `BATCH_SIZE` 天多睡一次"""

        time.sleep(random.uniform(self.MIN_DELAY_SECONDS, self.MAX_DELAY_SECONDS))
        if index % self.BATCH_SIZE == 0:
            logger.info(f"* 已處理 {index} 天，休息 {self.BATCH_REST_SECONDS} 秒")
            time.sleep(self.BATCH_REST_SECONDS)

    def get_coverage(self) -> Dict[str, Optional[str]]:
        """三張表各自補到哪一天（供人工確認進度）"""

        return {
            table: self.loader.get_latest_date(table)
            for table, _, _, _ in self.get_datasets()
        }
