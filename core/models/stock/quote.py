import datetime

import pandas as pd

from core.models.base.quote import BaseQuote
from core.utils import Scale

"""Quote structures: tick-level and daily-level pricing in backtesting"""


class TickQuote:
    """Tick 報價資訊（即時報價）"""

    def __init__(
        self,
        stock_id: str = "",
        time: pd.Timestamp = None,
        close: float = 0.0,
        volume: int = 0,  # Unit: Lot
        bid_price: float = 0.0,
        bid_volume: int = 0,  # Unit: Lot
        ask_price: float = 0.0,
        ask_volume: int = 0,  # Unit: Lot
        tick_type: int = 0,
    ):
        # Basic Info
        self.stock_id: str = stock_id  # Stock ID
        self.time: pd.Timestamp = time  # Quote timestamp

        # Current Price & Volume
        self.close: float = close  # 成交價
        self.volume: int = volume  # 成交量（Unit: Lot）

        # Bid & Ask Price & Volume
        self.bid_price: float = bid_price  # 委買價
        self.bid_volume: int = bid_volume  # 委買量
        self.ask_price: float = ask_price  # 委賣價
        self.ask_volume: int = ask_volume  # 委賣量

        # Tick Info
        self.tick_type: int = tick_type  # 內外盤別{1: 外盤, 2: 內盤, 0: 無法判定}


class StockQuote(BaseQuote):
    """個股報價資訊"""

    def __init__(
        self,
        stock_id: str = "",
        scale: Scale = None,
        date: datetime.datetime = None,
        cur_price: float = 0.0,
        volume: int = 0,  # Unit: Lot
        open: float = 0.0,
        high: float = 0.0,
        low: float = 0.0,
        close: float = 0.0,
        tick: TickQuote = None,
    ):
        super().__init__(
            symbol=stock_id,
            scale=scale,
            date=date,
            cur_price=cur_price,
            volume=volume,
            open=open,
            high=high,
            low=low,
            close=close,
        )

        # Tick Data
        self.tick_quote: TickQuote = tick  # tick quote data

    @property
    def stock_id(self) -> str:
        """symbol 的台股別名：既有策略與報表沿用 stock_id 取值，不需改寫"""

        return self.symbol
