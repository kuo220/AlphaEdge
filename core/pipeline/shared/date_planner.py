import datetime
import json
import sqlite3
from pathlib import Path
from typing import Iterable, List, Optional, Set

from loguru import logger

from core.config import DOWNLOADS_METADATA_DIR_PATH
from core.pipeline.utils.sqlite_utils import SQLiteUtils

"""
「這次要向站方請求哪些日期」的共用決策

**舊做法是 `MAX(date) + 1`**，於是中間缺的日子永遠不會再被嘗試（健檢 F-050）：
某天因為連線失敗沒抓到，隔天照樣從新的 `MAX(date)+1` 起跑，那個洞就留在資料庫裡，
而回測遇到缺日會當成休市靜默跳過（F-028）。

改為**差集**：

    候選日期 ＝ 日曆 − 表內已有的日期 − 已確認沒有資料的日期

三個集合各自的來源：

| 集合 | 來源 | 為什麼 |
|------|------|--------|
| 日曆 | `calendar_dates`（例如 `price` 表的交易日）；沒有就用平日 | 週末不開市，送出請求只會換回「查無資料」 |
| 表內已有 | 目標資料表的 `DISTINCT date` | 已經有的不必重抓 |
| 已確認沒有 | `NoDataDateStore` 的 JSON | 國定假日只需要問一次，之後不再浪費請求 |

**只有站方明確回覆「查無資料」才會寫進 `NoDataDateStore`**（見 `CrawlResult`）；
連線失敗、被擋、版面解析不出來都不會，所以那些日子下次還會再試。
這個分野就是整份工作的核心：**沒問到**與**問過了沒有**必須是兩件事。
"""


# 週六的 `weekday()` 值；用於判斷是否為週末
SATURDAY: int = 5


class NoDataDateStore:
    """
    - Description:
        記錄「已向站方確認過、當天確實沒有資料」的日期

        存成 JSON 而不是資料表，理由與 `BrokerTradingMetadataStore` 相同：
        這是執行期的爬取進度，不是資料本身，重建成本低且不該進版控。
        檔案不存在或損毀時一律當成空集合——最壞的結果只是多問幾次，
        比誤把「沒問到」當成「問過了沒有」安全得多。
    """

    def __init__(self, source: str, path: Optional[Path] = None):
        self.source: str = source
        self.path: Path = path or (
            DOWNLOADS_METADATA_DIR_PATH / "no_data" / f"{source}_no_data_dates.json"
        )
        self.dates: Set[datetime.date] = self.load()

    def load(self) -> Set[datetime.date]:
        """讀取已確認沒有資料的日期；檔案不存在或損毀時回空集合"""

        if not self.path.exists():
            return set()

        try:
            raw: List[str] = json.loads(self.path.read_text(encoding="utf-8"))
            return {datetime.date.fromisoformat(value) for value in raw}
        except Exception as error:
            logger.warning(
                f"[{self.source}] 讀取 no-data 紀錄失敗（{type(error).__name__}: {error}），"
                f"視為空集合；最壞只是多問幾次"
            )
            return set()

    def add(self, date: datetime.date) -> None:
        """記下一個「已確認沒有資料」的日期（尚未寫檔）"""

        self.dates.add(date)

    def save(self) -> None:
        """把目前的集合寫回檔案"""

        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text(
            json.dumps(sorted(date.isoformat() for date in self.dates), indent=2),
            encoding="utf-8",
        )
        logger.debug(f"[{self.source}] 已記錄 {len(self.dates)} 個確認無資料的日期")


class DatePlanner:
    """決定一次更新要向站方請求哪些日期"""

    @staticmethod
    def get_existing_dates(
        conn: sqlite3.Connection,
        table_name: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Set[datetime.date]:
        """
        - Description:
            取得目標資料表在區間內已有的日期
        - Parameters:
            - conn: sqlite3.Connection
                資料庫連線
            - table_name: str
                目標資料表
            - start_date / end_date: datetime.date
                查詢區間
        - Return:
            - Set[datetime.date]
                表不存在時為空集合（初次更新的正常狀態）
        """

        if not SQLiteUtils.check_table_exist(conn=conn, table_name=table_name):
            return set()

        rows = conn.execute(
            f"SELECT DISTINCT date FROM {table_name} WHERE date BETWEEN ? AND ?",
            (start_date.isoformat(), end_date.isoformat()),
        ).fetchall()

        return {datetime.date.fromisoformat(str(raw)[:10]) for (raw,) in rows if raw}

    @staticmethod
    def get_trading_dates(
        conn: sqlite3.Connection,
        table_name: str,
        start_date: datetime.date,
        end_date: datetime.date,
    ) -> Set[datetime.date]:
        """
        - Description:
            以某張表（實務上是 `price`）在區間內有資料的日期作為交易日曆

            比「非週末」精確：涵蓋國定假日與**補行交易日**（補班的週六照常開市，
            2013 起有 11 天，用「非週末」近似會整天漏抓）。
        - Parameters:
            - conn: sqlite3.Connection
                資料庫連線
            - table_name: str
                作為日曆來源的資料表
            - start_date / end_date: datetime.date
                查詢區間
        - Return:
            - Set[datetime.date]
                有資料的日期；表不存在時為空集合
        """

        return DatePlanner.get_existing_dates(conn, table_name, start_date, end_date)

    @staticmethod
    def generate_weekdays(
        start_date: datetime.date, end_date: datetime.date
    ) -> Set[datetime.date]:
        """區間內的所有平日（週一到週五）"""

        days: Set[datetime.date] = set()
        date: datetime.date = start_date
        while date <= end_date:
            if date.weekday() < SATURDAY:
                days.add(date)
            date += datetime.timedelta(days=1)
        return days

    @staticmethod
    def plan(
        conn: sqlite3.Connection,
        table_name: str,
        start_date: datetime.date,
        end_date: datetime.date,
        no_data_dates: Optional[Iterable[datetime.date]] = None,
        calendar_dates: Optional[Iterable[datetime.date]] = None,
        extra_dates: Optional[Iterable[datetime.date]] = None,
    ) -> List[datetime.date]:
        """
        - Description:
            算出這次要請求的日期清單（見模組說明的差集公式）
        - Parameters:
            - conn: sqlite3.Connection
                資料庫連線
            - table_name: str
                目標資料表
            - start_date / end_date: datetime.date
                更新區間
            - no_data_dates: Optional[Iterable[datetime.date]]
                已確認沒有資料的日期，會被排除
            - calendar_dates: Optional[Iterable[datetime.date]]
                交易日曆；None 表示改用「區間內所有平日」
            - extra_dates: Optional[Iterable[datetime.date]]
                無論如何都要納入候選的日期（例如補行交易日）
        - Return:
            - List[datetime.date]
                由早到晚排序的候選日期
        """

        if start_date > end_date:
            return []

        universe: Set[datetime.date] = (
            set(calendar_dates)
            if calendar_dates is not None
            else DatePlanner.generate_weekdays(start_date, end_date)
        )
        if extra_dates:
            universe |= set(extra_dates)

        universe = {date for date in universe if start_date <= date <= end_date}

        existing: Set[datetime.date] = DatePlanner.get_existing_dates(
            conn, table_name, start_date, end_date
        )
        candidates: Set[datetime.date] = universe - existing - set(no_data_dates or ())

        # 缺口與新日期分開報告：前者代表過去有一天沒補到，值得看一眼
        latest_existing: Optional[datetime.date] = max(existing) if existing else None
        gaps: List[datetime.date] = sorted(
            date
            for date in candidates
            if latest_existing is not None and date < latest_existing
        )
        if gaps:
            logger.warning(
                f"[{table_name}] 偵測到 {len(gaps)} 天缺口（表內最新為 {latest_existing}），"
                f"本次一併回補：{gaps[:10]}"
                + ("…（僅列前 10 筆）" if len(gaps) > 10 else "")
            )

        return sorted(candidates)
