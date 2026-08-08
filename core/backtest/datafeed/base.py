import datetime
from abc import ABC, abstractmethod
from typing import List

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

    @abstractmethod
    def get_quotes(self, date: datetime.date, scale: Scale) -> List[BaseQuote]:
        """
        - Description:
            取得指定日期、指定級別的報價
        - Parameters:
            - date: datetime.date
                交易日
            - scale: Scale
                報價級別（DAY / TICK）
        - Return:
            - List[BaseQuote]
                該日報價；無資料時回傳空 list
        """
        pass
