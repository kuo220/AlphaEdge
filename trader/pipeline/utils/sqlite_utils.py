import datetime
import sqlite3
from typing import Any, Optional, Tuple

from loguru import logger

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
                logger.warning(
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
                logger.warning(
                    f"No value found for column '{col_name}' in table: '{table_name}'"
                )
                return None
            return result[0]

        except sqlite3.Error as e:
            logger.error(f"SQLite error while querying {table_name}.{col_name}: {e}")
            return None

    @staticmethod
    def get_max_secondary_value_by_primary(
        conn: sqlite3.Connection,
        table_name: str,
        primary_col: str,
        secondary_col: str,
        default_primary_value: int,
        default_secondary_value: int,
    ) -> Tuple[int, int]:
        """
        - Description:
            查詢指定 table 中最大 primary_col 的值，並找出其對應的最大 secondary_col 值。

        - Parameters:
            - conn (sqlite3.Connection): 資料庫連線
            - table_name (str): 資料表名稱
            - primary_col (str): 主欄位名稱（如 'year'）
            - secondary_col (str): 次欄位名稱（如 'month', 'season'）
            - default_primary_value (int): 查詢失敗時回傳的主欄位預設值
            default_secondary_value (int): 查詢失敗時回傳的次欄位預設值

        - Returns:
            Tuple[int, int]: (主欄位最大值, 對應的次欄位最大值)，若查詢失敗則回傳預設值
        """
        latest_primary: Any = SQLiteUtils.get_table_latest_value(
            conn=conn,
            table_name=table_name,
            col_name=primary_col,
        )

        if latest_primary is None:
            return default_primary_value, default_secondary_value

        query: str = f"""
            SELECT {secondary_col}
            FROM {table_name}
            WHERE {primary_col} = ?
            ORDER BY CAST({secondary_col} AS INTEGER) DESC
            LIMIT 1
        """

        try:
            cursor = conn.execute(query, (latest_primary,))
            result = cursor.fetchone()
            latest_secondary = result[0] if result and result[0] is not None else None
        except Exception as e:
            logger.error(
                f"Failed to query {secondary_col} for {primary_col}={latest_primary} in table '{table_name}': {e}"
            )
            return default_primary_value, default_secondary_value

        if latest_secondary is None:
            return default_primary_value, default_secondary_value

        return int(latest_primary), int(latest_secondary)

    @staticmethod
    def drop_table(conn: sqlite3.Connection, table_name: str) -> bool:
        """
        - Description:
            刪除指定 SQLite 資料庫中的資料表。

        - Parameters:
            conn (sqlite3.Connection): 資料庫連線
            table_name (str): 要刪除的資料表名稱

        - Returns:
            bool: True if table dropped successfully, False otherwise
        """
        try:
            # 先檢查 table 是否存在
            if not SQLiteUtils.check_table_exist(conn=conn, table_name=table_name):
                logger.warning(f"Table '{table_name}' does not exist. Skip drop.")
                return False

            query: str = f"DROP TABLE IF EXISTS {table_name}"
            conn.execute(query)
            conn.commit()
            logger.info(f"Table '{table_name}' dropped successfully.")
            return True

        except sqlite3.Error as e:
            logger.error(f"Failed to drop table '{table_name}': {e}")
            return False
