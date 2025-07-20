import shutil
import sqlite3
import pandas as pd
from pathlib import Path

from trader.pipeline.loaders.base import BaseDataLoader
from trader.config import (
    DB_PATH,
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    BALANCE_SHEET_TABLE_NAME,
    COMPREHENSIVE_INCOME_TABLE_NAME,
    CASH_FLOW_TABLE_NAME,
    EQUITY_CHANGE_TABLE_NAME,
)


class FinancialStatementLoader(BaseDataLoader):
    """Financial Statement Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # Downloads directory
        self.fs_dir: Path = FINANCIAL_STATEMENT_DOWNLOADS_PATH

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""

        self.connect()
        self.fs_dir.mkdir(parents=True, exist_ok=True)


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
        pass


    def add_to_db(self, remove_files: bool = False) -> None:
        """Add Data into Database"""
        pass


    def create_balance_sheet_table(self) -> None:
        """ Create Balance Sheet Table """
        pass