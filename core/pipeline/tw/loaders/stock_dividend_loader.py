import sqlite3
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import DIVIDEND_DOWNLOADS_PATH, DIVIDEND_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
Stock Dividend Loader

與其他 loader 的差異：本表的三個來源會**合法地重疊**——上櫃同一筆除權息可能同時來自
FinMind 歷史回補與 TPEX 日更。因此入庫走 `INSERT OR REPLACE` 而非 `append`，
且在寫入前先跨檔去重，避免同批資料撞主鍵讓整個檔案被 except 吞掉。
"""


class StockDividendLoader(BaseDataLoader):
    """Stock Dividend Loader"""

    # 同一筆除權息若跨來源重複，保留優先序**最高**的那一筆。
    #
    # **不可依檔名字典序決定**（健檢 F-047）：舊版直接對 `sorted(dir.iterdir())`
    # 的結果 `drop_duplicates(keep="last")`，於是「留下哪一筆」取決於檔名的
    # 字母順序——今天剛好是 `twse_` 勝出，日後多一個來源（例如 `finmind_`）
    # 或檔名改個前綴，勝出的就換人，而且不會有任何跡象。
    #
    # 排序原則：交易所官方資料優先於第三方回補。清單中沒列到的來源排在最後。
    SOURCE_PRIORITY: List[str] = ["finmind", "tpex", "twse"]

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.dividend_dir: Path = DIVIDEND_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.dividend_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(self) -> None:
        """創建除權除息計算結果表 db"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        # 價格單位為元；還原係數 = 除權息參考價 / 除權息前收盤價（恆 < 1）
        # 現金股利單位為元／股；配股率為每股配股數（純除息時為 0）
        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {DIVIDEND_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "證券名稱" TEXT,
            "除權息前收盤價" REAL NOT NULL,
            "除權息參考價" REAL NOT NULL,
            "權息值合計" REAL,
            "權息別" TEXT,
            "現金股利" REAL,
            "配股率" REAL,
            "漲停價" REAL,
            "跌停價" REAL,
            "開盤競價基準" REAL,
            "減除股利參考價" REAL,
            "還原係數" REAL NOT NULL,
            "資料來源" TEXT NOT NULL,
            PRIMARY KEY ("date", "stock_id")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{DIVIDEND_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {DIVIDEND_TABLE_NAME} create successfully!")
        else:
            logger.warning(f"Table {DIVIDEND_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保除權除息資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=DIVIDEND_TABLE_NAME
        ):
            self.create_db()

        # 主鍵是 (date, stock_id, ...)，「某一檔的整段歷史」查不到索引（F-099）
        self.create_symbol_date_index(self.conn, DIVIDEND_TABLE_NAME)

    def add_to_db(self, remove_files: bool = False) -> None:
        """將資料夾中的所有 CSV 檔存入指定 SQLite 資料庫中的指定資料表"""

        if self.conn is None:
            self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        file_cnt: int = 0

        failed_files: List[str] = []
        dfs: List[pd.DataFrame] = []
        for file_path in sorted(self.dividend_dir.iterdir()):
            # Skip non-CSV files
            if file_path.suffix != ".csv":
                continue
            try:
                df: pd.DataFrame = pd.read_csv(file_path, dtype={"stock_id": str})
                dfs.append(df)
                file_cnt += 1
            except Exception as e:
                logger.warning(f"Error reading {file_path}: {e}")
                failed_files.append(str(file_path))

        if not dfs:
            logger.warning("No dividend CSV file to load")
            self.disconnect()
            return

        # 跨檔去重：同一筆除權息可能同時來自 FinMind 回補與 TPEX 日更
        merged_df: pd.DataFrame = pd.concat(dfs, ignore_index=True)
        row_cnt: int = len(merged_df)
        merged_df = self.dedup_by_source_priority(merged_df)
        logger.info(f"Dividend rows: {row_cnt} -> {len(merged_df)} after dedup")

        self.upsert(merged_df)

        self.conn.commit()
        self.disconnect()

        self.finish_load(
            source="dividend",
            succeeded=file_cnt,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=DIVIDEND_DOWNLOADS_PATH,
        )

    def dedup_by_source_priority(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        - Description:
            以「來源優先序」跨檔去重，而不是以檔名字典序

            同一個 `(date, stock_id)` 可能同時來自多個來源；依 `SOURCE_PRIORITY`
            由低到高排序後 `keep="last"`，勝出的就是優先序最高的那一筆。
        - Parameters:
            - df: pd.DataFrame
                合併後的除權息資料
        - Return:
            - pd.DataFrame
                去重後的資料（欄位順序不變）
        """

        if "資料來源" not in df.columns:
            logger.warning("除權息資料沒有「資料來源」欄，退回以出現順序去重")
            return df.drop_duplicates(subset=["date", "stock_id"], keep="last")

        # 清單中沒列到的來源排在最前（優先序最低）
        rank: pd.Series = (
            df["資料來源"]
            .map(
                {
                    source: index
                    for index, source in enumerate(self.SOURCE_PRIORITY, start=1)
                }
            )
            .fillna(0)
        )

        unknown: Set[str] = set(df.loc[rank == 0, "資料來源"].unique())
        if unknown:
            logger.warning(
                f"除權息出現未列入優先序的來源 {sorted(unknown)}，"
                f"將被排在最後（優先序最低）；請補進 SOURCE_PRIORITY"
            )

        ordered: pd.DataFrame = df.assign(_rank=rank).sort_values(
            "_rank", kind="stable"
        )
        deduped: pd.DataFrame = ordered.drop_duplicates(
            subset=["date", "stock_id"], keep="last"
        )
        return deduped.drop(columns=["_rank"]).sort_values(
            ["date", "stock_id"], kind="stable"
        )

    def upsert(self, df: pd.DataFrame) -> None:
        """
        - Description:
            以 `INSERT OR REPLACE` 寫入，讓重跑與跨來源覆蓋成為冪等操作

        - Parameters:
            - df: pd.DataFrame
                已去重的除權除息資料
        """

        cursor: sqlite3.Cursor = self.conn.cursor()
        columns: List[str] = list(df.columns)
        col_clause: str = ", ".join(f'"{col}"' for col in columns)
        placeholders: str = ", ".join("?" for _ in columns)

        insert_query: str = f"""
        INSERT OR REPLACE INTO {DIVIDEND_TABLE_NAME} ({col_clause})
        VALUES ({placeholders})
        """
        cursor.executemany(insert_query, df.itertuples(index=False, name=None))
        logger.info(f"Upserted {len(df)} rows into {DIVIDEND_TABLE_NAME}")
