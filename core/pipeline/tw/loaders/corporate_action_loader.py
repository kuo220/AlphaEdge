import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import (
    CORPORATE_ACTION_DOWNLOADS_PATH,
    CORPORATE_ACTION_TABLE_NAME,
    TW_STOCK_DB_PATH,
)
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
Corporate Action Loader

**入庫走 `INSERT OR REPLACE`**：同一筆事件會在每次回補時再取一次（端點是區間查詢，
一次一整年），`append` 會因主鍵衝突整批拋錯，讓「重跑」與「真的出錯」無法區分。

`資料來源` 有三種：`twse`／`tpex` 來自交易所端點，`detected` 是由行情偵測補的
（ETF 受益權單位分割不在任何結構化端點裡，0050 的 2025-06-18 就是這一類）。
跨來源重複時**交易所優先**——偵測出來的倍率是從價格反推的近似值，
端點給的是官方參考價。
"""


class CorporateActionLoader(BaseDataLoader):
    """把清洗後的公司行動事件寫入 SQLite"""

    # 同一筆事件若跨來源重複，保留優先序**最高**的那一筆。
    # 偵測值是從價格反推的近似，交易所給的才是官方參考價
    SOURCE_PRIORITY: List[str] = ["detected", "tpex", "twse"]

    def __init__(self) -> None:
        super().__init__()

        self.conn: Optional[sqlite3.Connection] = None
        self.corporate_action_dir: Path = CORPORATE_ACTION_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()
        self.create_missing_tables()
        self.corporate_action_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            self.conn = sqlite3.connect(TW_STOCK_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn = None

    def create_db(self) -> None:
        """建立公司行動事件表"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # 調整倍率 ＝ 恢復買賣參考價 ÷ 停止買賣前收盤價
        # **減資時 > 1（價格上調）、分割時 < 1**，與 `dividend.還原係數`（恆 < 1）方向相反
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {CORPORATE_ACTION_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "證券名稱" TEXT,
            "停止買賣前收盤價" REAL NOT NULL,
            "恢復買賣參考價" REAL NOT NULL,
            "調整倍率" REAL NOT NULL,
            "事件類型" TEXT NOT NULL,
            "原因" TEXT,
            "資料來源" TEXT NOT NULL,
            PRIMARY KEY ("date", "stock_id")
        );
        """
        cursor.execute(create_table_query)

        cursor.execute(f"PRAGMA table_info('{CORPORATE_ACTION_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {CORPORATE_ACTION_TABLE_NAME} create successfully!")
        else:
            logger.warning(
                f"Table {CORPORATE_ACTION_TABLE_NAME} create unsuccessfully!"
            )

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保公司行動資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=CORPORATE_ACTION_TABLE_NAME
        ):
            self.create_db()

        # 主鍵是 (date, stock_id)，「某一檔的整段歷史」查不到索引
        self.create_symbol_date_index(self.conn, CORPORATE_ACTION_TABLE_NAME)

    def add_to_db(self, remove_files: bool = False) -> None:
        """把下載目錄中的所有 CSV 寫入資料表"""

        if self.conn is None:
            self.connect()

        self.create_missing_tables()

        file_cnt: int = 0
        failed_files: List[str] = []
        dfs: List[pd.DataFrame] = []

        for file_path in sorted(self.corporate_action_dir.iterdir()):
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path, dtype={"stock_id": str})
                dfs.append(df)
                file_cnt += 1
            except Exception as error:
                logger.warning(f"Error reading {file_path}: {error}")
                failed_files.append(str(file_path))

        if not dfs:
            logger.warning("No corporate action CSV file to load")
            self.disconnect()
            return

        merged_df: pd.DataFrame = pd.concat(dfs, ignore_index=True)
        row_cnt: int = len(merged_df)
        merged_df = self.dedup_by_source_priority(merged_df)
        logger.info(f"Corporate action rows: {row_cnt} -> {len(merged_df)} after dedup")

        self.upsert(merged_df)

        self.conn.commit()
        self.disconnect()

        self.finish_load(
            source="corporate_action",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=CORPORATE_ACTION_DOWNLOADS_PATH,
        )

    def dedup_by_source_priority(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        - Description:
            以「來源優先序」跨檔去重，而不是以檔名字典序

            同一個 `(date, stock_id)` 可能同時來自端點與行情偵測；依
            `SOURCE_PRIORITY` 由低到高排序後 `keep="last"`，勝出的是優先序最高者。
            **不可依檔名字典序決定**：那會讓「留下哪一筆」
            取決於檔名的字母順序，日後多一個來源勝出的就換人，且不會有跡象。
        - Parameters:
            - df: pd.DataFrame
                合併後的公司行動資料
        - Return:
            - pd.DataFrame
                去重後的資料（欄位順序不變）
        """

        if "資料來源" not in df.columns:
            return df.drop_duplicates(subset=["date", "stock_id"], keep="last")

        work: pd.DataFrame = df.copy()
        work["_priority"] = work["資料來源"].apply(
            lambda source: (
                self.SOURCE_PRIORITY.index(source)
                if source in self.SOURCE_PRIORITY
                else -1
            )
        )
        work = work.sort_values(["date", "stock_id", "_priority"], kind="stable")
        work = work.drop_duplicates(subset=["date", "stock_id"], keep="last")
        return work.drop(columns=["_priority"])[df.columns]

    def upsert(self, df: pd.DataFrame) -> None:
        """
        - Description:
            以 `INSERT OR REPLACE` 寫入，讓重跑與跨來源覆蓋成為冪等操作
        - Parameters:
            - df: pd.DataFrame
                要寫入的資料
        """

        if df.empty:
            return

        columns: List[str] = list(df.columns)
        placeholders: str = ", ".join("?" for _ in columns)
        quoted: str = ", ".join(f'"{column}"' for column in columns)
        query: str = (
            f"INSERT OR REPLACE INTO {CORPORATE_ACTION_TABLE_NAME} "
            f"({quoted}) VALUES ({placeholders})"
        )

        self.conn.executemany(query, df.itertuples(index=False, name=None))
        logger.info(f"[corporate_action] 寫入 {len(df)} 列")
