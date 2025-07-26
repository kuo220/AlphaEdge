import datetime
from typing import Optional
import pandas as pd
import shioaji as sj
from shioaji.data import Ticks
from loguru import logger
from pathlib import Path

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.config import (
    LOGS_DIR_PATH,
    TICK_DOWNLOADS_PATH,
)


"""
Shioaji 台股 ticks 資料時間表：
From: 2020/03/02 ~ Today

目前資料庫資料時間：
From 2020/04/01 ~ 2024/05/10
"""


class StockTickCrawler(BaseDataCrawler):
    """爬取上市櫃股票 ticks"""

    def __init__(self):
        """初始化爬蟲設定"""

        super().__init__()

        self.tick_dir: Path = TICK_DOWNLOADS_PATH
        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Crawler"""

        # Set logger
        logger.add(f"{LOGS_DIR_PATH}/crawl_stock_tick.log")

        # Create the tick downloads directory
        self.tick_dir.mkdir(parents=True, exist_ok=True)

    def crawl(self) -> None:
        """Crawl Tick Data"""
        pass

    def crawl_stock_tick(
        self,
        api: sj.Shioaji,
        date: datetime.date,
        code: str,
    ) -> Optional[pd.DataFrame]:
        """透過 Shioaji 爬取指定個股的 tick data"""

        # 判斷 api 用量
        if api.usage().remaining_bytes / 1024**2 < 20:
            logger.warning(
                f"API quota low for {api}. Stopped crawling at stock {code} on {date}."
            )
            return None

        try:
            ticks: Ticks = api.ticks(
                contract=api.Contracts.Stocks[code], date=date.isoformat()
            )
            tick_df: pd.DataFrame = pd.DataFrame({**ticks})

            return tick_df if not tick_df.empty else None

        except Exception as e:
            logger.error(f"Error Crawling Tick Data: {code} {date} | {e}")
            return None
