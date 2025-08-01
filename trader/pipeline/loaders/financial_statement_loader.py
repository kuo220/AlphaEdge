import shutil
import sqlite3
from loguru import logger
import pandas as pd
from pathlib import Path
from typing import List

from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.pipeline.utils import FinancialStatementType
from trader.config import (
    DB_PATH,
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_META_DIR_PATH,
)


class FinancialStatementLoader(BaseDataLoader):
    """Financial Statement Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # Specify column data types
        self.text_not_null_cols: List[str] = ["date", "stock_id", "公司名稱"]
        self.int_not_null_cols: List[str] = ["year", "season"]

        # Reports Cleaned Columns Path
        self.balance_sheet_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.BALANCE_SHEET.lower()
            / f"{FinancialStatementType.BALANCE_SHEET.lower()}_cleaned_columns.json"
        )
        self.comprehensive_income_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.COMPREHENSIVE_INCOME.lower()
            / f"{FinancialStatementType.COMPREHENSIVE_INCOME.lower()}_cleaned_columns.json"
        )
        self.cash_flow_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.CASH_FLOW.lower()
            / f"{FinancialStatementType.CASH_FLOW.lower()}_cleaned_columns.json"
        )
        self.equity_change_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.EQUITY_CHANGE.lower()
            / f"{FinancialStatementType.EQUITY_CHANGE.lower()}_cleaned_columns.json"
        )

        self.cleaned_cols_paths: dict[str, Path] = {
            FinancialStatementType.BALANCE_SHEET: self.balance_sheet_cleaned_cols_path,
            FinancialStatementType.COMPREHENSIVE_INCOME: self.comprehensive_income_cleaned_cols_path,
            FinancialStatementType.CASH_FLOW: self.cash_flow_cleaned_cols_path,
            FinancialStatementType.EQUITY_CHANGE: self.equity_change_cleaned_cols_path,
        }

        # Downloads directory Path
        self.fs_dir: Path = FINANCIAL_STATEMENT_DOWNLOADS_PATH
        self.balance_sheet_dir: Path = (
            self.fs_dir / FinancialStatementType.BALANCE_SHEET.lower()
        )
        self.comprehensive_income_dir: Path = (
            self.fs_dir / FinancialStatementType.COMPREHENSIVE_INCOME.lower()
        )
        self.cash_flow_dir: Path = (
            self.fs_dir / FinancialStatementType.CASH_FLOW.lower()
        )
        self.equity_change_dir: Path = (
            self.fs_dir / FinancialStatementType.EQUITY_CHANGE.lower()
        )

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        # Connect Database
        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.fs_dir.mkdir(parents=True, exist_ok=True)
        self.balance_sheet_dir.mkdir(parents=True, exist_ok=True)
        self.comprehensive_income_dir.mkdir(parents=True, exist_ok=True)
        self.cash_flow_dir.mkdir(parents=True, exist_ok=True)
        self.equity_change_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn = None

    def create_db(
        self,
        table_name: str,
        cleaned_cols_path: Path,
    ) -> None:
        """Create New Database"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # Step 1: 讀取欄位定義 JSON
        cols: List[str] = DataUtils.load_json(file_path=cleaned_cols_path)
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
        col_defs.append("PRIMARY KEY (year, season, stock_id)")

        # Step 4: 組建 SQL
        col_defs_sql: str = ",\n            ".join(col_defs)
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {table_name}(
            {col_defs_sql}
        )
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{table_name}')")
        if cursor.fetchall():
            logger.info(f"Table {table_name} create successfully!")
            logger.info(create_table_query)
        else:
            logger.info(f"Table {table_name} create unsuccessfully!")

        self.conn.commit()

    def add_to_db(
        self,
        dir_path: Path,
        table_name: str,
        remove_files: bool = False,
    ) -> None:
        """Add Data into Database"""

        if self.conn is None:
            self.connect()

        file_cnt: int = 0
        for file_path in dir_path.iterdir():
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path)
                df.to_sql(table_name, self.conn, if_exists="append", index=False)
                logger.info(f"Save {file_path} into database")
                file_cnt += 1
            except Exception as e:
                logger.info(f"Error saving {file_path}: {e}")

        self.conn.commit()
        self.disconnect()

        if remove_files:
            shutil.rmtree(dir_path)
        logger.info(f"Total file processed: {file_cnt}")

    def create_missing_tables(self) -> None:
        """確保所有財報類型的資料表存在（除了尚未實作的）"""
        for fs_type in FinancialStatementType:
            if fs_type == FinancialStatementType.EQUITY_CHANGE:
                continue  # TODO: 實作後移除

            table_name: str = fs_type.lower()
            cleaned_cols_path: Path = self.cleaned_cols_paths[fs_type]

            if not SQLiteUtils.check_table_exist(conn=self.conn, table_name=table_name):
                self.create_db(
                    table_name=table_name, cleaned_cols_path=cleaned_cols_path
                )
