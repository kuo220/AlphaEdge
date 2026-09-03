import sqlite3
from dataclasses import dataclass
from pathlib import Path
from typing import List, Set

import pandas as pd
from loguru import logger

from core.pipeline.utils import FinMindDataType
from core.pipeline.utils.exceptions import DataLoadError

"""
FinMind「參考資料表」的共用入庫流程

台股總覽、台股總覽（含權證）、證券商資訊三張表都是**單鍵的現況快照**：
一支 CSV 對一張表、以單一欄位為主鍵、重跑只補新增的列。三者原本是三份逐字
複製的實作（約 85% 相同），只有四個東西不同——資料表名、CSV 檔名、去重鍵、
欄位順序——改一處要記得改三處。

**券商分點不走這裡**：它是 `(stock_id, date, securities_trader_id)` 三欄複合鍵的
時間序列，且分成 DataFrame 直入與 CSV 目錄批次兩條路徑，見 `broker_trading_loader.py`。
"""


@dataclass(frozen=True)
class ReferenceTableSpec:
    """
    一張參考資料表的入庫規格

    `label` 只用於 log 措辭——回補時那幾行是判斷「跑到哪張表」的唯一依據，
    合併實作時必須逐字保留原本的用字。
    """

    data_type: FinMindDataType  # 決定 downloads 底下的子目錄
    csv_name: str  # CSV 檔名
    table_name: str  # 目標資料表
    key_column: str  # 去重與「已存在」判定所用的單一主鍵欄
    column_order: List[str]  # 寫入前的欄位順序，須與 crawler schema 註解一致
    label: str  # log 用的人話名稱（Ex: "stock info"）


def load_reference_table(
    conn: sqlite3.Connection,
    finmind_dir: Path,
    spec: ReferenceTableSpec,
) -> None:
    """
    - Description:
        將單鍵參考資料表的 CSV 載入資料庫

        流程：讀 CSV → 查 DB 已存在的主鍵 → 檔內去重 → 過濾出新資料 →
        依 `column_order` 排欄 → `to_sql(append)`。
        **已存在的列一律跳過而非更新**：這三張表的既有語意就是「只補新增」。
    - Parameters:
        - conn: sqlite3.Connection
            資料庫連線（由 `FinMindLoader` 持有並負責開關）
        - finmind_dir: Path
            downloads 底下的 finmind 目錄
        - spec: ReferenceTableSpec
            該張表的入庫規格
    - Return:
        - None
    - Raise:
        - DataLoadError
            入庫失敗（欄位不符、檔案損毀、DB 錯誤）

            舊版整段包在 `try/except Exception` 裡、只記一行 `logger.error` 就回，
            於是三張 FinMind 參考表的入庫失敗會被算成「跳過」，
            `update_db` 照樣以結束碼 0 回報成功（健檢 F-045）。
    """

    data_type_dir: Path = finmind_dir / spec.data_type.value.lower()
    csv_path: Path = data_type_dir / spec.csv_name

    if not csv_path.exists():
        logger.warning(f"CSV file not found: {csv_path}")
        return

    try:
        logger.info(f"Loading {spec.label} from {csv_path.name}...")
        df: pd.DataFrame = pd.read_csv(csv_path)

        if df.empty:
            logger.warning(f"Skipped {csv_path.name} (file is empty)")
            return

        # 查詢資料庫中已存在的資料
        existing_query: str = f"""
        SELECT {spec.key_column}
        FROM {spec.table_name}
        """
        existing_df: pd.DataFrame = pd.read_sql_query(existing_query, conn)

        # 先處理同一個檔案內的重複資料
        original_count: int = len(df)
        if df[spec.key_column].duplicated().any():
            df = df.drop_duplicates(subset=[spec.key_column], keep="first")
            logger.debug(
                f"Removed {original_count - len(df)} duplicate rows within {csv_path.name}"
            )

        # 建立已存在的主鍵 set
        existing_keys: Set[str] = set()
        if not existing_df.empty:
            existing_keys = set(existing_df[spec.key_column].astype(str))  # type: ignore
            logger.info(f"Loaded {len(existing_keys)} existing records from database")

        # 過濾出新資料
        if existing_keys:
            mask: pd.Series = ~df[spec.key_column].astype(str).isin(existing_keys)
            new_df: pd.DataFrame = df[mask]

            if new_df.empty:
                logger.info(f"Skipped {csv_path.name} (all data already exists)")
                return
        else:
            new_df: pd.DataFrame = df

        # 確保欄位順序與 crawler schema 註解一致
        new_df = new_df[spec.column_order]

        # 插入新資料
        new_df.to_sql(
            spec.table_name,
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
        raise DataLoadError(spec.label, [csv_path.name], succeeded=0) from e
