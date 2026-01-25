import shutil
from pathlib import Path
from typing import List

from loguru import logger

try:
    import dolphindb as ddb
except ModuleNotFoundError:
    logger.info("Warning: dolphindb module is not installed")

from trader.config import (
    DDB_HOST,
    DDB_PASSWORD,
    DDB_PATH,
    DDB_PORT,
    DDB_USER,
    TICK_DB_NAME,
    TICK_DB_PATH,
    TICK_DOWNLOADS_PATH,
    TICK_TABLE_NAME,
)
from trader.pipeline.loaders.base import BaseDataLoader


class StockTickLoader(BaseDataLoader):
    """Stock Tick Loader"""

    def __init__(self):
        super().__init__()

        # DolphinDB Session
        self.session: ddb.session = None
        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Loader"""

        # Connect Database
        self.connect()

        # Ensure Database Table Exists
        self.create_missing_tables()

        # 檢查資料庫是否存在，並設定 TSDB Cache Engine
        if self.session.existsDatabase(TICK_DB_PATH):
            logger.info("Database exists!")

            # Set TSDBCacheEngineSize to 5GB (must < 8(maxMemSize) * 0.75 GB)
            script: str = """
            memSize = 2
            setTSDBCacheEngineSize(memSize)
            print("TSDBCacheEngineSize: " + string(getTSDBCacheEngineSize() / pow(1024, 3)) + "GB")
            """
            self.session.run(script)
        else:
            logger.info("Database doesn't exist!")
            self.create_db()

    def connect(self) -> None:
        """Connect to the Database"""

        self.session = ddb.session()
        self.session.connect(DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)

    def disconnect(self) -> None:
        """Disconnect the Database"""

        self.session.close()

    def create_db(self) -> None:
        """創建 dolphinDB"""

        start_time: str = "2020.03.01"
        end_time: str = "2030.12.31"

        if self.session.existsDatabase(TICK_DB_PATH):
            logger.info("Database exists!")
        else:
            logger.info("Database doesn't exist!\nCreating a database...")
            script: str = f"""
            create database "{DDB_PATH}{TICK_DB_NAME}"
            partitioned by VALUE({start_time}..{end_time}), HASH([SYMBOL, 25])
            engine='TSDB'
            create table "{DDB_PATH}{TICK_DB_NAME}"."{TICK_TABLE_NAME}"(
                stock_id SYMBOL
                time NANOTIMESTAMP
                close FLOAT
                volume INT
                bid_price FLOAT
                bid_volume INT
                ask_price FLOAT
                ask_volume INT
                tick_type INT
            )
            partitioned by time, stock_id,
            sortColumns=[`stock_id, `time],
            keepDuplicates=ALL
            """
            try:
                self.session.run(script)
                if self.session.existsDatabase(TICK_DB_PATH):
                    logger.info("Tick dolphinDB create successfully!")
                else:
                    logger.warning("Tick dolphinDB create unsuccessfully!")
            except Exception as e:
                logger.warning(f"Tick dolphinDB create unsuccessfully!\n{e}")

    def add_to_db(self, remove_files: bool = False) -> None:
        """將資料夾中的所有 CSV 檔存入 tick 的 DolphinDB 中"""

        # Ensure Database Table Exists
        self.create_missing_tables()

        self.append_all_csv_to_dolphinDB(TICK_DOWNLOADS_PATH)
        if remove_files:
            shutil.rmtree(TICK_DOWNLOADS_PATH)

    def append_csv_to_dolphinDB(self, csv_path: Path) -> None:
        """將單一 CSV 資料添加到已建立的 DolphinDB 資料表"""

        # Ensure Database Table Exists
        self.create_missing_tables()

        script: str = f"""
        db = database("{TICK_DB_PATH}")
        schemaTable = table(
            ["stock_id", "time", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"] as columnName,
            ["SYMBOL", "NANOTIMESTAMP", "FLOAT", "INT", "FLOAT", "INT", "FLOAT", "INT", "INT"] as columnType
        )
        loadTextEx(
            dbHandle=db,
            tableName="{TICK_TABLE_NAME}",
            partitionColumns=["time", "stock_id"],
            filename="{str(csv_path)}",
            delimiter=",",
            schema=schemaTable,
            containHeader=true
        )
        """
        try:
            self.session.run(script)
            logger.info("The csv file successfully save into database and table!")

        except Exception as e:
            logger.info(f"The csv file fail to save into database and table!\n{e}")

    def append_all_csv_to_dolphinDB(self, dir_path: Path) -> None:
        """將資料夾內所有 CSV 檔案附加到已建立的 DolphinDB 資料表（會檢查並過濾已存在的資料）"""

        # Ensure Database Table Exists
        self.create_missing_tables()

        # read all csv files in dir_path (.as_posix => replace \\ with / (for windows os))
        csv_files: List[Path] = list(dir_path.glob("*.csv"))
        logger.info(f"* Total csv files: {len(csv_files)}")

        # 如果沒有 CSV 檔案，提前返回
        if not csv_files:
            logger.warning(f"No CSV files found in {dir_path}. Skipping database load.")
            return

        # 取得資料庫中已存在的資料（使用所有欄位作為唯一鍵，避免誤判不同資料為重複）
        logger.info("Checking existing data in database to avoid duplicates...")
        existing_keys = self._get_existing_keys(use_all_columns=True)
        logger.info(f"Found {len(existing_keys)} existing records in database")

        # 處理每個 CSV 檔案
        total_csv = len(csv_files)
        csv_cnt = 0
        skipped_files = 0
        total_skipped_rows = 0
        total_new_rows = 0

        for csv_path in csv_files:
            csv_cnt += 1
            logger.info(f"Processing [{csv_cnt}/{total_csv}] {csv_path.name}...")

            try:
                # 讀取 CSV 並過濾已存在的資料
                # 使用所有欄位作為唯一鍵（與 _get_existing_keys 一致）
                new_rows_count, skipped_rows_count = self._load_csv_with_dedup(
                    csv_path, existing_keys, use_all_columns=True
                )

                if new_rows_count == 0:
                    logger.info(
                        f"Skipped {csv_path.name} (all data already exists in database)"
                    )
                    skipped_files += 1
                else:
                    total_new_rows += new_rows_count
                    total_skipped_rows += skipped_rows_count
                    logger.info(
                        f"Loaded {csv_path.name}: {new_rows_count} new rows, {skipped_rows_count} duplicates skipped"
                    )

            except Exception as e:
                logger.error(f"Error processing {csv_path.name}: {e}")

        logger.info(
            f"Completed: {csv_cnt - skipped_files} files loaded, {skipped_files} files skipped, "
            f"{total_new_rows} new rows, {total_skipped_rows} duplicates skipped"
        )

    def _get_existing_keys(self, use_all_columns: bool = True) -> set:
        """
        取得資料庫中已存在的資料的唯一鍵

        Args:
            use_all_columns: 如果為 True，使用所有欄位作為唯一鍵（最嚴格，避免誤判不同資料為重複）
                           如果為 False，只使用 (stock_id, time) 作為唯一鍵（較寬鬆，可能誤判）

        注意：這裡將 DB 的 NANOTIMESTAMP 轉換為 pandas Timestamp 用於比對，
        但不會影響實際存入 DB 的資料格式。實際存入時，CSV 中的字串格式會由
        DolphinDB 的 loadTextEx 根據 schema 自動轉換為 NANOTIMESTAMP。
        """
        try:
            import pandas as pd

            if use_all_columns:
                # 使用所有欄位作為唯一鍵，避免誤判不同資料為重複
                # 確保欄位順序與 CSV 一致
                script: str = f"""
                db = database("{TICK_DB_PATH}")
                t = loadTable(db, "{TICK_TABLE_NAME}")
                existing = select stock_id, time, close, volume, bid_price, bid_volume, ask_price, ask_volume, tick_type from t
                """
                result = self.session.run(script)
                if result is None or len(result) == 0:
                    return set()

                # 確保欄位順序一致
                column_order = [
                    "stock_id",
                    "time",
                    "close",
                    "volume",
                    "bid_price",
                    "bid_volume",
                    "ask_price",
                    "ask_volume",
                    "tick_type",
                ]
                result = result[column_order]

                # 將所有欄位轉換為 tuple 作為唯一鍵
                # 確保 time 轉換為 Timestamp 以便比對
                result["time"] = pd.to_datetime(result["time"])
                # 將每行轉換為 tuple（包含所有欄位，順序一致）
                keys = set(tuple(row) for row in result.values.tolist())
                return keys
            else:
                # 只使用 (stock_id, time) 作為唯一鍵（舊邏輯）
                script: str = f"""
                db = database("{TICK_DB_PATH}")
                t = loadTable(db, "{TICK_TABLE_NAME}")
                existing = select stock_id, time from t
                """
                result = self.session.run(script)
                if result is None or len(result) == 0:
                    return set()

                stock_ids = result["stock_id"].tolist()
                times = pd.to_datetime(result["time"]).tolist()
                keys = set(zip(stock_ids, times))
                return keys
        except Exception as e:
            logger.warning(
                f"Error getting existing keys: {e}. Assuming empty database."
            )
            return set()

    def _load_csv_with_dedup(
        self, csv_path: Path, existing_keys: set, use_all_columns: bool = True
    ) -> tuple[int, int]:
        """
        載入 CSV 檔案並過濾已存在的資料

        Args:
            csv_path: CSV 檔案路徑
            existing_keys: 已存在的資料的唯一鍵集合
            use_all_columns: 是否使用所有欄位作為唯一鍵

        Returns:
            (new_rows_count, skipped_rows_count)
        """
        import pandas as pd

        # 讀取 CSV
        df = pd.read_csv(csv_path)
        if df.empty:
            return 0, 0

        original_count = len(df)

        # 定義欄位順序（與資料庫一致）
        column_order = [
            "stock_id",
            "time",
            "close",
            "volume",
            "bid_price",
            "bid_volume",
            "ask_price",
            "ask_volume",
            "tick_type",
        ]

        # 確保欄位順序一致
        df = df[column_order]

        if use_all_columns:
            # 使用所有欄位作為唯一鍵（最嚴格，避免誤判不同資料為重複）
            # 將 time 轉換為 Timestamp 以便與 existing_keys 比對
            df_time_converted = df.copy()
            df_time_converted["time"] = pd.to_datetime(df_time_converted["time"])

            # 建立 key tuple（包含所有欄位）
            df["_key"] = [tuple(row) for row in df_time_converted.values.tolist()]

            # 先處理同一個檔案內的重複資料（保留第一筆）
            if df["_key"].duplicated().any():
                duplicate_count = df["_key"].duplicated().sum()
                df = df.drop_duplicates(subset=["_key"], keep="first")
                logger.debug(
                    f"Removed {duplicate_count} duplicate rows within {csv_path.name}"
                )

            # 過濾掉已存在的資料
            if existing_keys:
                mask = ~df["_key"].isin(existing_keys)
                new_df = df[mask].copy()
            else:
                new_df = df.copy()
        else:
            # 只使用 (stock_id, time) 作為唯一鍵（舊邏輯）
            df["_key"] = list(
                zip(df["stock_id"].astype(str), pd.to_datetime(df["time"]))
            )

            # 先處理同一個檔案內的重複資料（保留第一筆）
            if df["_key"].duplicated().any():
                duplicate_count = df["_key"].duplicated().sum()
                df = df.drop_duplicates(subset=["_key"], keep="first")
                logger.debug(
                    f"Removed {duplicate_count} duplicate rows within {csv_path.name}"
                )

            # 過濾掉已存在的資料
            if existing_keys:
                mask = ~df["_key"].isin(existing_keys)
                new_df = df[mask].copy()
            else:
                new_df = df.copy()

        # 移除臨時欄位
        new_df = new_df.drop(columns=["_key"])

        if new_df.empty:
            return 0, original_count

        # 確保 time 欄位保持原始字串格式（用於寫入 CSV 和 DB）
        # 理論上 time 應該還是字串（因為我們只在 _key 中轉換），但為了安全加上檢查
        # DolphinDB 的 loadTextEx 會根據 schema 自動將字串轉換為 NANOTIMESTAMP
        if pd.api.types.is_datetime64_any_dtype(new_df["time"]):
            # 轉換為微秒精度的字串格式（與原始 CSV 格式一致：%Y-%m-%d %H:%M:%S.%f）
            new_df["time"] = new_df["time"].dt.strftime("%Y-%m-%d %H:%M:%S.%f")

        # 將新資料寫入臨時 CSV（只包含新資料）
        temp_csv = csv_path.parent / f"{csv_path.stem}_temp_{csv_path.suffix}"
        new_df.to_csv(temp_csv, index=False)

        try:
            # 載入到 DolphinDB
            script: str = f"""
            db = database("{TICK_DB_PATH}")
            schemaTable = table(
                ["stock_id", "time", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"] as columnName,
                ["SYMBOL", "NANOTIMESTAMP", "FLOAT", "INT", "FLOAT", "INT", "FLOAT", "INT", "INT"] as columnType
            )
            loadTextEx(
                dbHandle=db,
                tableName="{TICK_TABLE_NAME}",
                partitionColumns=["time", "stock_id"],
                filename="{str(temp_csv.as_posix())}",
                delimiter=",",
                schema=schemaTable,
                containHeader=true
            )
            """
            self.session.run(script)

            # 更新 existing_keys（只更新成功載入的資料）
            # 從 new_df 建立新的 keys（因為 new_df 就是成功載入的資料）
            if use_all_columns:
                # 重新建立 key（包含所有欄位）
                new_df_time_converted = new_df.copy()
                new_df_time_converted["time"] = pd.to_datetime(
                    new_df_time_converted["time"]
                )
                new_keys = set(
                    tuple(row) for row in new_df_time_converted.values.tolist()
                )
            else:
                # 使用 (stock_id, time) 作為 key
                # 從 new_df 建立 keys（需要重新建立，因為 _key 欄位已被移除）
                new_df_time_converted = new_df.copy()
                new_df_time_converted["time"] = pd.to_datetime(
                    new_df_time_converted["time"]
                )
                new_keys = set(
                    zip(
                        new_df_time_converted["stock_id"].astype(str).tolist(),
                        new_df_time_converted["time"].tolist(),
                    )
                )
            existing_keys.update(new_keys)

            new_rows_count = len(new_df)
            skipped_rows_count = original_count - new_rows_count

            return new_rows_count, skipped_rows_count

        except Exception as e:
            # 如果載入失敗，不要更新 existing_keys，並重新拋出異常
            logger.error(f"Failed to load {csv_path.name} to DolphinDB: {e}")
            raise

        finally:
            # 刪除臨時檔案
            if temp_csv.exists():
                temp_csv.unlink()

    def create_missing_tables(self) -> None:
        """確保 Tick DB 存在，否則建立"""
        if not self.session.existsDatabase(TICK_DB_PATH):
            logger.info("Tick DB not found. Creating...")
            self.create_db()

    def clear_all_cache(self) -> None:
        """清除 Cache Data"""

        script: str = """
        clearAllCache()
        """
        self.session.run(script)

    def delete_dolphinDB(self, db_path: Path) -> None:
        """刪除資料庫"""

        logger.info("Start deleting database...")

        script: str = f"""
        if (existsDatabase("{str(db_path)}")) {{
            dropDatabase("{str(db_path)}")
        }}
        """
        self.session.run(script)

        if self.session.existsDatabase(str(db_path)):
            logger.info("Delete database unsuccessfully!")
        else:
            logger.info("Delete database successfully!")
