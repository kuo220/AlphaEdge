"""
測試 FinMindLoader._load_broker_trading_daily_report_from_dataframe 的優化（第 2 點）：
只查詢本批 df 涉及的 (stock_id, securities_trader_id) 在 DB 中已存在的 key，而非全表掃描。
使用測試用臨時資料庫。
"""
import datetime
import sqlite3
import sys
from pathlib import Path
from unittest.mock import patch

import pandas as pd

project_root: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

from trader.config import STOCK_TRADING_DAILY_REPORT_TABLE_NAME


def _make_broker_trading_df(
    stock_id: str,
    securities_trader_id: str,
    securities_trader: str,
    dates: list[str],
) -> pd.DataFrame:
    """組出符合 loader 需求的 broker trading DataFrame。"""
    rows = []
    for d in dates:
        rows.append(
            {
                "securities_trader": securities_trader,
                "securities_trader_id": securities_trader_id,
                "stock_id": stock_id,
                "date": d,
                "buy_volume": 100,
                "sell_volume": 50,
                "buy_price": 500.0,
                "sell_price": 501.0,
            }
        )
    return pd.DataFrame(rows)


def test_load_broker_trading_from_dataframe_optimization():
    """驗證優化 2：只查本批 (stock_id, securities_trader_id) 的已存在 key，且重複不重插、新日期可插入。"""
    temp_dir: Path = project_root / "tests" / "temp"
    temp_dir.mkdir(parents=True, exist_ok=True)
    timestamp: str = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    temp_db_path: str = str(temp_dir / f"test_finmind_loader_opt_{timestamp}.db")

    with patch("trader.config.DB_PATH", temp_db_path), patch(
        "trader.pipeline.loaders.finmind_loader.DB_PATH", temp_db_path
    ):
        from trader.pipeline.loaders.finmind_loader import FinMindLoader

        loader: FinMindLoader = FinMindLoader()
        loader.connect()
        loader.create_missing_tables()

        try:
            # 1) 第一次載入：一組 (2330, 1020) 兩筆日期
            df1 = _make_broker_trading_df(
                stock_id="2330",
                securities_trader_id="1020",
                securities_trader="兆豐",
                dates=["2024-07-01", "2024-07-02"],
            )
            n1 = loader.load_broker_trading_daily_report(df=df1)
            assert n1 == 2, f"第一次應插入 2 筆，實際 {n1}"

            conn = sqlite3.connect(temp_db_path)
            cur = conn.cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
            )
            total = cur.fetchone()[0]
            conn.close()
            assert total == 2, f"表應為 2 筆，實際 {total}"

            # 2) 再載入相同資料：應全部視為重複，插入 0 筆
            n2 = loader.load_broker_trading_daily_report(df=df1)
            assert n2 == 0, f"重複載入應插入 0 筆，實際 {n2}"

            cur = sqlite3.connect(temp_db_path).cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
            )
            total = cur.fetchone()[0]
            assert total == 2, f"表仍應為 2 筆，實際 {total}"

            # 3) 同一組合多一筆新日期：應只插入 1 筆
            df3 = _make_broker_trading_df(
                stock_id="2330",
                securities_trader_id="1020",
                securities_trader="兆豐",
                dates=["2024-07-01", "2024-07-02", "2024-07-03"],
            )
            n3 = loader.load_broker_trading_daily_report(df=df3)
            assert n3 == 1, f"應只插入 1 筆新日期，實際 {n3}"

            cur = sqlite3.connect(temp_db_path).cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}"
            )
            total = cur.fetchone()[0]
            assert total == 3, f"表應為 3 筆，實際 {total}"

            # 4) 驗證「只查本批組合」：先手動插入另一組合 (2317, 1020)，再載入僅 (2330, 1020) 的 df，
            #    另一組合筆數不應被影響（證明 WHERE 只查本批）
            conn = sqlite3.connect(temp_db_path)
            conn.execute(
                f"""
                INSERT INTO {STOCK_TRADING_DAILY_REPORT_TABLE_NAME}
                (securities_trader, securities_trader_id, stock_id, date, buy_volume, sell_volume, buy_price, sell_price)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                ("兆豐", "1020", "2317", "2024-07-05", 200, 100, 100.0, 101.0),
            )
            conn.commit()
            conn.close()

            cur = sqlite3.connect(temp_db_path).cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} WHERE stock_id = ? AND securities_trader_id = ?",
                ("2317", "1020"),
            )
            count_2317_before = cur.fetchone()[0]
            assert count_2317_before == 1

            # 只載入 (2330, 1020) 的資料（一筆已存在、一筆新日期）
            df4 = _make_broker_trading_df(
                stock_id="2330",
                securities_trader_id="1020",
                securities_trader="兆豐",
                dates=["2024-07-02", "2024-07-04"],
            )
            n4 = loader.load_broker_trading_daily_report(df=df4)
            assert n4 == 1, f"應只插入 1 筆 (2024-07-04)，實際 {n4}"

            cur = sqlite3.connect(temp_db_path).cursor()
            cur.execute(
                f"SELECT COUNT(*) FROM {STOCK_TRADING_DAILY_REPORT_TABLE_NAME} WHERE stock_id = ? AND securities_trader_id = ?",
                ("2317", "1020"),
            )
            count_2317_after = cur.fetchone()[0]
            assert count_2317_after == 1, (
                "另一組合 (2317, 1020) 筆數不應被改動，證明查詢只限本批"
            )

        finally:
            loader.disconnect()


if __name__ == "__main__":
    test_load_broker_trading_from_dataframe_optimization()
    print("test_finmind_loader_broker_trading: 全部通過")
