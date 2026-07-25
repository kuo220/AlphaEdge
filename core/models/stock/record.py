import datetime
from typing import Optional

from core.utils import PositionType, ShortMethod

"""StockTradeRecord: single stock trade event in backtesting (transaction and performance details)"""


class StockTradeRecord:
    """
    單筆股票交易紀錄

    欄位語意（見 backlog §2.6、§5.4）：
    - buy_* / sell_* 以「操作動作」對應：SHORT 的 sell_* 是放空開倉、buy_* 是回補
    - entry_* / exit_* 為方向中立欄位：entry 一律是開倉、exit 一律是平倉
    - ⚠ 報表與統計的時間軸一律使用 exit_date，不要用 sell_date
      （SHORT 的 sell_date 是開倉日，用它會把損益畫在開倉那天）
    """

    def __init__(
        self,
        id: int = 0,
        stock_id: str = "",
        is_closed: bool = False,
        position_type: PositionType = PositionType.LONG,
        buy_date: datetime.date = None,
        buy_price: float = 0.0,
        buy_volume: int = 0,
        sell_date: datetime.date = None,
        sell_price: float = 0.0,
        sell_volume: int = 0,
        commission: float = 0.0,
        tax: float = 0.0,
        transaction_cost: float = 0.0,
        realized_pnl: float = 0.0,
        roi: float = 0.0,
        short_method: Optional[ShortMethod] = None,
        borrow_fee: float = 0.0,
        interest: float = 0.0,
        margin: float = 0.0,
        holding_days: int = 0,
        roi_on_capital: float = 0.0,
    ):
        # Basic Info
        self.id: int = id  # 交易編號（每筆交易唯一編號）
        self.stock_id: str = stock_id  # 股票代號

        # Position Status
        self.is_closed: bool = is_closed  # 是否已經平倉
        self.position_type: PositionType = position_type  # 持倉方向（Long or Short）

        # Buy Info
        self.buy_date: datetime.date = buy_date  # 買入日期
        self.buy_price: float = buy_price  # 買入價位
        self.buy_volume: int = buy_volume  # 買入張數

        # Sell Info
        self.sell_date: datetime.date = sell_date  # 賣出日期
        self.sell_price: float = sell_price  # 賣出價位
        self.sell_volume: int = sell_volume  # 賣出張數

        # Transaction Costs
        self.commission: float = commission  # 交易手續費
        self.tax: float = tax  # 交易稅
        self.transaction_cost: float = (
            transaction_cost  # 總交易成本 = 交易手續費 + 交易稅 + 借券費 − 利息
        )

        # Transaction Performance
        self.realized_pnl: float = realized_pnl  # 已實現損益
        self.roi: float = roi  # 名目報酬率（供聚合統計使用）
        self.roi_on_capital: float = roi_on_capital  # 資金效率（僅供報表參考）

        # Short Info（LONG 一律維持預設值）
        self.short_method: Optional[ShortMethod] = short_method  # 放空管道
        self.borrow_fee: float = borrow_fee  # 借券費（融券手續費或 SBL 累計費用）
        self.interest: float = interest  # 融券保證金利息收入
        self.margin: float = margin  # 開倉時繳交的保證金
        self.holding_days: int = holding_days  # 持有曆日數

        # Direction-neutral Info（依方向自動推導，報表與統計一律使用這組欄位）
        self.entry_date: datetime.date = None
        self.entry_price: float = 0.0
        self.exit_date: datetime.date = None
        self.exit_price: float = 0.0

        self.setup_entry_exit()

    def setup_entry_exit(self) -> None:
        """依部位方向推導方向中立的開平倉欄位：LONG 先買後賣、SHORT 先賣後買"""

        if self.position_type == PositionType.SHORT:
            self.entry_date = self.sell_date
            self.entry_price = self.sell_price
            self.exit_date = self.buy_date
            self.exit_price = self.buy_price
        else:
            self.entry_date = self.buy_date
            self.entry_price = self.buy_price
            self.exit_date = self.sell_date
            self.exit_price = self.sell_price
