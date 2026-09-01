import sqlite3
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_MARGIN_DOWNLOADS_PATH,
    FUTURES_MARGIN_HISTORY_TABLE_NAME,
    TW_FUTURES_DB_PATH,
)
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
Futures Margin Loader（指數類）

**這張表是「變動序列」，不是每日快照**——只有保證金真的變動時才會新增列。
主鍵 `(effective_date, product)` 中的 `effective_date` 取自來源的「更新日期」，
即該組保證金開始適用的日子；同一組保證金連抓 30 天只會產生 1 列，
其餘 29 次被 `INSERT OR IGNORE` 擋掉。

因此「某日生效的保證金」的查法是**取 `effective_date <= 該日` 的最大者**，
不是 `effective_date = 該日`——後者只有在剛好調整的那天才查得到（見 S5 的 API）。

**只存每口固定金額的商品**。股票期貨給的是「適用比例 ＋ 級距」，語意不同，
存在另一張 `stock_futures_margin_rate_history`（S3），理由見
`backlog/台期貨保證金ETL.md` §一。
"""


class FuturesMarginLoader(BaseDataLoader):
    """Futures Margin Loader"""

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

        # Ensure Database Table Exists
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

        # 主鍵為 (effective_date, product)：本表是變動序列，見本檔開頭說明。
        #
        # 金額欄為 INT：TAIFEX 的保證金一律是整數元，沒有小數。
        #
        # `source` 區分資料來源：`snapshot` 來自現行一覽表、`announcement` 來自
        # 調整公告（S4）。兩者可能給出同一個 (effective_date, product)，
        # 屆時先寫入者留存——值相同，故不需要 upsert。
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {FUTURES_MARGIN_HISTORY_TABLE_NAME}(
            "effective_date" TEXT NOT NULL,
            "product" TEXT NOT NULL,
            "product_name" TEXT,
            "結算保證金" INT,
            "維持保證金" INT,
            "原始保證金" INT NOT NULL,
            "source" TEXT NOT NULL,
            PRIMARY KEY ("effective_date", "product")
        );
        """
        cursor.execute(create_table_query)

        # 下游最常見的查詢是「某商品在某日生效的保證金」，走
        # `WHERE product = ? AND effective_date <= ? ORDER BY effective_date DESC`，
        # 主鍵的前綴是 effective_date，幫不上這種查詢，故另建索引
        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_futures_margin_product
            ON {FUTURES_MARGIN_HISTORY_TABLE_NAME} ("product", "effective_date");
            """
        )

        cursor.execute(f"PRAGMA table_info('{FUTURES_MARGIN_HISTORY_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(
                f"Table {FUTURES_MARGIN_HISTORY_TABLE_NAME} create successfully!"
            )
        else:
            logger.warning(
                f"Table {FUTURES_MARGIN_HISTORY_TABLE_NAME} create unsuccessfully!"
            )

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保保證金歷史序列資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=FUTURES_MARGIN_HISTORY_TABLE_NAME
        ):
            self.create_db()

    def add_to_db(self, df: pd.DataFrame) -> int:
        """
        - Description:
            將清洗後的保證金寫入資料庫

            走 `INSERT OR IGNORE`：同一組保證金重複抓到時整批被忽略，
            這正是「變動序列」的實現方式，不需要另外判斷有沒有變。
        - Parameters:
            - df: pd.DataFrame
                cleaner 產出的 DataFrame
        - Return:
            - int
                實際新增的列數
        """

        if df is None or df.empty:
            logger.warning("[Futures Margin] 無資料可入庫")
            return 0

        if self.conn is None:
            self.connect()
        self.create_missing_tables()

        columns: List[str] = list(df.columns)
        placeholders: str = ", ".join(["?"] * len(columns))
        quoted: str = ", ".join(f'"{c}"' for c in columns)

        cursor: sqlite3.Cursor = self.conn.cursor()
        before: int = self.count_rows()
        cursor.executemany(
            f"INSERT OR IGNORE INTO {FUTURES_MARGIN_HISTORY_TABLE_NAME} "
            f"({quoted}) VALUES ({placeholders})",
            [
                tuple(str(v) if i == 0 else v for i, v in enumerate(row))
                for row in df.values
            ],
        )
        self.conn.commit()
        inserted: int = self.count_rows() - before

        if inserted:
            logger.info(f"* 新增 {inserted} 列保證金（共 {len(df)} 列，其餘已存在）")
        else:
            logger.info(f"* 保證金無變動，{len(df)} 列皆已存在")

        return inserted

    def count_rows(self) -> int:
        """目前表內的列數"""

        return self.conn.execute(
            f"SELECT COUNT(*) FROM {FUTURES_MARGIN_HISTORY_TABLE_NAME}"
        ).fetchone()[0]

    def get_effective_dates(self) -> Set[str]:
        """表內已有的所有生效日；updater 用來判斷是否需要入庫"""

        if self.conn is None:
            self.connect()
        self.create_missing_tables()

        return {
            row[0]
            for row in self.conn.execute(
                f"SELECT DISTINCT effective_date FROM {FUTURES_MARGIN_HISTORY_TABLE_NAME}"
            )
        }
