import datetime

from trader.utils import PositionType

"""
This module defines the structure for recording individual stock trade events,
capturing all relevant transaction and performance details during backtesting.
"""


class StockTradeRecord:
    """單筆股票交易紀錄"""

    def __init__(
        self,
        id: int = 0,
        stock_id: str = "",
        date: datetime.datetime = None,
        is_closed: bool = False,
        position_type: PositionType = PositionType.LONG,
        buy_price: float = 0.0,
        sell_price: float = 0.0,
        volume: float = 0.0,
        commission: float = 0.0,
        tax: float = 0.0,
        transaction_cost: float = 0.0,
        realized_pnl: float = 0.0,
        roi: float = 0.0,
    ):
        # Basic Info
        self.id: int = id  # 交易編號（每筆交易唯一編號）
        self.stock_id: str = stock_id  # 股票代號
        self.date: datetime.date | datetime.datetime = (
            date  # 交易日期（Tick會是Timestamp）
        )

        # Position Status
        self.is_closed: bool = is_closed  # 是否已經平倉
        self.position_type: PositionType = position_type  # 持倉方向（Long or Short）

        # Price & Quantity
        self.buy_price: float = buy_price  # 買入價位
        self.sell_price: float = sell_price  # 賣出價位
        self.volume: float = volume  # 交易股數

        # Transaction Costs
        self.commission: float = commission  # 交易手續費
        self.tax: float = tax  # 交易稅
        self.transaction_cost: float = (
            transaction_cost  # 總交易成本 = 交易手續費 + 交易稅
        )

        # Transaction Performance
        self.realized_pnl: float = realized_pnl  # 已實現損益
        self.roi: float = roi  # 報酬率
