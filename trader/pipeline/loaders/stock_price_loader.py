import shutil
import sqlite3
from pathlib import Path

import pandas as pd
from loguru import logger

from trader.config import DB_PATH, PRICE_DOWNLOADS_PATH, PRICE_TABLE_NAME
from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.utils.sqlite_utils import SQLiteUtils


class StockPriceLoader(BaseDataLoader):
    """Stock Price Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # Downloads directory Path
        self.price_dir: Path = PRICE_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

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
            PRIMARY KEY ("date", "stock_id", "證券名稱")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{PRICE_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {PRICE_TABLE_NAME} create successfully!")
        else:
            logger.warning(f"Table {PRICE_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def add_to_db(self, remove_files: bool = False) -> None:
        """Add Data into Database"""

        if self.conn is None:
            self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        # 取得所有 CSV 檔案並排序，確保處理順序一致
        csv_files = sorted([f for f in self.price_dir.iterdir() if f.suffix == ".csv"])
        total_files = len(csv_files)

        if total_files == 0:
            logger.info("No CSV files found in price directory")
            return

        logger.info(f"Found {total_files} CSV files to process")

        # 查詢資料庫中已存在的資料（根據主鍵）
        # 使用更有效率的查詢方式，只查詢需要的欄位
        logger.info("Loading existing data from database...")
        existing_query = f"""
        SELECT date, stock_id, "證券名稱"
        FROM {PRICE_TABLE_NAME}
        """
        existing_df = pd.read_sql_query(existing_query, self.conn)

        # 如果有已存在的資料，建立一個 set 來快速查找
        existing_keys = set()
        if not existing_df.empty:
            existing_keys = set(
                zip(
                    existing_df["date"].astype(str),
                    existing_df["stock_id"].astype(str),
                    existing_df["證券名稱"].astype(str),
                )
            )
            logger.info(f"Loaded {len(existing_keys)} existing records from database")
        else:
            logger.info("Database is empty, will insert all data")

        file_cnt: int = 0
        skipped_cnt: int = 0
        error_cnt: int = 0

        for idx, file_path in enumerate(csv_files, start=1):
            try:
                # 顯示進度
                logger.info(f"Processing [{idx}/{total_files}] {file_path.name}...")

                df: pd.DataFrame = pd.read_csv(file_path)

                if df.empty:
                    logger.warning(f"Skipped {file_path.name} (file is empty)")
                    skipped_cnt += 1
                    continue

                # 記錄原始資料筆數
                original_count = len(df)

                # 建立當前資料的 key tuple（用於過濾和去重）
                df["_key"] = list(
                    zip(
                        df["date"].astype(str),
                        df["stock_id"].astype(str),
                        df["證券名稱"].astype(str),
                    )
                )

                # 先處理同一個檔案內的重複資料（保留第一筆）
                if df["_key"].duplicated().any():
                    df = df.drop_duplicates(subset=["_key"], keep="first")
                    logger.debug(
                        f"Removed {original_count - len(df)} duplicate rows within {file_path.name}"
                    )

                # 過濾掉資料庫中已存在的資料
                if not existing_keys:
                    # 如果資料庫是空的，直接插入所有資料
                    new_df = df.drop(columns=["_key"])
                    new_keys = set(df["_key"])
                else:
                    # 過濾出新資料（不在 existing_keys 中的）
                    mask = ~df["_key"].isin(existing_keys)
                    new_df = df[mask].drop(columns=["_key"])

                    if new_df.empty:
                        logger.info(
                            f"Skipped {file_path.name} (all data already exists)"
                        )
                        skipped_cnt += 1
                        continue

                    # 取得要插入的新資料的 key（用於後續更新 existing_keys）
                    new_keys = set(df.loc[mask, "_key"])

                # 插入新資料（只有在插入成功後才更新 existing_keys）
                new_df.to_sql(
                    PRICE_TABLE_NAME, self.conn, if_exists="append", index=False
                )

                # 插入成功後，更新 existing_keys 避免後續檔案的重複資料
                existing_keys.update(new_keys)
                skipped_rows = original_count - len(new_df)
                if skipped_rows > 0:
                    logger.info(
                        f"Saved {file_path.name} into database ({len(new_df)} new rows, {skipped_rows} skipped)"
                    )
                else:
                    logger.info(
                        f"Saved {file_path.name} into database ({len(new_df)} rows)"
                    )
                file_cnt += 1
            except Exception as e:
                logger.error(f"Error saving {file_path.name}: {e}", exc_info=True)
                error_cnt += 1

        self.conn.commit()
        self.disconnect()

        if remove_files:
            shutil.rmtree(self.price_dir)
        logger.info(
            f"Total files processed: {file_cnt} new, {skipped_cnt} skipped, {error_cnt} errors"
        )

    def create_missing_tables(self) -> None:
        """確保股票價格資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=PRICE_TABLE_NAME
        ):
            self.create_db()
