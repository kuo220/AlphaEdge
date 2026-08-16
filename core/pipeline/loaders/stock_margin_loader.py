import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import DB_PATH, MARGIN_DOWNLOADS_PATH, MARGIN_TABLE_NAME
from core.pipeline.loaders.base import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils


class StockMarginLoader(BaseDataLoader):
    """Stock Margin Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.margin_dir: Path = MARGIN_DOWNLOADS_PATH

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
            self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(self) -> None:
        """創建信用交易（融資融券餘額）db"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # 數量單位一律為張；券資比為 %（融券今日餘額 / 融資今日餘額）
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {MARGIN_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "證券名稱" TEXT NOT NULL,
            "融資買進" INT NOT NULL,
            "融資賣出" INT NOT NULL,
            "融資現金償還" INT NOT NULL,
            "融資前日餘額" INT NOT NULL,
            "融資今日餘額" INT NOT NULL,
            "融資限額" INT NOT NULL,
            "融券買進" INT NOT NULL,
            "融券賣出" INT NOT NULL,
            "融券現券償還" INT NOT NULL,
            "融券前日餘額" INT NOT NULL,
            "融券今日餘額" INT NOT NULL,
            "融券限額" INT NOT NULL,
            "資券互抵" INT NOT NULL,
            "券資比" REAL NOT NULL,
            "註記" TEXT,
            PRIMARY KEY ("date", "stock_id")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{MARGIN_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {MARGIN_TABLE_NAME} create successfully!")
        else:
            logger.warning(f"Table {MARGIN_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保信用交易資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=MARGIN_TABLE_NAME
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
        partial_files: List[str] = []
        skipped_cnt: int = 0
        for file_path in self.margin_dir.iterdir():
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path, dtype={"stock_id": str})
                # 空字串的註記在 read_csv 後會變成 NaN，統一還原為空字串
                df["註記"] = df["註記"].fillna("")
                inserted, skipped = self.insert_dataframe(
                    self.conn, MARGIN_TABLE_NAME, df
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
            source="margin",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=MARGIN_DOWNLOADS_PATH,
            skipped_files=skipped_cnt,
            partial_files=partial_files,
        )
