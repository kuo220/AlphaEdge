"""清除只入庫單一市場的日頻批次（爬蟲缺口回補 S10）

## 問題

台股的日頻表都是**兩個來源拼成一天**：TWSE 一份、TPEX 一份，清洗後寫進同一張表。
若其中一個來源當天沒問到，另一個仍會照常入庫，於是那一天在庫裡**看起來是有資料的**
——只是少了半個市場。這種缺法：

- 不會被 `test_no_non_trading_day_batches` 抓到：日期軸完全正常，四張表都有那天。
- 不會被 `test_no_stale_replayed_batches` 抓到：內容是真的，只是少一半，指紋不碰撞。
- 不會被任何缺口統計抓到：缺口統計看的是「哪幾天完全沒有」。

2026-09-05 掃描結果（以「該市場檔數低於前後各 5 個交易日中位數的 10%」為判準）：

| 表 | 日期數 | 缺的市場 |
|----|------:|---------|
| `chip` | 9 | 全部是 TWSE |
| `price` | 2 | 全部是 TWSE |
| `margin` | 0 | — |

`margin` 掛零不是巧合：它的 TWSE 那條路徑一次要問五個 `selectType`，
任一個失敗都會讓整天判定失敗而不入庫，反而不會留下半套資料。

## 為什麼判準是「低於 10%」而不是「低於 85%」

85% 那條線是 S1 當時用來找受污染日的，它會連帶掃到 22 個**列數本來就偏低**的日期
（早年補行交易的週六、跌停鎖死的股災日），當成斷言只會變紅燈噪音。
本腳本要處理的是「整個市場不見了」，實測命中的 11 天該市場只剩 0~15 檔
（鄰日 1,020~1,339 檔），與正常日之間有兩個數量級的空隙，10% 這條線落在空隙裡。

## 處置

刪除該日**整天**的資料（不是只刪存在的那半邊），刪除前逐列匯出 CSV 備份。
兩支 updater 的候選日期都是差集，所以刪完重跑就會把整天重爬回來：

    python scripts/fix_single_market_batches.py --dry-run   # 只報告不寫入
    python scripts/fix_single_market_batches.py             # 執行，先備份再刪
    python -m tasks.update_db --target price                # 先補日曆來源
    python -m tasks.update_db --target chip                 # 再補籌碼

**`price` 要先補**：它同時是 `stock_chip_updater` 的交易日曆來源，
先刪後補的空窗期內，被刪掉的那天不會出現在籌碼的候選日期裡。

本腳本是**冪等**的：重爬成功之後再跑一次不會有任何待刪列。
"""

import argparse
import csv
import datetime
import sqlite3
import statistics
from pathlib import Path
from typing import Dict, List, Tuple

from core.config import (
    CHIP_TABLE_NAME,
    MARGIN_TABLE_NAME,
    PRICE_TABLE_NAME,
    STOCK_INFO_TABLE_NAME,
    TW_STOCK_DB_PATH,
)

# 掃描的資料表；三張都是「TWSE ＋ TPEX 拼成一天」的結構
SCANNED_TABLES: List[str] = [PRICE_TABLE_NAME, CHIP_TABLE_NAME, MARGIN_TABLE_NAME]

# 兩個市場別；`taiwan_stock_info.type` 的其餘值（`emerging`）與查不到的代號都不列入，
# 它們在日頻表裡佔比不到 1%，納入只會讓分母抖動
MARKETS: Tuple[str, str] = ("twse", "tpex")

# 判定「整個市場不見了」的門檻與鄰日窗寬，理由見模組說明
MISSING_RATIO: float = 0.1
NEIGHBOUR_RADIUS: int = 5

# 鄰日中位數低於此值時不判定：市場剛開辦或資料稀疏的早年，分母本來就小
MIN_NEIGHBOUR_MEDIAN: int = 100


def load_market_map(conn: sqlite3.Connection) -> Dict[str, str]:
    """個股代號 → 市場別

    `taiwan_stock_info` 是逐次快照，同一檔可能出現在多個日期。取先遇到的即可
    ——個股不會在 TWSE 與 TPEX 之間反覆搬家，而轉板的少數個案落在哪一邊，
    對「整個市場是否不見了」這個量級的判斷沒有影響。
    """

    market_map: Dict[str, str] = {}
    for stock_id, market in conn.execute(
        f"SELECT stock_id, type FROM {STOCK_INFO_TABLE_NAME}"
    ):
        market_map.setdefault(stock_id, market)
    return market_map


def count_by_market(
    conn: sqlite3.Connection, table: str, market_map: Dict[str, str]
) -> Dict[str, Dict[str, int]]:
    """逐日統計各市場的檔數"""

    per_date: Dict[str, Dict[str, int]] = {}
    for date, stock_id in conn.execute(f"SELECT date, stock_id FROM {table}"):
        counts: Dict[str, int] = per_date.setdefault(date, {m: 0 for m in MARKETS})
        market: str = market_map.get(stock_id, "")
        if market in counts:
            counts[market] += 1
    return per_date


def find_single_market_dates(
    per_date: Dict[str, Dict[str, int]],
) -> List[Tuple[str, str, int, int]]:
    """找出某一市場整批不見的日期，回傳 (日期, 缺的市場, 該日檔數, 鄰日中位數)"""

    dates: List[str] = sorted(per_date)
    hits: List[Tuple[str, str, int, int]] = []

    for i, date in enumerate(dates):
        lo: int = max(0, i - NEIGHBOUR_RADIUS)
        hi: int = min(len(dates), i + NEIGHBOUR_RADIUS + 1)
        neighbours: List[str] = [dates[j] for j in range(lo, hi) if j != i]
        if not neighbours:
            continue

        for market in MARKETS:
            median: float = statistics.median([per_date[d][market] for d in neighbours])
            if median < MIN_NEIGHBOUR_MEDIAN:
                continue
            if per_date[date][market] < MISSING_RATIO * median:
                hits.append((date, market, per_date[date][market], int(median)))

    return hits


def export_rows(
    conn: sqlite3.Connection, table: str, dates: List[str], backup_path: Path
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
        market_map: Dict[str, str] = load_market_map(conn)

        for table in SCANNED_TABLES:
            per_date: Dict[str, Dict[str, int]] = count_by_market(
                conn, table, market_map
            )
            hits: List[Tuple[str, str, int, int]] = find_single_market_dates(per_date)

            print(f"[{table}] 命中 {len(hits)} 天")
            for date, market, actual, median in hits:
                weekday: str = "一二三四五六日"[
                    datetime.date.fromisoformat(date).weekday()
                ]
                print(
                    f"  {date}（{weekday}）{market} 僅 {actual} 檔"
                    f"（鄰日中位數 {median}）"
                )

            if not hits:
                continue

            # 同一天可能兩個市場都命中，去重後才是要刪的日期
            dates: List[str] = sorted({date for date, _, _, _ in hits})
            affected: int = conn.execute(
                f"SELECT COUNT(*) FROM {table} "
                f"WHERE date IN ({','.join('?' * len(dates))})",
                dates,
            ).fetchone()[0]
            total += affected
            print(f"  整天刪除共 {affected:,} 列")

            if args.dry_run:
                print("  --dry-run：不寫入")
                continue

            backup_dir.mkdir(parents=True, exist_ok=True)
            backup_path: Path = backup_dir / f"single_market_{table}_{stamp}.csv"
            exported: int = export_rows(conn, table, dates, backup_path)
            print(f"  已備份 {exported:,} 列 → {backup_path}")

            deleted: int = delete_rows(conn, table, dates)
            print(f"  已刪除 {deleted:,} 列")

        if args.dry_run:
            print(f"\n--dry-run：共 {total:,} 列待處理，未寫入。")
        else:
            conn.commit()
            print(f"\n共處理 {total:,} 列，已提交。")
            print(
                "後續：先 `--target price`（日曆來源）再 `--target chip`，"
                "兩支 updater 的差集會把整天重爬回來"
            )
    finally:
        conn.close()


if __name__ == "__main__":
    main()
