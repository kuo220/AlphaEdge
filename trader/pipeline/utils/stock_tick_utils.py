import datetime
import json
import shutil
from pathlib import Path
from typing import Dict, List

import pandas as pd
from loguru import logger

try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed")

from trader.config import (
    API_KEYS,
    API_SECRET_KEYS,
    TICK_DOWNLOADS_PATH,
    TICK_METADATA_DIR_PATH,
    TICK_METADATA_PATH,
)
from trader.utils import ShioajiAPI


class StockTickUtils:
    """Tick DolphinDB Tools"""

    @staticmethod
    def get_table_earliest_date() -> datetime.date:
        """從 tick_metadata.json 中取得 tick table 的最早日期"""

        with open(TICK_METADATA_PATH, "r", encoding="utf-8") as data:
            time_data: Dict[str, str] = json.load(data)
            earliest_date: datetime.date = datetime.date.fromisoformat(
                time_data["earliest_date"]
            )
        return earliest_date

    @staticmethod
    def get_table_latest_date() -> datetime.date:
        """從 tick_metadata.json 中取得 tick table 的最新日期"""

        with open(TICK_METADATA_PATH, "r", encoding="utf-8") as data:
            time_data: Dict[str, str] = json.load(data)
            latest_date: datetime.date = datetime.date.fromisoformat(
                time_data["latest_date"]
            )
        return latest_date

    @staticmethod
    def update_tick_table_latest_date(date: datetime.date) -> None:
        """更新 tick_metadata.json 中的 table 最新時間"""

        if date is None:
            raise ValueError("Cannot update tick metadata: date is None")

        try:
            # Time range for updating
            metadata: Dict[str, str] = {
                "earliest_date": StockTickUtils.get_table_earliest_date().isoformat(),
                "latest_date": date.isoformat(),
            }

            # Write in new dates
            with open(TICK_METADATA_PATH, "w", encoding="utf-8") as data:
                json.dump(metadata, data, ensure_ascii=False, indent=4)
        except Exception as e:
            from loguru import logger

            logger.error(f"Failed to update tick metadata: {e}")
            raise

    @staticmethod
    def update_tick_table_date_range(
        start_date: datetime.date, end_date: datetime.date
    ) -> None:
        """更新 tick_metadata.json 中的 table 日期區間"""

        # Time range for updating
        metadata: Dict[str, str] = {
            "earliest_date": start_date.isoformat(),
            "latest_date": end_date.isoformat(),
        }

        # Write in new dates
        with open(TICK_METADATA_PATH, "w", encoding="utf-8") as data:
            json.dump(metadata, data, ensure_ascii=False, indent=4)

    @staticmethod
    def generate_tick_metadata_backup() -> None:
        """建立 tick_metadata 的備份檔案"""

        # 如果檔案不存在，先創建一個預設的 metadata 檔案
        if not TICK_METADATA_PATH.exists():
            # 確保目錄存在
            TICK_METADATA_PATH.parent.mkdir(parents=True, exist_ok=True)
            # 創建預設的 metadata 檔案
            default_metadata = {
                "earliest_date": "2020-04-01",
                "latest_date": "2020-04-01",
            }
            with open(TICK_METADATA_PATH, "w", encoding="utf-8") as f:
                import json

                json.dump(default_metadata, f, ensure_ascii=False, indent=4)

        backup_suffix: str = "_backup"
        backup_name: Path = TICK_METADATA_PATH.with_name(
            TICK_METADATA_PATH.stem + backup_suffix + TICK_METADATA_PATH.suffix
        )
        shutil.copy2(TICK_METADATA_PATH, backup_name)

    @staticmethod
    def setup_shioaji_apis() -> List[ShioajiAPI]:
        # Add API from 11 ~ 17 and add API_1 (Mine)
        api_list: list[ShioajiAPI] = []
        for key, secret in zip(API_KEYS, API_SECRET_KEYS):
            api: ShioajiAPI = ShioajiAPI(key, secret)
            api_list.append(api)
        return api_list

    @staticmethod
    def scan_tick_downloads_folder() -> Dict[str, str]:
        """
        掃描 tick 下載資料夾，記錄每個已下載檔案的股票代號和最後一筆資料的日期

        Returns:
            Dict[str, str]: 股票代號 -> 最後一筆資料日期 (YYYY-MM-DD 格式)
        """
        stock_last_dates: Dict[str, str] = {}

        # 確保資料夾存在
        if not TICK_DOWNLOADS_PATH.exists():
            logger.warning(
                f"Tick downloads folder does not exist: {TICK_DOWNLOADS_PATH}"
            )
            return stock_last_dates

        # 掃描所有 CSV 檔案
        csv_files = list(TICK_DOWNLOADS_PATH.glob("*.csv"))
        logger.info(f"Scanning {len(csv_files)} CSV files in tick downloads folder...")

        for csv_file in csv_files:
            stock_id = csv_file.stem  # 取得檔名（不含副檔名）作為股票代號

            try:
                # 讀取 CSV 檔案（只讀取 time 欄位以提升效能）
                df = pd.read_csv(csv_file, usecols=["time"])

                if df.empty:
                    logger.warning(f"File {csv_file.name} is empty. Skipping.")
                    continue

                # 取得最後一筆資料的時間
                last_time_str = df["time"].iloc[-1]

                # 解析時間字串（格式：YYYY-MM-DD HH:MM:SS.ffffff）
                try:
                    last_time = pd.to_datetime(last_time_str)
                    last_date = last_time.date()
                    stock_last_dates[stock_id] = last_date.isoformat()
                    logger.debug(
                        f"Stock {stock_id}: last date = {last_date.isoformat()}"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to parse time '{last_time_str}' in {csv_file.name}: {e}"
                    )
                    continue

            except Exception as e:
                logger.error(f"Error reading file {csv_file.name}: {e}")
                continue

        logger.info(f"Scanned {len(stock_last_dates)} stock files successfully")
        return stock_last_dates

    @staticmethod
    def update_tick_downloads_metadata() -> None:
        """
        掃描 tick 下載資料夾並更新 tick_downloads_metadata.json 中的股票資訊
        記錄每個已下載檔案的股票代號和最後一筆資料的日期
        此功能不影響原本的 tick_metadata.json
        """
        # 定義新的 metadata 檔案路徑
        downloads_metadata_path = (
            TICK_METADATA_DIR_PATH / "tick_downloads_metadata.json"
        )

        # 確保目錄存在
        downloads_metadata_path.parent.mkdir(parents=True, exist_ok=True)

        # 讀取現有的 metadata（如果存在）
        if downloads_metadata_path.exists():
            with open(downloads_metadata_path, "r", encoding="utf-8") as f:
                metadata: Dict = json.load(f)
        else:
            metadata: Dict = {"stocks": {}}

        # 掃描資料夾
        stock_last_dates = StockTickUtils.scan_tick_downloads_folder()

        # 更新或新增每個股票的資訊
        for stock_id, last_date in stock_last_dates.items():
            if stock_id not in metadata["stocks"]:
                metadata["stocks"][stock_id] = {}
            metadata["stocks"][stock_id]["last_date"] = last_date

        # 寫入更新後的 metadata
        with open(downloads_metadata_path, "w", encoding="utf-8") as f:
            json.dump(metadata, f, ensure_ascii=False, indent=4)

        logger.info(
            f"Updated tick downloads metadata with {len(stock_last_dates)} stocks"
        )
