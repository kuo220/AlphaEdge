import datetime
import sqlite3
from pathlib import Path
from typing import Optional

import pandas as pd
import pytest

from core.config import FUTURES_MARGIN_HISTORY_TABLE_NAME
from core.pipeline.tw.cleaners.futures_margin_cleaner import FuturesMarginCleaner
from core.pipeline.tw.loaders.futures_margin_loader import FuturesMarginLoader
from core.utils import FUTURES_MULTIPLIER

"""
台期貨保證金 ETL 的純函式測試（指數類）

**本來源真正會出事的地方不在網路層，而在三處**：
1. **生效日**取自檔案第一行的「更新日期」——解析失敗若退回今天，會產生一列
   日期錯誤但看起來完全正常的資料；
2. **欄位錯位**——來源是 CSV 且每列尾端有多餘逗號，錯一格就整批數字位移；
3. **變動序列的語意**——同一組保證金重複抓不可產生新列，否則「某日生效的保證金」
   會查到錯的那一列。

三者都不會報錯，故以固定 fixture 覆蓋。不連網路、不碰正式的 tw_futures.db。
"""

# 2026-09-01 自 TAIFEX 實際取得的內容縮影（含尾端多餘逗號與選擇權的 A／B 值）
INDEX_MARGIN_CSV: str = """更新日期:2026/08/12
商品別,結算保證金,維持保證金,原始保證金,,
臺股期貨,519000,538000,701000,
小型臺指,129750,134500,175250,
微型臺指期貨,25950,26900,35050,
臺指選擇權風險保證金(A)值,138000,143000,187000,
臺指選擇權風險保證金(B)值,69000,72000,94000,
電子期貨,724000,750000,978000,
小型電子期貨,90500,93750,122250,
金融期貨,117000,122000,158000,
小型金融期貨,29250,30500,39500,
臺灣中型100期貨,21000,22000,29000,
"""


@pytest.fixture
def cleaner(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FuturesMarginCleaner:
    """CSV 落地導向暫存區，不寫進真實的 downloads 目錄"""

    monkeypatch.setattr(
        "core.pipeline.tw.cleaners.futures_margin_cleaner.FUTURES_MARGIN_DOWNLOADS_PATH",
        tmp_path / "margin",
    )
    return FuturesMarginCleaner()


@pytest.fixture
def loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> FuturesMarginLoader:
    """入庫器 fixture，DB 與 downloads 目錄都改為暫存"""

    monkeypatch.setattr(
        "core.pipeline.tw.loaders.futures_margin_loader.TW_FUTURES_DB_PATH",
        tmp_path / "tw_futures.db",
    )
    monkeypatch.setattr(
        "core.pipeline.tw.loaders.futures_margin_loader.FUTURES_MARGIN_DOWNLOADS_PATH",
        tmp_path / "margin",
    )
    return FuturesMarginLoader()


# === 生效日 ===
def test_effective_date_comes_from_the_file_not_today(
    cleaner: FuturesMarginCleaner,
) -> None:
    """生效日取自「更新日期」，不是抓取日"""

    df: pd.DataFrame = cleaner.clean_index_margin(INDEX_MARGIN_CSV)

    assert set(df["effective_date"]) == {datetime.date(2026, 8, 12)}


def test_missing_effective_date_aborts_instead_of_defaulting(
    cleaner: FuturesMarginCleaner,
) -> None:
    """
    找不到更新日期時整批放棄，**不可退回今天**

    退回今天會產生一列日期錯誤但看起來正常的資料，比整批不入庫難查得多。
    """

    without_date: str = "\n".join(INDEX_MARGIN_CSV.splitlines()[1:])

    assert cleaner.clean_index_margin(without_date) is None


def test_full_width_colon_is_accepted(cleaner: FuturesMarginCleaner) -> None:
    """全形冒號也要能解析——站方用字不穩定，不值得為此整批失敗"""

    text: str = INDEX_MARGIN_CSV.replace("更新日期:", "更新日期：")

    assert cleaner.clean_index_margin(text) is not None


# === 解析與過濾 ===
def test_only_registered_products_are_kept(cleaner: FuturesMarginCleaner) -> None:
    """
    只收乘數已登錄的商品

    選擇權的風險保證金 A／B 值語意完全不同（不是每口金額），
    「臺灣中型100期貨」則是乘數未登錄，兩者都不可入庫。
    """

    df: pd.DataFrame = cleaner.clean_index_margin(INDEX_MARGIN_CSV)

    assert set(df["product"]) == {"TX", "MTX", "TMF", "TE", "ZEF", "TF", "ZFF"}
    assert all(p in FUTURES_MULTIPLIER for p in df["product"])


def test_amounts_are_parsed_into_the_right_columns(
    cleaner: FuturesMarginCleaner,
) -> None:
    """三個金額欄的順序是結算／維持／原始，錯位不會報錯只會靜默算錯"""

    df: pd.DataFrame = cleaner.clean_index_margin(INDEX_MARGIN_CSV).set_index("product")

    assert df.loc["TX", "結算保證金"] == 519000
    assert df.loc["TX", "維持保證金"] == 538000
    assert df.loc["TX", "原始保證金"] == 701000


def test_trailing_commas_do_not_shift_columns(cleaner: FuturesMarginCleaner) -> None:
    """來源每列尾端有多餘逗號，不可讓欄位位移"""

    df: pd.DataFrame = cleaner.clean_index_margin(INDEX_MARGIN_CSV).set_index("product")

    assert df.loc["MTX", "原始保證金"] == 175250


def test_source_is_marked_as_snapshot(cleaner: FuturesMarginCleaner) -> None:
    """來自現行一覽表的列標為 snapshot，與公告回補（S4）區分"""

    df: pd.DataFrame = cleaner.clean_index_margin(INDEX_MARGIN_CSV)

    assert set(df["source"]) == {"snapshot"}


def test_header_change_aborts(cleaner: FuturesMarginCleaner) -> None:
    """表頭對不上代表站方改版，整批中止而不是硬解"""

    changed: str = INDEX_MARGIN_CSV.replace("商品別,結算保證金", "品項,結算保證金")

    assert cleaner.clean_index_margin(changed) is None


# === 乘數比例檢查 ===
def test_multiplier_ratio_holds_within_each_index_family(
    cleaner: FuturesMarginCleaner,
) -> None:
    """
    同一標的指數的大小台，每點保證金相同

    加權 3,505／電子 244.50／金融 158.00——**三者本來就不同**，
    所以檢查必須分家族做，拿 TX 去比 TE 會誤判成解析錯誤。
    """

    df: pd.DataFrame = cleaner.clean_index_margin(INDEX_MARGIN_CSV).set_index("product")
    per_point = {p: df.loc[p, "原始保證金"] / FUTURES_MULTIPLIER[p] for p in df.index}

    assert per_point["TX"] == per_point["MTX"] == per_point["TMF"] == 3505.0
    assert per_point["TE"] == per_point["ZEF"] == 244.5
    assert per_point["TF"] == per_point["ZFF"] == 158.0


def test_column_shift_is_caught_by_the_ratio_check(
    cleaner: FuturesMarginCleaner,
) -> None:
    """
    同家族內的金額被動過就會被比例檢查擋下

    這是本 cleaner 唯一能自動偵測「數字對但欄位錯」的手段。
    """

    broken: str = INDEX_MARGIN_CSV.replace(
        "小型臺指,129750,134500,175250,", "小型臺指,129750,134500,175000,"
    )

    assert cleaner.clean_index_margin(broken) is None


# === 變動序列 ===
def test_first_load_inserts_every_row(loader: FuturesMarginLoader) -> None:
    """首次入庫寫入全部商品"""

    df: pd.DataFrame = _clean(loader)

    assert loader.add_to_db(df) == len(df)
    assert loader.count_rows() == len(df)


def test_reload_of_the_same_snapshot_adds_nothing(
    loader: FuturesMarginLoader,
) -> None:
    """
    同一組保證金重複抓不產生新列

    這正是「變動序列」的實現方式——不需要另外判斷有沒有變。
    """

    df: pd.DataFrame = _clean(loader)
    loader.add_to_db(df)

    assert loader.add_to_db(df) == 0
    assert loader.count_rows() == len(df)


def test_new_effective_date_appends_a_new_generation(
    loader: FuturesMarginLoader,
) -> None:
    """保證金調整後（新的生效日）會新增一整組，舊的保留"""

    df: pd.DataFrame = _clean(loader)
    loader.add_to_db(df)

    adjusted: pd.DataFrame = df.copy()
    adjusted["effective_date"] = datetime.date(2026, 9, 1)
    adjusted["原始保證金"] = adjusted["原始保證金"] + 10000

    assert loader.add_to_db(adjusted) == len(adjusted)
    assert loader.count_rows() == len(df) * 2


def test_effective_date_is_stored_as_iso_text(loader: FuturesMarginLoader) -> None:
    """日期以 ISO 字串存放，與 tw_futures.db 其他表一致"""

    loader.add_to_db(_clean(loader))
    row = loader.conn.execute(
        f"SELECT effective_date FROM {FUTURES_MARGIN_HISTORY_TABLE_NAME} LIMIT 1"
    ).fetchone()

    assert row[0] == "2026-08-12"


def test_lookup_takes_the_latest_effective_date_on_or_before(
    loader: FuturesMarginLoader,
) -> None:
    """
    「某日生效的保證金」＝ `effective_date <= 該日` 的最大者

    不是 `= 該日`——保證金不是每天都變，用等號只有剛好調整那天查得到。
    這條查詢語意是 S5 的 API 要實作的，先在此釘住。
    """

    df: pd.DataFrame = _clean(loader)
    loader.add_to_db(df)
    adjusted: pd.DataFrame = df.copy()
    adjusted["effective_date"] = datetime.date(2026, 9, 1)
    adjusted["原始保證金"] = 800000
    loader.add_to_db(adjusted)

    def initial_margin_on(date: str) -> Optional[int]:
        row = loader.conn.execute(
            f"SELECT 原始保證金 FROM {FUTURES_MARGIN_HISTORY_TABLE_NAME} "
            f"WHERE product = 'TX' AND effective_date <= ? "
            f"ORDER BY effective_date DESC LIMIT 1",
            (date,),
        ).fetchone()
        return None if row is None else row[0]

    assert initial_margin_on("2026-08-20") == 701000  # 調整前那一組仍生效
    assert initial_margin_on("2026-09-05") == 800000  # 調整後
    assert initial_margin_on("2026-08-01") is None  # 早於表內任何生效日


def test_index_exists_for_product_lookup(loader: FuturesMarginLoader) -> None:
    """建表時一併建立 (product, effective_date) 索引，主鍵前綴幫不上該查詢"""

    names = {
        row[0]
        for row in loader.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index'"
        )
    }

    assert "idx_futures_margin_product" in names


def _clean(loader: FuturesMarginLoader) -> pd.DataFrame:
    """以 loader 的暫存目錄清洗一份 fixture（避免寫到真實 downloads）"""

    cleaner: FuturesMarginCleaner = FuturesMarginCleaner.__new__(FuturesMarginCleaner)
    cleaner.margin_dir = loader.margin_dir
    cleaner.setup()
    return cleaner.clean_index_margin(INDEX_MARGIN_CSV)


def test_empty_db_reports_no_rows(loader: FuturesMarginLoader) -> None:
    """建表後即使沒有資料也不應拋錯"""

    assert loader.count_rows() == 0
    assert loader.get_effective_dates() == set()


def test_empty_dataframe_is_a_noop(loader: FuturesMarginLoader) -> None:
    """空 DataFrame 不入庫也不拋錯"""

    assert loader.add_to_db(pd.DataFrame()) == 0


def test_table_columns_match_cleaner_output(loader: FuturesMarginLoader) -> None:
    """
    清洗後的欄位須與資料表宣告完全一致（含順序）

    cleaner 加了欄位卻忘了改 schema 時，錯誤要到入庫才浮出來。
    """

    conn: sqlite3.Connection = loader.conn
    table_cols = [
        row[1]
        for row in conn.execute(
            f"PRAGMA table_info('{FUTURES_MARGIN_HISTORY_TABLE_NAME}')"
        )
    ]
    cleaner: FuturesMarginCleaner = FuturesMarginCleaner.__new__(FuturesMarginCleaner)
    cleaner.margin_dir = loader.margin_dir
    cleaner.setup()

    assert cleaner.margin_cleaned_cols == table_cols
