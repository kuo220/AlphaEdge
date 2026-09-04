"""清除 `chip`／`margin`／`price` 三張表的停滯與非交易日批次

## 問題

三支 cleaner 都是 `df.insert(0, "date", date)`——蓋上去的是**請求參數的日期**，
不是來源頁面內的日期。只要爬蟲把非交易日（或站方的過期快取頁）的回應當成有效
資料交出來，它就會被寫成那一天的資料，而且**不會觸發任何缺口統計**：
缺資料讓回測少算幾天，多資料讓回測多算幾天，後者沒有任何統計行會示警。

爬蟲端已由 `f278160`（2026-09-03「S2 台股五支 crawler 分流『休市 vs 失敗』」）修好
——實測 TWSE 2026-08-29（週六）回 `NO_DATA` 被 `judge_fetch()` 攔下。最後一批壞資料
寫於 2026-06-03，早於該修復。**本腳本只處理歷史殘留，不需要改任何 ETL 程式。**

## 三類批次與處置

1. **非交易日批次（刪除）**：該日期只有這張表有，`price`／`margin`／`chip`／
   `futures_large_trader` 其餘三張全無，且市場當天沒有開市。
2. **真實交易日但內容是停滯區塊（刪除後重爬）**：`chip` 有 6 天的 TWSE 部分被同一組
   908 檔的內容取代，該 908 檔的值在 12 天完全相同，在鄰近交易日只有 0.5~0.8% 巧合相符；
   受污染日列數 1,735~1,754，鄰日約 2,050，代表當天真正的資料沒進來。
   **這幾天不能只刪**——刪完要跑 `--target chip` 讓差集把它們重爬回來。
3. **`price` 的偽交易日（刪除）**：`2019-02-06` 是春節休市日，其餘三張表都沒有。
   它同時是 `stock_chip_updater` 的交易日曆來源，**必須先刪它**，否則後續重爬會把
   非交易日又當成候選日期。

## 使用方式

    python scripts/fix_chip_margin_stale_batches.py --dry-run   # 只報告不寫入
    python scripts/fix_chip_margin_stale_batches.py             # 執行，先備份再刪

刪除前會把每一列**原樣匯出成 CSV**（`--backup-dir`，預設 `data/downloads/tw_stock/meta/`），
所以這個動作是可還原的。本腳本是**冪等**的：刪過之後再次執行不會有任何待刪列。
"""

import argparse
import csv
import datetime
import sqlite3
from pathlib import Path
from typing import Dict, List, Tuple

from core.config import (
    CHIP_TABLE_NAME,
    MARGIN_TABLE_NAME,
    PRICE_TABLE_NAME,
    TW_STOCK_DB_PATH,
)

# `chip` 的非交易日批次：13 個週六日 ＋ `2025-01-23`
# （2025 年春節封關日為 01-22、開紅盤 02-03，故 01-23 也是休市）
CHIP_NON_TRADING_DATES: List[str] = [
    "2021-03-27",  # 週六
    "2023-05-14",  # 週日
    "2024-09-07",  # 週六
    "2024-09-08",  # 週日
    "2025-01-23",  # 週四，春節休市
    "2025-02-08",  # 週六
    "2025-03-08",  # 週六
    "2025-04-26",  # 週六
    "2025-05-31",  # 週六
    "2025-06-28",  # 週六
    "2025-07-13",  # 週日
    "2025-07-20",  # 週日
    "2025-07-27",  # 週日
    "2026-05-30",  # 週六
]

# `chip` 的真實交易日，但 TWSE 部分是停滯區塊。刪除後要重爬（見模組說明第 2 點）
CHIP_STALE_TRADING_DATES: List[str] = [
    "2017-12-18",
    "2023-05-12",
    "2024-02-16",
    "2025-01-22",
    "2025-03-24",
    "2025-04-23",
]

# `margin` 的非交易日批次：全為颱風全日停市日。
# 每一天都是前一個交易日的**逐位元複製**（融資／融券今日餘額與買進／賣出流量欄全同），
# 不是停市日的新申報——流量欄不可能對數百檔同時巧合相同
MARGIN_NON_TRADING_DATES: List[str] = [
    "2014-07-23",  # 麥德姆
    "2015-07-10",  # 昌鴻
    "2015-09-29",  # 杜鵑
    "2016-07-08",  # 尼伯特
    "2016-09-27",  # 梅姬
    "2016-09-28",  # 梅姬
]

# `price` 的偽交易日：2019 春節封關期間（1/30 封關、2/11 開紅盤）
PRICE_NON_TRADING_DATES: List[str] = ["2019-02-06"]

# 每張表要處理的日期；同一張表的兩類日期合併刪除，差別只在事後要不要重爬
TARGETS: Dict[str, List[str]] = {
    CHIP_TABLE_NAME: CHIP_NON_TRADING_DATES + CHIP_STALE_TRADING_DATES,
    MARGIN_TABLE_NAME: MARGIN_NON_TRADING_DATES,
    PRICE_TABLE_NAME: PRICE_NON_TRADING_DATES,
}


def count_rows(conn: sqlite3.Connection, table: str, dates: List[str]) -> int:
    """統計指定表在這些日期共有幾列"""

    placeholders: str = ",".join("?" * len(dates))
    query: str = f"SELECT COUNT(*) FROM {table} WHERE date IN ({placeholders})"
    return conn.execute(query, dates).fetchone()[0]


def export_rows(
    conn: sqlite3.Connection,
    table: str,
    dates: List[str],
    backup_path: Path,
) -> int:
    """把待刪列原樣匯出成 CSV，回傳匯出列數"""

    placeholders: str = ",".join("?" * len(dates))
    cursor: sqlite3.Cursor = conn.execute(
        f"SELECT * FROM {table} WHERE date IN ({placeholders}) ORDER BY date, stock_id",
        dates,
    )
    columns: List[str] = [d[0] for d in cursor.description]
    rows: List[Tuple] = cursor.fetchall()

    with backup_path.open("w", newline="", encoding="utf-8") as file:
        writer = csv.writer(file)
        writer.writerow(columns)
        writer.writerows(rows)

    return len(rows)


def delete_rows(conn: sqlite3.Connection, table: str, dates: List[str]) -> int:
    """刪除指定表在這些日期的所有列，回傳刪除列數"""

    placeholders: str = ",".join("?" * len(dates))
    cursor: sqlite3.Cursor = conn.execute(
        f"DELETE FROM {table} WHERE date IN ({placeholders})", dates
    )
    return cursor.rowcount


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只報告不寫入")
    parser.add_argument(
        "--backup-dir",
        default="data/downloads/tw_stock/meta",
        help="待刪列的 CSV 備份目錄",
    )
    args = parser.parse_args()

    stamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_dir: Path = Path(args.backup_dir)
    conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)

    total: int = 0
    try:
        for table, dates in TARGETS.items():
            affected: int = count_rows(conn, table, dates)
            total += affected
            print(f"[{table}] {len(dates)} 個日期、{affected:,} 列")

            if affected == 0:
                print("  已無待刪列（本腳本是冪等的）")
                continue

            if args.dry_run:
                print("  --dry-run：不寫入")
                continue

            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path: Path = backup_dir / f"stale_batches_{table}_{stamp}.csv"
            exported: int = export_rows(conn, table, dates, backup_path)
            print(f"  已備份 {exported:,} 列 → {backup_path}")

            deleted: int = delete_rows(conn, table, dates)
            print(f"  已刪除 {deleted:,} 列")

        if not args.dry_run:
            conn.commit()
            print(f"\n共處理 {total:,} 列，已提交。")
            print(
                "後續：`chip` 的 6 個真實交易日要重爬——"
                "`python -m tasks.update_db --target chip` 會由差集自動補回"
            )
        else:
            print(f"\n--dry-run：共 {total:,} 列待處理，未寫入。")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
