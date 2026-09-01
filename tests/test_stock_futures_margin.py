import datetime
from pathlib import Path
from typing import Dict, Optional

import pandas as pd
import pytest

from core.config import STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME
from core.pipeline.tw.cleaners.stock_futures_margin_cleaner import (
    StockFuturesMarginCleaner,
)
from core.pipeline.tw.loaders.stock_futures_margin_loader import (
    StockFuturesMarginLoader,
)

"""
股票期貨保證金 ETL 的純函式測試

**這份 CSV 是本專案目前最容易解錯的來源**，四個段落的欄位語意都不同：

| 段落 | 內容 | 欄位型態 |
|------|------|----------|
| 一(一) | 股票期貨（股票） | 適用比例 ＋ 級距 |
| 一(二) | 股票期貨（ETF） | **每口固定金額** |
| 二(一) | 股票選擇權（股票） | 比例，`a%`／`b%` 雙欄 |
| 二(二) | 股票選擇權（ETF） | `A值`／`B值`，**一個商品佔兩列** |

四件會靜默出錯的事，本檔逐一釘住：
1. **選擇權段落必須被丟掉**——代碼與股期高度相似（`DFF` vs `DFO`），混進來不會報錯；
2. **每段各有自己的更新日期**，用全檔第一個日期會讓 ETF 段的生效日錯 16 天；
3. **比例存小數**（`0.1350`），存成 `13.50` 會讓保證金差 100 倍；
4. **級距可以是空的**（處置股票），不可因此把該檔丟掉。

不連網路、不碰正式的 tw_futures.db。
"""

# 2026-09-01 自 TAIFEX 實際取得的內容縮影，四個段落齊全
STOCK_MARGIN_CSV: str = """一、股票期貨契約保證金一覽表
(一) 標的證券為股票之股票期貨契約
更新日期:2026/08/28
序號,股票期貨英文代碼,股票期貨標的證券代號,股票期貨中文簡稱,股票期貨標的證券,保證金所屬級距,結算保證金適用比例,維持保證金適用比例,原始保證金適用比例,
1,DFF    ,1101,台泥期貨,"臺灣水泥股份有限公司",級距1,10.00%,10.35%,13.50%,
2,CFF    ,1301,台塑期貨,"台灣塑膠工業股份有限公司",級距2,12.00%,12.42%,16.20%,
3,CAF    ,1303,南亞期貨,"南亞塑膠工業股份有限公司",級距3,15.00%,15.53%,20.25%,
4,NAF    ,3105,穩懋期貨,"穩懋半導體股份有限公司",,16.00%,16.56%,21.60%,
5,CDF    ,2330,台積電期貨,"台灣積體電路製造股份有限公司",級距1,10.00%,10.35%,13.50%,
(二) 標的證券為受益憑證之股票期貨契約
更新日期:2026/08/12
序號,股票期貨英文代碼,股票期貨標的證券代號,股票期貨中文簡稱,股票期貨標的證券,結算保證金,維持保證金,原始保證金,
1,NYF    ,0050,元大台灣50ETF期貨,元大台灣卓越50證券投資信託基金,64000,67000,87000,
2,SRF    ,0050,小型元大台灣50ETF期貨,元大台灣卓越50證券投資信託基金,6400,6700,8700,
二、股票選擇權契約保證金一覽表
(一) 標的證券為股票之股票選擇權契約
更新日期:2026/08/14
序號,股票選擇權英文代碼,股票選擇權標的證券代號,股票選擇權中文簡稱,股票選擇權標的證券,保證金所屬級距,結算保證金適用比例,,維持保證金適用比例
,,,,,,a%,b%,a%
1,DFO    ,1101,台泥選擇權,"臺灣水泥股份有限公司",級距1,10.00%,5.000%,10.35%
(二) 標的證券為受益憑證之股票選擇權契約
更新日期:2026/08/12
序號,股票選擇權英文代碼,股票選擇權標的證券代號,股票選擇權中文簡稱,股票選擇權標的證券,保證金,結算保證金,維持保證金,原始保證金
1,NYA    ,0050,元大台灣50ETF選擇權,元大台灣卓越50證券投資信託基金,A值,64000,67000,87000
,,,,,B值,32000,34000,44000
"""


@pytest.fixture
def cleaner(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> StockFuturesMarginCleaner:
    """CSV 落地導向暫存區"""

    monkeypatch.setattr(
        "core.pipeline.tw.cleaners.stock_futures_margin_cleaner"
        ".FUTURES_MARGIN_DOWNLOADS_PATH",
        tmp_path / "margin",
    )
    return StockFuturesMarginCleaner()


@pytest.fixture
def loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> StockFuturesMarginLoader:
    """入庫器 fixture，DB 與 downloads 目錄都改為暫存"""

    monkeypatch.setattr(
        "core.pipeline.tw.loaders.stock_futures_margin_loader.TW_FUTURES_DB_PATH",
        tmp_path / "tw_futures.db",
    )
    monkeypatch.setattr(
        "core.pipeline.tw.loaders.stock_futures_margin_loader"
        ".FUTURES_MARGIN_DOWNLOADS_PATH",
        tmp_path / "margin",
    )
    return StockFuturesMarginLoader()


def clean(cleaner: StockFuturesMarginCleaner) -> Dict[str, Optional[pd.DataFrame]]:
    """跑一次完整清洗"""

    return cleaner.clean_stock_margin(STOCK_MARGIN_CSV)


# === 段落切分 ===
def test_options_sections_are_dropped(cleaner: StockFuturesMarginCleaner) -> None:
    """
    選擇權兩段必須整段丟掉

    `DFO`／`NYA` 與股期的 `DFF`／`NYF` 只差一個字母，混進來完全不會報錯，
    但它們的保證金語意是風險保證金參數，不是每口保證金。
    """

    out = clean(cleaner)
    codes = set(out["rate"]["product_id"]) | set(out["amount"]["product"])

    assert "DFO" not in codes
    assert "NYA" not in codes
    assert codes == {"DFF", "CFF", "CAF", "NAF", "CDF", "NYF", "SRF"}


def test_rate_and_amount_are_split_by_column_type(
    cleaner: StockFuturesMarginCleaner,
) -> None:
    """
    **分表依據是「金額 vs 比例」不是「指數 vs 股票」**

    ETF 股期給的是每口固定金額，語意與臺股期貨相同，故走金額路徑。
    """

    out = clean(cleaner)

    assert set(out["rate"]["product_id"]) == {"DFF", "CFF", "CAF", "NAF", "CDF"}
    assert set(out["amount"]["product"]) == {"NYF", "SRF"}


# === 每段各有生效日 ===
def test_each_section_keeps_its_own_effective_date(
    cleaner: StockFuturesMarginCleaner,
) -> None:
    """
    比例段是 08/28、金額段是 08/12——**不是同一天**

    用全檔第一個找到的日期套用到全部，會讓 ETF 股期的生效日錯 16 天。
    """

    out = clean(cleaner)

    assert set(out["rate"]["effective_date"]) == {datetime.date(2026, 8, 28)}
    assert set(out["amount"]["effective_date"]) == {datetime.date(2026, 8, 12)}


# === 比例轉換 ===
def test_rates_are_stored_as_decimals(cleaner: StockFuturesMarginCleaner) -> None:
    """
    `13.50%` → `0.1350`

    存成 `13.50` 會讓保證金差 100 倍卻不會報錯。
    """

    df: pd.DataFrame = clean(cleaner)["rate"].set_index("product_id")

    assert df.loc["DFF", "原始保證金適用比例"] == 0.135
    assert df.loc["CFF", "原始保證金適用比例"] == 0.162
    assert df.loc["CAF", "原始保證金適用比例"] == 0.2025


def test_three_rate_columns_are_in_order(cleaner: StockFuturesMarginCleaner) -> None:
    """結算／維持／原始三欄的順序，錯位不會報錯只會靜默算錯"""

    df: pd.DataFrame = clean(cleaner)["rate"].set_index("product_id")

    assert df.loc["DFF", "結算保證金適用比例"] == 0.10
    assert df.loc["DFF", "維持保證金適用比例"] == 0.1035
    assert df.loc["DFF", "原始保證金適用比例"] == 0.135


# === 處置股票：級距為空 ===
def test_empty_tier_is_kept_as_null(cleaner: StockFuturesMarginCleaner) -> None:
    """
    級距為空的是處置／注意股票，比例更高——**不可因此把該檔丟掉**

    2026-09-01 實查 296 檔中有 15 檔如此（台玻、旺宏、南亞科、穩懋…）。
    """

    df: pd.DataFrame = clean(cleaner)["rate"].set_index("product_id")

    assert "NAF" in df.index
    # pandas 會把 object 欄的 None 正規化成 NaN；入庫後才是真正的 NULL
    # （見 test_null_tier_survives_the_round_trip）
    assert pd.isna(df.loc["NAF", "保證金所屬級距"])
    assert df.loc["NAF", "原始保證金適用比例"] == 0.216


# === 逗號與代碼 ===
def test_company_names_with_commas_do_not_shift_columns(
    cleaner: StockFuturesMarginCleaner,
) -> None:
    """
    標的證券名稱以引號包住且含逗號，必須用 csv 模組解析

    用 `split(",")` 會讓後面的欄位整排位移。
    """

    df: pd.DataFrame = clean(cleaner)["rate"].set_index("product_id")

    assert df.loc["CDF", "underlying_stock_id"] == "2330"
    assert df.loc["CDF", "原始保證金適用比例"] == 0.135


def test_product_codes_are_stripped(cleaner: StockFuturesMarginCleaner) -> None:
    """
    來源的代碼帶尾端空白（`DFF    `），必須 strip 才對得回標的池

    `futures_stock_universe.product_id` 是 3 碼無空白。
    """

    out = clean(cleaner)

    assert all(code == code.strip() for code in out["rate"]["product_id"])
    assert all(code == code.strip() for code in out["amount"]["product"])


# === 金額段 ===
def test_etf_amounts_use_the_shared_schema(
    cleaner: StockFuturesMarginCleaner,
) -> None:
    """ETF 股期的欄位與 `futures_margin_history` 一致，才能共用同一個 loader"""

    df: pd.DataFrame = clean(cleaner)["amount"]

    assert list(df.columns) == [
        "effective_date",
        "product",
        "product_name",
        "結算保證金",
        "維持保證金",
        "原始保證金",
        "source",
    ]
    assert df.set_index("product").loc["NYF", "原始保證金"] == 87000


# === 站方改版 ===
def test_missing_futures_section_aborts(cleaner: StockFuturesMarginCleaner) -> None:
    """找不到「一、股票期貨」段落代表改版，整份放棄"""

    assert cleaner.clean_stock_margin("只有一行沒有段落標記") is None


def test_header_change_yields_none_for_that_section(
    cleaner: StockFuturesMarginCleaner,
) -> None:
    """
    某一段的表頭對不上時只有該段為 None，另一段照常回傳

    兩段的來源與更新日期本來就獨立，一段壞掉不該讓另一段也不入庫。
    """

    broken: str = STOCK_MARGIN_CSV.replace(
        "保證金所屬級距,結算保證金適用比例", "級距,結算比例"
    )
    out = cleaner.clean_stock_margin(broken)

    assert out["rate"] is None
    assert out["amount"] is not None and len(out["amount"]) == 2


# === 入庫 ===
def test_first_load_inserts_every_row(loader: StockFuturesMarginLoader) -> None:
    """首次入庫寫入全部商品"""

    df: pd.DataFrame = _clean_with(loader)

    assert loader.add_to_db(df) == len(df)
    assert loader.count_rows() == len(df)


def test_reload_adds_nothing(loader: StockFuturesMarginLoader) -> None:
    """比例沒變就不產生新列——變動序列的實現方式"""

    df: pd.DataFrame = _clean_with(loader)
    loader.add_to_db(df)

    assert loader.add_to_db(df) == 0


def test_new_effective_date_appends(loader: StockFuturesMarginLoader) -> None:
    """比例調整後（新的生效日）新增一整組，舊的保留"""

    df: pd.DataFrame = _clean_with(loader)
    loader.add_to_db(df)

    adjusted: pd.DataFrame = df.copy()
    adjusted["effective_date"] = datetime.date(2026, 9, 1)
    adjusted["原始保證金適用比例"] = 0.2025

    assert loader.add_to_db(adjusted) == len(adjusted)
    assert loader.count_rows() == len(df) * 2


def test_null_tier_survives_the_round_trip(loader: StockFuturesMarginLoader) -> None:
    """級距為 NULL 的列要能入庫並讀回仍是 NULL"""

    loader.add_to_db(_clean_with(loader))
    row = loader.conn.execute(
        f"SELECT 保證金所屬級距, 原始保證金適用比例 "
        f"FROM {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME} WHERE product_id = 'NAF'"
    ).fetchone()

    assert row == (None, 0.216)


def test_lookup_takes_the_latest_effective_date_on_or_before(
    loader: StockFuturesMarginLoader,
) -> None:
    """查詢語意與金額表相同：`effective_date <= 該日` 的最大者（供 S5 用）"""

    df: pd.DataFrame = _clean_with(loader)
    loader.add_to_db(df)
    adjusted: pd.DataFrame = df.copy()
    adjusted["effective_date"] = datetime.date(2026, 9, 1)
    adjusted["原始保證金適用比例"] = 0.2025
    loader.add_to_db(adjusted)

    def rate_on(date: str) -> Optional[float]:
        row = loader.conn.execute(
            f"SELECT 原始保證金適用比例 "
            f"FROM {STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME} "
            f"WHERE product_id = 'DFF' AND effective_date <= ? "
            f"ORDER BY effective_date DESC LIMIT 1",
            (date,),
        ).fetchone()
        return None if row is None else row[0]

    assert rate_on("2026-08-30") == 0.135
    assert rate_on("2026-09-05") == 0.2025
    assert rate_on("2026-08-01") is None


def test_table_columns_match_cleaner_output(
    loader: StockFuturesMarginLoader, cleaner: StockFuturesMarginCleaner
) -> None:
    """清洗後的欄位須與資料表宣告完全一致（含順序）"""

    table_cols = [
        row[1]
        for row in loader.conn.execute(
            f"PRAGMA table_info('{STOCK_FUTURES_MARGIN_RATE_HISTORY_TABLE_NAME}')"
        )
    ]

    assert cleaner.rate_cleaned_cols == table_cols


def _clean_with(loader: StockFuturesMarginLoader) -> pd.DataFrame:
    """以 loader 的暫存目錄清洗一份 fixture（避免寫到真實 downloads）"""

    cleaner: StockFuturesMarginCleaner = StockFuturesMarginCleaner.__new__(
        StockFuturesMarginCleaner
    )
    cleaner.margin_dir = loader.margin_dir
    cleaner.setup()
    return cleaner.clean_stock_margin(STOCK_MARGIN_CSV)["rate"]
