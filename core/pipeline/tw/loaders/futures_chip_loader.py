import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from core.config import (
    FUTURES_CHIP_DOWNLOADS_PATH,
    FUTURES_INSTITUTIONAL_CHIP_TABLE_NAME,
    FUTURES_LARGE_TRADER_TABLE_NAME,
    FUTURES_PUT_CALL_RATIO_TABLE_NAME,
    TW_FUTURES_DB_PATH,
)
from core.pipeline.shared.base_loader import BaseDataLoader

"""
台期貨籌碼 Loader（三張表）

**三個資料集分三張表**，理由與保證金分兩張表相同：主鍵不同、欄位不同。
硬塞同一張表會讓多數欄位永遠是 NULL，且下游得先判斷「這是哪一種籌碼」
才知道該讀哪一組欄位。

| 表 | 主鍵 | 一天的列數 |
|----|------|-----------|
| `futures_institutional_chip` | (date, product_name, investor) | 商品數 × 3 |
| `futures_large_trader` | (date, product, expiry, trader_type) | 約 1,400 |
| `futures_put_call_ratio` | (date) | 1 |

**建表用 `CREATE TABLE ... AS` 的變體**：這三個來源的欄位數多且會隨交易所調整
（三大法人 15 欄、大額 10 欄），逐欄寫死 schema 會在來源加欄位時整批失敗。
故以第一次入庫的 DataFrame 推導欄位，只把**主鍵與型別**釘死。
"""


class FuturesChipLoader(BaseDataLoader):
    """把清洗後的籌碼資料寫進 tw_futures.db"""

    # {表名: 主鍵欄位}
    PRIMARY_KEYS: dict = {
        FUTURES_INSTITUTIONAL_CHIP_TABLE_NAME: ("date", "product_name", "investor"),
        FUTURES_LARGE_TRADER_TABLE_NAME: ("date", "product", "expiry", "trader_type"),
        FUTURES_PUT_CALL_RATIO_TABLE_NAME: ("date",),
    }

    def __init__(self):
        super().__init__()

        self.conn: Optional[sqlite3.Connection] = None
        self.chip_dir: Path = FUTURES_CHIP_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()
        self.chip_dir.mkdir(parents=True, exist_ok=True)

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

    def create_db(self, table: str, df: pd.DataFrame) -> None:
        """
        - Description:
            依 DataFrame 的欄位建表（若不存在）

            **欄位由資料推導、主鍵寫死**：三個來源的欄位數多且會隨交易所調整，
            逐欄寫死會在來源加欄位時整批入庫失敗；但主鍵不能推導——推錯會讓
            重跑產生重複列而不是被擋下。
        - Parameters:
            - table: str
                表名
            - df: pd.DataFrame
                本次要寫入的資料（用來推導欄位）
        """

        keys: tuple = self.PRIMARY_KEYS[table]
        columns: list = []
        for column in df.columns:
            # 主鍵與名稱類欄位存文字，其餘存數值
            is_text: bool = column in keys or column.endswith("_name")
            columns.append(
                f'"{column}" {"TEXT NOT NULL" if column in keys else ("TEXT" if is_text else "REAL")}'
            )

        primary_key: str = ", ".join(f'"{key}"' for key in keys)
        self.conn.execute(
            f"CREATE TABLE IF NOT EXISTS {table} ({', '.join(columns)}, "
            f"PRIMARY KEY ({primary_key}));"
        )
        self.conn.commit()

    def create_missing_tables(self) -> None:
        """三張表的欄位要等第一批資料才知道，故建表延後到 `add_to_db()`"""

        pass

    def add_to_db(self, table: str, df: pd.DataFrame) -> int:
        """
        - Description:
            寫入單一資料集

            **用 `INSERT OR IGNORE`**：籌碼是既成事實，同一天重跑不該產生第二份，
            也不該覆蓋——與行情表同一種語意。
        - Parameters:
            - table: str
                目標表名
            - df: pd.DataFrame
                清洗後的資料
        - Return:
            - int
                實際新增的列數
        """

        if df is None or df.empty:
            return 0

        self.connect()
        self.create_db(table, df)

        columns: str = ", ".join(f'"{column}"' for column in df.columns)
        placeholders: str = ", ".join("?" for _ in df.columns)
        cursor: sqlite3.Cursor = self.conn.cursor()

        before: int = self.count_rows(table)
        cursor.executemany(
            f"INSERT OR IGNORE INTO {table} ({columns}) VALUES ({placeholders})",
            df.astype(object)
            .where(pd.notna(df), None)
            .itertuples(index=False, name=None),
        )
        self.conn.commit()
        inserted: int = self.count_rows(table) - before

        logger.info(f"[Futures Chip] {table}：新增 {inserted} 列（共 {len(df)} 列）")
        return inserted

    def count_rows(self, table: str) -> int:
        """表內列數；表還不存在時為 0"""

        try:
            return self.conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
        except sqlite3.OperationalError:
            return 0

    def get_latest_date(self, table: str) -> Optional[str]:
        """表內最新的資料日期；供 updater 續跑（表不存在時為 None）"""

        self.connect()
        try:
            row = self.conn.execute(f"SELECT MAX(date) FROM {table}").fetchone()
        except sqlite3.OperationalError:
            return None
        return row[0] if row else None

    def save_csv(self, df: pd.DataFrame, file_name: str) -> Optional[Path]:
        """留一份中繼檔供稽核（與其他 ETL 一致）"""

        if df is None or df.empty:
            return None

        path: Path = self.chip_dir / file_name
        df.to_csv(path, index=False, encoding="utf-8-sig")
        return path
