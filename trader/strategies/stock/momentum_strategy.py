# Python standard library
import sys
import datetime
from pathlib import Path
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd

from trader.api import Data, Chip, Tick, QXData
from trader.models import StockAccount, StockQuote, StockOrder, StockTradeRecord
from trader.utils import Action, Market, Scale, PositionType
from trader.strategies.stock import BaseStockStrategy


class MomentumStrategy(BaseStockStrategy):
    """Strategy"""

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum"
        self.init_capital: float = 1000000.0
        self.max_holdings: int = 10
        self.scale: Scale = Scale.DAY

        self.start_date: datetime.date = datetime.date(2020, 4, 1)
        self.end_date: datetime.date = datetime.date(2024, 5, 10)

    def set_account(self, account: StockAccount):
        """設置虛擬帳戶資訊"""
        self.account = account

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉策略（Long & Short）"""

        open_positions: List[StockQuote] = []

        if self.max_positions == 0:
            return None

        for stock_quote in stock_quotes:

            # Condition 1: 當日漲 > 9% 的股票
            yesterday: datetime.date = stock_quote.date - datetime.timedelta(days=1)
            self.qx_data.date = yesterday

            close_price_yesterday: pd.DataFrame = self.qx_data.get("price", "收盤價", 1)
            price_chg: float = (
                stock_quote.close / close_price_yesterday[stock_quote.code][0] - 1
            ) * 100

            if price_chg < 9:
                continue

            # Condition 2: Volume > 5000
            self.qx_data.date = stock_quote.date
            volume = self.qx_data.get("volume", "成交量", 1)

            if volume[stock_quote.code][0] < 5000:
                continue

            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.OPEN)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉策略（Long & Short）"""

        pass

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損策略"""
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算 Open or Close 的部位大小"""
        pass
