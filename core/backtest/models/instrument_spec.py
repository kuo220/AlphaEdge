from abc import ABC, abstractmethod
from typing import Optional, Tuple

from core.utils import PRICE_LIMIT_RATIO
from core.utils.instrument import StockUtils

"""InstrumentSpec: 商品規格（報價單位換算、跳動點、漲跌停規則）"""


class InstrumentSpec(ABC):
    """
    商品規格：報價單位換算、跳動點、漲跌停規則

    市場差異最集中的地方，被成交價驗證與每日權益快照兩處使用。
    對應 Lean 的 SymbolProperties。
    """

    @abstractmethod
    def to_units(self, volume: int) -> int:
        """
        - Description:
            下單數量 → 計價單位（台股：張 → 股 ×1000；期貨：口 → 契約乘數）
        - Parameters:
            - volume: int
                下單數量（台股為張、期貨為口）
        - Return:
            - int
                計價單位數量
        """
        pass

    @abstractmethod
    def round_to_tick(self, price: float, direction: str = "nearest") -> float:
        """
        - Description:
            將價格對齊該商品的跳動點，避免算出不可能成交的價格
        - Parameters:
            - price: float
                原始價格
            - direction: str
                取整方向："up"（進位）、"down"（捨去）、"nearest"（就近）
        - Return:
            - float
                對齊檔位後的價格
        """
        pass

    @abstractmethod
    def get_price_limits(
        self, prev_close: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        - Description:
            依前一交易日收盤價推算漲跌停區間
        - Parameters:
            - prev_close: float
                前一交易日收盤價
        - Return:
            - Tuple[Optional[float], Optional[float]]
                (跌停價, 漲停價)；無漲跌停制度時回傳 (None, None)
        """
        pass


class TwStockSpec(InstrumentSpec):
    """台股規格：1 張 ＝ 1000 股、六段跳動點、漲跌停 ±10%"""

    def to_units(self, volume: int) -> int:
        """張 → 股（×1000）"""

        return StockUtils.convert_lot_to_share(volume)

    def round_to_tick(self, price: float, direction: str = "nearest") -> float:
        """對齊台股六段分段檔位"""

        return StockUtils.round_to_tick(price, direction)

    def get_price_limits(
        self, prev_close: float
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        - Description:
            台股漲跌停為前收 ±10%，並各自往內對齊檔位（漲停捨去、跌停進位）

            對齊方向不可對調：漲停若進位會算出高於法定漲停的價格。
        """

        if not prev_close:
            return (None, None)

        limit_up: float = self.round_to_tick(
            prev_close * (1 + PRICE_LIMIT_RATIO), "down"
        )
        limit_down: float = self.round_to_tick(
            prev_close * (1 - PRICE_LIMIT_RATIO), "up"
        )
        return (limit_down, limit_up)
