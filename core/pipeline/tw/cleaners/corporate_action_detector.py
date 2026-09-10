import datetime
import sqlite3
from typing import List, Optional

import pandas as pd
from loguru import logger

from core.config import (
    CORPORATE_ACTION_TABLE_NAME,
    DIVIDEND_TABLE_NAME,
    PRICE_TABLE_NAME,
    TW_STOCK_DB_PATH,
)
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
由行情反推公司行動候選（`detected` 來源）

**為什麼需要這條路**：ETF 的受益權單位分割**不在任何結構化端點裡**。S1 查遍
`TWTB8U`（變更交易）與 TWSE OpenAPI 的 143 個端點都找不到 0050 在 2025-06-18
的一拆四；那類事件走的是公告系統而非可查詢的資料集。少了這條路，
最有名的那一筆分割就補不進來。

**判準只需要一個事實**：台股單日漲跌幅上限是 ±10%，所以非除權息日出現超過
15% 的單日變動，多半是公司行動或資料錯誤。這個判準不需要任何外部資料。

⚠️ **但槓桿與反向 ETF 是例外，它們的漲跌幅上限是 ±20%**（標的的兩倍）。
實測 2025-04-07 關稅重挫那天，00631L／00640L／00647L／00650L／00663L 等
一整批同時跌到 −20%（例如 00631L 由 200.30 到 160.25，倍率 0.80），
**那天它們都沒有任何公司行動**——單純是跌停。S1 的原始判準沒有考慮這一點。

因此本模組**不把它們濾掉，而是標記**（`疑似槓桿反向ETF` 欄）：直接濾掉會連
真正的反向分割一起藏起來，而 S1 正好就查到 00632R 在 2024-12-11 做過反向分割。
判讀時先看這一欄，再看停牌日數——公司行動幾乎都伴隨停止買賣數日，跌停不會。

**本模組只產出候選，不自動入庫**：倍率是從價格反推的近似值，而且「資料錯誤」
與「公司行動」在數字上長得一樣。要寫進資料表得由人確認後以 `detected` 來源
明確加入（見 `CorporateActionUpdater.load_detected_events()`）。
"""

# 台股單日漲跌幅上限 ±10%，超過這個門檻必然不是正常交易
DETECTION_THRESHOLD: float = 0.15


def detect_unexplained_moves(
    conn: Optional[sqlite3.Connection] = None,
    threshold: float = DETECTION_THRESHOLD,
    start_date: Optional[datetime.date] = None,
) -> pd.DataFrame:
    """
    - Description:
        找出「單日變動超過門檻、且無法由除權息或已知公司行動解釋」的日期

        這同時是 S4 護欄的判定式：事件表補齊後，這裡回傳的每一筆都應該要能
        被解釋掉；解釋不掉的就是新事件或資料錯誤。
    - Parameters:
        - conn: Optional[sqlite3.Connection]
            共用連線；未指定時自行以**唯讀**模式開啟
        - threshold: float
            單日變動的門檻（小數，預設 0.15）
        - start_date: Optional[datetime.date]
            只看這一天之後的資料；None 表示全期間
    - Return:
        - pd.DataFrame
            欄位為 `date`／`stock_id`／`前一日收盤`／`收盤價`／`推估倍率`／`停牌日數`
    """

    owns_conn: bool = conn is None
    if owns_conn:
        conn = sqlite3.connect(f"file:{TW_STOCK_DB_PATH}?mode=ro", uri=True)

    try:
        date_filter: str = ""
        params: List[str] = []
        if start_date is not None:
            date_filter = "WHERE date >= ?"
            params.append(str(start_date))

        prices: pd.DataFrame = pd.read_sql_query(
            f"SELECT date, stock_id, 收盤價 FROM {PRICE_TABLE_NAME} {date_filter}",
            conn,
            params=params or None,
        )
        if prices.empty:
            return _empty_result()

        prices = prices[pd.to_numeric(prices["收盤價"], errors="coerce") > 0]
        prices["收盤價"] = prices["收盤價"].astype(float)
        prices = prices.sort_values(["stock_id", "date"], kind="stable")

        grouped = prices.groupby("stock_id", sort=False)
        prices["前一日收盤"] = grouped["收盤價"].shift(1)
        prices["前一交易日"] = grouped["date"].shift(1)
        prices = prices.dropna(subset=["前一日收盤"])

        prices["推估倍率"] = prices["收盤價"] / prices["前一日收盤"]
        candidates: pd.DataFrame = prices[
            (prices["推估倍率"] - 1).abs() > threshold
        ].copy()

        if candidates.empty:
            return _empty_result()

        # 停牌日數：公司行動多半伴隨停止買賣，這是與「資料錯誤」的區別線索之一
        candidates["停牌日數"] = (
            pd.to_datetime(candidates["date"])
            - pd.to_datetime(candidates["前一交易日"])
        ).dt.days

        candidates = _drop_explained(conn, candidates)

        # 槓桿／反向 ETF 的代號以 L／R 結尾，其漲跌幅上限是 ±20%
        candidates["疑似槓桿反向ETF"] = (
            candidates["stock_id"].astype(str).str.upper().str.endswith(("L", "R"))
        )

        return candidates[
            [
                "date",
                "stock_id",
                "前一日收盤",
                "收盤價",
                "推估倍率",
                "停牌日數",
                "疑似槓桿反向ETF",
            ]
        ].sort_values(["date", "stock_id"], kind="stable")
    finally:
        if owns_conn:
            conn.close()


def _empty_result() -> pd.DataFrame:
    """回傳欄位齊全的空表，讓呼叫端不必分辨「沒有候選」與「查不到資料」"""

    return pd.DataFrame(
        columns=[
            "date",
            "stock_id",
            "前一日收盤",
            "收盤價",
            "推估倍率",
            "停牌日數",
            "疑似槓桿反向ETF",
        ]
    )


def _drop_explained(conn: sqlite3.Connection, candidates: pd.DataFrame) -> pd.DataFrame:
    """
    - Description:
        濾掉能被除權息或已知公司行動解釋的候選

        兩張表都以 `(date, stock_id)` 對齊。**`dividend` 表不存在時不濾**——
        那代表尚未跑過除權息 ETL，此時把候選全數保留才是誠實的（濾掉等於
        宣稱「已確認無關」）。
    - Parameters:
        - conn: sqlite3.Connection
            資料連線
        - candidates: pd.DataFrame
            尚未過濾的候選
    - Return:
        - pd.DataFrame
            過濾後的候選
    """

    for table, label in (
        (DIVIDEND_TABLE_NAME, "除權息"),
        (CORPORATE_ACTION_TABLE_NAME, "公司行動"),
    ):
        if not SQLiteUtils.check_table_exist(conn=conn, table_name=table):
            logger.warning(f"[detector] {table} 不存在，不以{label}過濾候選")
            continue

        known: pd.DataFrame = pd.read_sql_query(
            f"SELECT date, stock_id FROM {table}", conn
        )
        if known.empty:
            continue

        before: int = len(candidates)
        keys = set(zip(known["date"].astype(str), known["stock_id"].astype(str)))
        # 以向量化比對取代 `apply(lambda ...)`：後者會把 `keys` 綁進閉包（B023），
        # 而且逐列呼叫在 630 萬列的行情表上慢得沒有必要
        pairs = pd.Series(
            list(
                zip(
                    candidates["date"].astype(str),
                    candidates["stock_id"].astype(str),
                )
            ),
            index=candidates.index,
        )
        candidates = candidates[~pairs.isin(keys)]
        logger.info(f"[detector] 以{label}解釋掉 {before - len(candidates)} 筆候選")

    return candidates
