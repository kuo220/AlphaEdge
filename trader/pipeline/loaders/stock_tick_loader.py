import shutil
import time
from pathlib import Path
from typing import List, Optional

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
        self.session: Optional[ddb.session] = None
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

    def connect(self, max_retries: int = 3, retry_delay: float = 1.0) -> None:
        """
        Connect to the Database with retry mechanism

        Parameters:
            max_retries: Maximum number of connection retry attempts
            retry_delay: Delay in seconds between retry attempts
        """

        for attempt in range(1, max_retries + 1):
            try:
                self.session = ddb.session()
                self.session.connect(DDB_HOST, DDB_PORT, DDB_USER, DDB_PASSWORD)
                logger.info("Successfully connected to DolphinDB")
                return
            except Exception as e:
                if attempt < max_retries:
                    logger.warning(
                        f"Connection attempt {attempt}/{max_retries} failed: {e}. "
                        f"Retrying in {retry_delay} seconds..."
                    )
                    time.sleep(retry_delay)
                else:
                    logger.error(
                        f"Failed to connect to DolphinDB after {max_retries} attempts: {e}"
                    )
                    raise

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

    def create_missing_tables(self) -> None:
        """確保 Tick DB 存在，否則建立"""

        if not self.session.existsDatabase(TICK_DB_PATH):
            logger.info("Tick DB not found. Creating...")
            self.create_db()

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
        """將資料夾內所有 CSV 檔案附加到已建立的 DolphinDB 資料表"""

        # Ensure Database Table Exists
        self.create_missing_tables()

        # read all csv files in dir_path (.as_posix => replace \\ with / (for windows os))
        csv_files: List[str] = [str(csv.as_posix()) for csv in dir_path.glob("*.csv")]
        logger.info(f"* Total csv files: {len(csv_files)}")

        script: str = f"""
        db = database("{TICK_DB_PATH}")
        schemaTable = table(
            ["stock_id", "time", "close", "volume", "bid_price", "bid_volume", "ask_price", "ask_volume", "tick_type"] as columnName,
            ["SYMBOL", "NANOTIMESTAMP", "FLOAT", "INT", "FLOAT", "INT", "FLOAT", "INT", "INT"] as columnType
        )

        total_csv = {len(csv_files)}
        csv_cnt = 0

        for (csv_path in {csv_files}) {{
            loadTextEx(
                dbHandle=db,
                tableName="{TICK_TABLE_NAME}",
                partitionColumns=["time", "stock_id"],
                filename=csv_path,
                delimiter=",",
                schema=schemaTable,
                containHeader=true
            )
            csv_cnt += 1
            print("* Status: " + string(csv_cnt) + "/" + string(total_csv))
        }}
        """
        try:
            self.session.run(script)
            logger.info("All csv files successfully save into database and table!")

        except Exception as e:
            logger.info(f"All csv files fail to save into database and table!\n{e}")

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
