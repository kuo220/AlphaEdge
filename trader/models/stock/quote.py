import datetime
from typing import Dict, List, Optional, Union
import pandas as pd

from trader.utils import Commission, PositionType, Scale


"""
This module defines data structures for representing stock quotes during backtesting,
including tick-level and daily-level pricing information.
"""


class TickQuote:
    """  Tick 報價資訊（即時報價） """

    def __init__(
        self,
        code: str="",
        time: pd.Timestamp=None,
        close: float=0.0,
        volume: int=0,
        bid_price: float=0.0,
        bid_volume: int=0,
        ask_price: float=0.0,
        ask_volume: int=0,
        tick_type: int=0
    ):
        # Basic Info
        self.code: str = code                                            # Stock code
        self.time: pd.Timestamp = time                                   # Quote timestamp

        # Current Price & Volume
        self.close: float = close                                        # 成交價
        self.volume: float = volume                                      # 成交量（Unit: Lot）

        # Bid & Ask Price & Volume
        self.bid_price: float = bid_price                                # 委買價
        self.bid_volume: int = bid_volume                                # 委買量
        self.ask_price: float = ask_price                                # 委賣價
        self.ask_volume: int = ask_volume                                # 委賣量

        # Tick Info
        self.tick_type: int = tick_type                                  # 內外盤別{1: 外盤, 2: 內盤, 0: 無法判定}


class StockQuote:
    """ 個股報價資訊 """

    def __init__(
        self,
        code: str="",
        scale: Scale=None,
        date: datetime.datetime=None,
        cur_price: float=0.0,
        volume: float=0.0,
        open: float=0.0,
        high: float=0.0,
        low: float=0.0,
        close: float=0.0,
        tick: TickQuote=None
    ):
        # Basic Info
        self.code: str = code                                            # Stock code
        self.scale: Scale = scale                                        # Quote scale (DAY or TICK or ALL)
        self.date: Union[datetime.date, datetime.datetime] = date        # Current date

        # Current Price & Volume
        self.cur_price: float = cur_price                                # Current price
        self.volume: float = volume                                      # order's volume (Unit: Lots)

        # OHLC Info
        self.open: float = open                                          # Open price
        self.high: float = high                                          # High price
        self.low: float = low                                            # Low price
        self.close: float = close                                        # Close price

        # Tick Data
        self.tick_quote: TickQuote = tick                                # tick quote data