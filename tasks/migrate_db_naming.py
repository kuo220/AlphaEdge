"""資料庫命名軸線遷移：DB 檔名補上市場軸、`underlying_market` 欄正名

見 `docs/dev/naming-axes.md`。**本腳本只動資料，不動程式碼**——執行完之後
還要把 `core/config.py` 的兩個檔名值與 loader／cleaner／測試裡的欄位名一併改掉，
兩者必須同一批進行，否則程式會找不到資料庫。

用法（比照其他 task，以 -m 執行）：
    python -m tasks.migrate_db_naming --dry-run   # 只列出要做什麼
    python -m tasks.migrate_db_naming             # 實際執行（會先備份）
"""

import argparse
import shutil
import sqlite3
from pathlib import Path
from typing import Dict, List, Optional, Tuple

from loguru import logger

from core.config import DATABASE_DIR_PATH, FUTURES_STOCK_UNIVERSE_TABLE_NAME

# 檔名遷移：舊檔名 → 新檔名（新名補上市場軸 tw_，與 downloads/tw_stock、tw_futures 對齊）
DB_RENAMES: List[Tuple[str, str]] = [
    ("stock.db", "tw_stock.db"),
    ("futures.db", "tw_futures.db"),
]

# 欄位正名：該欄存的是「上市／上櫃」，屬掛牌板別（軸 C）不是市場（軸 A）
COLUMN_RENAME: Tuple[str, str, str] = (
    FUTURES_STOCK_UNIVERSE_TABLE_NAME,
    "underlying_market",
    "underlying_listing_board",
)


def get_row_counts(db_path: Path) -> Dict[str, int]:
    """取得資料庫內每張表的列數，作為遷移前後的比對基準"""

    conn: sqlite3.Connection = sqlite3.connect(db_path)
    try:
        tables: List[str] = [
            row[0]
            for row in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' ORDER BY name"
            )
        ]
        return {
            t: conn.execute(f'SELECT COUNT(*) FROM "{t}"').fetchone()[0] for t in tables
        }
    finally:
        conn.close()


def rename_column(db_path: Path, dry_run: bool) -> bool:
    """把 futures 標的池的 underlying_market 欄改名；已改過則跳過（冪等）"""

    table, old_col, new_col = COLUMN_RENAME
    conn: sqlite3.Connection = sqlite3.connect(db_path)
    try:
        exists: bool = bool(
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
            ).fetchone()
        )
        if not exists:
            logger.info(f"* {db_path.name} 沒有 {table} 表，跳過欄位改名")
            return False

        cols: List[str] = [r[1] for r in conn.execute(f"PRAGMA table_info('{table}')")]
        if new_col in cols:
            logger.info(f"* {table}.{new_col} 已存在，跳過（冪等）")
            return False
        if old_col not in cols:
            logger.warning(f"* {table} 找不到 {old_col} 欄，跳過")
            return False

        if dry_run:
            logger.info(f"[dry-run] 將改名 {table}.{old_col} → {new_col}")
            return True

        conn.execute(f'ALTER TABLE "{table}" RENAME COLUMN "{old_col}" TO "{new_col}"')
        conn.commit()
        logger.info(f"* 已改名 {table}.{old_col} → {new_col}")
        return True
    finally:
        conn.close()


def main() -> None:
    """執行遷移：先備份 → 欄位改名 → 檔名改名 → 比對列數"""

    parser = argparse.ArgumentParser(
        description="資料庫命名軸線遷移（見 docs/dev/naming-axes.md）"
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="只列出要做什麼，不實際變更"
    )
    args = parser.parse_args()

    backup_dir: Path = DATABASE_DIR_PATH / "_backup_before_naming_migration"

    # 1. 備份（futures.db 很小；stock.db 只改檔名不動內容，故不整份複製）
    futures_src: Optional[Path] = None
    for old_name, _ in DB_RENAMES:
        src: Path = DATABASE_DIR_PATH / old_name
        if old_name == "futures.db" and src.exists():
            futures_src = src

    if futures_src and not args.dry_run:
        backup_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(futures_src, backup_dir / futures_src.name)
        logger.info(f"* 已備份 {futures_src.name} → {backup_dir}")

    # 2. 欄位改名（在改檔名之前做，路徑才還是舊的）
    if futures_src and futures_src.exists():
        before: Dict[str, int] = get_row_counts(futures_src)
        rename_column(futures_src, args.dry_run)
        if not args.dry_run:
            after: Dict[str, int] = get_row_counts(futures_src)
            if before != after:
                raise RuntimeError(f"列數在欄位改名後改變：{before} → {after}")
            logger.info(f"* 列數比對通過：{after}")

    # 3. 檔名改名
    for old_name, new_name in DB_RENAMES:
        src = DATABASE_DIR_PATH / old_name
        dst: Path = DATABASE_DIR_PATH / new_name
        if not src.exists():
            logger.info(f"* {old_name} 不存在，跳過（可能已遷移）")
            continue
        if dst.exists():
            raise RuntimeError(f"{new_name} 已存在，請先確認要保留哪一份再重跑")
        if args.dry_run:
            logger.info(f"[dry-run] 將改名 {old_name} → {new_name}")
            continue
        src.rename(dst)
        logger.info(f"* 已改名 {old_name} → {new_name}")

    if args.dry_run:
        logger.info("dry-run 結束，未做任何變更")
        return

    logger.info(
        "資料遷移完成。**接著必須同步改程式碼**："
        "core/config.py 的 TW_STOCK_DB_NAME／TW_FUTURES_DB_NAME 值、"
        "futures_stock_universe loader 的建表欄位、cleaner 的欄位指派與相關測試。"
    )


if __name__ == "__main__":
    main()
