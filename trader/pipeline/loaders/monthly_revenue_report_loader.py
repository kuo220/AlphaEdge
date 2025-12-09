import shutil
import sqlite3
from pathlib import Path
from typing import List

import pandas as pd
from loguru import logger

from trader.config import (
    DB_PATH,
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
    MONTHLY_REVENUE_TABLE_NAME,
)
from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.utils import DataType
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils.sqlite_utils import SQLiteUtils


class MonthlyRevenueReportLoader(BaseDataLoader):
    """TWSE & TPEX Monthly Revenue Report Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # Specify column data types
        self.text_not_null_cols: List[str] = ["stock_id", "公司名稱"]
        self.int_not_null_cols: List[str] = ["year", "month"]

        # Downloads directory Path
        self.mrr_dir: Path = MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH

        # MMR Cleaned Columns Path
        self.monthly_revenue_report_cleaned_cols_path: Path = (
            MONTHLY_REVENUE_REPORT_META_DIR_PATH
            / f"{DataType.MRR.lower()}_cleaned_columns.json"
        )

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        # Connect Database
        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        # Create the downloads directory
        self.mrr_dir.mkdir(parents=True, exist_ok=True)

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

        # Step 1: 讀取欄位定義 JSON
        cols: List[str] = DataUtils.load_json(
            file_path=self.monthly_revenue_report_cleaned_cols_path
        )
        col_defs: List[str] = []

        # Step 2: 指定欄位型別
        for col in cols:
            col_name = f'"{col}"'

            if col in self.text_not_null_cols:
                col_defs.append(f"{col_name} TEXT NOT NULL")
            elif col in self.int_not_null_cols:
                col_defs.append(f"{col_name} INT NOT NULL")
            else:
                col_defs.append(f"{col_name} REAL")

        # Step 3: 加 PRIMARY KEY
        col_defs.append('PRIMARY KEY ("year", "month", "stock_id", "公司名稱")')

        # Step 4: 組建 SQL
        col_defs_sql: str = ",\n            ".join(col_defs)
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {MONTHLY_REVENUE_TABLE_NAME}(
            {col_defs_sql}
        )
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{MONTHLY_REVENUE_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {MONTHLY_REVENUE_TABLE_NAME} create successfully!")
            logger.info(create_table_query)
        else:
            logger.warning(f"Table {MONTHLY_REVENUE_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def add_to_db(self, remove_files: bool = False) -> None:
        """Add Data into Database"""

        if self.conn is None:
            self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        file_cnt: int = 0
        for file_path in self.mrr_dir.iterdir():
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path)

                # 檢查並過濾掉已存在的記錄
                if not df.empty:
                    # 確保 stock_id 是字串型別，避免與資料庫中的 TEXT 型別不一致
                    if "stock_id" in df.columns:
                        df["stock_id"] = df["stock_id"].astype(str)

                    # 查詢資料庫中已存在的記錄
                    existing_query: str = f"""
                    SELECT year, month, stock_id, "公司名稱"
                    FROM {MONTHLY_REVENUE_TABLE_NAME}
                    """
                    existing_df: pd.DataFrame = pd.read_sql_query(
                        existing_query, self.conn
                    )

                    # 確保 existing_df 的 stock_id 也是字串型別
                    if not existing_df.empty and "stock_id" in existing_df.columns:
                        existing_df["stock_id"] = existing_df["stock_id"].astype(str)

                    if not existing_df.empty:
                        # 合併 DataFrame 來找出重複的記錄
                        df_merged: pd.DataFrame = df.merge(
                            existing_df,
                            on=["year", "month", "stock_id", "公司名稱"],
                            how="left",
                            indicator=True,
                        )
                        # 只保留不存在於資料庫中的記錄
                        df_new: pd.DataFrame = df_merged[
                            df_merged["_merge"] == "left_only"
                        ].drop(columns=["_merge"])
                        # 還原原始欄位（移除合併時可能產生的重複欄位）
                        df_new = df_new[df.columns]
                    else:
                        df_new: pd.DataFrame = df

                    # 只插入新記錄
                    if not df_new.empty:
                        df_new.to_sql(
                            MONTHLY_REVENUE_TABLE_NAME,
                            self.conn,
                            if_exists="append",
                            index=False,
                        )
                        logger.info(
                            f"Save {file_path} into database "
                            f"({len(df_new)} new records, {len(df) - len(df_new)} duplicates skipped)"
                        )
                    else:
                        logger.info(
                            f"Skip {file_path}: all records already exist in database"
                        )
                else:
                    logger.warning(f"Skip {file_path}: file is empty")

                file_cnt += 1
            except Exception as e:
                logger.warning(f"Error saving {file_path}: {e}")

        self.conn.commit()
        self.disconnect()

        if remove_files:
            shutil.rmtree(self.mrr_dir)
        logger.info(f"Total file processed: {file_cnt}")

    def create_missing_tables(self) -> None:
        """確保月營收資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=MONTHLY_REVENUE_TABLE_NAME
        ):
            self.create_db()
