import datetime
import sqlite3
from loguru import logger
from typing import Tuple, Optional, Any


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
    def get_table_earliest_value(
        conn: sqlite3.Connection,
        table_name: str,
        col_name: str,
    ) -> Optional[datetime.date]:
        """
        - Description: Retrieve the earliest value in the table.
        - Parameters:
            - conn: sqlite3.Connection
                SQLite database connection object.
            - table_name: str
                Name of the table to query.
            - col_name: str
                Name of the value column to search.
        - Return: Optional[Any]
            - The earliest value in the column, or None if not found.
        """

        query: str = (
            f"SELECT {col_name} FROM {table_name} ORDER BY {col_name} ASC LIMIT 1"
        )

        try:
            cursor: sqlite3.Cursor = conn.execute(query)
            result: Optional[tuple[Any, ...]] = cursor.fetchone()

            if result is None or result[0] is None:
                logger.info(
                    f"No value found for column '{col_name}' in table: '{table_name}'"
                )
                return None

            return result[0]

        except sqlite3.Error as e:
            logger.error(f"SQLite error while querying {table_name}.{col_name}: {e}")
            return None

    @staticmethod
    def get_table_latest_value(
        conn: sqlite3.Connection,
        table_name: str,
        col_name: str,
    ) -> Optional[Any]:
        """
        - Description: Retrieve the latest value in the table.
        - Parameters:
            - conn: sqlite3.Connection
                SQLite database connection object.
            - table_name: str
                Name of the table to query.
            - col_name: str
                Name of the value column to search.
        - Return: Optional[Any]
            - The latest value in the column, or None if not found.
        """

        query: str = (
            f"SELECT {col_name} FROM {table_name} ORDER BY {col_name} DESC LIMIT 1"
        )

        try:
            cursor: sqlite3.Cursor = conn.execute(query)
            result: Optional[Tuple[Any, ...]] = cursor.fetchone()

            if result is None or result[0] is None:
                logger.info(
                    f"No value found for column '{col_name}' in table: '{table_name}'"
                )
                return None
            return result[0]

        except sqlite3.Error as e:
            logger.error(f"SQLite error while querying {table_name}.{col_name}: {e}")
            return None
