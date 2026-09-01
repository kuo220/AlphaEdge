import shutil
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
from loguru import logger

from core.config import (
    FINMIND_DOWNLOADS_PATH,
    SECURITIES_TRADER_INFO_TABLE_NAME,
    STOCK_INFO_TABLE_NAME,
    STOCK_INFO_WITH_WARRANT_TABLE_NAME,
    TW_STOCK_DB_PATH,
)
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.tw.loaders.finmind import (
    broker_info_loader,
    broker_trading_loader,
    schema,
    stock_info_loader,
)
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
FinMind Loader

本檔是**門面（facade）**：對外介面與呼叫方式維持不變，四張表的 schema 與各自的
入庫流程拆在 `core/pipeline/tw/loaders/finmind/` 底下（見該套件的說明）。
"""


class FinMindLoader(BaseDataLoader):
    """FinMind Loader - 將 FinMind 資料存入 Sqlite3"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # Downloads directory Path
        self.finmind_dir: Path = FINMIND_DOWNLOADS_PATH

        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""
        self.connect()

        # Ensure Database Tables Exist
        self.create_missing_tables()

        self.finmind_dir.mkdir(parents=True, exist_ok=True)

    def connect(self) -> None:
        """Connect to the Database"""

        if self.conn is None:
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(self, *args, **kwargs) -> None:
        """Create New Database Tables"""

        # 創建四個資料表
        schema.create_stock_info_table(self.conn)
        schema.create_stock_info_with_warrant_table(self.conn)
        schema.create_broker_info_table(self.conn)
        schema.create_broker_trading_daily_report_table(self.conn)

    def create_missing_tables(self) -> None:
        """確保所有 FinMind 資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=STOCK_INFO_TABLE_NAME
        ):
            schema.create_stock_info_table(self.conn)

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=STOCK_INFO_WITH_WARRANT_TABLE_NAME
        ):
            schema.create_stock_info_with_warrant_table(self.conn)

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=SECURITIES_TRADER_INFO_TABLE_NAME
        ):
            schema.create_broker_info_table(self.conn)

        # broker trading 表與索引：每次都呼叫，表已存在時 CREATE TABLE/INDEX IF NOT EXISTS 為 no-op
        schema.create_broker_trading_daily_report_table(self.conn)

    def add_to_db(self, remove_files: bool = False) -> None:
        """Add Data into Database from CSV files"""

        if self.conn is None:
            self.connect()

        # Ensure Database Tables Exist
        self.create_missing_tables()

        # 處理四個 CSV 檔案
        self.load_stock_info()
        self.load_stock_info_with_warrant()
        self.load_broker_info()
        self.load_broker_trading_daily_report()  # 不傳入 df，從 CSV 檔案載入

        self.conn.commit()
        self.disconnect()

        if remove_files:
            shutil.rmtree(self.finmind_dir)
            logger.info(f"Removed directory: {self.finmind_dir}")

    def load_stock_info(self) -> None:
        """載入台股總覽資料到資料庫"""

        stock_info_loader.load_stock_info(self.conn, self.finmind_dir)

    def load_stock_info_with_warrant(self) -> None:
        """載入台股總覽(含權證)資料到資料庫"""

        stock_info_loader.load_stock_info_with_warrant(self.conn, self.finmind_dir)

    def load_broker_info(self) -> None:
        """載入證券商資訊表資料到資料庫"""

        broker_info_loader.load_broker_info(self.conn, self.finmind_dir)

    def load_broker_trading_daily_report(
        self,
        df: Optional[pd.DataFrame] = None,
        commit: bool = True,
    ) -> Optional[int]:
        """載入當日券商分點統計表資料到資料庫

        如果傳入 df 參數，則直接從 DataFrame 載入；否則從 CSV 檔案載入

        Args:
            df: 可選的 DataFrame，如果提供則直接載入此 DataFrame
                必須包含以下欄位：
                - stock_id
                - date
                - securities_trader_id
                - buy_volume, sell_volume, buy_price, sell_price (可選)
                - securities_trader (可選)
                如果為 None，則從 CSV 檔案載入（檔案結構：broker_trading/{broker_id}/{stock_id}.csv）
            commit: 是否在寫入後立即 commit；若為 False（例如批次更新時由 updater 定期 commit），則不呼叫 conn.commit()

        Returns:
            int: 如果從 DataFrame 載入，返回成功插入的資料筆數
            None: 如果從 CSV 檔案載入，不返回值
        """
        if self.conn is None:
            self.connect()

        # 確保資料表存在
        self.create_missing_tables()

        # 如果提供了 DataFrame，直接載入
        if df is not None:
            return broker_trading_loader.load_from_dataframe(
                self.conn, df, commit=commit
            )
        else:
            # 從 CSV 檔案載入
            broker_trading_loader.load_from_files(self.conn, self.finmind_dir)
            return None
