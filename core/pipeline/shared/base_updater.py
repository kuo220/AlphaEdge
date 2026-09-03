import datetime
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import Callable, List, Optional

import pandas as pd
from loguru import logger

from core.pipeline.shared.base_crawler import CrawlResult, CrawlStatus

"""
所有 updater 的共同基底，以及**每批一行的結果統計**

updater 原本跑完只會印「Latest available date: ...」，那句話在「今天什麼都沒抓到」
時長得跟正常一模一樣。`UpdateStats` 把一批更新拆成四個數字，讓「請求了幾天、
其中幾天真的沒資料、幾天是連不上」變成看得到的東西——連不上的那幾天下次會重試，
沒資料的那幾天不會，兩者混在一起就是資料靜靜缺一天的成因。
"""


@dataclass
class UpdateStats:
    """一批更新的結果統計"""

    requested: int = 0  # 送出請求的日期數
    ok: int = 0  # 拿到資料
    no_data: int = 0  # 站方明確回覆沒有資料（休市或尚未公布）
    unreachable: int = 0  # 取不到且無法斷定站方有沒有資料，下次會重試
    clean_failed: int = 0  # 抓到了但清洗失敗（版面異常），同樣下次會重試

    def record(self, *results: CrawlResult) -> CrawlStatus:
        """
        - Description:
            記錄同一天的多個來源結果，並回報這一天整體算哪一種

            同一天的上市與上櫃各爬一次，三種結果的判準：

            - 任一來源失敗 → `FAILED`。**即使另一邊成功也算失敗**，
              因為這天只拿到一半的資料，下次必須重來。
            - 全部來源都說沒有 → `NO_DATA`，可以記進永久名單。
            - 其餘 → `OK`。
        - Parameters:
            - results: CrawlResult
                同一天各來源的結果
        - Return:
            - CrawlStatus
                這一天的整體結果
        """

        self.requested += 1

        if any(result.is_failed for result in results):
            self.unreachable += 1
            return CrawlStatus.FAILED

        if all(result.is_no_data for result in results):
            self.no_data += 1
            return CrawlStatus.NO_DATA

        self.ok += 1
        return CrawlStatus.OK

    def count_clean_failure(self) -> None:
        """清洗失敗：從 ok 移到 unreachable，並單獨計數"""

        self.ok = max(self.ok - 1, 0)
        self.unreachable += 1
        self.clean_failed += 1

    def summary_line(self, source: str) -> str:
        """單行統計字串"""

        line: str = (
            f"[{source}] 本批統計："
            f"{self.requested} requested / {self.ok} ok / "
            f"{self.no_data} no data / {self.unreachable} unreachable"
        )
        if self.clean_failed:
            line += f"（其中 {self.clean_failed} 天是清洗失敗）"
        return line

    def report(self, source: str) -> None:
        """
        - Description:
            輸出統計行；有 unreachable 時提升為 warning

            用 `logger.info` 印出「12 天連不上」跟印出「一切正常」在 log 裡
            同樣不起眼，所以連不上的時候要換一個層級。
        - Parameters:
            - source: str
                資料來源名稱
        """

        line: str = self.summary_line(source)
        if self.unreachable:
            logger.warning(f"{line}；unreachable 的日期下次執行會自動重試")
        else:
            logger.info(line)


class BaseDataUpdater(ABC):
    """Base Class of Data Updater"""

    def __init__(self):
        pass

    @staticmethod
    def clean_one(
        clean: Callable[..., Optional[pd.DataFrame]],
        raw: pd.DataFrame,
        date: datetime.date,
        label: str,
    ) -> bool:
        """
        - Description:
            清洗單一來源的單日資料，**把失敗隔離在這一天之內**

            `BaseDataCleaner.check_column_count()` 會在版面不符時拋
            `ColumnLayoutError`。若讓它一路往上炸，一個異常的歷史日期就會中止
            整段回補——而且是在最壞的時間點：本批已爬好、尚未入庫的日期全部作廢
            （`load_batch()` 每 100 天才呼叫一次）。

            爬取層的失敗已經是逐日隔離的（見 `CrawlResult`），清洗層沒有理由不是。
        - Parameters:
            - clean: Callable
                cleaner 的清洗函式
            - raw: pd.DataFrame
                原始表格
            - date: datetime.date
                該日
            - label: str
                來源名稱，只用於訊息
        - Return:
            - bool
                清洗成功且有資料為 True
        """

        try:
            cleaned: Optional[pd.DataFrame] = clean(raw, date)
        except Exception as error:
            logger.error(
                f"[{label}] {date} 清洗失敗（{type(error).__name__}: {error}），"
                f"本日計為失敗、下次執行會重試"
            )
            return False

        if cleaned is None or cleaned.empty:
            logger.warning(f"Cleaned {label} dataframe empty on {date}")

        return True

    @staticmethod
    def report_cleaner_failures(dates: List[datetime.date]) -> None:
        """清洗失敗的日期列一次，讓「哪幾天要重跑」不必翻整份 log"""

        if not dates:
            return

        logger.error(
            f"* 有 {len(dates)} 天清洗失敗、已標記為待重試：{dates[:10]}"
            + ("…（僅列前 10 筆）" if len(dates) > 10 else "")
        )

    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""
        pass

    @abstractmethod
    def update(self, *args, **kwargs) -> None:
        """Update the Database"""
        pass
