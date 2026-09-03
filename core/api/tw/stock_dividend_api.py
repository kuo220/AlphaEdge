import datetime
import sqlite3
from typing import Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from core.api.base import BaseDataAPI
from core.config import (
    API_LOG_FILE_LEVEL,
    API_LOGS_DIR_PATH,
    DIVIDEND_TABLE_NAME,
    TW_STOCK_DB_PATH,
)
from core.utils.log_manager import LogManager

"""
Stock dividend API: query SQLite dividend table（除權除息計算結果表）

本表同時服務兩個互不相同的需求，取值時務必分清楚：
- **價格序列還原**（`docs/exchanges/data_coverage.md`〈股價還原〉）：用「還原係數」
- **放空的股利補償現金流**：用「現金股利」

具名查詢方法一律回傳 `{stock_id: 值}` 對照表，與 `StockPriceAPI` 的
`get_close_map()` 系列同型，策略層與回測層不需要知道資料表欄位名。
"""


class StockDividendAPI(BaseDataAPI):
    """Stock dividend API"""

    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        # 由 DataFeed 傳入共用連線；未指定時自行建立（與 StockPriceAPI 同慣例）
        self.conn: Optional[sqlite3.Connection] = conn
        self.owns_conn: bool = conn is None

        # 後復權累乘係數快取：{stock_id: (除權息日 ndarray, 累乘係數 ndarray)}
        # 回測會逐日呼叫，每次重掃全表不划算，故整表只載入一次
        self.factor_cache: Optional[Dict[str, Tuple[np.ndarray, np.ndarray]]] = None

        self.setup()

    def setup(self):
        """Set Up the Config of Data API"""

        if self.owns_conn:
            self.conn = sqlite3.connect(TW_STOCK_DB_PATH)
        LogManager.setup_logger(
            "stock_dividend_api.log",
            log_dir=API_LOGS_DIR_PATH,
            level=API_LOG_FILE_LEVEL,
        )

    def get(self, date: datetime.date) -> pd.DataFrame:
        """取得所有股票指定日期的除權除息資料"""

        query: str = f"""
        SELECT * FROM {DIVIDEND_TABLE_NAME}
        WHERE date = ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=self.sql_params(
                date,
            ),
        )
        return df

    def get_range(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得所有股票日期範圍內的除權除息資料"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {DIVIDEND_TABLE_NAME}
        WHERE date BETWEEN ? AND ?
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=self.sql_params(start_date, end_date),
        )
        return df

    def get_stock_dividend(
        self,
        stock_id: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> pd.DataFrame:
        """取得指定個股的除權除息資料（依日期排序，供還原係數累乘使用）"""

        if start_date > end_date:
            return pd.DataFrame()

        query: str = f"""
        SELECT * FROM {DIVIDEND_TABLE_NAME}
        WHERE stock_id = ?
        AND date BETWEEN ? AND ?
        ORDER BY date
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=self.sql_params(stock_id, start_date, end_date),
        )
        return df

    def get_adjust_factor_map(self, date: datetime.date) -> Dict[str, float]:
        """
        - Description:
            取得指定日期除權息的還原係數對照表

            係數 = 除權息參考價 / 除權息前收盤價（恆 < 1），代表除權息造成的價格落差比例。
            **沒有除權息的股票不會出現在回傳值中**——key 不存在即代表當日無需還原，
            呼叫端不應以 1.0 當作預設值寫進資料，兩者語意不同

        - Parameters:
            - date: datetime.date
                除權息交易日

        - Return:
            - Dict[str, float]
                `{stock_id: 還原係數}`；當日無除權息時回傳空 dict
        """

        return self.build_column_map(self.get(date), "還原係數")

    def get_cash_dividend_map(self, date: datetime.date) -> Dict[str, float]:
        """
        - Description:
            取得指定日期的每股現金股利對照表（單位：元／股）

            供融券放空的股利補償計算使用；純除權（無現金股利）時值為 0

        - Parameters:
            - date: datetime.date
                除權息交易日

        - Return:
            - Dict[str, float]
                `{stock_id: 現金股利}`；當日無除權息時回傳空 dict
        """

        return self.build_column_map(self.get(date), "現金股利")

    def get_stock_dividend_ratio_map(self, date: datetime.date) -> Dict[str, float]:
        """取得指定日期的每股配股數對照表（純除息時為 0）"""

        return self.build_column_map(self.get(date), "配股率")

    def get_opening_reference_price_map(self, date: datetime.date) -> Dict[str, float]:
        """
        - Description:
            取得指定日期的開盤競價基準對照表

            除權息日的漲跌停須以此為基準，沿用前一交易日收盤會讓整段區間偏移
            （見 `docs/exchanges/data_coverage.md`〈股價還原〉）

        - Parameters:
            - date: datetime.date
                除權息交易日

        - Return:
            - Dict[str, float]
                `{stock_id: 開盤競價基準}`；當日無除權息時回傳空 dict
        """

        return self.build_column_map(self.get(date), "開盤競價基準")

    # === 後復權累乘係數：還原價由這一組提供 ===
    def load_factor_cache(self) -> Dict[str, Tuple[np.ndarray, np.ndarray]]:
        """
        - Description:
            載入並快取每檔股票的**後復權累乘係數**

            後復權的定義：以最早日為基準，歷史價格不變、除權息之後的價格往上還原。
            某日 t 的累乘係數為該檔所有「除權息日 ≤ t」的單次係數倒數之連乘：

                factor(stock, t) = Π (除權息前收盤價 / 除權息參考價)

            單次係數（`還原係數` 欄位）恆 < 1，故其倒數 > 1，累乘後越晚的價格被放大越多，
            這正是把「除權息造成的跳空」從報酬率裡扣掉的效果。

            **不用前復權**：前復權會讓同一個歷史日期的價格隨著每次新除權息而改變，
            LONG baseline 會在每次除權息後自動失效，回歸保護等於形同虛設
            （決策理由見 `docs/exchanges/data_coverage.md`〈還原方式〉）。

            快取在**整個 process 生命週期內有效**：回測期間資料表不會變動；
            若在同一個 process 內更新了 `dividend` 表，須自行呼叫 `reset_factor_cache()`

        - Return:
            - Dict[str, Tuple[np.ndarray, np.ndarray]]
                `{stock_id: (除權息日, 累乘係數)}`，兩個陣列皆已依日期排序
        """

        if self.factor_cache is not None:
            return self.factor_cache

        query: str = f"""
        SELECT date, stock_id, 還原係數 FROM {DIVIDEND_TABLE_NAME}
        ORDER BY stock_id, date
        """
        df: pd.DataFrame = pd.read_sql_query(query, self.conn)

        cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = {}
        if df.empty:
            self.factor_cache = cache
            return cache

        df["date"] = pd.to_datetime(df["date"])
        # 單次係數為 0 或負值代表清洗端漏擋，這裡再擋一次，避免整段累乘被汙染成 0／負數
        df = df[df["還原係數"] > 0]
        df["累乘係數"] = df.groupby("stock_id")["還原係數"].transform(
            lambda s: (1.0 / s).cumprod()
        )

        for stock_id, group in df.groupby("stock_id"):
            cache[str(stock_id)] = (
                group["date"].to_numpy(dtype="datetime64[ns]"),
                group["累乘係數"].to_numpy(dtype=float),
            )

        self.factor_cache = cache
        return cache

    def reset_factor_cache(self) -> None:
        """清掉累乘係數快取（更新 `dividend` 表後需呼叫）"""

        self.factor_cache = None

    def get_cumulative_factor(self, stock_id: str, date: datetime.date) -> float:
        """
        - Description:
            取得指定個股在指定日期的後復權累乘係數

        - Parameters:
            - stock_id: str
                股票代號
            - date: datetime.date
                查詢日期

        - Return:
            - float
                累乘係數；該日之前無除權息時為 `1.0`（代表不需還原）
        """

        cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = self.load_factor_cache()
        entry: Optional[Tuple[np.ndarray, np.ndarray]] = cache.get(str(stock_id))

        if entry is None:
            return 1.0

        ex_dates, factors = entry
        # 除權息日「當日」即已套用新價格，故用 right 邊界（date >= 除權息日 才算數）
        idx: int = int(np.searchsorted(ex_dates, np.datetime64(date), side="right"))

        if idx == 0:
            return 1.0
        return float(factors[idx - 1])

    def get_cumulative_factor_map(self, date: datetime.date) -> Dict[str, float]:
        """
        - Description:
            取得單日全市場的後復權累乘係數對照表

            與 `get_adjust_factor_map()` 的差異（兩者容易混淆）：
            - `get_adjust_factor_map()`：**當日單次**除權息的落差比例，只有當日除權息的股票才有值
            - 本方法：**歷史累乘**係數，所有曾經除權息過的股票都有值

            未曾除權息的股票不會出現在回傳值中，呼叫端取不到時視為 `1.0`

        - Parameters:
            - date: datetime.date
                查詢日期

        - Return:
            - Dict[str, float]
                `{stock_id: 累乘係數}`
        """

        cache: Dict[str, Tuple[np.ndarray, np.ndarray]] = self.load_factor_cache()
        target: np.datetime64 = np.datetime64(date)

        factor_map: Dict[str, float] = {}
        for stock_id, (ex_dates, factors) in cache.items():
            idx: int = int(np.searchsorted(ex_dates, target, side="right"))
            if idx:
                factor_map[stock_id] = float(factors[idx - 1])

        return factor_map

    def get_ex_dividend_dates(
        self,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> List[datetime.date]:
        """取得日期範圍內所有出現除權息的交易日（已排序、去重）"""

        if start_date > end_date:
            return []

        query: str = f"""
        SELECT DISTINCT date FROM {DIVIDEND_TABLE_NAME}
        WHERE date BETWEEN ? AND ?
        ORDER BY date
        """
        df: pd.DataFrame = pd.read_sql_query(
            query,
            self.conn,
            params=self.sql_params(start_date, end_date),
        )

        if df.empty:
            return []
        return pd.to_datetime(df["date"]).dt.date.tolist()
