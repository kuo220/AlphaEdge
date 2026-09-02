import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import DIVIDEND_DOWNLOADS_PATH, DIVIDEND_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
Stock Dividend Loader

與其他 loader 的差異：本表的三個來源會**合法地重疊**——上櫃同一筆除權息可能同時來自
FinMind 歷史回補與 TPEX 日更。因此入庫走 `INSERT OR REPLACE` 而非 `append`，
且在寫入前先跨檔去重，避免同批資料撞主鍵讓整個檔案被 except 吞掉。
"""


class StockDividendLoader(BaseDataLoader):
    """Stock Dividend Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.dividend_dir: Path = DIVIDEND_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.dividend_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(self) -> None:
        """創建除權除息計算結果表 db"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # 價格單位為元；還原係數 = 除權息參考價 / 除權息前收盤價（恆 < 1）
        # 現金股利單位為元／股；配股率為每股配股數（純除息時為 0）
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {DIVIDEND_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "證券名稱" TEXT,
            "除權息前收盤價" REAL NOT NULL,
            "除權息參考價" REAL NOT NULL,
            "權息值合計" REAL,
            "權息別" TEXT,
            "現金股利" REAL,
            "配股率" REAL,
            "漲停價" REAL,
            "跌停價" REAL,
            "開盤競價基準" REAL,
            "減除股利參考價" REAL,
            "還原係數" REAL NOT NULL,
            "資料來源" TEXT NOT NULL,
            PRIMARY KEY ("date", "stock_id")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{DIVIDEND_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {DIVIDEND_TABLE_NAME} create successfully!")
        else:
            logger.warning(f"Table {DIVIDEND_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保除權除息資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=DIVIDEND_TABLE_NAME
        ):
            self.create_db()

    def add_to_db(self, remove_files: bool = False) -> None:
        """將資料夾中的所有 CSV 檔存入指定 SQLite 資料庫中的指定資料表"""

        if self.conn is None:
            self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        file_cnt: int = 0

        failed_files: List[str] = []
        dfs: List[pd.DataFrame] = []
        for file_path in sorted(self.dividend_dir.iterdir()):
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path, dtype={"stock_id": str})
                dfs.append(df)
                file_cnt += 1
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")
                failed_files.append(str(file_path))

        if not dfs:
            logger.warning("No dividend CSV file to load")
            self.disconnect()
            return

        # 跨檔去重：同一筆除權息可能同時來自 FinMind 回補與 TPEX 日更
        merged_df: pd.DataFrame = pd.concat(dfs, ignore_index=True)
        row_cnt: int = len(merged_df)
        merged_df = merged_df.drop_duplicates(subset=["date", "stock_id"], keep="last")
        logger.info(f"Dividend rows: {row_cnt} -> {len(merged_df)} after dedup")

        self.upsert(merged_df)

        self.conn.commit()
        self.disconnect()

        self.finish_load(
            source="dividend",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=DIVIDEND_DOWNLOADS_PATH,
        )

    def upsert(self, df: pd.DataFrame) -> None:
        """
        - Description:
            以 `INSERT OR REPLACE` 寫入，讓重跑與跨來源覆蓋成為冪等操作

        - Parameters:
            - df: pd.DataFrame
                已去重的除權除息資料
        """

        cursor: sqlite3.Cursor = self.conn.cursor()
        columns: List[str] = list(df.columns)
        col_clause: str = ", ".join(f'"{col}"' for col in columns)
        placeholders: str = ", ".join("?" for _ in columns)

        insert_query: str = f"""
        INSERT OR REPLACE INTO {DIVIDEND_TABLE_NAME} ({col_clause})
        VALUES ({placeholders})
        """
        cursor.executemany(insert_query, df.itertuples(index=False, name=None))
        logger.info(f"Upserted {len(df)} rows into {DIVIDEND_TABLE_NAME}")
