import datetime
import sqlite3
from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd

"""Abstract base class for data access APIs. Provides a common interface for querying data from the database"""


class BaseDataAPI(ABC):
    """Base Class of Data API"""

    def __init__(self):
        pass

    @abstractmethod
    def setup(self):
        """Set Up the Config of Data API"""
        pass

    @staticmethod
    def sql_params(*values: Any) -> Tuple[Any, ...]:
        """
        - Description:
            把查詢參數轉成 SQLite 收得下的型別；`date`／`datetime` 轉 ISO 字串

            **不轉的話是靠 Python 3.12 已 deprecated 的預設 date adapter**
            （健檢 F-025）：那個 adapter 隨時可能被移除，屆時每一支 API 都會
            在同一天壞掉，而且錯誤訊息只會說「型別不支援」。

            資料表的 `date` 欄一律是 `TEXT`（`YYYY-MM-DD`），ISO 字串本來就是
            正確的比較對象；`datetime` 只取日期部分，與欄位格式對齊。
        - Parameters:
            - values: Any
                查詢參數；非日期型別原樣通過
        - Return:
            - Tuple[Any, ...]
                可直接傳給 `params=` 的 tuple
        """

        converted: List[Any] = []
        for value in values:
            if isinstance(value, datetime.datetime):
                converted.append(value.date().isoformat())
            elif isinstance(value, datetime.date):
                converted.append(value.isoformat())
            else:
                converted.append(value)
        return tuple(converted)

    @staticmethod
    def build_column_map(df: pd.DataFrame, column: str) -> Dict[str, Any]:
        """
        - Description:
            由單日全市場 DataFrame 建立 `{stock_id: 欄位值}` 對照表

            具名查詢方法的共用底座。策略若自行「逐檔建 mask 再取欄位」，
            不但是 O(n²)，還會把資料表欄位名洩漏到策略層。

            同一檔重複出現時取**第一筆**，與原本 `df.loc[mask, col].iloc[0]`
            的取值一致——改成取最後一筆會讓歷史回歸逐筆對不上。

            **值維持資料庫原樣不做轉型**（含 `NaN`）：缺資料與「有資料但值異常」
            是兩件事，前者以 key 不存在表示，後者留給呼叫端依自身門檻判斷。
        - Parameters:
            - df: pd.DataFrame
                單日全市場資料
            - column: str
                要取的欄位名
        - Return:
            - Dict[str, Any]
                對照表；`df` 為空或無該欄位時回傳空 dict
        """

        if df.empty or column not in df.columns:
            return {}

        deduped: pd.DataFrame = df.drop_duplicates(subset="stock_id", keep="first")
        return dict(zip(deduped["stock_id"], deduped[column]))

    def close(self) -> None:
        """
        - Description:
            關閉資料連線

            單次回測原本會開出 8~10 條互不相干的 SQLite 連線且從不關閉
            。預設實作關掉 `self.conn`；
            非 SQLite 的資料源（如 DolphinDB）自行覆寫。
        """

        if not getattr(self, "owns_conn", True):
            # 共用連線由建立者（DataFeed）負責關閉，避免其他持有者拿到已關閉的連線
            return

        conn: Optional[sqlite3.Connection] = getattr(self, "conn", None)
        if conn is not None:
            conn.close()
            self.conn = None

    def __enter__(self) -> "BaseDataAPI":
        """支援 with 語法，離開區塊即關閉連線"""

        return self

    def __exit__(self, exc_type, exc_value, traceback) -> None:
        """離開 with 區塊時關閉連線"""

        self.close()
