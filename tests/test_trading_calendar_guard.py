import hashlib
import sqlite3
from pathlib import Path
from typing import Dict, List, Set, Tuple

import pytest

from core.config import (
    CHIP_TABLE_NAME,
    MARGIN_TABLE_NAME,
    PRICE_TABLE_NAME,
    TW_FUTURES_DB_PATH,
    TW_STOCK_DB_PATH,
)

"""日頻表的非交易日批次與停滯重播護欄（爬蟲缺口回補 S1）

三支 cleaner 都是 `df.insert(0, "date", date)`——蓋上去的是**請求參數的日期**，
不是來源頁面內的日期。爬蟲端已由 `f278160` 補上休市判斷，但那道判斷靠的是站方
回覆的內容，站方行為一變就可能再破一次，而**壞掉的樣子不會讓任何既有測試變紅**：
缺資料會讓缺口統計出聲，多資料不會。

本檔用兩個互補的判準把「多出來的資料」釘住：

1. `test_no_non_trading_day_batches`：日期軸。某張表有、其他三張全無的日期。
2. `test_no_stale_replayed_batches`：內容軸。同一批內容被蓋上不同日期。

以 2026-09-04 清理前的資料實測（見
`backlog/爬蟲缺口回補與非交易日批次清理.md` S1）：測試 1 抓到全部 21 個非交易日批次，
測試 2 抓到 2 個重播群組共 7 個日期。

**已知盲區：部分受污染的真實交易日兩條都抓不到。** 那 5 天（`2023-05-12`、
`2024-02-16`、`2025-01-22`、`2025-03-24`、`2025-04-23`）是真實交易日，日期軸沒有異常；
而停滯的只是 TWSE 那半邊（908 列 / 全日約 1,750 列），前 50 大來自正常的 TPEX 部分，
指紋因此不碰撞。它們當時是靠「列數低於前後各 5 個交易日中位數的 85%」掃出來的，
但那個判準會同時掃到 22 個列數本來就偏低的日期（早年補行交易的週六、只入庫單一市場的日子），
當成斷言只會變成紅燈噪音，故列為人工複查而非護欄。
"""

# 四張表都還有資料的最後一天。**必須夾上界**——各表尾端落後不同
# （`chip` 補到 2026-06-18、`margin` 到 2026-08-14），不夾的話 `price` 領先的
# 那幾天會被誤判成「price 獨有」
COMMON_RANGE_END: str = "2026-06-18"

# 內容指紋取「絕對值最大的 N 筆」。取極端值是因為它們最不可能巧合相同：
# 買賣超為 0 或個位數張的個股每天都有一大票，拿來當指紋會誤報
FINGERPRINT_SIZE: int = 50

pytestmark = pytest.mark.slow


def load_dates(conn: sqlite3.Connection, table: str) -> Set[str]:
    """取得指定表在共同區間內的所有日期"""

    return {
        row[0]
        for row in conn.execute(
            f"SELECT DISTINCT date FROM {table} WHERE date <= ?", (COMMON_RANGE_END,)
        )
    }


@pytest.mark.skipif(
    not Path(TW_STOCK_DB_PATH).exists() or not Path(TW_FUTURES_DB_PATH).exists(),
    reason="需要 tw_stock.db 與 tw_futures.db 才能交叉比對交易日",
)
def test_no_non_trading_day_batches() -> None:
    """沒有任何一張日頻表存在「只有它有」的日期

    市場開市與否對所有來源都一樣。某張表有、其他三張全無的日期，
    只可能是站方在休市日回了東西而清洗端照請求日期寫了進去。
    """

    stock_conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)
    futures_conn: sqlite3.Connection = sqlite3.connect(TW_FUTURES_DB_PATH)
    try:
        price: Set[str] = load_dates(stock_conn, PRICE_TABLE_NAME)
        chip: Set[str] = load_dates(stock_conn, CHIP_TABLE_NAME)
        margin: Set[str] = load_dates(stock_conn, MARGIN_TABLE_NAME)
        large_trader: Set[str] = load_dates(futures_conn, "futures_large_trader")
    finally:
        stock_conn.close()
        futures_conn.close()

    assert not (chip - price - margin - large_trader), (
        f"`{CHIP_TABLE_NAME}` 有其他三張表都沒有的日期："
        f"{sorted(chip - price - margin - large_trader)}"
    )
    assert not (margin - price - chip - large_trader), (
        f"`{MARGIN_TABLE_NAME}` 有其他三張表都沒有的日期："
        f"{sorted(margin - price - chip - large_trader)}"
    )
    assert not (price - chip - margin - large_trader), (
        f"`{PRICE_TABLE_NAME}` 有其他三張表都沒有的日期："
        f"{sorted(price - chip - margin - large_trader)}"
    )


@pytest.mark.skipif(
    not Path(TW_STOCK_DB_PATH).exists(),
    reason="需要 tw_stock.db 才能比對籌碼內容指紋",
)
def test_no_stale_replayed_batches() -> None:
    """沒有兩個日期共用同一份籌碼內容

    站方在某些請求下會回一份**過期頁**，清洗端蓋上請求日期後，同一批數字就會
    出現在好幾天。實際發生過：2017-12-18 的 TWSE 內容被複製到另外 11 個日期，
    其中 5 天還是真實交易日（真正的資料因此沒進來）。

    以每日「絕對值最大的 50 筆 `(stock_id, 三大法人買賣超股數)`」為指紋——
    真實行情不可能有兩天的前 50 大完全一致。
    """

    conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)
    try:
        rows: List[Tuple[str, str, int]] = conn.execute(
            f"SELECT date, stock_id, 三大法人買賣超股數 FROM {CHIP_TABLE_NAME} "
            f"WHERE 三大法人買賣超股數 <> 0"
        ).fetchall()
    finally:
        conn.close()

    by_date: Dict[str, List[Tuple[int, str, int]]] = {}
    for date, stock_id, value in rows:
        by_date.setdefault(date, []).append((abs(value), stock_id, value))

    fingerprints: Dict[str, List[str]] = {}
    for date, entries in by_date.items():
        top: List[Tuple[int, str, int]] = sorted(entries, reverse=True)[
            :FINGERPRINT_SIZE
        ]
        digest: str = hashlib.md5(
            str([(stock_id, value) for _, stock_id, value in top]).encode()
        ).hexdigest()
        fingerprints.setdefault(digest, []).append(date)

    collisions: List[List[str]] = [
        sorted(dates) for dates in fingerprints.values() if len(dates) > 1
    ]

    assert not collisions, f"以下日期共用同一份籌碼內容（過期頁被重播）：{collisions}"
