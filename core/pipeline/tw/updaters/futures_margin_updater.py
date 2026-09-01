import sqlite3
from typing import Dict, Optional

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_MARGIN_HISTORY_TABLE_NAME,
    STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME,
    TW_FUTURES_DB_PATH,
)
from core.pipeline.shared.base_updater import BaseDataUpdater
from core.pipeline.tw.cleaners.futures_margin_cleaner import FuturesMarginCleaner
from core.pipeline.tw.crawlers.futures_margin_crawler import FuturesMarginCrawler
from core.pipeline.tw.loaders.futures_margin_loader import FuturesMarginLoader
from core.utils.log_manager import LogManager

"""
台期貨保證金 Updater

**兩支來源、三條入庫路徑**：

| 來源 | 內容 | 入庫 |
|------|------|------|
| 指數類一覽表 | 指數期貨的每口金額 | `futures_margin_history` |
| 股票類一覽表 一(一) | 股票股期的**適用比例** | `stock_futures_margin_rate_history` |
| 股票類一覽表 一(二) | **ETF 股期的每口金額** | `futures_margin_history`（與指數期貨同表） |

**分表的依據是「金額 vs 比例」，不是「指數 vs 股票」**——ETF 股期給的是每口固定
金額，語意與臺股期貨相同。

**各段的生效日不同**（2026-09-01 實查：指數類 08/12、股票股期 08/28、
ETF 股期 08/12），故三條路徑各自帶自己的 `effective_date`，不共用。

**一次請求就結束，沒有逐日／逐商品迴圈**：來源是「現行一覽表」，整份一次回傳。
因此本 updater 不需要節流，也沒有續跑起點的問題。

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
            更新台期貨保證金（指數類 ＋ 股票類）

            **兩支來源各自獨立**：一支失敗不影響另一支——它們的生效日與更新頻率
            本來就不同，把它們綁在一起只會讓一邊的站方問題連累另一邊。
        """

        self.update_index_margin()
        self.update_stock_margin()
        self.log_summary()

    def update_index_margin(self) -> None:
        """
        更新指數類保證金（每口金額）

        任一層回傳 None 即中止，**不做部分入庫**：一覽表是一組相互一致的數字，
        解析出問題時只入一半比整批不入更難察覺。
        """

        logger.info("* Start Updating TAIFEX Futures Margin (Index)")

        text: Optional[str] = self.crawler.crawl_index_margin()
        if text is None:
            logger.warning("[Futures Margin] 取得指數類一覽表失敗，跳過")
            return

        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_index_margin(text)
        if cleaned_df is None or cleaned_df.empty:
            logger.warning("[Futures Margin] 指數類清洗結果為空，跳過")
            return

        effective_date: str = str(cleaned_df["effective_date"].iloc[0])
        inserted: int = self.loader.add_to_db(cleaned_df)
        logger.info(
            f"* 指數類 生效日 {effective_date}："
            f"抓到 {len(cleaned_df)} 個商品、新增 {inserted} 列"
        )

    def update_stock_margin(self) -> None:
        """
        - Description:
            更新股票類保證金

            **一份 CSV 拆成兩條入庫路徑**：股票股期的比例進比例表、
            ETF 股期的金額進 `futures_margin_history`（與指數期貨同表）。
            兩段的生效日不同，故各自帶自己的日期。
        """

        logger.info("* Start Updating TAIFEX Futures Margin (Stock)")

        text: Optional[str] = self.crawler.crawl_stock_margin()
        if text is None:
            logger.warning("[Stock Futures Margin] 取得股票類一覽表失敗，跳過")
            return

        cleaned: Optional[Dict[str, Optional[pd.DataFrame]]] = (
            self.cleaner.clean_stock_margin(text)
        )
        if cleaned is None:
            logger.warning("[Stock Futures Margin] 股票類清洗結果為空，跳過")
            return

        rate_df: Optional[pd.DataFrame] = cleaned.get("rate")
        if rate_df is not None and not rate_df.empty:
            inserted: int = self.loader.add_rates_to_db(rate_df)
            logger.info(
                f"* 股票股期（比例）生效日 {rate_df['effective_date'].iloc[0]}："
                f"抓到 {len(rate_df)} 檔、新增 {inserted} 列"
            )

        amount_df: Optional[pd.DataFrame] = cleaned.get("amount")
        if amount_df is not None and not amount_df.empty:
            # ETF 股期給的是每口金額，與指數期貨同一張表
            inserted: int = self.loader.add_to_db(amount_df)
            logger.info(
                f"* ETF 股期（金額）生效日 {amount_df['effective_date'].iloc[0]}："
                f"抓到 {len(amount_df)} 檔、新增 {inserted} 列"
            )

    def log_summary(self) -> None:
        """
        更新後逐表回報現況，讓「有沒有真的補到」一眼可見

        **新增 0 列是正常狀態不是失敗**：保證金沒調整時本來就不會有新列。
        """

        for table, key in (
            (FUTURES_MARGIN_HISTORY_TABLE_NAME, "product"),
            (STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME, "product_id"),
        ):
            total: int = self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[
                0
            ]
            products: int = self.conn.execute(
                f"SELECT COUNT(DISTINCT {key}) FROM {table}"
            ).fetchone()[0]
            date_range = self.conn.execute(
                f"SELECT MIN(effective_date), MAX(effective_date) FROM {table}"
            ).fetchone()

            logger.info(
                f"* {table}：{total} 列、{products} 個商品，"
                f"生效日範圍 {date_range[0]} ~ {date_range[1]}"
            )
