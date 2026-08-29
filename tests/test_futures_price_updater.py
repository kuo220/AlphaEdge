import datetime
import sqlite3
from pathlib import Path
from typing import List, Optional

import pandas as pd
import pytest

from core.config import FUTURES_PRICE_DAILY_TABLE_NAME
from core.pipeline.updaters.futures_price_updater import FuturesPriceUpdater
from core.utils import FuturesSession

"""
台期貨行情 Updater 測試：續跑起點、商品防呆、日期挑選

**逐商品續跑**是本檔的重點——各商品上市日不同且會陸續加入設定檔，
若以全表最新日當起點，新商品的歷史會整段補不到且不會有任何錯誤訊息。
不連網路（crawler 以 stub 取代）、不碰正式的 futures.db。
"""

DATE: datetime.date = datetime.date(2026, 8, 27)


@pytest.fixture
def updater(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FuturesPriceUpdater:
    """Updater fixture，DB 與 downloads 目錄都改為暫存"""

    db_path: Path = tmp_path / "futures.db"
    monkeypatch.setattr(
        "core.pipeline.updaters.futures_price_updater.FUTURES_DB_PATH", db_path
    )
    monkeypatch.setattr(
        "core.pipeline.loaders.futures_price_loader.FUTURES_DB_PATH", db_path
    )

    futures_price_updater: FuturesPriceUpdater = FuturesPriceUpdater()
    futures_price_updater.loader.futures_price_dir = tmp_path / "price"
    futures_price_updater.loader.futures_price_dir.mkdir(parents=True, exist_ok=True)
    futures_price_updater.cleaner.futures_price_dir = (
        futures_price_updater.loader.futures_price_dir
    )
    return futures_price_updater


def insert_row(conn: sqlite3.Connection, date: str, product: str) -> None:
    """直接塞一列，用來製造「表內已有資料」的狀態"""

    conn.execute(
        f"INSERT OR IGNORE INTO {FUTURES_PRICE_DAILY_TABLE_NAME} "
        f'("date", product, expiry, session, 成交量) VALUES (?, ?, ?, ?, ?)',
        (date, product, "202609", "day", 1),
    )
    conn.commit()


# === 逐商品續跑 ===
def test_start_date_falls_back_to_default_when_no_data(
    updater: FuturesPriceUpdater,
) -> None:
    """表內沒有該商品時，起點為傳入的預設日"""

    default: datetime.date = datetime.date(1998, 7, 21)

    assert updater.get_actual_update_start_date("TX", default) == default


def test_start_date_resumes_from_latest(updater: FuturesPriceUpdater) -> None:
    """表內已有資料時，起點為最新日 +1"""

    insert_row(updater.conn, "2026-08-27", "TX")

    assert updater.get_actual_update_start_date(
        "TX", datetime.date(1998, 7, 21)
    ) == datetime.date(2026, 8, 28)


def test_resume_is_per_product(updater: FuturesPriceUpdater) -> None:
    """
    新加入的商品不可被既有商品的進度擋住

    TX 已補到 2026，此時把 MTX 加進設定檔，MTX 的起點仍須是預設日；
    若以全表最新日為準，MTX 的歷史會整段補不到且不會有任何錯誤訊息。
    """

    insert_row(updater.conn, "2026-08-27", "TX")
    default: datetime.date = datetime.date(1998, 7, 21)

    assert updater.get_actual_update_start_date("TX", default) == datetime.date(
        2026, 8, 28
    )
    assert updater.get_actual_update_start_date("MTX", default) == default


# === 商品防呆 ===
def test_update_rejects_unknown_product(updater: FuturesPriceUpdater) -> None:
    """
    商品代碼拼錯必須在送出任何請求之前擋下

    否則整段回補會安靜地全部查無資料，看起來就像「這幾年一直都是假日」。
    """

    with pytest.raises(ValueError, match="未知的期貨商品代碼"):
        updater.update(start_date=DATE, end_date=DATE, products=["TXX"])


# === 日期挑選 ===
def test_weekends_are_skipped(
    updater: FuturesPriceUpdater, monkeypatch: pytest.MonkeyPatch
) -> None:
    """週末不送出請求；2026-08-22／23 為週六日"""

    monkeypatch.setattr(updater, "get_traded_weekend_dates", lambda *_: set())

    dates: List[datetime.date] = updater.get_candidate_dates(
        datetime.date(2026, 8, 21), datetime.date(2026, 8, 24)
    )

    assert dates == [datetime.date(2026, 8, 21), datetime.date(2026, 8, 24)]


def test_traded_weekend_is_included(
    updater: FuturesPriceUpdater, monkeypatch: pytest.MonkeyPatch
) -> None:
    """補行交易日（開市的週末）必須納入，否則那天整天缺資料"""

    traded: datetime.date = datetime.date(2026, 8, 22)
    monkeypatch.setattr(updater, "get_traded_weekend_dates", lambda *_: {traded})

    dates: List[datetime.date] = updater.get_candidate_dates(
        datetime.date(2026, 8, 21), datetime.date(2026, 8, 24)
    )

    assert traded in dates


# === 串接 ===
def test_update_writes_rows_end_to_end(
    updater: FuturesPriceUpdater, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """crawler 以 stub 取代，驗證 clean → load 的串接與 session 標記"""

    day_raw = pd.DataFrame(
        [
            [
                "TX",
                "202609",
                46175,
                46517,
                46006,
                46078,
                "▲75",
                "▲0.16%",
                26057,
                50701,
                76758,
                46064,
                104881,
                46077,
                46088,
                49651,
                24962,
            ]
        ]
    )
    night_raw = pd.DataFrame(
        [
            [
                "TX",
                "202609",
                46002,
                46142,
                45766,
                45993,
                "▼-10",
                "▼-0.02%",
                26057,
                "-",
                "-",
                45983,
                45993,
                49651,
                24962,
            ]
        ]
    )

    def fake_crawl(
        date: datetime.date, product: str, session: FuturesSession
    ) -> Optional[pd.DataFrame]:
        return day_raw.copy() if session == FuturesSession.DAY else night_raw.copy()

    monkeypatch.setattr(updater.crawler, "crawl_futures_price", fake_crawl)
    monkeypatch.setattr(updater, "get_traded_weekend_dates", lambda *_: set())
    updater.BATCH_RANDOM_DELAY_MIN = 0
    updater.BATCH_RANDOM_DELAY_MAX = 0

    updater.update(start_date=DATE, end_date=DATE, products=["TX"])

    conn = sqlite3.connect(tmp_path / "futures.db")
    rows = conn.execute(
        f"SELECT session, 結算價 FROM {FUTURES_PRICE_DAILY_TABLE_NAME} ORDER BY session"
    ).fetchall()

    assert rows == [("day", 46064.0), ("night", None)]
