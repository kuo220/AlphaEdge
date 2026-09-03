import sqlite3
from pathlib import Path
from typing import List, Optional, Set

import pandas as pd
from loguru import logger

from core.config import PRICE_DOWNLOADS_PATH, PRICE_TABLE_NAME, TW_STOCK_DB_PATH
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils.sqlite_utils import SQLiteUtils


class StockPriceLoader(BaseDataLoader):
    """Stock Price Loader"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.price_dir: Path = PRICE_DOWNLOADS_PATH

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.price_dir.mkdir(parents=True, exist_ok=True)

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
        """Create New Database"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {PRICE_TABLE_NAME}(
            "date" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "證券名稱" TEXT NOT NULL,
            "開盤價" REAL,
            "最高價" REAL,
            "最低價" REAL,
            "收盤價" REAL,
            "漲跌價差" REAL,
            "成交股數" INTEGER,
            "成交金額" INTEGER,
            "成交筆數" INTEGER,
            "最後揭示買價" REAL,
            "最後揭示買量" INTEGER,
            "最後揭示賣價" REAL,
            "最後揭示賣量" INTEGER,
            "本益比" REAL,
            PRIMARY KEY ("date", "stock_id", "證券名稱")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{PRICE_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {PRICE_TABLE_NAME} create successfully!")
        else:
            logger.warning(f"Table {PRICE_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保股票價格資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=PRICE_TABLE_NAME
        ):
            self.create_db()

        # 主鍵是 (date, stock_id, ...)，「某一檔的整段歷史」查不到索引（F-099）
        self.create_symbol_date_index(self.conn, PRICE_TABLE_NAME)

    def add_to_db(
        self,
        remove_files: bool = False,
        only_dates: Optional[Set[str]] = None,
    ) -> None:
        """
        - Description:
            將 downloads 內的 CSV 入庫；**有任何檔案失敗就拋 `DataLoadError`**

            舊版逐檔 `except Exception` 後只記 `logger.error` 並 `error_cnt += 1`，
            跑完照樣印一行 summary 就結束，行程結束碼是 0（健檢 F-043）。
            這與 2026-08-16 margin 事故是同一個形狀：缺的列要事後逐日比對才會發現。

            **去重改走 `INSERT OR IGNORE`**：舊版每批都把整張 `price` 表的主鍵
            （近 1,300 萬列）讀進記憶體建 set（F-044）。改用資料庫自己的主鍵約束，
            記憶體不再隨資料量成長，且「重跑」與「真的出錯」仍分得開——
            重複列靜靜跳過，欄位不符、檔案損毀才會拋出。
        - Parameters:
            - remove_files: bool
                全部成功後是否刪除 downloads 目錄
            - only_dates: Optional[Set[str]]
                只處理這些日期（`YYYYMMDD`）的檔案；None 表示整個目錄
        - Raise:
            - DataLoadError
                有任何檔案入庫失敗
        """

        if self.conn is None:
            self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        # 取得要處理的 CSV 並排序，確保處理順序一致
        csv_files: List[Path] = self.select_csv_files(self.price_dir, only_dates)
        total_files: int = len(csv_files)

        if total_files == 0:
            logger.info("No CSV files found in price directory")
            return

        logger.info(f"Found {total_files} CSV files to process")

        succeeded: int = 0
        skipped_files: int = 0
        failed_files: List[str] = []

        for idx, file_path in enumerate(csv_files, start=1):
            try:
                logger.info(f"Processing [{idx}/{total_files}] {file_path.name}...")

                df: pd.DataFrame = pd.read_csv(file_path)

                if df.empty:
                    logger.warning(f"Skipped {file_path.name} (file is empty)")
                    skipped_files += 1
                    continue

                # 同一檔內的重複列先去掉：`INSERT OR IGNORE` 擋得掉，
                # 但先去掉才數得準「這檔到底寫進去幾列」
                original_count: int = len(df)
                df = df.drop_duplicates(
                    subset=["date", "stock_id", "證券名稱"], keep="first"
                )
                if len(df) < original_count:
                    logger.debug(
                        f"Removed {original_count - len(df)} duplicate rows "
                        f"within {file_path.name}"
                    )

                inserted: int
                ignored: int
                inserted, ignored = self.insert_dataframe(
                    self.conn, PRICE_TABLE_NAME, df
                )
            except Exception as e:
                logger.error(f"Error saving {file_path.name}: {e}")
                failed_files.append(file_path.name)
                continue

            if inserted == 0:
                logger.info(f"Skipped {file_path.name} (all data already exists)")
                skipped_files += 1
                continue

            if ignored:
                # **不進 `partial_files`**：`INSERT OR IGNORE` 只知道「主鍵已存在」，
                # 不知道值有沒有不同。重跑一個部分入庫過的日期（例如 `--from`
                # 往前拉）本來就會有大量 ignored，把它當成「同鍵不同值」示警
                # 只會訓練讀 log 的人忽略那行警告
                logger.info(
                    f"Saved {file_path.name} into database "
                    f"({inserted} new rows, {ignored} already existed)"
                )
            else:
                logger.info(f"Saved {file_path.name} into database ({inserted} rows)")
            succeeded += 1

        self.conn.commit()
        self.disconnect()

        self.finish_load(
            source="price",
            succeeded=succeeded,
            failed_files=failed_files,
            remove_files=remove_files,
            downloads_path=self.price_dir,
            skipped_files=skipped_files,
        )
