import sqlite3
from pathlib import Path
from typing import List, Set

import pandas as pd
from loguru import logger

from core.config import SECURITIES_TRADER_INFO_TABLE_NAME
from core.pipeline.utils import FinMindDataType

"""證券商資訊表的 CSV 入庫"""


def load_broker_info(conn: sqlite3.Connection, finmind_dir: Path) -> None:
    """載入證券商資訊表資料到資料庫"""

    data_type_dir: Path = finmind_dir / FinMindDataType.BROKER_INFO.value.lower()
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
        existing_df: pd.DataFrame = pd.read_sql_query(existing_query, conn)

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
            existing_broker_ids = set(existing_df["securities_trader_id"].astype(str))  # type: ignore
            logger.info(
                f"Loaded {len(existing_broker_ids)} existing records from database"
            )

        # 過濾出新資料
        if existing_broker_ids:
            mask: pd.Series = ~df["securities_trader_id"].astype(str).isin(
                existing_broker_ids
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
            conn,
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
