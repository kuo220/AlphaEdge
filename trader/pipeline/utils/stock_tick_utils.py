import datetime
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List

import shioaji as sj

try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed")

from trader.config import API_KEYS, API_SECRET_KEYS, TICK_METADATA_PATH
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

        # Time range for updating
        metadata: Dict[str, str] = {
            "earliest_date": StockTickUtils.get_table_earliest_date().isoformat(),
            "latest_date": date.isoformat(),
        }

        # Write in new dates
        with open(TICK_METADATA_PATH, "w", encoding="utf-8") as data:
            json.dump(metadata, data, ensure_ascii=False, indent=4)

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
