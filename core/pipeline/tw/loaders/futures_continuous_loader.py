import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_CONTINUOUS_DOWNLOADS_PATH,
    FUTURES_CONTINUOUS_TABLE_NAME,
    TW_FUTURES_DB_PATH,
)
from core.pipeline.shared.base_loader import BaseDataLoader

"""
Futures Continuous Loader

**本表是衍生表，不是爬回來的**：來源是同一個 DB 裡的 `futures_price_daily`，
故整組 ETL 沒有 crawler 與 cleaner，只有「建表的 updater」與本 loader。

**主鍵含 `method` 與 `roll_rule`**（`(date, product, session, method, roll_rule)`）：
連續合約不是唯一的——調整方式與換月規則各三種，同一天可以有多條合法的序列。
把兩者塞進主鍵，三種調整方式與三種換月規則可以並存於同一張表，
研究時直接 `WHERE method = ? AND roll_rule = ?` 取用，不必為每種組合建一張表。

**欄位語言沿用來源**（中文 OHLC）：本表的數字直接來自 `futures_price_daily`，
欄名跟著來源走（見 `docs/pipeline/etl-ingestion.md` §3.4）；
主鍵與旗標欄則一律英文。
"""


class FuturesContinuousLoader(BaseDataLoader):
    """把建好的連續合約序列寫進 `futures_continuous`"""

    def __init__(self):
        super().__init__()

        self.conn: Optional[sqlite3.Connection] = None
        self.continuous_dir: Path = FUTURES_CONTINUOUS_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()
        self.create_missing_tables()
        self.continuous_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            TW_FUTURES_DB_PATH.parent.mkdir(parents=True, exist_ok=True)
            self.conn = sqlite3.connect(TW_FUTURES_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn = None

    def create_db(self) -> None:
        """Create New Database Table"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # `expiry` 是**當天實際採用的契約**，不是主鍵的一部分——同一天在同一組
        # （method, roll_rule）之下只會有一個當家契約。把它存下來是為了讓
        # 換月接點可被稽核：`roll_flag = 1` 的那幾天，`expiry` 必定與前一天不同。
        #
        # `adj_factor` 是**已套用的調整量**，存下來才能還原回真實價格：
        # BACKWARD 為加減量（原始價 ＝ 調整價 − adj_factor），
        # RATIO 為乘數（原始價 ＝ 調整價 ÷ adj_factor），NONE 恆為 0。
        # 最新一段的 adj_factor 為 0／1——逆向調整以最新為基準，那一段就是真實價。
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {FUTURES_CONTINUOUS_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "product" TEXT NOT NULL,
            "session" TEXT NOT NULL,
            "method" TEXT NOT NULL,
            "roll_rule" TEXT NOT NULL,
            "expiry" TEXT NOT NULL,
            "開盤價" REAL,
            "最高價" REAL,
            "最低價" REAL,
            "收盤價" REAL,
            "成交量" INT,
            "結算價" REAL,
            "未沖銷契約量" INT,
            "roll_flag" INT NOT NULL,
            "roll_gap" REAL,
            "adj_factor" REAL,
            PRIMARY KEY ("date", "product", "session", "method", "roll_rule")
        );
        """
        cursor.execute(create_table_query)

        # 最常見的查詢是「某商品某組設定的整段序列」，主鍵前綴是 date，幫不上忙
        cursor.execute(
            f"""
            CREATE INDEX IF NOT EXISTS idx_futures_continuous_series
            ON {FUTURES_CONTINUOUS_TABLE_NAME}
            ("product", "session", "method", "roll_rule", "date");
            """
        )
        self.conn.commit()

    def create_missing_tables(self) -> None:
        """Ensure Database Tables Exist"""

        self.create_db()

    def add_to_db(self, df: pd.DataFrame) -> int:
        """
        - Description:
            寫入連續合約序列

            **用 `INSERT OR REPLACE` 而不是 `IGNORE`**：本表是衍生表，
            重建時同一組主鍵的值**應該**被新的結果覆蓋——調整方式的實作修正後，
            舊值若被 `IGNORE` 留著，表裡會混著兩代結果且無從分辨。
        - Parameters:
            - df: pd.DataFrame
                已建好的序列
        - Return:
            - int
                寫入列數
        """

        if df is None or df.empty:
            logger.warning("[Futures Continuous] 沒有資料可寫入")
            return 0

        columns: str = ", ".join(f'"{column}"' for column in df.columns)
        placeholders: str = ", ".join("?" for _ in df.columns)
        query: str = (
            f"INSERT OR REPLACE INTO {FUTURES_CONTINUOUS_TABLE_NAME} "
            f"({columns}) VALUES ({placeholders})"
        )

        cursor: sqlite3.Cursor = self.conn.cursor()
        cursor.executemany(query, df.itertuples(index=False, name=None))
        self.conn.commit()

        logger.info(f"[Futures Continuous] 寫入 {len(df)} 列")
        return len(df)

    def save_csv(self, df: pd.DataFrame, file_name: str) -> Optional[Path]:
        """
        把序列另存一份 CSV 供稽核

        衍生表沒有「原始下載檔」可以回溯，出錯時只能重跑；留一份中繼檔
        至少能直接 diff 兩次建表的差異。
        """

        if df is None or df.empty:
            return None

        path: Path = self.continuous_dir / file_name
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
