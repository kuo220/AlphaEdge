import datetime

from core.models.base.order import BaseOrder
from core.utils import Action, PositionType

"""FuturesOrder: 台期貨訂單（數量單位為口）"""


class FuturesOrder(BaseOrder):
    """
    期貨買賣的訂單

    **`volume` 的單位是口**。期貨沒有「張」，也沒有股數換算——PnL 直接由
    價格變動 × 乘數 × 口數決定。
    """

    def __init__(
        self,
        product: str = "",
        expiry: str = "",
        date: datetime.datetime = None,
        action: Action = Action.BUY,
        position_type: PositionType = PositionType.LONG,
        price: float = 0.0,
        volume: int = 0,  # Unit: Contract（口）
    ):
        super().__init__(
            symbol=f"{product}{expiry}",
            date=date,
            action=action,
            position_type=position_type,
            price=price,
            volume=volume,
        )

        # Contract Info
        self.product: str = product  # 商品代碼（Ex: TX）
        self.expiry: str = expiry  # 到期月份（Ex: 202601）

    @property
    def contract_id(self) -> str:
        """symbol 的期貨別名：`{product}{expiry}`"""

        return self.symbol
