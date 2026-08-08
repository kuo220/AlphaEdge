import datetime
from typing import Union

from core.utils import Scale

"""BaseQuote: 市場無關的報價骨架（識別欄位一律為 symbol）"""


class BaseQuote:
    """
    報價資訊的共用骨架

    識別欄位命名為 symbol 而非 stock_id：引擎骨架不應該知道自己在跑哪個市場，
    台股的 stock_id 由 StockQuote 以 property 別名維持相容（見 backlog Phase1-1）。
    """

    def __init__(
        self,
        symbol: str = "",
        scale: Scale = None,
        date: datetime.datetime = None,
        cur_price: float = 0.0,
        volume: int = 0,  # Unit: Lot
        open: float = 0.0,
        high: float = 0.0,
        low: float = 0.0,
        close: float = 0.0,
    ):
        # Basic Info
        self.symbol: str = symbol  # 商品代號（台股為股票代號、期貨為契約代號）
        self.scale: Scale = scale  # Quote scale (DAY or TICK or ALL)
        self.date: Union[datetime.date, datetime.datetime] = date  # Current date

        # Current Price & Volume
        self.cur_price: float = cur_price  # Current price
        self.volume: int = volume  # order's volume (Unit: Lot)

        # OHLC Info
        self.open: float = open  # Open price
        self.high: float = high  # High price
        self.low: float = low  # Low price
        self.close: float = close  # Close price
