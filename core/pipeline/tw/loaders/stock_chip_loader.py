import sqlite3
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import CHIP_DOWNLOADS_PATH, CHIP_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils


class StockChipLoader(BaseDataLoader):
    """Stock Chip Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

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
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

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
            "自營商買進股數(自行買賣)" INT,
            "自營商賣出股數(自行買賣)" INT,
            "自營商買賣超股數(自行買賣)" INT,
            "自營商買進股數(避險)" INT,
            "自營商賣出股數(避險)" INT,
            "自營商買賣超股數(避險)" INT,
            "自營商買進股數" INT,
            "自營商賣出股數" INT,
            "自營商買賣超股數" INT NOT NULL,
            "三大法人買賣超股數" INT NOT NULL,
            PRIMARY KEY ("date", "stock_id", "證券名稱")
        );
        """
        # PRIMARY KEY (date, stock_id)
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{CHIP_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {CHIP_TABLE_NAME} create successfully!")
        else:
            logger.warning(f"Table {CHIP_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保三大法人盤後籌碼資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=CHIP_TABLE_NAME
        ):
            self.create_db()

    def add_to_db(
        self,
        remove_files: bool = False,
        only_dates: Optional[Set[str]] = None,
    ) -> None:
        """將資料夾中的所有 CSV 檔存入指定 SQLite 資料庫中的指定資料表"""

        if self.conn is None:
            self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        file_cnt: int = 0

        failed_files: List[str] = []
        partial_files: List[str] = []
        skipped_cnt: int = 0
        for file_path in self.select_csv_files(self.chip_dir, only_dates):
            try:
                df: pd.DataFrame = pd.read_csv(file_path)
                inserted, skipped = self.insert_dataframe(
                    self.conn, CHIP_TABLE_NAME, df
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
            source="chip",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=CHIP_DOWNLOADS_PATH,
            skipped_files=skipped_cnt,
            partial_files=partial_files,
        )
