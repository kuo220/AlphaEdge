"""
測試 data.db 中是否存在指定的資料表

使用方法（從專案根目錄執行）：
    python -m tests.test_db_tables

測試內容：
    檢查 data.db 中是否存在以下資料表：
    1. stock_info (taiwan_stock_info)
    2. stock_info_with_warrant (taiwan_stock_info_with_warrant)
    3. broker_info (taiwan_securities_trader_info)

測試 broker_trading 資料：
    測試 broker_trading 資料表並顯示幾筆資料：

    只檢查資料表存在性（預設行為）：
        python -m tests.test_db_tables

    另外顯示 broker_trading 的幾筆資料（預設 5 筆）：
        python -m tests.test_db_tables --broker-trading

    顯示 broker_trading 的幾筆資料並指定筆數（例如 10 筆）：
        python -m tests.test_db_tables --broker-trading --limit 10
"""

import argparse
import sqlite3
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

# 直接使用表名常數，避免導入 config 時的依賴問題
STOCK_INFO_TABLE_NAME = "taiwan_stock_info"
STOCK_INFO_WITH_WARRANT_TABLE_NAME = "taiwan_stock_info_with_warrant"
SECURITIES_TRADER_INFO_TABLE_NAME = "taiwan_securities_trader_info"
STOCK_TRADING_DAILY_REPORT_TABLE_NAME = "taiwan_stock_trading_daily_report_secid_agg"

# 嘗試從 config 獲取 DB_PATH，如果失敗則使用預設路徑
try:
    # 載入 .env 檔案（在導入 config 之前）
    try:
        from dotenv import load_dotenv

        # 載入專案根目錄的 .env 檔案
        env_path = project_root / ".env"
        if env_path.exists():
            load_dotenv(dotenv_path=env_path)
        else:
            load_dotenv()
    except ImportError:
        pass

    from trader.config import DB_PATH
except (ImportError, ModuleNotFoundError):
    # 如果無法導入 config，使用預設路徑
    DB_PATH = project_root / "trader" / "database" / "data.db"


def check_table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
    """
    檢查資料表中是否存在於資料庫中

    Args:
        conn: SQLite 資料庫連接
        table_name: 資料表名稱

    Returns:
        如果資料表存在則返回 True，否則返回 False
    """
    cursor: sqlite3.Cursor = conn.cursor()
    cursor.execute(
        """
        SELECT name FROM sqlite_master 
        WHERE type='table' AND name=?
        """,
        (table_name,),
    )
    result = cursor.fetchone()
    return result is not None


def get_table_row_count(conn: sqlite3.Connection, table_name: str) -> int:
    """
    取得資料表的資料筆數

    Args:
        conn: SQLite 資料庫連接
        table_name: 資料表名稱

    Returns:
        資料表的資料筆數
    """
    cursor: sqlite3.Cursor = conn.cursor()
    try:
        cursor.execute(f"SELECT COUNT(*) FROM {table_name}")
        result = cursor.fetchone()
        return result[0] if result else 0
    except sqlite3.Error:
        return 0


def test_db_tables() -> bool:
    """
    測試 data.db 中是否存在指定的資料表
    """
    print(f"\n{'='*60}")
    print(f"測試 data.db 資料表存在性")
    print(f"{'='*60}")
    print(f"\n資料庫路徑: {DB_PATH}")

    # 檢查資料庫檔案是否存在
    if not DB_PATH.exists():
        print(f"\n[錯誤] 資料庫檔案不存在於 {DB_PATH}")
        return False

    print(f"[OK] 資料庫檔案存在")

    # 連接資料庫
    try:
        conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
        print(f"[OK] 成功連接到資料庫\n")
    except sqlite3.Error as e:
        print(f"\n[錯誤] 無法連接到資料庫: {e}")
        return False

    # 定義要檢查的資料表
    tables_to_check = [
        ("stock_info", STOCK_INFO_TABLE_NAME),
        ("stock_info_with_warrant", STOCK_INFO_WITH_WARRANT_TABLE_NAME),
        ("broker_info", SECURITIES_TRADER_INFO_TABLE_NAME),
    ]

    # 檢查每個資料表
    all_exist = True
    results = []

    for display_name, table_name in tables_to_check:
        exists = check_table_exists(conn, table_name)
        row_count = get_table_row_count(conn, table_name) if exists else 0

        status = "[OK]" if exists else "[X]"
        results.append((display_name, table_name, exists, row_count))

        print(f"{status} {display_name}")
        print(f"   表名: {table_name}")
        print(f"   存在: {'是' if exists else '否'}")
        if exists:
            print(f"   資料筆數: {row_count:,}")
        print()

        if not exists:
            all_exist = False

    # 關閉資料庫連接
    conn.close()

    # 顯示總結
    print(f"{'='*60}")
    if all_exist:
        print("[OK] 所有資料表都存在！")
        print(f"{'='*60}\n")
        print("資料表摘要:")
        for display_name, table_name, exists, row_count in results:
            print(f"   - {display_name} ({table_name}): {row_count:,} 筆")
        return True
    else:
        print("[X] 部分資料表不存在！")
        print(f"{'='*60}\n")
        print("缺失的資料表:")
        for display_name, table_name, exists, row_count in results:
            if not exists:
                print(f"   - {display_name} ({table_name})")
        return False


def test_broker_trading_data(limit: int = 5) -> None:
    """
    測試 broker_trading 資料表並顯示幾筆資料

    使用方法（從專案根目錄執行）：
        python -m tests.test_db_tables --broker-trading --limit 10

    Args:
        limit: 要顯示的資料筆數（預設為 5 筆）
    """
    print(f"\n{'='*60}")
    print(f"測試 broker_trading 資料表資料")
    print(f"{'='*60}")
    print(f"\n資料庫路徑: {DB_PATH}")

    # 檢查資料庫檔案是否存在
    if not DB_PATH.exists():
        print(f"\n[錯誤] 資料庫檔案不存在於 {DB_PATH}")
        return

    print(f"[OK] 資料庫檔案存在")

    # 連接資料庫
    try:
        conn: sqlite3.Connection = sqlite3.connect(DB_PATH)
        print(f"[OK] 成功連接到資料庫\n")
    except sqlite3.Error as e:
        print(f"\n[錯誤] 無法連接到資料庫: {e}")
        return

    # 檢查資料表是否存在
    if not check_table_exists(conn, STOCK_TRADING_DAILY_REPORT_TABLE_NAME):
        print(f"[X] 資料表 {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} 不存在")
        conn.close()
        return

    print(f"[OK] 資料表 {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} 存在")

    # 取得資料筆數
    row_count = get_table_row_count(conn, STOCK_TRADING_DAILY_REPORT_TABLE_NAME)
    print(f"[OK] 資料筆數: {row_count:,} 筆\n")

    if row_count == 0:
        print("[警告] 資料表中沒有資料")
        conn.close()
        return

    # 查詢前幾筆資料
    cursor: sqlite3.Cursor = conn.cursor()
    try:
        query = f"""
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
        LIMIT {limit}
        """
        cursor.execute(query)
        results = cursor.fetchall()

        # 取得欄位名稱
        column_names = [description[0] for description in cursor.description]

        print(f"{'='*60}")
        print(f"顯示前 {len(results)} 筆資料:")
        print(f"{'='*60}\n")

        # 顯示資料
        for idx, row in enumerate(results, 1):
            print(f"第 {idx} 筆:")
            for col_name, value in zip(column_names, row):
                if value is None:
                    print(f"   {col_name}: None")
                elif isinstance(value, float):
                    print(f"   {col_name}: {value:,.2f}")
                elif isinstance(value, int):
                    print(f"   {col_name}: {value:,}")
                else:
                    print(f"   {col_name}: {value}")
            print()

        print(f"{'='*60}")
        print(f"[完成] 已顯示 {len(results)} 筆資料（共 {row_count:,} 筆）")
        print(f"{'='*60}\n")

    except sqlite3.Error as e:
        print(f"[錯誤] 查詢資料時發生錯誤: {e}")
    finally:
        conn.close()


def parse_args() -> argparse.Namespace:
    """
    解析命令列參數

    範例：
        python -m tests.test_db_tables
        python -m tests.test_db_tables --broker-trading
        python -m tests.test_db_tables --broker-trading --limit 10
    """
    parser = argparse.ArgumentParser(description="測試 data.db 資料表與抽樣查詢")
    parser.add_argument(
        "--broker-trading",
        action="store_true",
        help="額外測試 broker_trading 資料表並顯示抽樣資料",
    )
    parser.add_argument(
        "--limit",
        type=int,
        default=5,
        help="broker_trading 抽樣顯示筆數（預設 5）",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    success: bool = test_db_tables()

    if args.broker_trading:
        test_broker_trading_data(limit=args.limit)

    if success:
        print("\n[完成] 測試完成！")
    else:
        print("\n[警告] 測試未完全成功，請檢查上述輸出")
        sys.exit(1)
