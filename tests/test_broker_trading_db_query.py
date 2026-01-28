"""
測試腳本：查詢 data.db 資料庫中的 broker_trading 資料
用於確認資料是否真的有存進資料庫

使用方法（從專案根目錄執行）：
    # 基本查詢（顯示所有統計資訊）
    python -m tests.test_broker_trading_db_query

    # 查詢特定股票
    python -m tests.test_broker_trading_db_query --stock-id 2330

    # 查詢特定券商
    python -m tests.test_broker_trading_db_query --trader-id 1020

    # 查詢特定股票和券商組合
    python -m tests.test_broker_trading_db_query --stock-id 2330 --trader-id 1020

    # 調整顯示筆數
    python -m tests.test_broker_trading_db_query --limit 20

    # 組合使用多個參數
    python -m tests.test_broker_trading_db_query --stock-id 2330 --trader-id 1020 --limit 50

功能說明：
    - 顯示資料庫基本資訊（總筆數、日期範圍、不重複股票數、不重複券商數）
    - 顯示前 N 筆資料（預設 10 筆）
    - 如果指定股票或券商，會顯示符合條件的資料
    - 顯示各股票資料筆數統計（前 10 名）
    - 顯示各券商資料筆數統計（前 10 名）

注意事項：
    - 資料庫路徑由 trader.config.DB_PATH 決定
    - 資料表名稱由 trader.config.STOCK_TRADING_DAILY_REPORT_TABLE_NAME 決定
    - 如果資料庫或資料表不存在，會顯示錯誤訊息
    - 此腳本只讀取資料，不會修改資料庫
"""

import sqlite3
import sys
from pathlib import Path
from typing import Optional

import pandas as pd

# 添加專案根目錄到 Python 路徑
project_root: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from trader.config import DB_PATH, STOCK_TRADING_DAILY_REPORT_TABLE_NAME


def test_broker_trading_db_query(
    stock_id: Optional[str] = None,
    securities_trader_id: Optional[str] = None,
    limit: int = 10,
) -> None:
    """
    查詢資料庫中的 broker_trading 資料

    Args:
        stock_id: 股票代碼（可選）
        securities_trader_id: 券商代碼（可選）
        limit: 限制查詢筆數
    """
    print(f"\n{'='*60}")
    print(f"查詢 Broker Trading 資料庫資料")
    print(f"{'='*60}")

    # 檢查資料庫檔案是否存在
    if not DB_PATH.exists():
        print(f"❌ 資料庫檔案不存在: {DB_PATH}")
        return

    print(f"\n📁 資料庫路徑: {DB_PATH}")
    print(f"📊 資料表名稱: {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}")

    try:
        # 連接資料庫
        conn = sqlite3.connect(str(DB_PATH))

        # 1. 檢查表是否存在
        cursor = conn.cursor()
        cursor.execute(
            """
            SELECT name FROM sqlite_master 
            WHERE type='table' AND name=?
            """,
            (STOCK_TRADING_DAILY_REPORT_TABLE_NAME,),
        )
        table_exists = cursor.fetchone() is not None

        if not table_exists:
            print(f"\n❌ 資料表不存在: {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}")
            conn.close()
            return

        print(f"\n✅ 資料表存在")

        # 2. 查詢總筆數
        query_count = f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
        cursor.execute(query_count)
        total_count = cursor.fetchone()[0]
        print(f"\n📊 總資料筆數: {total_count:,}")

        if total_count == 0:
            print("\n⚠️  資料表中沒有任何資料")
            conn.close()
            return

        # 3. 查詢日期範圍
        query_date_range = f"""
        SELECT 
            MIN(date) as earliest_date,
            MAX(date) as latest_date
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        """
        cursor.execute(query_date_range)
        date_range = cursor.fetchone()
        if date_range and date_range[0]:
            print(f"📅 日期範圍: {date_range[0]} ~ {date_range[1]}")

        # 4. 查詢不重複的股票和券商數量
        query_unique_stocks = f"""
        SELECT COUNT(DISTINCT stock_id) 
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        """
        cursor.execute(query_unique_stocks)
        unique_stocks = cursor.fetchone()[0]
        print(f"📈 不重複股票數: {unique_stocks}")

        query_unique_traders = f"""
        SELECT COUNT(DISTINCT securities_trader_id) 
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        """
        cursor.execute(query_unique_traders)
        unique_traders = cursor.fetchone()[0]
        print(f"🏢 不重複券商數: {unique_traders}")

        # 5. 查詢前 N 筆資料
        print(f"\n{'='*60}")
        print(f"查詢前 {limit} 筆資料")
        print(f"{'='*60}")

        query_data = f"""
        SELECT 
            securities_trader,
            securities_trader_id,
            stock_id,
            date,
            buy_volume,
            sell_volume,
            buy_price,
            sell_price
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        ORDER BY date DESC, stock_id, securities_trader_id
        LIMIT ?
        """

        df = pd.read_sql_query(query_data, conn, params=(limit,))
        print(f"\n{df.to_string(index=False)}")

        # 6. 如果有指定股票或券商，查詢特定資料
        if stock_id or securities_trader_id:
            print(f"\n{'='*60}")
            print(f"查詢特定條件資料")
            print(f"{'='*60}")

            conditions = []
            params = []

            if stock_id:
                conditions.append("stock_id = ?")
                params.append(stock_id)
                print(f"📈 股票代碼: {stock_id}")

            if securities_trader_id:
                conditions.append("securities_trader_id = ?")
                params.append(securities_trader_id)
                print(f"🏢 券商代碼: {securities_trader_id}")

            where_clause = " AND ".join(conditions)
            query_specific = f"""
            SELECT 
                securities_trader,
                securities_trader_id,
                stock_id,
                date,
                buy_volume,
                sell_volume,
                buy_price,
                sell_price
            FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
            WHERE {where_clause}
            ORDER BY date DESC
            LIMIT ?
            """
            params.append(limit)

            df_specific = pd.read_sql_query(query_specific, conn, params=params)
            print(f"\n找到 {len(df_specific)} 筆資料:")
            print(f"\n{df_specific.to_string(index=False)}")

        # 7. 統計每個股票的資料筆數（前 10 名）
        print(f"\n{'='*60}")
        print(f"各股票資料筆數統計（前 10 名）")
        print(f"{'='*60}")

        query_stats = f"""
        SELECT 
            stock_id,
            COUNT(*) as count,
            MIN(date) as earliest_date,
            MAX(date) as latest_date
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        GROUP BY stock_id
        ORDER BY count DESC
        LIMIT 10
        """
        df_stats = pd.read_sql_query(query_stats, conn)
        print(f"\n{df_stats.to_string(index=False)}")

        # 8. 統計每個券商的資料筆數（前 10 名）
        print(f"\n{'='*60}")
        print(f"各券商資料筆數統計（前 10 名）")
        print(f"{'='*60}")

        query_trader_stats = f"""
        SELECT 
            securities_trader_id,
            securities_trader,
            COUNT(*) as count,
            MIN(date) as earliest_date,
            MAX(date) as latest_date
        FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
        GROUP BY securities_trader_id, securities_trader
        ORDER BY count DESC
        LIMIT 10
        """
        df_trader_stats = pd.read_sql_query(query_trader_stats, conn)
        print(f"\n{df_trader_stats.to_string(index=False)}")

        conn.close()

        print(f"\n{'='*60}")
        print(f"✅ 查詢完成！")
        print(f"{'='*60}")

    except sqlite3.Error as e:
        print(f"\n❌ 資料庫錯誤: {e}")
    except Exception as e:
        print(f"\n❌ 發生錯誤: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="查詢 broker_trading 資料庫資料")
    parser.add_argument("--stock-id", type=str, help="股票代碼（可選）", default=None)
    parser.add_argument("--trader-id", type=str, help="券商代碼（可選）", default=None)
    parser.add_argument("--limit", type=int, help="限制查詢筆數", default=10)

    args = parser.parse_args()

    test_broker_trading_db_query(
        stock_id=args.stock_id,
        securities_trader_id=args.trader_id,
        limit=args.limit,
    )
