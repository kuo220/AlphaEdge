import sqlite3
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_DB_PATH,
    FUTURES_PRICE_DAILY_TABLE_NAME,
    FUTURES_PRICE_DOWNLOADS_PATH,
)
from core.pipeline.loaders.base import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
Futures Price Loader

**與其他 loader 唯一的結構性差異：寫入 `futures.db` 而非 `stock.db`**。
期貨的主鍵是合約（product ＋ expiry ＋ session），與 `stock_id` 語意不同，
混在同一個 DB 會讓「這張表的主鍵是什麼」失去單一答案。
"""


class FuturesPriceLoader(BaseDataLoader):
    """Futures Price Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection（指向 futures.db）
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.futures_price_dir: Path = FUTURES_PRICE_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.futures_price_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            # 期貨與股票分庫，故不是 DB_PATH
            FUTURES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn: sqlite3.Connection = sqlite3.connect(FUTURES_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(self) -> None:
        """創建台期貨每日行情 db"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # 價格單位為指數點；成交量與未沖銷契約量單位為口。
        #
        # **價格欄位一律允許 NULL**，這與 stock 各表刻意不同：
        # - 夜盤沒有結算價與未沖銷契約量（那是日結數字，日盤時段才產出）
        # - 某個契約整個時段沒有成交時，OHLC 本來就不存在
        # 這些欄位若宣告 NOT NULL，cleaner 就得填 0 才寫得進來，
        # 而結算價 0 會讓損益與維持率整段歸零且無任何徵兆。
        #
        # 主鍵含 session：同一天同一契約的日盤與夜盤是兩筆獨立行情。
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {FUTURES_PRICE_DAILY_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "product" TEXT NOT NULL,
            "expiry" TEXT NOT NULL,
            "session" TEXT NOT NULL,
            "開盤價" REAL,
            "最高價" REAL,
            "最低價" REAL,
            "收盤價" REAL,
            "成交量" INT NOT NULL,
            "結算價" REAL,
            "未沖銷契約量" INT,
            "最後最佳買價" REAL,
            "最後最佳賣價" REAL,
            PRIMARY KEY ("date", "product", "expiry", "session")
        );
        """
        cursor.execute(create_table_query)

        cursor.execute(f"PRAGMA table_info('{FUTURES_PRICE_DAILY_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {FUTURES_PRICE_DAILY_TABLE_NAME} create successfully!")
        else:
            logger.warning(
                f"Table {FUTURES_PRICE_DAILY_TABLE_NAME} create unsuccessfully!"
            )

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保台期貨每日行情資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=FUTURES_PRICE_DAILY_TABLE_NAME
        ):
            self.create_db()

    def add_to_db(
        self,
        remove_files: bool = False,
        only_dates: Optional[Set[str]] = None,
    ) -> None:
        """將資料夾中的所有 CSV 檔存入 futures.db 的每日行情表"""

        if self.conn is None:
            self.connect()

        self.create_missing_tables()

        file_cnt: int = 0
        failed_files: List[str] = []
        partial_files: List[str] = []
        skipped_cnt: int = 0

        for file_path in self.select_csv_files(self.futures_price_dir, only_dates):
            try:
                # product／expiry／session 一律當字串：expiry 可能是 202609 或
                # 202609W1，讓 pandas 自行推斷會把前者變成 202609.0 而主鍵走樣
                df: pd.DataFrame = pd.read_csv(
                    file_path,
                    dtype={"product": str, "expiry": str, "session": str},
                )
                inserted, skipped = self.insert_dataframe(
                    self.conn, FUTURES_PRICE_DAILY_TABLE_NAME, df
                )
                if inserted == 0 and skipped > 0:
                    # 整檔已在資料庫中：loader 每次都掃全目錄，重跑必然走到這裡
                    skipped_cnt += 1
                    continue
                if skipped > 0:
                    partial_files.append(str(file_path))
                logger.info(f"Save {file_path} into database")
                file_cnt += 1
            except Exception as e:
                logger.warning(f"Error saving {file_path}: {e}")
                failed_files.append(str(file_path))

        self.conn.commit()
        self.disconnect()

        self.finish_load(
            source="futures_price",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=FUTURES_PRICE_DOWNLOADS_PATH,
            skipped_files=skipped_cnt,
            partial_files=partial_files,
        )
