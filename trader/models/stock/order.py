import datetime

from trader.utils import Action, PositionType


"""StockOrder: structure for stock orders in backtesting (direction, quantity, price)"""


class StockOrder:
    """個股買賣的訂單"""

    def __init__(
        self,
        stock_id: str = "",  # 股票代號
        date: datetime.datetime = None,  # 交易日期（Tick會是Timestamp）
        action: Action = Action.BUY,  # 訂單動作（Buy / Sell）
        position_type: PositionType = PositionType.LONG,  # 持倉方向（Long / Short）
        price: float = 0.0,  # 交易價位
        volume: int = 0,  # 交易張數（Unit: Lot）
    ):
        # Basic Info
        self.stock_id: str = stock_id
        self.date: datetime.datetime = date

        # Order Info
        self.action: Action = action
        self.position_type: PositionType = position_type
        self.price: float = price
        self.volume: int = volume
