"""把 price 表中「沒有成交價」的列由 0 改回 NULL

## 問題

無成交日（或站方以 `--` 表示無報價）的 OHLC 在來源是 `--`，`StockPriceCleaner`
轉數值後得到 NaN，接著被 `DataUtils.fill_nan(df, 0)` **一律填成 0**。
於是資料庫裡留下一個**看起來完全正常的假價格**：當天成交價 0 元。

回測沒有任何理由懷疑它——`price` 表的欄位型別是 REAL，0 是合法的數字——
於是這些列會被 `StockQuoteAdapter` 轉成 `StockQuote(close=0.0)`，
策略拿它算報酬、下單、停損，得到的結果與現實無關（健檢 F-037）。

實測（2026-09-03，`tw_stock.db`）：

    收盤價 = 0 的列                     104,046
    其中成交股數也是 0                    96,089
    其中成交股數 > 0（版面錯位）           7,957

**後者一樣要修**：`2833A` 台壽甲 2013-01-02 的成交金額 27,521 ÷ 成交股數 754
＝ 每股 36.5 元，但 OHLC 四欄全是 0。價格欄是壞的，不是那天真的以 0 元成交。

## 為什麼是改成 NULL 而不是刪除

那幾列的成交量、成交金額、成交筆數是**真的**，`margin`／`chip` 也可能參照到
同一天的同一檔。刪掉會連正確的部分一起丟掉；改成 NULL 則精確表達
「這幾個欄位沒有值」，下游 `StockQuoteAdapter.has_valid_price()` 會濾掉它們。

## 使用方式

    python scripts/fix_price_no_trade_rows.py --dry-run   # 只報告不寫入
    python scripts/fix_price_no_trade_rows.py

本腳本是**冪等**的：改成 NULL 之後再次執行不會有任何待改列。
"""

import argparse
import sqlite3
from typing import List, Tuple

from core.config import PRICE_TABLE_NAME, TW_STOCK_DB_PATH

# 沒有成交價時要改成 NULL 的欄位。
# 成交股數／成交金額／成交筆數**不在此列**——那些值是真的，0 就是 0。
PRICE_COLUMNS: List[str] = [
    "開盤價",
    "最高價",
    "最低價",
    "收盤價",
    "最後揭示買價",
    "最後揭示賣價",
]

# 判定「沒有成交價」的條件：四個 OHLC 欄全為 0。
# 合法的收盤價不可能是 0，四欄同時為 0 更不可能是巧合。
NO_TRADE_CONDITION: str = (
    '"開盤價" = 0 AND "最高價" = 0 AND "最低價" = 0 AND "收盤價" = 0'
)


def count_affected(conn: sqlite3.Connection) -> int:
    """待修正的列數"""

    query: str = f'SELECT COUNT(*) FROM "{PRICE_TABLE_NAME}" WHERE {NO_TRADE_CONDITION}'
    return conn.execute(query).fetchone()[0]


def sample_affected(conn: sqlite3.Connection, limit: int = 5) -> List[Tuple]:
    """抽幾列出來看，確認條件抓對了東西"""

    query: str = f"""
    SELECT date, stock_id, "證券名稱", "成交股數", "成交金額"
    FROM "{PRICE_TABLE_NAME}"
    WHERE {NO_TRADE_CONDITION}
    ORDER BY date
    LIMIT ?
    """
    return conn.execute(query, (limit,)).fetchall()


def fix_rows(conn: sqlite3.Connection) -> int:
    """把符合條件的列的價格欄改成 NULL；回傳實際更新列數"""

    set_clause: str = ", ".join(f'"{col}" = NULL' for col in PRICE_COLUMNS)
    query: str = (
        f'UPDATE "{PRICE_TABLE_NAME}" SET {set_clause} WHERE {NO_TRADE_CONDITION}'
    )
    cursor: sqlite3.Cursor = conn.execute(query)
    conn.commit()
    return cursor.rowcount


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="把 price 表中沒有成交價的列由 0 改回 NULL"
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="只報告待修正的列數與範例，不寫入資料庫",
    )
    args: argparse.Namespace = parser.parse_args()

    conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)
    try:
        affected: int = count_affected(conn)
        print(f"待修正列數：{affected}")

        for row in sample_affected(conn):
            print(f"  {row}")

        if affected == 0:
            print("沒有待修正的列（本腳本是冪等的）")
            return

        if args.dry_run:
            print("--dry-run：未寫入任何資料")
            return

        updated: int = fix_rows(conn)
        print(f"已將 {updated} 列的 {'、'.join(PRICE_COLUMNS)} 改為 NULL")

        remaining: int = count_affected(conn)
        print(f"修正後仍符合條件的列數：{remaining}（應為 0）")
    finally:
        conn.close()


if __name__ == "__main__":
    main()
