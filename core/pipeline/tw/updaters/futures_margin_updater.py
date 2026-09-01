import sqlite3
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import FUTURES_MARGIN_HISTORY_TABLE_NAME, TW_FUTURES_DB_PATH
from core.pipeline.shared.base_updater import BaseDataUpdater
from core.pipeline.tw.cleaners.futures_margin_cleaner import FuturesMarginCleaner
from core.pipeline.tw.crawlers.futures_margin_crawler import FuturesMarginCrawler
from core.pipeline.tw.loaders.futures_margin_loader import FuturesMarginLoader
from core.utils.log_manager import LogManager

"""
台期貨保證金 Updater（指數類）

**一次請求就結束，沒有逐日／逐商品迴圈**：來源是一份「現行一覽表」，
整份一次回傳。因此本 updater 不需要節流，也沒有續跑起點的問題。

「重跑冪等」在這裡的實現方式與其他 updater 不同：不是靠比對日期範圍，
而是靠**主鍵 `(effective_date, product)` ＋ `INSERT OR IGNORE`**——
保證金沒變就沒有新的 `effective_date`，整批被忽略，表內列數不變。

歷史（2020/03 起的調整公告）屬 `backlog/台期貨保證金ETL.md` S4，不在本檔。
"""


class FuturesMarginUpdater(BaseDataUpdater):
    """Futures Margin Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection（tw_futures.db；供 log_summary 查詢用）
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: FuturesMarginCrawler = FuturesMarginCrawler()
        self.cleaner: FuturesMarginCleaner = FuturesMarginCleaner()
        self.loader: FuturesMarginLoader = FuturesMarginLoader()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        if self.conn is None:
            TW_FUTURES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(TW_FUTURES_DB_PATH)
        LogManager.setup_logger("update_futures_margin.log")

    def update(self) -> None:
        """
        - Description:
            更新台期貨保證金（指數類）

            crawl → clean → load 各一次。任一層回傳 None 即中止，
            **不做部分入庫**：一覽表是一組相互一致的數字，
            解析出問題時只入一半比整批不入更難察覺。
        """

        logger.info("* Start Updating TAIFEX Futures Margin (Index)")

        text: Optional[str] = self.crawler.crawl_index_margin()
        if text is None:
            logger.warning("[Futures Margin] 取得指數類一覽表失敗，本次中止")
            return

        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_index_margin(text)
        if cleaned_df is None or cleaned_df.empty:
            logger.warning("[Futures Margin] 指數類清洗結果為空，本次中止")
            return

        effective_date: str = str(cleaned_df["effective_date"].iloc[0])
        inserted: int = self.loader.add_to_db(cleaned_df)

        self.log_summary(effective_date, inserted, len(cleaned_df))

    def log_summary(self, effective_date: str, inserted: int, crawled: int) -> None:
        """
        更新後回報結果，讓「有沒有真的補到」一眼可見

        **`inserted == 0` 是正常狀態不是失敗**：保證金沒調整時本來就不會有新列。
        """

        products: List[str] = [
            row[0]
            for row in self.conn.execute(
                f"SELECT DISTINCT product FROM {FUTURES_MARGIN_HISTORY_TABLE_NAME} "
                f"ORDER BY product"
            )
        ]
        total: int = self.conn.execute(
            f"SELECT COUNT(*) FROM {FUTURES_MARGIN_HISTORY_TABLE_NAME}"
        ).fetchone()[0]
        date_range = self.conn.execute(
            f"SELECT MIN(effective_date), MAX(effective_date) "
            f"FROM {FUTURES_MARGIN_HISTORY_TABLE_NAME}"
        ).fetchone()

        logger.info(
            f"* 本次生效日 {effective_date}：抓到 {crawled} 個商品、新增 {inserted} 列"
        )
        logger.info(
            f"* 表內合計 {total} 列，商品 {products}，"
            f"生效日範圍 {date_range[0]} ~ {date_range[1]}"
        )
