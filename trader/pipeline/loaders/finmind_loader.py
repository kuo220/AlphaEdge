import sqlite3
from pathlib import Path
from typing import List, Optional, Set, Tuple

import pandas as pd
from loguru import logger

from trader.config import (
    DB_PATH,
    FINMIND_DOWNLOADS_PATH,
    SECURITIES_TRADER_INFO_TABLE_NAME,
    STOCK_INFO_TABLE_NAME,
    STOCK_INFO_WITH_WARRANT_TABLE_NAME,
    STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
)
from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.utils import FinMindDataType
from trader.pipeline.utils.sqlite_utils import SQLiteUtils


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
            self.conn: sqlite3.Connection = sqlite3.connect(DB_PATH)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        if self.conn:
            self.conn.close()
            self.conn: Optional[sqlite3.Connection] = None

    def create_db(self, *args, **kwargs) -> None:
        """Create New Database Tables"""

        # 創建四個資料表
        self._create_stock_info_table()
        self._create_stock_info_with_warrant_table()
        self._create_broker_info_table()
        self._create_broker_trading_daily_report_table()

    def _create_stock_info_table(self) -> None:
        """創建台股總覽資料表"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {STOCK_INFO_TABLE_NAME}(
            "industry_category" TEXT,
            "stock_id" TEXT NOT NULL,
            "stock_name" TEXT,
            "type" TEXT,
            "date" TEXT,
            PRIMARY KEY ("stock_id")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{STOCK_INFO_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(f"Table {STOCK_INFO_TABLE_NAME} create successfully!")
        else:
            logger.warning(f"Table {STOCK_INFO_TABLE_NAME} create unsuccessfully!")

        self.conn.commit()

    def _create_stock_info_with_warrant_table(self) -> None:
        """創建台股總覽(含權證)資料表"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {STOCK_INFO_WITH_WARRANT_TABLE_NAME}(
            "industry_category" TEXT,
            "stock_id" TEXT NOT NULL,
            "stock_name" TEXT,
            "type" TEXT,
            "date" TEXT,
            PRIMARY KEY ("stock_id")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{STOCK_INFO_WITH_WARRANT_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(
                f"Table {STOCK_INFO_WITH_WARRANT_TABLE_NAME} create successfully!"
            )
        else:
            logger.warning(
                f"Table {STOCK_INFO_WITH_WARRANT_TABLE_NAME} create unsuccessfully!"
            )

        self.conn.commit()

    def _create_broker_info_table(self) -> None:
        """創建證券商資訊表"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {SECURITIES_TRADER_INFO_TABLE_NAME}(
            "securities_trader_id" TEXT NOT NULL,
            "securities_trader" TEXT,
            "date" TEXT,
            "address" TEXT,
            "phone" TEXT,
            PRIMARY KEY ("securities_trader_id")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{SECURITIES_TRADER_INFO_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(
                f"Table {SECURITIES_TRADER_INFO_TABLE_NAME} create successfully!"
            )
        else:
            logger.warning(
                f"Table {SECURITIES_TRADER_INFO_TABLE_NAME} create unsuccessfully!"
            )

        self.conn.commit()

    def _create_broker_trading_daily_report_table(self) -> None:
        """創建當日券商分點統計表"""

        cursor: sqlite3.Cursor = self.conn.cursor()

        create_table_query: str = f"""
        CREATE TABLE IF NOT EXISTS {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}(
            "securities_trader" TEXT,
            "securities_trader_id" TEXT NOT NULL,
            "stock_id" TEXT NOT NULL,
            "date" TEXT NOT NULL,
            "buy_volume" INTEGER,
            "sell_volume" INTEGER,
            "buy_price" REAL,
            "sell_price" REAL,
            PRIMARY KEY ("stock_id", "date", "securities_trader_id")
        );
        """
        cursor.execute(create_table_query)

        # 檢查是否成功建立 table
        cursor.execute(f"PRAGMA table_info('{STOCK_TRADING_DAILY_REPORT_TABLE_NAME}')")
        if cursor.fetchall():
            logger.info(
                f"Table {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} create successfully!"
            )
        else:
            logger.warning(
                f"Table {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} create unsuccessfully!"
            )

        self.conn.commit()

    def create_missing_tables(self) -> None:
        """確保所有 FinMind 資料表存在"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=STOCK_INFO_TABLE_NAME
        ):
            self._create_stock_info_table()

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=STOCK_INFO_WITH_WARRANT_TABLE_NAME
        ):
            self._create_stock_info_with_warrant_table()

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=SECURITIES_TRADER_INFO_TABLE_NAME
        ):
            self._create_broker_info_table()

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=STOCK_TRADING_DAILY_REPORT_TABLE_NAME
        ):
            self._create_broker_trading_daily_report_table()

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
            import shutil

            shutil.rmtree(self.finmind_dir)
            logger.info(f"Removed directory: {self.finmind_dir}")

    def load_stock_info(self) -> None:
        """載入台股總覽資料到資料庫"""

        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.STOCK_INFO.value.lower()
        )
        csv_path: Path = data_type_dir / "taiwan_stock_info.csv"

        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            return

        try:
            logger.info(f"Loading stock info from {csv_path.name}...")
            df: pd.DataFrame = pd.read_csv(csv_path)

            if df.empty:
                logger.warning(f"Skipped {csv_path.name} (file is empty)")
                return

            # 查詢資料庫中已存在的資料
            existing_query: str = f"""
            SELECT stock_id
            FROM {STOCK_INFO_TABLE_NAME}
            """
            existing_df: pd.DataFrame = pd.read_sql_query(existing_query, self.conn)

            # 先處理同一個檔案內的重複資料
            original_count: int = len(df)
            if df["stock_id"].duplicated().any():
                df = df.drop_duplicates(subset=["stock_id"], keep="first")
                logger.debug(
                    f"Removed {original_count - len(df)} duplicate rows within {csv_path.name}"
                )

            # 建立已存在的 stock_id set
            existing_stock_ids: Set[str] = set()
            if not existing_df.empty:
                existing_stock_ids = set(existing_df["stock_id"].astype(str))  # type: ignore
                logger.info(
                    f"Loaded {len(existing_stock_ids)} existing records from database"
                )

            # 過濾出新資料
            if existing_stock_ids:
                mask: pd.Series = ~df["stock_id"].astype(str).isin(existing_stock_ids)
                new_df: pd.DataFrame = df[mask]

                if new_df.empty:
                    logger.info(f"Skipped {csv_path.name} (all data already exists)")
                    return
            else:
                new_df: pd.DataFrame = df

            # 確保欄位順序與 crawler schema 註解一致
            # 順序：industry_category, stock_id, stock_name, type, date
            column_order: List[str] = [
                "industry_category",
                "stock_id",
                "stock_name",
                "type",
                "date",
            ]
            new_df = new_df[column_order]

            # 插入新資料
            new_df.to_sql(
                STOCK_INFO_TABLE_NAME,
                self.conn,
                if_exists="append",
                index=False,
            )

            skipped_rows: int = original_count - len(new_df)
            if skipped_rows > 0:
                logger.info(
                    f"Saved {csv_path.name} into database ({len(new_df)} new rows, {skipped_rows} skipped)"
                )
            else:
                logger.info(f"Saved {csv_path.name} into database ({len(new_df)} rows)")

        except Exception as e:
            logger.error(f"Error loading {csv_path.name}: {e}", exc_info=True)

    def load_stock_info_with_warrant(self) -> None:
        """載入台股總覽(含權證)資料到資料庫"""

        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.STOCK_INFO_WITH_WARRANT.value.lower()
        )
        csv_path: Path = data_type_dir / "taiwan_stock_info_with_warrant.csv"

        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            return

        try:
            logger.info(f"Loading stock info with warrant from {csv_path.name}...")
            df: pd.DataFrame = pd.read_csv(csv_path)

            if df.empty:
                logger.warning(f"Skipped {csv_path.name} (file is empty)")
                return

            # 查詢資料庫中已存在的資料
            existing_query: str = f"""
            SELECT stock_id
            FROM {STOCK_INFO_WITH_WARRANT_TABLE_NAME}
            """
            existing_df: pd.DataFrame = pd.read_sql_query(existing_query, self.conn)

            # 先處理同一個檔案內的重複資料
            original_count: int = len(df)
            if df["stock_id"].duplicated().any():
                df = df.drop_duplicates(subset=["stock_id"], keep="first")
                logger.debug(
                    f"Removed {original_count - len(df)} duplicate rows within {csv_path.name}"
                )

            # 建立已存在的 stock_id set
            existing_stock_ids: Set[str] = set()
            if not existing_df.empty:
                existing_stock_ids = set(existing_df["stock_id"].astype(str))  # type: ignore
                logger.info(
                    f"Loaded {len(existing_stock_ids)} existing records from database"
                )

            # 過濾出新資料
            if existing_stock_ids:
                mask: pd.Series = ~df["stock_id"].astype(str).isin(existing_stock_ids)
                new_df: pd.DataFrame = df[mask]

                if new_df.empty:
                    logger.info(f"Skipped {csv_path.name} (all data already exists)")
                    return
            else:
                new_df: pd.DataFrame = df

            # 確保欄位順序與 crawler schema 註解一致
            # 順序：industry_category, stock_id, stock_name, type, date
            column_order: List[str] = [
                "industry_category",
                "stock_id",
                "stock_name",
                "type",
                "date",
            ]
            new_df = new_df[column_order]

            # 插入新資料
            new_df.to_sql(
                STOCK_INFO_WITH_WARRANT_TABLE_NAME,
                self.conn,
                if_exists="append",
                index=False,
            )

            skipped_rows: int = original_count - len(new_df)
            if skipped_rows > 0:
                logger.info(
                    f"Saved {csv_path.name} into database ({len(new_df)} new rows, {skipped_rows} skipped)"
                )
            else:
                logger.info(f"Saved {csv_path.name} into database ({len(new_df)} rows)")

        except Exception as e:
            logger.error(f"Error loading {csv_path.name}: {e}", exc_info=True)

    def load_broker_info(self) -> None:
        """載入證券商資訊表資料到資料庫"""

        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.BROKER_INFO.value.lower()
        )
        csv_path: Path = data_type_dir / "taiwan_securities_trader_info.csv"

        if not csv_path.exists():
            logger.warning(f"CSV file not found: {csv_path}")
            return

        try:
            logger.info(f"Loading broker info from {csv_path.name}...")
            df: pd.DataFrame = pd.read_csv(csv_path)

            if df.empty:
                logger.warning(f"Skipped {csv_path.name} (file is empty)")
                return

            # 查詢資料庫中已存在的資料
            existing_query: str = f"""
            SELECT securities_trader_id
            FROM {SECURITIES_TRADER_INFO_TABLE_NAME}
            """
            existing_df: pd.DataFrame = pd.read_sql_query(existing_query, self.conn)

            # 先處理同一個檔案內的重複資料
            original_count: int = len(df)
            if df["securities_trader_id"].duplicated().any():
                df = df.drop_duplicates(subset=["securities_trader_id"], keep="first")
                logger.debug(
                    f"Removed {original_count - len(df)} duplicate rows within {csv_path.name}"
                )

            # 建立已存在的 broker_id set
            existing_broker_ids: Set[str] = set()
            if not existing_df.empty:
                existing_broker_ids = set(
                    existing_df["securities_trader_id"].astype(str)
                )  # type: ignore
                logger.info(
                    f"Loaded {len(existing_broker_ids)} existing records from database"
                )

            # 過濾出新資料
            if existing_broker_ids:
                mask: pd.Series = (
                    ~df["securities_trader_id"].astype(str).isin(existing_broker_ids)
                )
                new_df: pd.DataFrame = df[mask]

                if new_df.empty:
                    logger.info(f"Skipped {csv_path.name} (all data already exists)")
                    return
            else:
                new_df: pd.DataFrame = df

            # 確保欄位順序與 crawler schema 註解一致
            # 順序：securities_trader_id, securities_trader, date, address, phone
            column_order: List[str] = [
                "securities_trader_id",
                "securities_trader",
                "date",
                "address",
                "phone",
            ]
            new_df = new_df[column_order]

            # 插入新資料
            new_df.to_sql(
                SECURITIES_TRADER_INFO_TABLE_NAME,
                self.conn,
                if_exists="append",
                index=False,
            )

            skipped_rows: int = original_count - len(new_df)
            if skipped_rows > 0:
                logger.info(
                    f"Saved {csv_path.name} into database ({len(new_df)} new rows, {skipped_rows} skipped)"
                )
            else:
                logger.info(f"Saved {csv_path.name} into database ({len(new_df)} rows)")

        except Exception as e:
            logger.error(f"Error loading {csv_path.name}: {e}", exc_info=True)

    def load_broker_trading_daily_report(
        self, df: Optional[pd.DataFrame] = None
    ) -> Optional[int]:
        """載入當日券商分點統計表資料到資料庫

        如果傳入 df 參數，則直接從 DataFrame 載入；否則從 CSV 檔案載入。

        Args:
            df: 可選的 DataFrame，如果提供則直接載入此 DataFrame。
                必須包含以下欄位：
                - stock_id
                - date
                - securities_trader_id
                - buy_volume, sell_volume, buy_price, sell_price (可選)
                - securities_trader (可選)
                如果為 None，則從 CSV 檔案載入（檔案結構：broker_trading/{broker_id}/{stock_id}.csv）

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
            return self._load_broker_trading_daily_report_from_dataframe(df)
        else:
            # 從 CSV 檔案載入
            self._load_broker_trading_daily_report_from_files()
            return None

    def _load_broker_trading_daily_report_from_dataframe(self, df: pd.DataFrame) -> int:
        """從 DataFrame 載入當日券商分點統計表資料到資料庫

        Args:
            df: 要載入的 DataFrame

        Returns:
            int: 成功插入的資料筆數
        """
        if df is None or df.empty:
            logger.warning("DataFrame is empty, skipping load")
            return 0

        # 查詢資料庫中已存在的資料（根據複合主鍵）
        existing_query: str = f"""
        SELECT DISTINCT stock_id, date, securities_trader_id
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        """
        try:
            existing_df: pd.DataFrame = pd.read_sql_query(existing_query, self.conn)

            if not existing_df.empty:
                # 建立已存在的鍵集合
                existing_keys: Set[Tuple[str, str, str]] = set(
                    zip(
                        existing_df["stock_id"].astype(str),
                        existing_df["date"].astype(str),
                        existing_df["securities_trader_id"].astype(str),
                    )
                )
            else:
                existing_keys: Set[Tuple[str, str, str]] = set()

            # 建立當前資料的 key tuple
            df["_key"] = list(
                zip(
                    df["stock_id"].astype(str),
                    df["date"].astype(str),
                    df["securities_trader_id"].astype(str),
                )
            )

            # 先處理同一個 DataFrame 內的重複資料
            original_count: int = len(df)
            if df["_key"].duplicated().any():
                df = df.drop_duplicates(subset=["_key"], keep="first")
                logger.debug(
                    f"Removed {original_count - len(df)} duplicate rows within DataFrame"
                )

            # 過濾出新資料
            if existing_keys:
                mask: pd.Series = ~df["_key"].isin(existing_keys)
                new_df: pd.DataFrame = df[mask].drop(columns=["_key"])

                if new_df.empty:
                    logger.debug("All data already exists in database, skipping insert")
                    return 0
            else:
                new_df: pd.DataFrame = df.drop(columns=["_key"])

            # 確保欄位順序與 crawler schema 註解一致
            # 順序：securities_trader, securities_trader_id, stock_id, date, buy_volume, sell_volume, buy_price, sell_price
            column_order: List[str] = [
                "securities_trader",
                "securities_trader_id",
                "stock_id",
                "date",
                "buy_volume",
                "sell_volume",
                "buy_price",
                "sell_price",
            ]
            # 只選擇存在的欄位
            available_columns: List[str] = [
                col for col in column_order if col in new_df.columns
            ]
            new_df = new_df[available_columns]

            # 插入新資料
            new_df.to_sql(
                STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
                self.conn,
                if_exists="append",
                index=False,
            )
            self.conn.commit()

            skipped_rows: int = original_count - len(new_df)
            if skipped_rows > 0:
                logger.info(
                    f"✅ Saved {len(new_df)} new records to database "
                    f"({skipped_rows} duplicates skipped)"
                )
            else:
                logger.info(f"✅ Saved {len(new_df)} records to database")

            return len(new_df)

        except Exception as e:
            logger.error(
                f"Error loading broker trading daily report from DataFrame: {e}",
                exc_info=True,
            )
            # 如果檢查失敗，嘗試直接插入（可能會因為重複鍵而失敗，但至少嘗試）
            try:
                column_order: List[str] = [
                    "securities_trader",
                    "securities_trader_id",
                    "stock_id",
                    "date",
                    "buy_volume",
                    "sell_volume",
                    "buy_price",
                    "sell_price",
                ]
                available_columns: List[str] = [
                    col for col in column_order if col in df.columns
                ]
                df[available_columns].to_sql(
                    STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
                    self.conn,
                    if_exists="append",
                    index=False,
                )
                self.conn.commit()
                logger.info(f"✅ Saved {len(df)} records to database (fallback mode)")
                return len(df)
            except Exception as insert_error:
                logger.error(f"Error inserting data to database: {insert_error}")
                return 0

    def _load_broker_trading_daily_report_from_files(self) -> None:
        """載入當日券商分點統計表資料到資料庫

        新的檔案結構：broker_trading/{broker_id}/{stock_id}.csv
        會遍歷所有 broker_id 資料夾，讀取每個 stock_id 的 CSV 檔案
        """

        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.BROKER_TRADING.value.lower()
        )

        if not data_type_dir.exists():
            logger.warning(f"Directory not found: {data_type_dir}")
            return

        # 查詢資料庫中已存在的資料（根據複合主鍵）
        existing_query: str = f"""
        SELECT stock_id, date, securities_trader_id
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        """
        existing_df: pd.DataFrame = pd.read_sql_query(existing_query, self.conn)

        # 建立已存在的 key set
        existing_keys: Set[Tuple[str, str, str]] = set()
        if not existing_df.empty:
            existing_keys = set(
                zip(
                    existing_df["stock_id"].astype(str),
                    existing_df["date"].astype(str),
                    existing_df["securities_trader_id"].astype(str),
                )
            )  # type: ignore
            logger.info(f"Loaded {len(existing_keys)} existing records from database")

        # 遍歷所有 broker_id 資料夾
        broker_dirs: List[Path] = [d for d in data_type_dir.iterdir() if d.is_dir()]

        if not broker_dirs:
            logger.warning(f"No broker directories found in {data_type_dir}")
            return

        logger.info(f"Found {len(broker_dirs)} broker directories to process")

        total_new_rows: int = 0
        total_skipped_rows: int = 0
        processed_files: int = 0
        skipped_files: int = 0

        # 遍歷每個 broker_id 資料夾
        for broker_dir in broker_dirs:
            broker_id: str = broker_dir.name
            # 取得該 broker 資料夾下的所有 CSV 檔案
            csv_files: List[Path] = list(broker_dir.glob("*.csv"))

            for csv_path in csv_files:
                stock_id: str = csv_path.stem  # 檔名（不含副檔名）就是 stock_id
                processed_files += 1

                try:
                    logger.debug(
                        f"Loading broker trading daily report from "
                        f"broker_id={broker_id}, stock_id={stock_id}..."
                    )
                    df: pd.DataFrame = pd.read_csv(csv_path, encoding="utf-8-sig")

                    if df.empty:
                        logger.debug(
                            f"Skipped {broker_id}/{stock_id}.csv (file is empty)"
                        )
                        skipped_files += 1
                        continue

                    # 建立當前資料的 key tuple
                    df["_key"] = list(
                        zip(
                            df["stock_id"].astype(str),
                            df["date"].astype(str),
                            df["securities_trader_id"].astype(str),
                        )
                    )

                    # 先處理同一個檔案內的重複資料
                    original_count: int = len(df)
                    if df["_key"].duplicated().any():
                        df = df.drop_duplicates(subset=["_key"], keep="first")
                        logger.debug(
                            f"Removed {original_count - len(df)} duplicate rows "
                            f"within {broker_id}/{stock_id}.csv"
                        )

                    # 過濾出新資料
                    if existing_keys:
                        mask: pd.Series = ~df["_key"].isin(existing_keys)
                        new_df: pd.DataFrame = df[mask].drop(columns=["_key"])

                        if new_df.empty:
                            logger.debug(
                                f"Skipped {broker_id}/{stock_id}.csv "
                                f"(all data already exists)"
                            )
                            skipped_files += 1
                            continue
                    else:
                        new_df: pd.DataFrame = df.drop(columns=["_key"])

                    # 確保欄位順序與 crawler schema 註解一致
                    # 順序：securities_trader, securities_trader_id, stock_id, date, buy_volume, sell_volume, buy_price, sell_price
                    column_order: List[str] = [
                        "securities_trader",
                        "securities_trader_id",
                        "stock_id",
                        "date",
                        "buy_volume",
                        "sell_volume",
                        "buy_price",
                        "sell_price",
                    ]
                    # 只選擇存在的欄位
                    available_columns: List[str] = [
                        col for col in column_order if col in new_df.columns
                    ]
                    new_df = new_df[available_columns]

                    # 插入新資料
                    new_df.to_sql(
                        STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
                        self.conn,
                        if_exists="append",
                        index=False,
                    )

                    skipped_rows: int = original_count - len(new_df)
                    total_new_rows += len(new_df)
                    total_skipped_rows += skipped_rows

                    if skipped_rows > 0:
                        logger.debug(
                            f"Saved {broker_id}/{stock_id}.csv into database "
                            f"({len(new_df)} new rows, {skipped_rows} skipped)"
                        )
                    else:
                        logger.debug(
                            f"Saved {broker_id}/{stock_id}.csv into database "
                            f"({len(new_df)} rows)"
                        )

                    # 更新 existing_keys，避免後續檔案重複處理相同資料
                    new_keys: Set[Tuple[str, str, str]] = set(
                        zip(
                            new_df["stock_id"].astype(str),
                            new_df["date"].astype(str),
                            new_df["securities_trader_id"].astype(str),
                        )
                    )
                    existing_keys.update(new_keys)

                except Exception as e:
                    logger.error(
                        f"Error loading {broker_id}/{stock_id}.csv: {e}",
                        exc_info=True,
                    )
                    skipped_files += 1
                    continue

        # 輸出總結
        logger.info(
            f"✅ Broker trading daily report loading completed. "
            f"Processed {processed_files} files, skipped {skipped_files} files. "
            f"Total: {total_new_rows} new rows, {total_skipped_rows} skipped rows"
        )
