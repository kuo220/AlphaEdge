# Python standard library
import datetime
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np
import pandas as pd
from loguru import logger

from trader.api.financial_statement_api import FinancialStatementAPI
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from trader.api.stock_chip_api import StockChipAPI
from trader.api.stock_price_api import StockPriceAPI
from trader.api.stock_tick_api import StockTickAPI
from trader.models import StockAccount, StockOrder, StockPosition, StockQuote
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Action, Market, PositionType, Scale, Units
from trader.utils.instrument import StockUtils
from trader.utils.market_calendar import MarketCalendar


class MomentumStrategy(BaseStockStrategy):
    """Strategy"""

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum"
        self.init_capital: float = 1000000.0
        self.max_holdings: int = 10
        self.scale: Scale = Scale.DAY

        self.start_date: datetime.date = datetime.date(2020, 5, 1)
        self.end_date: datetime.date = datetime.date(2025, 5, 31)

        self.setup_apis()

    def setup_account(self, account: StockAccount) -> None:
        """設置虛擬帳戶資訊"""

        self.account: StockAccount = account

    def setup_apis(self) -> None:
        """設置資料 API"""

        self.chip: StockChipAPI = StockChipAPI()
        self.mrr: MonthlyRevenueReportAPI = MonthlyRevenueReportAPI()
        self.fs: FinancialStatementAPI = FinancialStatementAPI()

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
            return []

        yesterday: datetime.date = MarketCalendar.get_last_trading_date(
            api=self.price, date=stock_quotes[0].date
        )

        yesterday_prices: pd.DataFrame = self.price.get(yesterday)

        for stock_quote in stock_quotes:
            # Condition 1: 當日漲 > 9% 的股票
            mask: pd.Series = yesterday_prices["stock_id"] == stock_quote.stock_id
            if yesterday_prices.loc[mask, "收盤價"].empty:
                logger.warning(f"股票 {stock_quote.stock_id} {yesterday} 收盤價為空")
                continue
            yesterday_close_price: float = yesterday_prices.loc[mask, "收盤價"].iloc[0]

            if yesterday_close_price == 0:
                logger.warning(
                    f"股票 {stock_quote.stock_id} {yesterday} 收盤價為 0 或 None"
                )
                continue

            price_chg: float = (stock_quote.close / yesterday_close_price - 1) * 100

            if price_chg < 9:
                continue
            logger.info(f"股票 {stock_quote.stock_id} 漲幅 {round(price_chg, 2)}%")
            # Condition 2: Volume > 5000 Lot
            if stock_quote.volume < 5000:
                continue

            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉策略（Long & Short）"""

        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                position: Optional[StockPosition] = (
                    self.account.get_first_open_position(stock_quote.stock_id)
                )
                if position is None:
                    logger.warning(f"股票 {stock_quote.stock_id} 沒有開倉記錄")
                    continue
                if stock_quote.date >= position.date + datetime.timedelta(days=1):
                    close_positions.append(stock_quote)

        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損策略"""
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算 Open or Close 的部位大小"""

        orders: List[StockOrder] = []

        if action == Action.BUY:
            if self.max_holdings is not None:
                available_position_cnt: int = max(
                    0, self.max_holdings - self.account.get_position_count()
                )

            if available_position_cnt > 0:
                per_position_size: float = self.account.balance / available_position_cnt

                for stock_quote in stock_quotes:
                    # 計算可買張數：可用資金 / 每張價格
                    open_volume: int = int(
                        per_position_size / (stock_quote.close * Units.LOT)
                    )

                    if open_volume >= 1:
                        orders.append(
                            StockOrder(
                                stock_id=stock_quote.stock_id,
                                date=stock_quote.date,
                                action=action,
                                position_type=PositionType.LONG,
                                price=stock_quote.cur_price,
                                volume=open_volume,
                            )
                        )
                        available_position_cnt -= 1

                    if available_position_cnt == 0:
                        break
        elif action == Action.SELL:
            for stock_quote in stock_quotes:
                position: Optional[StockPosition] = (
                    self.account.get_first_open_position(stock_quote.stock_id)
                )

                if position is None:
                    continue

                orders.append(
                    StockOrder(
                        stock_id=stock_quote.stock_id,
                        date=stock_quote.date,
                        action=action,
                        position_type=position.position_type,
                        price=stock_quote.cur_price,
                        volume=position.volume,
                    )
                )
        return orders
