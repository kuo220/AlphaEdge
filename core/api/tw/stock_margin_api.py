import datetime
import sqlite3
from typing import Any, Dict, Optional

import pandas as pd

from core.api.base import BaseDataAPI
from core.config import API_LOGS_DIR_PATH, MARGIN_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.utils.sqlite_utils import SQLiteUtils
from core.utils.log_manager import LogManager

"""Stock margin trading API: query SQLite margin table（融資融券餘額，單位：張）"""


class StockMarginAPI(BaseDataAPI):
    """Stock margin trading API"""

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        # 由 DataFeed 傳入共用連線；未指定時自行建立
        self.conn: Optional[sqlite3.Connection] = conn
        self.owns_conn: bool = conn is None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        if self.owns_conn:
            self.conn = sqlite3.connect(TW_STOCK_DB_PATH)
        LogManager.setup_logger("stock_margin_api.log", log_dir=API_LOGS_DIR_PATH)

    def get(self, date: datetime.date) -> pd.DataFrame:
        """取得所有股票指定日期的信用交易資料"""

        query: str = f"""
        SELECT * FROM {MARGIN_TABLE_NAME}
        WHERE date = ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(date,),
        )
        return df

    def get_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得所有股票日期範圍內的信用交易資料"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {MARGIN_TABLE_NAME}
        WHERE date BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(start_date, end_date),
        )
        return df

    def get_stock_margin(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定個股的信用交易資料"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {MARGIN_TABLE_NAME}
        WHERE stock_id = ?
        AND date BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(stock_id, start_date, end_date),
        )
        return df

    def get_short_balance(self, date: datetime.date) -> pd.DataFrame:
        """取得所有股票指定日期的融券餘額與券資比（券源檢核用）"""

        query: str = f"""
        SELECT date, stock_id, 證券名稱, 融券今日餘額, 融券限額, 券資比, 註記
        FROM {MARGIN_TABLE_NAME}
        WHERE date = ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(date,),
        )
        return df

    def get_short_balance_map(self, date: datetime.date) -> Dict[str, int]:
        """
        - Description:
            取得單日全市場的融券今日餘額對照表（張），供回測的券源檢核使用

            **`margin` 表不存在時回傳空 dict 而非拋錯**：該表的歷史回補是獨立作業，
            尚未執行時回測仍應能跑，由呼叫端（`FillModel`）以 warning 表明
            「查無資料，本次跳過檢核」，而不是靜默地把所有標的都當成借不到券。
        - Parameters:
            - date: datetime.date
                查詢日期
        - Return:
            - Dict[str, int]
                `{stock_id: 融券今日餘額（張）}`；查無資料時為空 dict
        """

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=MARGIN_TABLE_NAME
        ):
            return {}

        df: pd.DataFrame = self.get_short_balance(date)
        balance_map: Dict[str, Any] = self.build_column_map(df, "融券今日餘額")

        result: Dict[str, int] = {}
        for stock_id, balance in balance_map.items():
            try:
                result[stock_id] = int(balance)
            except (TypeError, ValueError):
                continue

        return result

    def get_stock_short_balance(
        self,
        stock_id: str,
        date: datetime.date,
    ) -> Optional[int]:
        """
        - Description:
            取得指定個股在指定日期的融券今日餘額（單位：張），供回測開倉前的券源檢核使用

        - Parameters:
            - stock_id: str
                股票代號
            - date: datetime.date
                查詢日期

        - Return:
            - Optional[int]
                融券今日餘額（張）；查無資料時回傳 None（呼叫端須自行決定是否跳過檢核）
        """

        query: str = f"""
        SELECT 融券今日餘額 FROM {MARGIN_TABLE_NAME}
        WHERE stock_id = ?
        AND date = ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(stock_id, date),
        )

        if df.empty:
            return None
        return int(df.iloc[0, 0])
