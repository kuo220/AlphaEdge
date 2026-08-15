import datetime
from abc import ABC, abstractmethod
from typing import Dict, List

from core.models import BaseQuote
from core.strategies.base import BaseStrategy
from core.utils import Scale

"""BaseDataFeed: 資料載入、報價轉換與交易日判定"""


class BaseDataFeed(ABC):
    """
    資料源：把某個市場的原始資料變成引擎看得懂的報價

    不算「行為 model」，但必須一起抽——否則引擎的資料載入仍會直接 import
    各市場的具體 API，`Backtester` 就不可能與市場無關。
    """

    @abstractmethod
    def setup(self, strategy: BaseStrategy) -> None:
        """
        - Description:
            依策略宣告的級別建立所需的資料 API
        - Parameters:
            - strategy: BaseStrategy
                本次回測的策略
        """
        pass

    @abstractmethod
    def is_market_open(self, date: datetime.date) -> bool:
        """
        - Description:
            判斷指定日期是否為該市場的交易日
        - Parameters:
            - date: datetime.date
                待判定的日期
        - Return:
            - bool
        """
        pass

    def close(self) -> None:
        """關閉所有資料連線；預設為 no-op，有連線的資料源自行覆寫"""

        pass

    def get_price_limit_basis(self, date: datetime.date) -> Dict[str, float]:
        """
        - Description:
            取得當日「漲跌停基準價」與前一交易日收盤不同的標的

            一般日子的基準就是前收盤，由 `FillModel` 自行累積即可；
            但除權息日的基準是交易所另行公告的**開盤競價基準**，沿用前收會讓
            整段漲跌停區間偏移。有這類公告的市場覆寫本方法即可。
        - Parameters:
            - date: datetime.date
                交易日
        - Return:
            - Dict[str, float]
                `{symbol: 基準價}`；沒有這種公告的市場回傳空 dict（預設）
        """

        return {}

    def get_short_balance(self, date: datetime.date) -> Dict[str, int]:
        """
        - Description:
            取得當日可放空的券源餘額

            台股為融券今日餘額（張）。**空 dict 代表「查無資料」而非「都借不到」**，
            `FillModel` 查不到時一律放行。沒有券源概念的市場沿用預設即可。
        - Parameters:
            - date: datetime.date
                交易日
        - Return:
            - Dict[str, int]
                `{symbol: 可借券張數}`；預設為空 dict
        """

        return {}

    @abstractmethod
    def get_quotes(
        self,
        date: datetime.date,
        scale: Scale,
        adjusted: bool = False,
    ) -> List[BaseQuote]:
        """
        - Description:
            取得指定日期、指定級別的報價
        - Parameters:
            - date: datetime.date
                交易日
            - scale: Scale
                報價級別（DAY / TICK）
            - adjusted: bool
                是否附上還原價（掛在 `BaseQuote.adj_close`，OHLC 一律維持原始價）。
                不支援還原的市場忽略此參數即可
        - Return:
            - List[BaseQuote]
                該日報價；無資料時回傳空 list
        """
        pass
