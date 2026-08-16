"""修正 price 表中 ETF 被記在 4 碼代號下的歷史資料

## 問題

`price` 的主鍵是 `(date, stock_id, 證券名稱)`——**含證券名稱**，所以同一天同一代號
可以並存兩檔完全不同的商品，不會撞鍵也不會有任何錯誤訊息：

| 代號 | 並存商品 | 天數 | 期間 |
|------|----------|-----:|------|
| `6201` | 亞弘電（上市股）＋ 寶富櫃／元大富櫃50（上櫃 ETF） | 992 | 2013-01-02 ~ 2017-01-16 |
| `6202` | 盛群（上市股）＋ 寶富盈（上櫃 ETF） | 89 | 2013-01-02 ~ 2013-05-20 |

成因是 `price` 表把上市（TWSE）與上櫃（TPEX）資料合併存放，卻沒有市場欄位；
早年上櫃來源的 ETF 代號是 4 碼，與上市股票的代號空間相撞。

影響：`StockUtils.filter_common_stocks()` 只保留「4 碼且 1001~9958」的代號，
`6201`／`6202` 因此**通過 ETF 過濾**，回測涵蓋 2017-01-17 之前時，
`StockQuoteAdapter` 會為同一天產生兩個 `symbol` 相同的 `StockQuote`。

## 為什麼是改號而不是刪除

`006201` 在 2017-01-17 之前沒有任何資料，那 992 列是該 ETF 該期間的**唯一紀錄**，
刪掉等於少掉四年歷史。

改號的依據來自同一個資料庫的 `margin` 表——它早就把這些 ETF 存在 6 碼代號下，
連「寶富櫃 → 元大富櫃50」的改名日 2016-06-27 都與 price 完全吻合：

    margin: 寶富櫃      006201  2013-01-02 ~ 2016-06-24
    margin: 元大富櫃50   006201  2016-06-27 ~ 至今
    margin: 寶富盈      006202  2013-01-02 ~ 2013-05-20

## 使用方式

    python dev/scripts/fix_price_etf_stock_id.py --dry-run   # 只報告不寫入
    python dev/scripts/fix_price_etf_stock_id.py

本腳本是**冪等**的：改號後再次執行不會有任何待改列。
"""

import argparse
import sqlite3
from typing import Dict, List, Tuple

from core.config import DB_PATH

# 4 碼舊代號 → (正確的 6 碼代號, 該代號下屬於 ETF 的證券名稱)
ETF_CODE_FIXES: Dict[str, Tuple[str, Tuple[str, ...]]] = {
    "6201": ("006201", ("寶富櫃", "元大富櫃50")),
    "6202": ("006202", ("寶富盈",)),
}


def count_affected(conn: sqlite3.Connection, old: str, names: Tuple[str, ...]) -> int:
    """計算指定舊代號下、屬於 ETF 的列數"""

    placeholders: str = ",".join("?" * len(names))
    return conn.execute(
        f"select count(*) from price where stock_id = ? and 證券名稱 in ({placeholders})",
        (old, *names),
    ).fetchone()[0]


def count_conflicts(
    conn: sqlite3.Connection, old: str, new: str, names: Tuple[str, ...]
) -> int:
    """計算改號後會撞主鍵的列數；非 0 代表不可直接改號"""

    placeholders: str = ",".join("?" * len(names))
    return conn.execute(
        f"""
        select count(*) from price p
        where p.stock_id = ? and p.證券名稱 in ({placeholders})
          and exists (
              select 1 from price q
              where q.date = p.date and q.stock_id = ? and q.證券名稱 = p.證券名稱
          )
        """,
        (old, *names, new),
    ).fetchone()[0]


def find_ambiguous_codes(conn: sqlite3.Connection) -> List[Tuple[str, int]]:
    """找出仍有「同一天同一代號對應多個證券名稱」的代號"""

    return conn.execute("""
        select stock_id, count(*) from (
            select date, stock_id from price group by date, stock_id having count(*) > 1
        ) group by stock_id order by 2 desc
    """).fetchall()


def main() -> None:
    """執行改號；`--dry-run` 時只報告不寫入"""

    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dry-run", action="store_true", help="只報告，不寫入資料庫")
    args = parser.parse_args()

    conn: sqlite3.Connection = sqlite3.connect(DB_PATH)

    print("=== 動手前 ===")
    for code, count in find_ambiguous_codes(conn):
        print(f"  代號 {code} 有 {count} 天對應多個證券名稱")

    total_planned: int = 0
    for old, (new, names) in ETF_CODE_FIXES.items():
        affected: int = count_affected(conn, old, names)
        conflicts: int = count_conflicts(conn, old, new, names)
        print(f"  {old} → {new}: 待改 {affected} 列，撞鍵 {conflicts} 列")
        if conflicts:
            raise SystemExit(f"中止：{old} → {new} 會撞主鍵 {conflicts} 列，需人工處理")
        total_planned += affected

    if args.dry_run:
        print(f"\n[dry-run] 預計改號 {total_planned} 列，未寫入")
        conn.close()
        return

    if total_planned == 0:
        print("\n無待改列，資料已是正確狀態")
        conn.close()
        return

    conn.execute("BEGIN")
    try:
        updated: int = 0
        for old, (new, names) in ETF_CODE_FIXES.items():
            placeholders: str = ",".join("?" * len(names))
            updated += conn.execute(
                f"update price set stock_id = ? "
                f"where stock_id = ? and 證券名稱 in ({placeholders})",
                (new, old, *names),
            ).rowcount
        conn.commit()
        print(f"\n已改號 {updated} 列")
    except Exception:
        conn.rollback()
        print("\n失敗，已 rollback")
        raise

    print("\n=== 動手後 ===")
    remaining: List[Tuple[str, int]] = find_ambiguous_codes(conn)
    if remaining:
        for code, count in remaining:
            print(f"  ⚠ 代號 {code} 仍有 {count} 天對應多個證券名稱")
    else:
        print("  已無任何代號對應多個證券名稱")

    conn.close()


if __name__ == "__main__":
    main()
