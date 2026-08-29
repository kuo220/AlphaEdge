import datetime
from io import StringIO
from pathlib import Path

import pandas as pd
import pytest

from core.pipeline.cleaners.futures_price_cleaner import FuturesPriceCleaner
from core.utils import FuturesSession

"""
台期貨行情清洗測試

以合成的原始表格驗證日盤（17 欄）與夜盤（15 欄）兩種版面能收斂為同一組欄位，
不連網路、不連 DB；CSV 輸出導向 tmp_path，不污染 downloads 目錄。

**本檔最重要的兩條**是 `-` 不可填 0、以及成交量取該時段自己的量——
兩者出錯都不會報錯，只會讓損益與成交量統計靜默偏掉。
"""

DATE: datetime.date = datetime.date(2026, 8, 27)

# 日盤原始表格，17 欄
# 契約,到期月份,開,高,低,最後成交,漲跌價,漲跌%,盤後量,一般量,合計量,結算價,未沖銷,買價,賣價,史高,史低
# 末列為 NaN 佔位列（真實回應確實有），須被濾除
DAY_RAW_CSV: str = """\
TX,202609,46175,46517,46006,46078,▲75,▲0.16%,26057,50701,76758,46064,104881,46077,46088,49651,24962
TX,202610,46303,46655,46193,46258,▲112,▲0.24%,131,271,402,46246,779,46250,46268,46789,39852
,,,,,,,,,,,,,,,,
"""

# 夜盤原始表格，15 欄：無「盤後／一般／合計」三分欄，結算價與未沖銷恆為 `-`
# 契約,到期月份,開,高,低,最後成交,漲跌價,漲跌%,成交量,結算價,未沖銷,買價,賣價,史高,史低
NIGHT_RAW_CSV: str = """\
TX,202609,46002,46142,45766,45993,▼-10,▼-0.02%,26057,-,-,45983,45993,49651,24962
TX,202706,,,,,-,-,0,-,-,47318,47363,51411,41461
"""

# 週別合約：MTX 有 202609W1 這類契約，不可被轉成數值
WEEKLY_RAW_CSV: str = """\
MTX,202609W1,45900,45990,45850,45968,▲60,▲0.13%,10,59,69,45968,69,45960,45975,49700,24956
MTX,202609,45880,46000,45800,45950,▲50,▲0.11%,100,200,300,45950,500,45940,45960,49700,24956
"""


@pytest.fixture
def cleaner(tmp_path: Path) -> FuturesPriceCleaner:
    """清洗器 fixture，輸出目錄改為暫存目錄"""

    futures_price_cleaner: FuturesPriceCleaner = FuturesPriceCleaner()
    futures_price_cleaner.futures_price_dir = tmp_path
    return futures_price_cleaner


def read_raw(raw_csv: str) -> pd.DataFrame:
    """還原為爬蟲回傳的 DataFrame（契約與到期月份保留為字串）"""

    return pd.read_csv(StringIO(raw_csv), header=None, converters={0: str, 1: str})


# === 兩種版面收斂為同一組欄位 ===
def test_day_and_night_produce_same_columns(cleaner: FuturesPriceCleaner) -> None:
    """日盤 17 欄、夜盤 15 欄，清洗後欄位必須完全一致，否則無法入同一張表"""

    day = cleaner.clean_futures_price(
        read_raw(DAY_RAW_CSV), DATE, "TX", FuturesSession.DAY
    )
    night = cleaner.clean_futures_price(
        read_raw(NIGHT_RAW_CSV), DATE, "TX", FuturesSession.NIGHT
    )

    assert list(day.columns) == list(night.columns)
    assert list(day.columns) == cleaner.futures_price_cleaned_cols


def test_session_column_is_tagged(cleaner: FuturesPriceCleaner) -> None:
    """session 是主鍵的一部分，少了它日盤與夜盤會互相覆蓋"""

    day = cleaner.clean_futures_price(
        read_raw(DAY_RAW_CSV), DATE, "TX", FuturesSession.DAY
    )
    night = cleaner.clean_futures_price(
        read_raw(NIGHT_RAW_CSV), DATE, "TX", FuturesSession.NIGHT
    )

    assert set(day["session"]) == {"day"}
    assert set(night["session"]) == {"night"}


# === `-` 不可填 0 ===
def test_night_settlement_is_null_not_zero(cleaner: FuturesPriceCleaner) -> None:
    """
    夜盤沒有結算價與未沖銷契約量，必須是 NULL

    填 0 會讓「沒有結算價」變成「結算價是 0」，損益與維持率整段歸零且無徵兆。
    """

    night = cleaner.clean_futures_price(
        read_raw(NIGHT_RAW_CSV), DATE, "TX", FuturesSession.NIGHT
    )

    assert night["結算價"].isna().all()
    assert night["未沖銷契約量"].isna().all()
    assert not (night["結算價"] == 0).any()


def test_missing_price_stays_null(cleaner: FuturesPriceCleaner) -> None:
    """該時段完全沒成交的契約，OHLC 為 NULL 而非 0；但成交量是實實在在的 0 口"""

    night = cleaner.clean_futures_price(
        read_raw(NIGHT_RAW_CSV), DATE, "TX", FuturesSession.NIGHT
    )
    no_trade = night[night["expiry"] == "202706"].iloc[0]

    assert pd.isna(no_trade["開盤價"])
    assert pd.isna(no_trade["收盤價"])
    assert no_trade["成交量"] == 0


def test_day_settlement_is_kept(cleaner: FuturesPriceCleaner) -> None:
    """日盤有結算價與未沖銷契約量，不可被 `-` 的處理誤清掉"""

    day = cleaner.clean_futures_price(
        read_raw(DAY_RAW_CSV), DATE, "TX", FuturesSession.DAY
    )
    near = day.iloc[0]

    assert near["結算價"] == 46064
    assert near["未沖銷契約量"] == 104881


# === 成交量取該時段自己的量 ===
def test_volume_is_per_session_not_total(cleaner: FuturesPriceCleaner) -> None:
    """
    日盤取「一般成交量」而非「合計成交量」

    日盤與夜盤各存一列，若日盤存合計，兩列相加會把夜盤的量算兩次。
    """

    day = cleaner.clean_futures_price(
        read_raw(DAY_RAW_CSV), DATE, "TX", FuturesSession.DAY
    )
    night = cleaner.clean_futures_price(
        read_raw(NIGHT_RAW_CSV), DATE, "TX", FuturesSession.NIGHT
    )

    # 原始表：盤後 26057、一般 50701、合計 76758
    assert day.iloc[0]["成交量"] == 50701
    assert night.iloc[0]["成交量"] == 26057
    assert day.iloc[0]["成交量"] + night.iloc[0]["成交量"] == 76758


# === 到期月份 ===
def test_weekly_expiry_stays_string(cleaner: FuturesPriceCleaner) -> None:
    """週契約 202609W1 與月契約 202609 只能都當字串"""

    out = cleaner.clean_futures_price(
        read_raw(WEEKLY_RAW_CSV), DATE, "MTX", FuturesSession.DAY
    )

    assert list(out["expiry"]) == ["202609W1", "202609"]
    assert all(isinstance(v, str) for v in out["expiry"])


# === 版面改制防呆 ===
def test_wrong_column_count_returns_none(cleaner: FuturesPriceCleaner) -> None:
    """欄位數不符代表來源改制，必須中止而非錯位入庫"""

    # 拿夜盤的 15 欄資料當日盤（17 欄）清洗
    out = cleaner.clean_futures_price(
        read_raw(NIGHT_RAW_CSV), DATE, "TX", FuturesSession.DAY
    )

    assert out is None


def test_empty_input_returns_none(cleaner: FuturesPriceCleaner) -> None:
    """crawler 查無資料時回傳 None，cleaner 不可炸掉"""

    assert cleaner.clean_futures_price(None, DATE, "TX", FuturesSession.DAY) is None
    assert (
        cleaner.clean_futures_price(pd.DataFrame(), DATE, "TX", FuturesSession.DAY)
        is None
    )


# === 濾除無效列 ===
def test_placeholder_rows_are_dropped(cleaner: FuturesPriceCleaner) -> None:
    """真實回應末尾帶一列全 NaN 的佔位列，不可入庫"""

    out = cleaner.clean_futures_price(
        read_raw(DAY_RAW_CSV), DATE, "TX", FuturesSession.DAY
    )

    assert len(out) == 2
    assert out["product"].notna().all()


def test_primary_key_is_unique(cleaner: FuturesPriceCleaner) -> None:
    """(date, product, expiry, session) 為主鍵，清洗後不得有重複"""

    out = cleaner.clean_futures_price(
        read_raw(DAY_RAW_CSV), DATE, "TX", FuturesSession.DAY
    )

    assert not out.duplicated(subset=["date", "product", "expiry", "session"]).any()
