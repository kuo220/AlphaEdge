import sqlite3
from abc import ABC, abstractmethod
from typing import Optional

"""Abstract base class for data access APIs. Provides a common interface for querying data from the database"""


class BaseDataAPI(ABC):
    """Base Class of Data API"""

    def __init__(self):
        pass

    @abstractmethod
    def setup(self):
        """Set Up the Config of Data API"""
        pass

    def close(self) -> None:
        """
        - Description:
            關閉資料連線

            單次回測原本會開出 8~10 條互不相干的 SQLite 連線且從不關閉
            （見 backlog Phase2-7）。預設實作關掉 `self.conn`；
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
