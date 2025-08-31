# Python standard library
import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd

from trader.api import (
    FinancialStatementAPI,
    MonthlyRevenueReportAPI,
    StockChipAPI,
    StockPriceAPI,
    StockTickAPI,
)
from trader.models import StockAccount, StockOrder, StockQuote, StockTradeRecord
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Action, Market, PositionType, Scale, Units


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

        self.setup_account(StockAccount(init_capital=self.init_capital))
        self.setup_apis()

    def setup_account(self, account: StockAccount):
        """設置虛擬帳戶資訊"""

        self.account = account

    def setup_apis(self):
        """設置資料 API"""

        self.chip = StockChipAPI()
        self.mrr = MonthlyRevenueReportAPI()
        self.fs = FinancialStatementAPI()

        if self.scale in (Scale.TICK, Scale.MIX):
            self.tick: StockTickAPI = StockTickAPI()

        elif self.scale in (Scale.DAY, Scale.MIX):
            self.price: StockPriceAPI = StockPriceAPI()

        elif self.scale in (Scale.MIX, Scale.ALL):
            self.tick: StockTickAPI = StockTickAPI()
            self.price: StockPriceAPI = StockPriceAPI()

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉策略（Long & Short）"""

        open_positions: List[StockQuote] = []

        if self.max_holdings == 0:
            return None

        for stock_quote in stock_quotes:
            # Condition 1: 當日漲 > 9% 的股票
            yesterday: datetime.date = stock_quote.date - datetime.timedelta(days=1)
            price_yesterday: pd.DataFrame = self.price.get(yesterday)

            price_chg: float = (
                stock_quote.close
                / price_yesterday[price_yesterday["stock_id"] == stock_quote.stock_id][
                    "收盤價"
                ]
                - 1
            ) * 100

            if price_chg < 9:
                continue

            # Condition 2: Volume > 5000 Lot
            if stock_quote.volume < 5000 * Units.LOT:
                continue

            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.OPEN)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉策略（Long & Short）"""

        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                if stock_quote.date >= self.account.get_first_open_position(
                    stock_quote.stock_id
                ).date + datetime.timedelta(days=1):
                    close_positions.append(stock_quote)

        return self.calculate_position_size(close_positions, Action.CLOSE)

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
