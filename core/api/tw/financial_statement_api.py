import sqlite3
from typing import Optional, Set

import pandas as pd

from core.api.base import BaseDataAPI
from core.config import (
    API_LOG_FILE_LEVEL,
    API_LOGS_DIR_PATH,
    BALANCE_SHEET_TABLE_NAME,
    CASH_FLOW_TABLE_NAME,
    COMPREHENSIVE_INCOME_TABLE_NAME,
    EQUITY_CHANGE_TABLE_NAME,
    TW_STOCK_DB_PATH,
)
from core.utils.log_manager import LogManager

"""
Financial Statement Data API: query SQLite financial statement tables

**表名由呼叫端傳入**（四張報表共用同一組查詢），故一定要走白名單（健檢 F-026）：
表名不能參數化，只能拼進 SQL，而拼字串的地方就是注入的入口。四張表是封閉集合，
白名單既擋得住，也讓「傳錯表名」在當下就報錯，而不是回一張空表。
"""


class FinancialStatementAPI(BaseDataAPI):
    """Financial Statement Data API"""

    # 允許查詢的資料表；表名不可參數化，只能以白名單擋下非預期的值
    ALLOWED_TABLES: Set[str] = {
        BALANCE_SHEET_TABLE_NAME,
        COMPREHENSIVE_INCOME_TABLE_NAME,
        CASH_FLOW_TABLE_NAME,
        EQUITY_CHANGE_TABLE_NAME,
    }

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        # 由 DataFeed 傳入共用連線；未指定時自行建立
        self.conn: Optional[sqlite3.Connection] = conn
        self.owns_conn: bool = conn is None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        if self.owns_conn:
            self.conn = sqlite3.connect(TW_STOCK_DB_PATH)
        LogManager.setup_logger(
            "financial_statement_api.log",
            log_dir=API_LOGS_DIR_PATH,
            level=API_LOG_FILE_LEVEL,
        )

    @classmethod
    def check_table_name(cls, table_name: str) -> str:
        """
        - Description:
            確認表名在白名單內；不在就當場拋出
        - Parameters:
            - table_name: str
                呼叫端傳入的資料表名稱
        - Return:
            - str
                原樣回傳，供直接拼進 SQL
        - Raise:
            - ValueError
                表名不在 `ALLOWED_TABLES` 內
        """

        if table_name not in cls.ALLOWED_TABLES:
            raise ValueError(
                f"不支援的財報資料表：{table_name!r}；"
                f"可用的有 {sorted(cls.ALLOWED_TABLES)}"
            )
        return table_name

    def get(
        self,
        table_name: str,
        year: int,
        season: int,
    ) -> pd.DataFrame:
        """取得指定年度跟季度的財報"""

        table_name = self.check_table_name(table_name)
        query: str = f"""
        SELECT * FROM {table_name}
        WHERE year = ? AND season = ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=self.sql_params(year, season),
        )
        return df

    def get_range(
        self,
        table_name: str,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
    ) -> pd.DataFrame:
        """取得指定年度跟季度的範圍內的財報"""

        table_name = self.check_table_name(table_name)
        query: str = f"""
        SELECT * FROM {table_name}
        WHERE year BETWEEN ? AND ?
        AND season BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=self.sql_params(start_year, end_year, start_season, end_season),
        )
        return df
