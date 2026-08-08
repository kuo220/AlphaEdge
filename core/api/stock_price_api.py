import datetime
import sqlite3
from typing import Any, Dict, Optional

import pandas as pd
from loguru import logger

from core.api.base import BaseDataAPI
from core.config import DB_PATH, PRICE_TABLE_NAME
from core.pipeline.utils.constant import PriceColumn
from core.utils.constant import Units
from core.utils.log_manager import LogManager

"""Stock Price API: query SQLite price table"""


class StockPriceAPI(BaseDataAPI):
    """Stock Price API"""

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        # 由 DataFeed 傳入共用連線；未指定時自行建立（見 backlog Phase2-7）
        self.conn: Optional[sqlite3.Connection] = conn
        self.owns_conn: bool = conn is None

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Data API"""

        if self.owns_conn:
            self.conn = sqlite3.connect(DB_PATH)
        LogManager.setup_logger("stock_price_api.log")

    def get(self, date: datetime.date) -> pd.DataFrame:
        """取得所有股票指定日期的 Price"""

        query: str = f"""
        SELECT * FROM {PRICE_TABLE_NAME}
        WHERE date = ?
        """
        return pd.read_sql_query(
            query,
            self.conn,
            params=(date,),
        )

    def get_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得所有股票指定日期範圍的 Price"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {PRICE_TABLE_NAME}
        WHERE date BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(start_date, end_date),
        )
        return df

    def get_stock_price(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定個股的 Price"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {PRICE_TABLE_NAME}
        WHERE stock_id = ?
        AND date BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=(stock_id, start_date, end_date),
        )
        return df

    # === 具名查詢：策略層一律走這一組，不要自行操作 DataFrame 欄位 ===
    def get_close_map(self, date: datetime.date) -> Dict[str, Any]:
        """
        - Description:
            取得單日全市場的收盤價對照表

            策略的共通樣式是「拿一整天的全市場 DataFrame → 逐檔建 mask → 取欄位」，
            那是 O(n²) 且把資料表欄位名洩漏到策略層。本方法一次查詢建成 dict，
            策略改為 O(1) 查表，也不需要知道欄位叫什麼。

            取值細節（重複、缺欄位、`NaN`）見 `BaseDataAPI.build_column_map()`。
        - Parameters:
            - date: datetime.date
                查詢日期
        - Return:
            - close_map: Dict[str, Any]
                {stock_id: 收盤價}；同一檔重複出現時取第一筆
        """

        df: pd.DataFrame = self.get(date)
        return self.build_column_map(df, PriceColumn.CLOSE.value)

    def get_volume_lots_map(self, date: datetime.date) -> Dict[str, int]:
        """
        - Description:
            取得單日全市場的成交量（張）對照表

            股 → 張的換算在 API 內完成，策略不再自行除以 `Units.LOT`。

            此處**不使用** `StockUtils.convert_share_to_lot()`：`core/utils/instrument.py`
            相依 `MarketCalendar`，而後者相依本檔案，引用會造成循環 import。
            `core/api/` 位於 `StockUtils` 之下，不應反向相依。
        - Parameters:
            - date: datetime.date
                查詢日期
        - Return:
            - volume_map: Dict[str, int]
                {stock_id: 成交量（張）}；成交股數無法轉為整數者不納入
        """

        df: pd.DataFrame = self.get(date)
        share_map: Dict[str, Any] = self.build_column_map(
            df, PriceColumn.SHARES.value
        )

        volume_map: Dict[str, int] = {}
        for stock_id, shares in share_map.items():
            try:
                volume_map[stock_id] = int(int(shares) / Units.LOT)
            except (TypeError, ValueError):
                continue

        return volume_map

    def get_close_series(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.Series:
        """
        - Description:
            取得指定個股在區間內的收盤價序列
        - Parameters:
            - stock_id: str
                股票代號
            - start_date: datetime.date
                起始日（含）
            - end_date: datetime.date
                結束日（含）
        - Return:
            - series: pd.Series
                index 為原始 date 欄位、已依日期排序；查無資料時為空 Series
        """

        df: pd.DataFrame = self.get_stock_price(stock_id, start_date, end_date)

        if df.empty or PriceColumn.CLOSE.value not in df.columns:
            return pd.Series(dtype=float, name=PriceColumn.CLOSE.value)

        df = df.sort_values("date")
        series: pd.Series = df[PriceColumn.CLOSE.value]
        series.index = df["date"]
        return series
