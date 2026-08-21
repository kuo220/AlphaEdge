import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import (
    DB_PATH,
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_META_DIR_PATH,
)
from core.pipeline.loaders.base import BaseDataLoader
from core.pipeline.utils import FinancialStatementType
from core.pipeline.utils.data_utils import DataUtils
from core.pipeline.utils.sqlite_utils import SQLiteUtils


class FinancialStatementLoader(BaseDataLoader):
    """Financial Statement Loader"""

    # 各報表的主鍵。其他三張是「一家公司一列」，權益變動表攤平成長表後
    # 一家公司一季有數十列，必須把攤平出來的兩個維度一起納入主鍵才唯一；
    # 且來源端點（逐檔查詢）不回傳公司名稱，故該表不含 `公司名稱`
    PRIMARY_KEYS: dict[str, List[str]] = {
        FinancialStatementType.BALANCE_SHEET: [
            "year",
            "season",
            "stock_id",
            "公司名稱",
        ],
        FinancialStatementType.COMPREHENSIVE_INCOME: [
            "year",
            "season",
            "stock_id",
            "公司名稱",
        ],
        FinancialStatementType.CASH_FLOW: ["year", "season", "stock_id", "公司名稱"],
        FinancialStatementType.EQUITY_CHANGE: [
            "year",
            "season",
            "stock_id",
            "權益項目",
            "變動原因",
        ],
    }

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # Specify column data types
        self.text_not_null_cols: List[str] = [
            "date",
            "stock_id",
            "公司名稱",
            "權益項目",
            "變動原因",
        ]
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
            self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(
        self,
        table_name: str,
        cleaned_cols_path: Path,
        primary_keys: Optional[List[str]] = None,
    ) -> None:
        """Create New Database"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # Step 1: 讀取欄位定義 JSON
        cols: List[str] = DataUtils.load_json(file_path=cleaned_cols_path)
        col_defs: List[str] = []

        # Step 2: 指定欄位型別
        for col in cols:
            col_name: str = f'"{col}"'

            if col in self.text_not_null_cols:
                col_defs.append(f"{col_name} TEXT NOT NULL")
            elif col in self.int_not_null_cols:
                col_defs.append(f"{col_name} INT NOT NULL")
            else:
                col_defs.append(f"{col_name} REAL")

        # Step 3: 加 PRIMARY KEY
        pk_cols: List[str] = primary_keys or ["year", "season", "stock_id", "公司名稱"]
        pk_sql: str = ", ".join(f'"{col}"' for col in pk_cols)
        col_defs.append(f"PRIMARY KEY ({pk_sql})")

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
            logger.warning(f"Table {table_name} create unsuccessfully!")

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保所有財報類型的資料表存在"""

        for fs_type in FinancialStatementType:
            table_name: str = fs_type.lower()
            cleaned_cols_path: Path = self.cleaned_cols_paths[fs_type]

            if not cleaned_cols_path.exists():
                # 欄位定義由 cleaner 產出，缺檔就建不出表；靜默跳過會讓入庫階段
                # 才炸在「no such table」，離真正的原因太遠
                logger.warning(
                    f"Cleaned columns not found for {table_name}: {cleaned_cols_path}"
                )
                continue

            if not SQLiteUtils.check_table_exist(conn=self.conn, table_name=table_name):
                self.create_db(
                    table_name=table_name,
                    cleaned_cols_path=cleaned_cols_path,
                    primary_keys=self.PRIMARY_KEYS[fs_type],
                )

    def add_to_db(
        self,
        dir_path: Path,
        table_name: str,
        remove_files: bool = False,
        only_files: Optional[List[Path]] = None,
    ) -> None:
        """
        - Description:
            Add Data into Database

            `only_files` 給分批入庫用：權益變動表是逐檔查詢，整段回補會落地上千個
            CSV，若每一批都掃整個目錄，重複讀取的成本會隨批次數線性長大。
        - Parameters:
            - dir_path: Path
                CSV 所在目錄
            - table_name: str
                目標資料表
            - remove_files: bool
                成功後是否刪除來源目錄
            - only_files: Optional[List[Path]]
                只入庫這些檔案；None 表示掃整個目錄
        """

        if self.conn is None:
            self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        file_cnt: int = 0

        failed_files: List[str] = []
        partial_files: List[str] = []
        skipped_cnt: int = 0
        target_files: List[Path] = (
            list(dir_path.iterdir()) if only_files is None else only_files
        )
        for file_path in target_files:
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path)
                inserted, skipped = self.insert_dataframe(self.conn, table_name, df)
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
            source="fs",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=dir_path,
            skipped_files=skipped_cnt,
            partial_files=partial_files,
        )
