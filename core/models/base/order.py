import datetime

from core.utils import Action, PositionType

"""BaseOrder: 市場無關的訂單骨架（識別欄位一律為 symbol）"""


class BaseOrder:
    """
    買賣訂單的共用骨架

    方向（LONG／SHORT）與市場（股票／期貨）是兩條獨立的軸：
    position_type 屬前者，故留在本骨架；放空管道等台股專屬欄位由 StockOrder 補上。
    """

    def __init__(
        self,
        symbol: str = "",  # 商品代號
        date: datetime.datetime = None,  # 交易日期（Tick會是Timestamp）
        action: Action = Action.BUY,  # 訂單動作（Buy / Sell）
        position_type: PositionType = PositionType.LONG,  # 持倉方向（Long / Short）
        price: float = 0.0,  # 交易價位
        volume: int = 0,  # 交易數量（台股為張、期貨為口）
    ):
        # Basic Info
        self.symbol: str = symbol
        self.date: datetime.datetime = date

        # Order Info
        self.action: Action = action
        self.position_type: PositionType = position_type
        self.price: float = price
        self.volume: int = volume
