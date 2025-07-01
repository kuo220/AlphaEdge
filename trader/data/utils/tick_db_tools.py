import datetime
import json
import os
import shutil
import sys
from pathlib import Path
from typing import List, Dict
import pandas as pd
try:
    import dolphindb as ddb
except ModuleNotFoundError:
    print("Warning: dolphindb module is not installed.")

from trader.config import TICK_METADATA_PATH


class TickDBTools:
    """ Tick DolphinDB Tools """

    @staticmethod
    def format_tick_data(df: pd.DataFrame, stock_id: str) -> pd.DataFrame:
        """ 統一 tick data 的格式 """

        df.rename(columns={'ts': 'time'}, inplace=True)
        df['stock_id'] = stock_id
        new_columns_order: List[str] = [
            'stock_id','time', 'close',
            'volume', 'bid_price', 'bid_volume',
            'ask_price', 'ask_volume', 'tick_type'
        ]
        df = df[new_columns_order]

        return df


    @staticmethod
    def format_time_to_microsec(df: pd.DataFrame) -> pd.DataFrame:
        """ 將 tick dataframe 時間格式格式化至微秒（才能存進 dolphinDB） """

        # 若 time 欄位沒有精確到微秒則格式化
        if not df['time'].astype(str).str.match(r'.*\.\d{6}$').all():
            # 將 'time' 欄位轉換為 datetime 格式，並補足到微秒，同時加上年月日
            df['time'] = pd.to_datetime(df['time'], errors='coerce').dt.strftime('%Y-%m-%d %H:%M:%S.%f')

        return df


    @staticmethod
    def get_table_earliest_date() -> datetime.date:
        """ 從 tick_metadata.json 中取得 tick table 的最早日期 """

        with open(TICK_METADATA_PATH, "r", encoding="utf-8") as data:
            time_data: Dict[str, str] = json.load(data)
            earliest_date: datetime.date = datetime.date.fromisoformat(time_data["earliest_date"])
        return earliest_date


    @staticmethod
    def get_table_latest_date() -> datetime.date:
        """ 從 tick_metadata.json 中取得 tick table 的最新日期 """

        with open(TICK_METADATA_PATH, "r", encoding="utf-8") as data:
            time_data: Dict[str, str] = json.load(data)
            latest_date: datetime.date = datetime.date.fromisoformat(time_data["latest_date"])
        return latest_date


    @staticmethod
    def update_tick_table_latest_date(date: datetime.date) -> None:
        """ 更新 tick_metadata.json 中的 table 最新時間 """

        # Time range for updating
        metadata: Dict[str, str] = {
            "earliest_date": TickDBTools.get_table_earliest_date().isoformat(),
            "latest_date": date.isoformat()
        }

        # Write in new dates
        with open(TICK_METADATA_PATH, "w", encoding="utf-8") as data:
            json.dump(metadata, data, ensure_ascii=False, indent=4)


    @staticmethod
    def update_tick_table_date_range(start_date: datetime.date, end_date: datetime.date) -> None:
        """ 更新 tick_metadata.json 中的 table 日期區間 """

        # Time range for updating
        metadata: Dict[str, str] = {
            "earliest_date": start_date.isoformat(),
            "latest_date": end_date.isoformat()
        }

        # Write in new dates
        with open(TICK_METADATA_PATH, "w", encoding="utf-8") as data:
            json.dump(metadata, data, ensure_ascii=False, indent=4)


    @staticmethod
    def generate_tick_metadata_backup() -> None:
        """ 建立 tick_metadata 的備份檔案 """

        backup_suffix: str = "_backup"
        backup_name: Path = TICK_METADATA_PATH.with_name(TICK_METADATA_PATH.stem + backup_suffix + TICK_METADATA_PATH.suffix)
        shutil.copy2(TICK_METADATA_PATH, backup_name)