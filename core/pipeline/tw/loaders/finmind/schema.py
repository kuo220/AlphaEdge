import sqlite3

from loguru import logger

from core.config import (
    SECURITIES_TRADER_INFO_TABLE_NAME,
    STOCK_INFO_TABLE_NAME,
    STOCK_INFO_WITH_WARRANT_TABLE_NAME,
    STOCK_TRADING_DAILY_REPORT_TABLE_NAME,
)

"""FinMind 四張資料表的 schema（建表與索引）"""


def create_stock_info_table(conn: sqlite3.Connection) -> None:
    """創建台股總覽資料表"""

    cursor: sqlite3.Cursor = conn.cursor()

    create_table_query: str = f"""
    CREATE TABLE IF NOT EXISTS {STOCK_INFO_TABLE_NAME}(
        "industry_category" TEXT,
        "stock_id" TEXT NOT NULL,
        "stock_name" TEXT,
        "type" TEXT,
        "date" TEXT,
        PRIMARY KEY ("stock_id")
    );
    """
    cursor.execute(create_table_query)

    # 檢查是否成功建立 table
    cursor.execute(f"PRAGMA table_info('{STOCK_INFO_TABLE_NAME}')")
    if cursor.fetchall():
        logger.info(f"Table {STOCK_INFO_TABLE_NAME} create successfully!")
    else:
        logger.warning(f"Table {STOCK_INFO_TABLE_NAME} create unsuccessfully!")

    conn.commit()


def create_stock_info_with_warrant_table(conn: sqlite3.Connection) -> None:
    """創建台股總覽(含權證)資料表"""

    cursor: sqlite3.Cursor = conn.cursor()

    create_table_query: str = f"""
    CREATE TABLE IF NOT EXISTS {STOCK_INFO_WITH_WARRANT_TABLE_NAME}(
        "industry_category" TEXT,
        "stock_id" TEXT NOT NULL,
        "stock_name" TEXT,
        "type" TEXT,
        "date" TEXT,
        PRIMARY KEY ("stock_id")
    );
    """
    cursor.execute(create_table_query)

    # 檢查是否成功建立 table
    cursor.execute(f"PRAGMA table_info('{STOCK_INFO_WITH_WARRANT_TABLE_NAME}')")
    if cursor.fetchall():
        logger.info(f"Table {STOCK_INFO_WITH_WARRANT_TABLE_NAME} create successfully!")
    else:
        logger.warning(
            f"Table {STOCK_INFO_WITH_WARRANT_TABLE_NAME} create unsuccessfully!"
        )

    conn.commit()


def create_broker_info_table(conn: sqlite3.Connection) -> None:
    """創建證券商資訊表"""

    cursor: sqlite3.Cursor = conn.cursor()

    create_table_query: str = f"""
    CREATE TABLE IF NOT EXISTS {SECURITIES_TRADER_INFO_TABLE_NAME}(
        "securities_trader_id" TEXT NOT NULL,
        "securities_trader" TEXT,
        "date" TEXT,
        "address" TEXT,
        "phone" TEXT,
        PRIMARY KEY ("securities_trader_id")
    );
    """
    cursor.execute(create_table_query)

    # 檢查是否成功建立 table
    cursor.execute(f"PRAGMA table_info('{SECURITIES_TRADER_INFO_TABLE_NAME}')")
    if cursor.fetchall():
        logger.info(f"Table {SECURITIES_TRADER_INFO_TABLE_NAME} create successfully!")
    else:
        logger.warning(
            f"Table {SECURITIES_TRADER_INFO_TABLE_NAME} create unsuccessfully!"
        )

    conn.commit()


def create_broker_trading_daily_report_table(conn: sqlite3.Connection) -> None:
    """創建當日券商分點統計表"""

    cursor: sqlite3.Cursor = conn.cursor()

    create_table_query: str = f"""
    CREATE TABLE IF NOT EXISTS {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}(
        "securities_trader" TEXT,
        "securities_trader_id" TEXT NOT NULL,
        "stock_id" TEXT NOT NULL,
        "date" TEXT NOT NULL,
        "buy_volume" INTEGER,
        "sell_volume" INTEGER,
        "buy_price" REAL,
        "sell_price" REAL,
        PRIMARY KEY ("stock_id", "date", "securities_trader_id")
    );
    """
    cursor.execute(create_table_query)

    # 檢查是否成功建立 table
    cursor.execute(f"PRAGMA table_info('{STOCK_TRADING_DAILY_REPORT_TABLE_NAME}')")
    if cursor.fetchall():
        logger.info(
            f"Table {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} create successfully!"
        )
    else:
        logger.warning(
            f"Table {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} create unsuccessfully!"
        )

    conn.commit()

    # 建立 metadata GROUP BY 查詢用索引，避免每批更新時卡頓；IF NOT EXISTS 具 idempotent
    cursor.execute(
        f"CREATE INDEX IF NOT EXISTS idx_broker_trading_secid_stock_date "
        f"ON {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} (securities_trader_id, stock_id, date);"
    )
    conn.commit()
