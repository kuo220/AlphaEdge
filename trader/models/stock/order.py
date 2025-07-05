import datetime
from typing import Dict, List, Optional, Union
import pandas as pd

from trader.utils import Commission, PositionType, Scale


"""
This module defines the structure for stock orders used in the backtesting phase,
including trade direction, quantity, and price information.
"""


class StockOrder:
    """ 個股買賣的訂單 """

    def __init__(
        self,
        code: str="",
        date: datetime.datetime=None,
        price: float=0.0,
        volume: float=0.0,
        position_type: PositionType=PositionType.LONG
     ):
        # Basic Info
        self.code: str = code                                            # 股票代號
        self.date: datetime.datetime = date                              # 交易日期（Tick會是Timestamp）

        # Order Info
        self.price: float = price                                        # 交易價位
        self.volume: float = volume                                      # 交易數量（Unit: Lot）
        self.position_type: PositionType = position_type                 # 持倉方向（Long or Short）