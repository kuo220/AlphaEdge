import datetime
import sqlite3
from typing import Optional

import pandas as pd

from trader.api.base import BaseDataAPI
from trader.config import (
    DB_PATH,
    SECURITIES_TRADER_INFO_TABLE_NAME,
    STOCK_INFO_TABLE_NAME,
    STOCK_INFO_WITH_WARRANT_TABLE_NAME,
    STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
)
from trader.utils.log_manager import LogManager

"""取得 FinMind 資料的 API

Usage:
    from trader.api.finmind_api import FinMindAPI

    api = FinMindAPI()

    # 台股總覽（不含權證）
    df = api.get_all_stock_info()
    row = api.get_stock_info("2330")

    # 台股總覽（含權證）
    df = api.get_all_stock_info_with_warrant()
    row = api.get_stock_info_with_warrant("2330")

    # 證券商資訊
    df = api.get_all_broker_info()
    row = api.get_broker_info("9A00")

    # 當日券商分點統計（依股票、日期、券商查詢）
    df = api.get_broker_trading_for_stock_on_date("2330", date)
    df = api.get_broker_trading_for_stock_in_range("2330", start_date, end_date)
    df = api.get_broker_trading_by_date(date)
    df = api.get_broker_trading_range(start_date, end_date)
    df = api.get_broker_trading_by_broker_and_date("永豐金證券", date)
"""


class FinMindAPI(BaseDataAPI):
    """FinMind 資料 API：台股總覽、證券商資訊、券商分點日報"""

    def __init__(self) -> None:
        self.conn: Optional[sqlite3.Connection] = None
        self.setup()

    def setup(self) -> None:
        """設定連線與 log"""

        self.conn = sqlite3.connect(DB_PATH)
        LogManager.setup_logger("finmind_api.log")

    # -----------------------------------------------------------------------
    # 台股總覽 (taiwan_stock_info)
    # -----------------------------------------------------------------------
    # 欄位: industry_category, stock_id, stock_name, type, date
    # PK: stock_id
    #

    def get_stock_info(self, stock_id: str) -> pd.DataFrame:
        """取得單一股票的台股總覽（不含權證）"""

        query: str = f"""
        SELECT * FROM {STOCK_INFO_TABLE_NAME}
        WHERE stock_id = ?
        """
        return pd.read_sql_query(query, self.conn, params=(stock_id,))

    def get_all_stock_info(self) -> pd.DataFrame:
        """取得全部台股總覽（不含權證）"""

        query: str = f"SELECT * FROM {STOCK_INFO_TABLE_NAME}"
        return pd.read_sql_query(query, self.conn)

    # -----------------------------------------------------------------------
    # 台股總覽含權證 (taiwan_stock_info_with_warrant)
    # -----------------------------------------------------------------------
    # 欄位同上，PK: stock_id
    #

    def get_stock_info_with_warrant(self, stock_id: str) -> pd.DataFrame:
        """取得單一股票的台股總覽（含權證）"""

        query: str = f"""
        SELECT * FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}
        WHERE stock_id = ?
        """
        return pd.read_sql_query(query, self.conn, params=(stock_id,))

    def get_all_stock_info_with_warrant(self) -> pd.DataFrame:
        """取得全部台股總覽（含權證）"""

        query: str = f"SELECT * FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}"
        return pd.read_sql_query(query, self.conn)

    # -----------------------------------------------------------------------
    # 證券商資訊 (taiwan_securities_trader_info)
    # -----------------------------------------------------------------------
    # 欄位: securities_trader_id, securities_trader, date, address, phone
    # PK: securities_trader_id
    #

    def get_broker_info(self, securities_trader_id: str) -> pd.DataFrame:
        """依證券商代號取得單一證券商資訊"""

        query: str = f"""
        SELECT * FROM {SECURITIES_TRADER_INFO_TABLE_NAME}
        WHERE securities_trader_id = ?
        """
        return pd.read_sql_query(query, self.conn, params=(securities_trader_id,))

    def get_all_broker_info(self) -> pd.DataFrame:
        """取得全部證券商資訊"""

        query: str = f"SELECT * FROM {SECURITIES_TRADER_INFO_TABLE_NAME}"
        return pd.read_sql_query(query, self.conn)

    # -----------------------------------------------------------------------
    # 當日券商分點統計 (taiwan_stock_trading_daily_report_secid_agg)
    # -----------------------------------------------------------------------
    # 欄位: securities_trader, securities_trader_id, stock_id, date,
    #       buy_volume, sell_volume, buy_price, sell_price
    # PK: (stock_id, date, securities_trader_id)
    #

    def get_broker_trading_by_date(self, date: datetime.date) -> pd.DataFrame:
        """取得指定日期的全部券商分點日報"""

        query: str = f"""
        SELECT * FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        WHERE date = ?
        """
        return pd.read_sql_query(query, self.conn, params=(date,))

    def get_broker_trading_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得日期區間內的全部券商分點日報"""

        if start_date > end_date:
            return pd.DataFrame()
        query: str = f"""
        SELECT * FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        WHERE date BETWEEN ? AND ?
        """
        return pd.read_sql_query(query, self.conn, params=(start_date, end_date))

    def get_broker_trading_for_stock_on_date(
        self,
        stock_id: str,
        date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定股票在指定日期的券商分點日報（單日）"""

        query: str = f"""
        SELECT * FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        WHERE stock_id = ? AND date = ?
        """
        return pd.read_sql_query(
            query,
            self.conn,
            params=(stock_id, date),
        )

    def get_broker_trading_for_stock_in_range(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定股票在日期區間內的券商分點日報（多日）"""

        if start_date > end_date:
            return pd.DataFrame()
        query: str = f"""
        SELECT * FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        WHERE stock_id = ? AND date BETWEEN ? AND ?
        """
        return pd.read_sql_query(
            query,
            self.conn,
            params=(stock_id, start_date, end_date),
        )

    def get_broker_trading_by_broker_and_date(
        self,
        securities_trader: str,
        date: datetime.date,
    ) -> pd.DataFrame:
        """依券商中文名稱與日期取得該券商當日所有股票的分點日報"""

        query: str = f"""
        SELECT * FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        WHERE securities_trader = ? AND date = ?
        """
        return pd.read_sql_query(
            query,
            self.conn,
            params=(securities_trader, date),
        )
