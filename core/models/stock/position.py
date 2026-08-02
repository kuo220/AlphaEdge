import datetime
from typing import Optional

from core.utils import PositionType, ShortMethod


class StockPosition:
    """
    庫存未平倉倉位資訊

    放空欄位的計算時點（見 backlog §4.3，不遵守會導致重複計費）：
    - MARGIN 融券手續費：開倉時一次收取，記入 borrow_fee
    - MARGIN 融券利息：平倉時依 exit_date − entry_date 一次算出，不逐日累加
    - SBL 借券費：由 accrue_holding_cost() 逐日計提至 accrued_borrow_fee
    """

    def __init__(
        self,
        id: int = 0,
        stock_id: str = "",
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
        short_method: Optional[ShortMethod] = None,
        is_day_trade: bool = False,
        margin: float = 0.0,
        short_proceeds: float = 0.0,
        borrow_fee: float = 0.0,
        accrued_borrow_fee: float = 0.0,
        holding_days: int = 0,
    ):
        # Basic Info
        self.id: int = id  # 倉位編號（每筆倉位唯一編號）
        self.stock_id: str = stock_id  # 股票代號
        self.is_closed: bool = is_closed  # 是否已經平倉
        self.position_type: PositionType = position_type  # 持倉方向（Long or Short）

        # Position Info
        self.date: datetime.date = date  # 開倉日期
        self.price: float = price  # 開倉價位
        self.volume: int = volume  # 開倉張數

        # Transaction Costs
        self.commission: float = commission  # 開倉手續費
        self.tax: float = tax  # 開倉交易稅
        self.transaction_cost: float = transaction_cost  # 開倉交易成本

        # Transaction Performance （以後再寫更新未實現損益的函數）
        self.unrealized_pnl: float = unrealized_pnl  # 未實現損益
        self.unrealized_roi: float = unrealized_roi  # 未實現報酬率

        # Short Info（LONG 部位一律維持預設值，不受影響）
        self.short_method: Optional[ShortMethod] = short_method  # 放空管道
        self.is_day_trade: bool = is_day_trade  # 是否為現股當沖
        self.margin: float = margin  # 已繳保證金
        self.short_proceeds: float = short_proceeds  # 融券賣出擔保價款（不計入可用餘額）
        self.borrow_fee: float = borrow_fee  # 開倉時一次收取的融券手續費
        self.accrued_borrow_fee: float = accrued_borrow_fee  # SBL 逐日計提的借券費
        self.holding_days: int = holding_days  # 已持有曆日數
