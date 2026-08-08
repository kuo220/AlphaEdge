import datetime

from core.utils import PositionType

"""BasePosition: 市場無關的未平倉部位骨架（識別欄位一律為 symbol）"""


class BasePosition:
    """
    未平倉部位的共用骨架

    只收「每個市場都有」的欄位：識別、方向、開倉資訊、交易成本與未實現損益。
    保證金、借券費、持有天數等信用交易欄位屬台股專屬，由 StockPosition 補上。
    """

    def __init__(
        self,
        id: int = 0,
        symbol: str = "",
        is_closed: bool = False,
        position_type: PositionType = PositionType.LONG,
        date: datetime.date = None,
        price: float = 0.0,
        volume: int = 0,
        commission: float = 0.0,
        tax: float = 0.0,
        transaction_cost: float = 0.0,
        unrealized_pnl: float = 0.0,
        unrealized_roi: float = 0.0,
    ):
        # Basic Info
        self.id: int = id  # 倉位編號（每筆倉位唯一編號）
        self.symbol: str = symbol  # 商品代號
        self.is_closed: bool = is_closed  # 是否已經平倉
        self.position_type: PositionType = position_type  # 持倉方向（Long or Short）

        # Position Info
        self.date: datetime.date = date  # 開倉日期
        self.price: float = price  # 開倉價位
        self.volume: int = volume  # 開倉數量（台股為張、期貨為口）

        # Transaction Costs
        self.commission: float = commission  # 開倉手續費
        self.tax: float = tax  # 開倉交易稅
        self.transaction_cost: float = transaction_cost  # 開倉交易成本

        # Transaction Performance
        self.unrealized_pnl: float = unrealized_pnl  # 未實現損益
        self.unrealized_roi: float = unrealized_roi  # 未實現報酬率
