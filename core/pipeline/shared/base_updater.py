from abc import ABC, abstractmethod
from dataclasses import dataclass

from loguru import logger

from core.pipeline.shared.base_crawler import CrawlResult

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

    def record(self, *results: CrawlResult) -> bool:
        """
        - Description:
            記錄同一天的多個來源結果，並回報這一天是否**確定**沒有資料

            同一天的上市與上櫃各爬一次：只要有任何一邊失敗，這天就**不算**
            確定沒資料——否則下次就不會再補這天了。
        - Parameters:
            - results: CrawlResult
                同一天各來源的結果
        - Return:
            - bool
                所有來源都明確回覆沒有資料為 True
        """

        self.requested += 1

        if any(result.is_failed for result in results):
            self.unreachable += 1
            return False

        if all(result.is_no_data for result in results):
            self.no_data += 1
            return True

        self.ok += 1
        return False

    def summary_line(self, source: str) -> str:
        """單行統計字串"""

        return (
            f"[{source}] 本批統計："
            f"{self.requested} requested / {self.ok} ok / "
            f"{self.no_data} no data / {self.unreachable} unreachable"
        )

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

    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""
        pass

    @abstractmethod
    def update(self, *args, **kwargs) -> None:
        """Update the Database"""
        pass
