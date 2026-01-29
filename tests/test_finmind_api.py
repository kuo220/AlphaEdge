"""
測試 FinMindAPI 的每一個 function 是否正常運作

直接使用 data.db 唯讀查詢，不更動資料庫

使用方法（從專案根目錄執行）：
    python -m tests.test_finmind_api

測試內容（對應 trader.api.finmind_api）：
    1. get_stock_info(stock_id) - 單一股票台股總覽（不含權證）
    2. get_all_stock_info() - 全部台股總覽（不含權證）
    3. get_stock_info_with_warrant(stock_id) - 單一股票台股總覽（含權證）
    4. get_all_stock_info_with_warrant() - 全部台股總覽（含權證）
    5. get_broker_info(securities_trader_id) - 單一證券商資訊
    6. get_all_broker_info() - 全部證券商資訊
    7. get_broker_trading_by_date(date) - 指定日期券商分點日報
    8. get_broker_trading_range(start_date, end_date) - 日期區間券商分點日報
    9. get_broker_trading_for_stock_on_date(stock_id, date) - 指定股票指定日期券商分點（單日）
    10. get_broker_trading_for_stock_in_range(stock_id, start_date, end_date) - 指定股票區間券商分點（多日）
    11. get_broker_trading_by_broker_and_date(securities_trader, date) - 依券商中文名與日期取得該券商當日分點日報
"""

import datetime
import sys
from pathlib import Path

# 添加專案根目錄到 Python 路徑
project_root: Path = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

import pandas as pd

from trader.api.finmind_api import FinMindAPI


def test_finmind_api() -> bool:
    """測試 FinMindAPI 所有方法（唯讀，使用 data.db）"""
    print("\n" + "=" * 60)
    print("測試 FinMindAPI 各 function（使用 data.db 唯讀）")
    print("=" * 60)

    api = FinMindAPI()
    all_ok = True

    def check(name: str, df: pd.DataFrame) -> None:
        nonlocal all_ok
        try:
            assert isinstance(df, pd.DataFrame), f"{name} 應回傳 DataFrame"
            print(f"[OK] {name}")
            if len(df) > 0:
                n = min(5, len(df))
                print(f"    前 {n} 筆（共 {len(df)} 筆）：")
                print(df.head(5).to_string(index=False))
            else:
                print(f"    筆數: 0（空 DataFrame）")
            print()
        except Exception as e:
            print(f"[X] {name}: {e}")
            all_ok = False

    # 1. get_stock_info
    df = api.get_stock_info("2330")
    check("get_stock_info(stock_id)", df)

    # 2. get_all_stock_info
    df = api.get_all_stock_info()
    check("get_all_stock_info()", df)

    # 3. get_stock_info_with_warrant
    df = api.get_stock_info_with_warrant("2330")
    check("get_stock_info_with_warrant(stock_id)", df)

    # 4. get_all_stock_info_with_warrant
    df = api.get_all_stock_info_with_warrant()
    check("get_all_stock_info_with_warrant()", df)

    # 5. get_broker_info
    df = api.get_broker_info("9A00")
    check("get_broker_info(securities_trader_id)", df)

    # 6. get_all_broker_info
    df = api.get_all_broker_info()
    check("get_all_broker_info()", df)

    # 7. get_broker_trading_by_date
    d = datetime.date(2024, 7, 1)
    df = api.get_broker_trading_by_date(d)
    check("get_broker_trading_by_date(date)", df)

    # 8. get_broker_trading_range
    start = datetime.date(2024, 7, 1)
    end = datetime.date(2024, 7, 15)
    df = api.get_broker_trading_range(start, end)
    check("get_broker_trading_range(start_date, end_date)", df)
    # start > end 應回傳空 DataFrame（API 邏輯）
    df_empty = api.get_broker_trading_range(end, start)
    try:
        assert isinstance(df_empty, pd.DataFrame) and len(df_empty) == 0
        print("[OK] get_broker_trading_range(start > end) 回傳空 DataFrame")
        print(f"    筆數: 0（空 DataFrame）")
        print()
    except Exception as e:
        print(f"[X] get_broker_trading_range(start > end): {e}")
        all_ok = False

    # 9. get_broker_trading_for_stock_on_date（單一股票、單日）
    df = api.get_broker_trading_for_stock_on_date("2330", d)
    check("get_broker_trading_for_stock_on_date(stock_id, date)", df)

    # 10. get_broker_trading_for_stock_in_range（單一股票、日期區間）
    df = api.get_broker_trading_for_stock_in_range("2330", start, end)
    check("get_broker_trading_for_stock_in_range(stock_id, start_date, end_date)", df)
    df_empty = api.get_broker_trading_for_stock_in_range("2330", end, start)
    try:
        assert isinstance(df_empty, pd.DataFrame) and len(df_empty) == 0
        print(
            "[OK] get_broker_trading_for_stock_in_range(start > end) 回傳空 DataFrame"
        )
        print(f"    筆數: 0（空 DataFrame）")
        print()
    except Exception as e:
        print(f"[X] get_broker_trading_for_stock_in_range(start > end): {e}")
        all_ok = False

    # 11. get_broker_trading_by_broker_and_date（券商中文名、日期）- 例：合庫台中 2024-07-01
    df = api.get_broker_trading_by_broker_and_date("合庫台中", d)
    check("get_broker_trading_by_broker_and_date(securities_trader, date)", df)

    print("=" * 60)
    if all_ok:
        print("[完成] 所有 FinMindAPI 測試通過")
    else:
        print("[失敗] 部分測試未通過")
    print("=" * 60 + "\n")
    return all_ok


if __name__ == "__main__":
    ok = test_finmind_api()
    sys.exit(0 if ok else 1)
