import datetime
import os
import shutil
import sqlite3
import time
from io import StringIO
from pathlib import Path
from typing import List, Tuple, Optional, Any

import numpy as np
import pandas as pd


"""
Utility class for common SQLite operations: table check, date retrieval, query execution.
Shared across crawlers for reusability and clean separation of logic.
"""


class SQLiteUtils:
    @staticmethod
    def check_table_exist(conn: sqlite3.Connection, table_name: str) -> bool:
        """檢查 SQLite3 Database 中的 table 是否存在"""

        query: str = "SELECT count(*) FROM sqlite_master WHERE type='table' AND name=?"
        result: Tuple[int] = conn.execute(query, (table_name,)).fetchone()
        return result[0] == 1

    @staticmethod
    def get_table_earliest_date(
        conn: sqlite3.Connection, table_name: str, col_name: str
    ) -> datetime.datetime:
        """
        # 從指定資料表與欄位中取得最舊的日期資料（以遞增排序取第一筆）
        - Description: Retrieve the earliest date from a specific column in a SQLite3 table.
        - Parameters:
            - conn: sqlite3.Connection
                SQLite database connection object.
            - table_name: str
                Name of the table to query.
            - col_name: str
                Name of the date column to search.
        - Return:
            - A datetime object representing the earliest date in the column.
        """

        query: str = (
            f"SELECT {col_name} FROM {table_name} ORDER BY {col_name} ASC LIMIT 1"
        )
        cursor: sqlite3.Cursor = conn.execute(query)
        result: Optional[Tuple[Any]] = cursor.fetchone()

        if result is None or result[0] is None:
            raise ValueError(f"No date found in table: {table_name}")
        return datetime.datetime.strptime(result[0], "%Y-%m-%d")

    @staticmethod
    def get_table_latest_date(
        conn: sqlite3.Connection, table_name: str, col_name: str
    ) -> datetime.datetime:
        """
        # 從指定資料表與欄位中取得最新的日期資料（以遞減排序取第一筆）
        - Description: Retrieve the latest date from a specific column in a SQLite3 table.
        - Parameters:
            - conn: sqlite3.Connection
                SQLite database connection object.
            - table_name: str
                Name of the table to query.
            - col_name: str
                Name of the date column to search.
        - Return:
            - A datetime object representing the latest date in the column.
        """

        query: str = (
            f"SELECT {col_name} FROM {table_name} ORDER BY {col_name} DESC LIMIT 1"
        )
        cursor: sqlite3.Cursor = conn.execute(query)
        result: Optional[Tuple[Any]] = cursor.fetchone()

        if result is None or result[0] is None:
            raise ValueError(f"No date found in table: {table_name}")
        return datetime.datetime.strptime(result[0], "%Y-%m-%d")
