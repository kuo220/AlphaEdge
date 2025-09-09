import datetime

from trader.utils import PositionType

"""
This module defines the structure for stock orders used in the backtesting phase,
including trade direction, quantity, and price information.
"""


class StockOrder:
    """個股買賣的訂單"""

    def __init__(
        self,
        stock_id: str = "",
        date: datetime.datetime = None,
        price: float = 0.0,
        volume: int = 0,  # Unit: Lot
        position_type: PositionType = PositionType.LONG,
    ):
        # Basic Info
        self.stock_id: str = stock_id  # 股票代號
        self.date: datetime.datetime = date  # 交易日期（Tick會是Timestamp）

        # Order Info
        self.price: float = price  # 交易價位
        self.volume: int = volume  # 交易張數（Unit: Lot）
        self.position_type: PositionType = position_type  # 持倉方向（Long or Short）
