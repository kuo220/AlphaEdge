"""
刪除 price table 中指定日期的資料

Usage:
    python -m tasks.delete_price_data --date 2025-07-13
    python -m tasks.delete_price_data --date 2025/7/13
"""

import argparse
import datetime
import sqlite3
from typing import List

from loguru import logger

from trader.config import DB_PATH, PRICE_TABLE_NAME


def parse_date(date_str: str) -> str:
    """解析日期字串，返回標準格式 YYYY-MM-DD"""
    # 嘗試多種日期格式
    formats: List[str] = [
        "%Y-%m-%d",  # 2025-07-13
        "%Y/%m/%d",  # 2025/7/13 或 2025/07/13
        "%Y-%m-%d",  # 2025-7-13
    ]

    for fmt in formats:
        try:
            date_obj: datetime.date = datetime.datetime.strptime(date_str, fmt).date()
            return date_obj.strftime("%Y-%m-%d")
        except ValueError:
            continue

    raise ValueError(f"無法解析日期格式: {date_str}")


def delete_price_data_by_date(date_str: str) -> None:
    """刪除 price table 中指定日期的所有資料"""

    # 解析日期
    try:
        formatted_date: str = parse_date(date_str)
    except ValueError as e:
        logger.error(f"日期解析失敗: {e}")
        return

    logger.info(f"準備刪除 price table 中日期為 {formatted_date} 的資料...")

    # 連接資料庫
    conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
    cursor: sqlite3.Cursor = conn.cursor()

    try:
        # 先查詢要刪除的資料筆數
        count_query: str = f'SELECT COUNT(*) FROM "{PRICE_TABLE_NAME}" WHERE date = ?'
        cursor.execute(count_query, (formatted_date,))
        count: int = cursor.fetchone()[0]

        if count == 0:
            logger.warning(f"price table 中沒有日期為 {formatted_date} 的資料")
            return

        logger.info(f"找到 {count} 筆資料需要刪除")

        # 刪除資料
        delete_query: str = f'DELETE FROM "{PRICE_TABLE_NAME}" WHERE date = ?'
        cursor.execute(delete_query, (formatted_date,))

        # 提交變更
        conn.commit()

        # 驗證刪除結果
        cursor.execute(count_query, (formatted_date,))
        remaining_count: int = cursor.fetchone()[0]

        if remaining_count == 0:
            logger.info(f"✅ 成功刪除 {count} 筆資料")
        else:
            logger.warning(f"⚠️ 刪除後仍有 {remaining_count} 筆資料存在")

    except sqlite3.Error as e:
        logger.error(f"資料庫操作失敗: {e}")
        conn.rollback()
    finally:
        conn.close()


def main() -> None:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="刪除 price table 中指定日期的資料"
    )
    parser.add_argument(
        "--date",
        type=str,
        required=True,
        help="要刪除的日期 (格式: YYYY-MM-DD 或 YYYY/MM/DD，例如: 2025-07-13 或 2025/7/13)",
    )

    args: argparse.Namespace = parser.parse_args()
    delete_price_data_by_date(args.date)


if __name__ == "__main__":
    main()
