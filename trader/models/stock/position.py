import datetime

from trader.utils import PositionType


class StockPosition:
    """庫存未平倉倉位資訊"""

    def __init__(
        self,
        id: int=0,
        stock_id: str="",
        position_type: PositionType=PositionType.LONG,
        date: datetime.date=None,
        price: float=0.0,
        volume: int=0,
        commission: float=0.0,
        tax: float=0.0,
        transaction_cost: float=0.0,
        unrealized_pnl: float=0.0,
        unrealized_roi: float=0.0,
    ):
        # Basic Info
        self.id: int = id  # 倉位編號（每筆倉位唯一編號）
        self.stock_id: str = stock_id  # 股票代號
        self.position_type: PositionType = position_type  # 持倉方向（Long or Short）

        # Position Info
        self.date: datetime.date = date  # 開倉日期
        self.price: float = price  # 開倉價位
        self.volume: int = volume  # 開倉張數

        # Transaction Costs
        self.commission: float = commission  # 開倉手續費
        self.tax: float = tax  # 開倉交易稅
        self.transaction_cost: float = transaction_cost  # 開倉交易成本

        # Transaction Performance
        self.unrealized_pnl: float = unrealized_pnl  # 未實現損益
        self.unrealized_roi: float = unrealized_roi  # 未實現報酬率