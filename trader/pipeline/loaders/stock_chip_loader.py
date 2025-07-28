import shutil
import sqlite3
from loguru import logger
import pandas as pd
from pathlib import Path

from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.config import CHIP_TABLE_NAME, CHIP_DOWNLOADS_PATH, DB_PATH


class StockChipLoader(BaseDataLoader):
    """Stock Chip Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # Downloads directory Path
        self.chip_dir: Path = CHIP_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.chip_dir.mkdir(parents=True, exist_ok=True)

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
        """創建三大法人盤後籌碼db"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {CHIP_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "證券名稱" TEXT NOT NULL,
            "外資買進股數" INT NOT NULL,
            "外資賣出股數" INT NOT NULL,
            "外資買賣超股數" INT NOT NULL,
            "投信買進股數" INT NOT NULL,
            "投信賣出股數" INT NOT NULL,
            "投信買賣超股數" INT NOT NULL,
            "自營商買進股數_自行買賣" INT,
            "自營商賣出股數_自行買賣" INT,
            "自營商買賣超股數_自行買賣" INT,
            "自營商買進股數_避險" INT,
            "自營商賣出股數_避險" INT,
            "自營商買賣超股數_避險" INT,
            "自營商買賣超股數" INT NOT NULL,
            "三大法人買賣超股數" INT NOT NULL,
            PRIMARY KEY (date, stock_id)
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{CHIP_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {CHIP_TABLE_NAME} create successfully!")
        else:
            logger.info(f"Table {CHIP_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def add_to_db(self, remove_files: bool = False) -> None:
        """將資料夾中的所有 CSV 檔存入指定 SQLite 資料庫中的指定資料表。"""

        if self.conn is None:
            self.connect()

        file_cnt: int = 0
        for file_path in self.chip_dir.iterdir():
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path)
                df.to_sql(CHIP_TABLE_NAME, self.conn, if_exists="append", index=False)
                logger.info(f"Save {file_path} into database.")
                file_cnt += 1
            except Exception as e:
                logger.info(f"Error saving {file_path}: {e}")

        self.conn.commit()
        self.disconnect()

        if remove_files:
            shutil.rmtree(CHIP_DOWNLOADS_PATH)
        logger.info(f"Total file processed: {file_cnt}")

    def create_missing_tables(self) -> None:
        """確保三大法人盤後籌碼資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=CHIP_TABLE_NAME
        ):
            self.create_db()
