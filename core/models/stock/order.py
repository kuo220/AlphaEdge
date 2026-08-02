import datetime
from typing import Optional

from core.utils import Action, PositionType, ShortMethod

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
        short_method: Optional[ShortMethod] = None,  # 放空管道（由引擎補值）
        is_day_trade: bool = False,  # 是否為現股當沖（由引擎補值）
    ):
        # Basic Info
        self.stock_id: str = stock_id
        self.date: datetime.datetime = date

        # Order Info
        self.action: Action = action
        self.position_type: PositionType = position_type
        self.price: float = price
        self.volume: int = volume

        # Short Info（策略不需自行填寫，由 Backtester._enrich_orders 依策略設定補值）
        self.short_method: Optional[ShortMethod] = short_method
        self.is_day_trade: bool = is_day_trade
