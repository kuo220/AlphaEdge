import shutil
import sqlite3
from loguru import logger
import pandas as pd
from pathlib import Path

from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.config import PRICE_DOWNLOADS_PATH, PRICE_TABLE_NAME, DB_PATH


class StockPriceLoader(BaseDataLoader):
    """Stock Price Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # Downloads directory Path
        self.price_dir: Path = PRICE_DOWNLOADS_PATH

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=PRICE_TABLE_NAME
        ):
            self.create_db()

        self.price_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn = None

    def create_db(self) -> None:
        """Create New Database"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {PRICE_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "證券名稱" TEXT NOT NULL,
            "開盤價" REAL,
            "最高價" REAL,
            "最低價" REAL,
            "收盤價" REAL,
            "漲跌價差" REAL,
            "成交股數" INTEGER,
            "成交金額" INTEGER,
            "成交筆數" INTEGER,
            "最後揭示買價" REAL,
            "最後揭示買量" INTEGER,
            "最後揭示賣價" REAL,
            "最後揭示賣量" INTEGER,
            "本益比" REAL,
            PRIMARY KEY (date, stock_id)
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{PRICE_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {PRICE_TABLE_NAME} create successfully!")
        else:
            logger.info(f"Table {PRICE_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()
        self.disconnect()

    def add_to_db(self, remove_files: bool = False) -> None:
        """Add Data into Database"""

        if self.conn is None:
            self.connect()

        file_cnt: int = 0
        for file_path in self.price_dir.iterdir():
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path)
                df.to_sql(PRICE_TABLE_NAME, self.conn, if_exists="append", index=False)
                logger.info(f"Saved {file_path} into database.")
                file_cnt += 1
            except Exception as e:
                logger.info(f"Error saving {file_path}: {e}")

        self.conn.commit()
        self.disconnect()

        if remove_files:
            shutil.rmtree(self.price_dir)
        logger.info(f"Total files processed: {file_cnt}")
