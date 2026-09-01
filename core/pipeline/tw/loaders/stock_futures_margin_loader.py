import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_MARGIN_DOWNLOADS_PATH,
    STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME,
    TW_FUTURES_DB_PATH,
)
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
Stock Futures Margin Rate Loader

**只存「適用比例」型的股票期貨**（標的為股票者）。標的為受益憑證（ETF）的股期
給的是**每口固定金額**，語意與臺股期貨相同，寫進 `futures_margin_history`
（由 `FuturesMarginLoader` 負責）——**分表的依據是「金額 vs 比例」，
不是「指數 vs 股票」**。

與 `futures_margin_history` 相同，本表是**變動序列**：主鍵
`(effective_date, product_id)` 的 `effective_date` 取自來源該段落的「更新日期」，
比例沒變就沒有新列。查「某日生效的比例」一律取 `effective_date <= 該日` 的最大者。

**每口保證金要自己算**：`標的股價 × 契約單位 × 比例`，其中契約單位取自
`futures_stock_universe.contract_size`（2000 股／100 股）、股價取自 `tw_stock.db`
的 `price` 表。這是本表與金額表最大的使用差異。
"""


class StockFuturesMarginLoader(BaseDataLoader):
    """Stock Futures Margin Rate Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection（指向 tw_futures.db）
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.margin_dir: Path = FUTURES_MARGIN_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()
        self.create_missing_tables()
        self.margin_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            TW_FUTURES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(TW_FUTURES_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn = None

    def create_db(self) -> None:
        """Create New Database Table"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # 主鍵為 (effective_date, product_id)：本表是變動序列，見本檔開頭說明。
        #
        # **比例欄存的是小數**（`0.1350` 而非 `13.50`）：下游直接乘不必再除以 100，
        # 而「忘記除 100」會讓保證金差 100 倍卻不會報錯。
        #
        # `保證金所屬級距` **可以是 NULL**：處置／注意股票沒有級距但仍有（更高的）
        # 比例，2026-09-01 實查 296 檔中有 15 檔如此。不可因為級距為空就丟掉該檔。
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME}(
            "effective_date" TEXT NOT NULL,
            "product_id" TEXT NOT NULL,
            "underlying_stock_id" TEXT NOT NULL,
            "product_name" TEXT,
            "保證金所屬級距" TEXT,
            "結算保證金適用比例" REAL,
            "維持保證金適用比例" REAL,
            "原始保證金適用比例" REAL NOT NULL,
            "source" TEXT NOT NULL,
            PRIMARY KEY ("effective_date", "product_id")
        );
        """
        cursor.execute(create_table_query)

        # 下游查的是「某商品在某日生效的比例」，主鍵前綴是 effective_date 幫不上忙
        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_stock_futures_margin_product
            ON {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME}
            ("product_id", "effective_date");
            """
        )

        cursor.execute(
            f"PRAGMA table_info('{STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME}')"
        )
        if cursor.fetchall():
            logger.info(
                f"Table {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME} "
                f"create successfully!"
            )
        else:
            logger.warning(
                f"Table {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME} "
                f"create unsuccessfully!"
            )

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保股期保證金比例表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME
        ):
            self.create_db()

    def add_to_db(self, df: pd.DataFrame) -> int:
        """
        - Description:
            將清洗後的比例寫入資料庫

            走 `INSERT OR IGNORE`：比例沒變時整批被忽略，
            這正是「變動序列」的實現方式。
        - Parameters:
            - df: pd.DataFrame
                cleaner 產出的比例 DataFrame
        - Return:
            - int
                實際新增的列數
        """

        if df is None or df.empty:
            logger.warning("[Stock Futures Margin] 無資料可入庫")
            return 0

        if self.conn is None:
            self.connect()
        self.create_missing_tables()

        columns: List[str] = list(df.columns)
        placeholders: str = ", ".join(["?"] * len(columns))
        quoted: str = ", ".join(f'"{c}"' for c in columns)

        before: int = self.count_rows()
        self.conn.executemany(
            f"INSERT OR IGNORE INTO {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME} "
            f"({quoted}) VALUES ({placeholders})",
            [
                tuple(str(v) if i == 0 else v for i, v in enumerate(row))
                for row in df.values
            ],
        )
        self.conn.commit()
        inserted: int = self.count_rows() - before

        if inserted:
            logger.info(
                f"* 新增 {inserted} 列股期保證金比例（共 {len(df)} 列，其餘已存在）"
            )
        else:
            logger.info(f"* 股期保證金比例無變動，{len(df)} 列皆已存在")

        return inserted

    def count_rows(self) -> int:
        """目前表內的列數"""

        return self.conn.execute(
            f"SELECT COUNT(*) FROM {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME}"
        ).fetchone()[0]
