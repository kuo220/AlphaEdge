import datetime
import sqlite3
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_STOCK_UNIVERSE_TABLE_NAME,
    PRICE_TABLE_NAME,
    TW_FUTURES_DB_PATH,
    TW_STOCK_DB_PATH,
)
from core.pipeline.shared.base_updater import BaseDataUpdater
from core.pipeline.tw.cleaners.futures_stock_universe_cleaner import (
    FuturesStockUniverseCleaner,
)
from core.pipeline.tw.crawlers.futures_stock_universe_crawler import (
    FuturesStockUniverseCrawler,
)
from core.pipeline.tw.loaders.futures_stock_universe_loader import (
    FuturesStockUniverseLoader,
)
from core.utils import StockFuturesType, TimeUtils
from core.utils.log_manager import LogManager

"""
股票期貨標的池 Updater

**存在的理由：股期不能像指數期貨那樣把商品清單寫死在 `FUTURES_TARGET_PRODUCTS`**。
指數期貨 5~15 檔、幾年才動一次，字面值清單完全夠用；股期 320 檔且會隨掛牌／下市
異動，手寫清單必然過期，也沒有地方放契約單位的歷史序列。故清單改由本表提供，
下游（Phase6-2 的股期行情 ETL）以 `get_active_products()` 取得要爬的商品，
不必為每一檔手動指定。

1. **一次請求就結束，沒有回補區間**
    來源是一張完整的清單頁，不分日期也不分商品，與 `futures_price_updater`
    「逐商品 × 逐時段 × 逐日」的形態完全不同，故本類沒有節流與分批入庫。

2. 冪等：同一天重跑不會產生第二份快照
    快照日就是執行日，主鍵為 (snapshot_date, product_id)，重跑會被
    `INSERT OR IGNORE` 擋下。爬之前先查表可以連請求都省下來。

3. 更新頻率建議「每日」而不是「每月」
    掛牌／下市日在本表只能由快照差分推得，快照愈稀疏，推出來的日期誤差愈大。
    整份清單一天只有一次請求，成本可以忽略。
"""


class FuturesStockUniverseUpdater(BaseDataUpdater):
    """Futures Stock Universe Updater"""

    def __init__(self):
        super().__init__()

        self.crawler: FuturesStockUniverseCrawler = FuturesStockUniverseCrawler()
        self.cleaner: FuturesStockUniverseCleaner = FuturesStockUniverseCleaner()
        self.loader: FuturesStockUniverseLoader = FuturesStockUniverseLoader()

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        LogManager.setup_logger("futures_stock_universe_updater.log")

    def update(
        self,
        snapshot_date: Optional[datetime.date] = None,
        force: bool = False,
    ) -> None:
        """
        - Description:
            抓取一份股票期貨標的池快照並入庫

            **快照日預設為今天而不是「最新交易日」**：本表記錄的是「這一天在
            TAIFEX 看到的清單」，不是某個交易日的行情，假日抓到的清單一樣有效。
        - Parameters:
            - snapshot_date: Optional[datetime.date]
                快照日；None 表示今天
            - force: bool
                當日快照已存在時是否仍重抓。預設不重抓，連請求都省下來
        """

        snapshot_date = snapshot_date or datetime.date.today()

        if not force and self.is_snapshot_loaded(snapshot_date):
            logger.info(
                f"* {snapshot_date} 的標的池快照已存在，略過（force=True 可重抓）"
            )
            return

        logger.info(f"* Start Updating TAIFEX Stock Futures Universe: {snapshot_date}")

        raw_df: Optional[pd.DataFrame] = self.crawler.crawl_stock_universe()
        if raw_df is None or raw_df.empty:
            logger.warning("[Futures Universe] 未取得標的清單，本次不入庫")
            return

        cleaned_df: Optional[pd.DataFrame] = self.cleaner.clean_stock_universe(
            raw_df, snapshot_date
        )
        if cleaned_df is None or cleaned_df.empty:
            logger.warning("[Futures Universe] 清洗後無有效資料，本次不入庫")
            return

        # 差分要拿「入庫前」的最近一份快照比，入庫後就比不出差異了
        previous_date: Optional[str] = self.get_latest_snapshot_date(
            before=snapshot_date
        )

        self.loader.add_to_db(
            remove_files=False,
            only_dates={TimeUtils.format_date(snapshot_date)},
        )

        self.log_summary(cleaned_df)
        self.log_snapshot_diff(cleaned_df, previous_date)
        self.log_underlying_match(cleaned_df)

    def is_snapshot_loaded(self, snapshot_date: datetime.date) -> bool:
        """檢查該日快照是否已入庫"""

        conn: sqlite3.Connection = sqlite3.connect(TW_FUTURES_DB_PATH)
        try:
            if not self.table_exists(conn, FUTURES_STOCK_UNIVERSE_TABLE_NAME):
                return False

            query: str = f"""
                SELECT COUNT(*) FROM {FUTURES_STOCK_UNIVERSE_TABLE_NAME}
                WHERE snapshot_date = ?
            """
            count: int = conn.execute(query, (str(snapshot_date),)).fetchone()[0]
            return count > 0
        finally:
            conn.close()

    def get_latest_snapshot_date(
        self, before: Optional[datetime.date] = None
    ) -> Optional[str]:
        """
        - Description:
            取得最新一份快照的日期

        - Parameters:
            - before: Optional[datetime.date]
                只看早於此日的快照；None 表示不設限
        - Return:
            - Optional[str]
                快照日；表不存在或尚無資料時為 None
        """

        conn: sqlite3.Connection = sqlite3.connect(TW_FUTURES_DB_PATH)
        try:
            if not self.table_exists(conn, FUTURES_STOCK_UNIVERSE_TABLE_NAME):
                return None

            if before is None:
                query: str = f"SELECT MAX(snapshot_date) FROM {FUTURES_STOCK_UNIVERSE_TABLE_NAME}"
                row = conn.execute(query).fetchone()
            else:
                query: str = f"""
                    SELECT MAX(snapshot_date) FROM {FUTURES_STOCK_UNIVERSE_TABLE_NAME}
                    WHERE snapshot_date < ?
                """
                row = conn.execute(query, (str(before),)).fetchone()

            return row[0] if row and row[0] else None
        finally:
            conn.close()

    @classmethod
    def get_active_products(
        cls,
        product_types: Optional[List[str]] = None,
        snapshot_date: Optional[str] = None,
    ) -> List[str]:
        """
        - Description:
            取得最新快照中仍在列的商品代碼（＝ 行情頁的 `commodity_id`）

            **這是 Phase6-2 股期行情 ETL 的商品清單來源**：股期不走
            `FUTURES_TARGET_PRODUCTS`，改由本表提供，故新掛牌的標的只要跑過一次
            標的池更新就會自動進入爬取範圍，不需要為每一檔手動指定。

            ⚠️ **回傳的是「最新快照有的」而不是「歷史上有過的」**：已下市的商品
            不會出現在這裡。要回補下市商品的歷史行情，須自行以歷史快照取清單。
        - Parameters:
            - product_types: Optional[List[str]]
                只取這些商品類型（見 `StockFuturesType`）；None 表示全部
            - snapshot_date: Optional[str]
                指定快照日；None 表示取最新一份
        - Return:
            - List[str]
                商品代碼清單，依代碼排序；表不存在或尚無快照時為空清單
        """

        conn: sqlite3.Connection = sqlite3.connect(TW_FUTURES_DB_PATH)
        try:
            if not cls.table_exists(conn, FUTURES_STOCK_UNIVERSE_TABLE_NAME):
                logger.warning(
                    f"[Futures Universe] {FUTURES_STOCK_UNIVERSE_TABLE_NAME} 不存在；"
                    f"請先執行 --target futures_stock_universe"
                )
                return []

            if snapshot_date is None:
                row = conn.execute(
                    f"SELECT MAX(snapshot_date) FROM {FUTURES_STOCK_UNIVERSE_TABLE_NAME}"
                ).fetchone()
                snapshot_date = row[0] if row and row[0] else None

            if snapshot_date is None:
                logger.warning("[Futures Universe] 標的池尚無任何快照")
                return []

            query: str = f"""
                SELECT product_id FROM {FUTURES_STOCK_UNIVERSE_TABLE_NAME}
                WHERE snapshot_date = ?
            """
            params: tuple = (snapshot_date,)

            if product_types:
                placeholders: str = ",".join("?" * len(product_types))
                query += f" AND product_type IN ({placeholders})"
                params += tuple(product_types)

            query += " ORDER BY product_id"

            return [row[0] for row in conn.execute(query, params)]
        finally:
            conn.close()

    @staticmethod
    def table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        """檢查資料表是否存在（本類的查詢都可能在建表前被呼叫）"""

        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table_name,),
        ).fetchone()
        return row is not None

    @staticmethod
    def log_summary(df: pd.DataFrame) -> None:
        """彙報本次快照的組成"""

        logger.info(f"* 標的池快照共 {len(df)} 檔")

        for product_type in StockFuturesType:
            count: int = int((df["product_type"] == product_type.value).sum())
            logger.info(f"  - {product_type.value}: {count} 檔")

        night_count: int = int(df["night_session_time"].notna().sum())
        logger.info(f"  - 有盤後交易時段（夜盤）: {night_count} 檔")

    def log_snapshot_diff(self, df: pd.DataFrame, previous_date: Optional[str]) -> None:
        """
        - Description:
            與前一份快照比對，列出新增、消失與契約單位異動的商品

            這三者就是本表要回答的問題（掛牌／下市／乘數調整），但**都是觀測值**：
            第一份快照沒有可比的對象，之後每一次差異也只代表「兩次觀測之間發生了
            變化」，不是官方生效日。要精確的日期須另抓 TAIFEX 商品異動公告。
        - Parameters:
            - df: pd.DataFrame
                本次快照
            - previous_date: Optional[str]
                前一份快照的日期；None 表示這是第一份
        """

        if previous_date is None:
            logger.info("* 這是第一份標的池快照，尚無可比對的前一份")
            return

        conn: sqlite3.Connection = sqlite3.connect(TW_FUTURES_DB_PATH)
        try:
            previous_df: pd.DataFrame = pd.read_sql_query(
                f"""
                SELECT product_id, underlying_name, contract_size
                FROM {FUTURES_STOCK_UNIVERSE_TABLE_NAME}
                WHERE snapshot_date = ?
                """,
                conn,
                params=(previous_date,),
            )
        finally:
            conn.close()

        current: Set[str] = set(df["product_id"])
        previous: Set[str] = set(previous_df["product_id"])

        added: List[str] = sorted(current - previous)
        removed: List[str] = sorted(previous - current)

        logger.info(
            f"* 與 {previous_date} 的快照比對：新增 {len(added)}、消失 {len(removed)}"
        )
        if added:
            logger.info(f"  - 新增（疑似掛牌）: {added}")
        if removed:
            logger.info(f"  - 消失（疑似下市）: {removed}")

        merged: pd.DataFrame = df.merge(
            previous_df, on="product_id", suffixes=("", "_prev")
        )
        changed: pd.DataFrame = merged[
            merged["contract_size"] != merged["contract_size_prev"]
        ]
        if not changed.empty:
            # 契約單位變動多半來自標的除權息後的契約調整，**是 PnL 會算錯的直接原因**，
            # 故不與上面的新增／消失混在同一行，單獨以 warning 列出
            logger.warning(
                f"[Futures Universe] {len(changed)} 檔的契約單位有異動，"
                f"請確認是否為除權息契約調整："
                + ", ".join(
                    f"{row.product_id} {row.underlying_name} "
                    f"{row.contract_size_prev} → {row.contract_size}"
                    for row in changed.itertuples()
                )
            )

    @staticmethod
    def log_underlying_match(df: pd.DataFrame) -> None:
        """
        - Description:
            檢查標的證券代號能否對回 tw_stock.db 的現股行情

            **這是本表最重要的驗收點**：股期回測要對照現股的除權息與籌碼，
            對不上的標的即使行情爬得回來也接不進下游。對不上通常有兩種成因：
            標的是 ETF（現股行情本來就不在 `price` 表的涵蓋範圍內），或是
            上櫃標的尚未回補；兩者都不是錯誤，故記 info 不記 warning。
        - Parameters:
            - df: pd.DataFrame
                本次快照
        """

        stock_ids: List[str] = sorted(set(df["underlying_stock_id"]))
        if not stock_ids:
            return

        conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)
        try:
            placeholders: str = ",".join("?" * len(stock_ids))
            matched: Set[str] = {
                row[0]
                for row in conn.execute(
                    f"""
                    SELECT DISTINCT stock_id FROM {PRICE_TABLE_NAME}
                    WHERE stock_id IN ({placeholders})
                    """,
                    tuple(stock_ids),
                )
            }
        except sqlite3.Error as error:
            logger.warning(f"[Futures Universe] 無法比對現股代號：{error}")
            return
        finally:
            conn.close()

        unmatched: List[str] = [sid for sid in stock_ids if sid not in matched]
        logger.info(
            f"* 標的代號比對現股 {PRICE_TABLE_NAME} 表："
            f"{len(matched)}/{len(stock_ids)} 檔對得上"
        )
        if unmatched:
            logger.info(f"  - 對不上的標的（多為 ETF 或尚未回補的上櫃股）: {unmatched}")
