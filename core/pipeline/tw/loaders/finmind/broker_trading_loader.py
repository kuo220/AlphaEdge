import sqlite3
from pathlib import Path
from typing import List, Set, Tuple

import pandas as pd
from loguru import logger

from core.config import STOCK_TRADING_DAILY_REPORT_TABLE_NAME
from core.pipeline.shared.base_loader import BaseDataLoader
from core.pipeline.utils import FinMindDataType
from core.pipeline.utils.exceptions import DataLoadError

"""
券商分點統計表的入庫：DataFrame 直入與 CSV 目錄批次兩條路徑

兩條路徑的去重邏輯不同：DataFrame 路徑**只查本批涉及的 (stock_id, securities_trader_id)**
（updater 每次只帶一個組合，全表掃描會隨資料量線性變慢）；CSV 路徑一次讀進全表的
主鍵集合，因為它本來就要走遍所有券商資料夾。
"""


def load_from_dataframe(
    conn: sqlite3.Connection, df: pd.DataFrame, commit: bool = True
) -> int:
    """從 DataFrame 載入當日券商分點統計表資料到資料庫

    Args:
        df: 要載入的 DataFrame
        commit: 是否在寫入後立即 commit

    Returns:
        int: 成功插入的資料筆數
    """
    if df is None or df.empty:
        logger.warning("DataFrame is empty, skipping load")
        return 0

    # 從本批 df 取得唯一的 (stock_id, securities_trader_id) 組合，只查這些組合在 DB 中已存在的 key（優化：避免全表掃描）
    unique_pairs: List[Tuple[str, str]] = [
        (str(row["stock_id"]), str(row["securities_trader_id"]))
        for row in df[["stock_id", "securities_trader_id"]]
        .drop_duplicates()
        .to_dict("records")
    ]
    if not unique_pairs:
        logger.warning(
            "DataFrame has no (stock_id, securities_trader_id) pairs, skipping load"
        )
        return 0

    # 建構 WHERE 條件：只查詢本批涉及的 (stock_id, securities_trader_id)
    placeholders: str = " OR ".join(
        ["(stock_id = ? AND securities_trader_id = ?)"] * len(unique_pairs)
    )
    flat_params: List[str] = [p for pair in unique_pairs for p in pair]
    existing_query: str = f"""
    SELECT DISTINCT stock_id, date, securities_trader_id
    FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
    WHERE {placeholders}
    """
    try:
        existing_df: pd.DataFrame = pd.read_sql_query(
            existing_query, conn, params=flat_params
        )

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
            conn,
            if_exists="append",
            index=False,
        )
        if commit:
            conn.commit()

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
        # **不再有 fallback 盲插、也不再回 0**：舊版失敗後回 0，
        # 呼叫端把 0 當成「本批皆為重複」而回報 SUCCESS，
        # 於是入庫失敗被算成成功（健檢 F-045）。
        logger.opt(exception=True).error(
            f"Error loading broker trading daily report from DataFrame: {e}",
        )
        raise DataLoadError("broker_trading", ["<dataframe>"], succeeded=0) from e


def load_from_files(conn: sqlite3.Connection, finmind_dir: Path) -> None:
    """載入當日券商分點統計表資料到資料庫

    新的檔案結構：broker_trading/{broker_id}/{stock_id}.csv
    會遍歷所有 broker_id 資料夾，讀取每個 stock_id 的 CSV 檔案
    """

    data_type_dir: Path = finmind_dir / FinMindDataType.BROKER_TRADING.value.lower()

    if not data_type_dir.exists():
        logger.warning(f"Directory not found: {data_type_dir}")
        return

    # 查詢資料庫中已存在的資料（根據複合主鍵）
    existing_query: str = f"""
    SELECT stock_id, date, securities_trader_id
    FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
    """
    existing_df: pd.DataFrame = pd.read_sql_query(existing_query, conn)

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
    failed_files: List[str] = []

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
                    logger.debug(f"Skipped {broker_id}/{stock_id}.csv (file is empty)")
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
                    conn,
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
                # **失敗不再算成 skipped**：兩者混在一起時，
                # 「今天有 300 檔沒入庫」與「今天有 300 檔本來就沒新資料」
                # 在 log 裡長得一模一樣。單檔失敗仍不中止整批（其餘券商照跑），
                # 但跑完會由 `finish_load()` 拋出。
                logger.opt(exception=True).error(
                    f"Error loading {broker_id}/{stock_id}.csv: {e}",
                )
                failed_files.append(f"{broker_id}/{stock_id}.csv")
                continue

    # 輸出總結
    logger.info(
        f"Broker trading daily report loading finished. "
        f"Processed {processed_files} files, skipped {skipped_files} files, "
        f"failed {len(failed_files)} files. "
        f"Total: {total_new_rows} new rows, {total_skipped_rows} skipped rows"
    )

    BaseDataLoader.finish_load(
        source="broker_trading",
        succeeded=processed_files - skipped_files - len(failed_files),
        failed_files=failed_files,
        skipped_files=skipped_files,
    )
