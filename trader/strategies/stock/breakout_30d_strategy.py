# Python standard library
import datetime
from typing import List, Optional, Tuple

import pandas as pd
from loguru import logger

from trader.api.stock_price_api import StockPriceAPI
from trader.models import StockAccount, StockOrder, StockPosition, StockQuote
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Action, Market, PositionType, Scale, Units
from trader.utils.market_calendar import MarketCalendar


class Breakout30DStrategy(BaseStockStrategy):
    """
    經典 30 日突破策略 (30-Day Breakout)

    核心邏輯：
    - 用「過去 30 個交易日最高價與最低價」決定進出場
    - 突破過去 30 天最高價 → 做多 (buy breakout)
    - 跌破過去 30 天最低價 → 出場 (sell breakout)
    """

    DEFAULT_LOOKBACK_DAYS: int = 30
    DEFAULT_MAX_HOLDINGS: int = 10
    DEFAULT_BACKTEST_START_DATE: datetime.date = datetime.date(2020, 5, 1)
    DEFAULT_BACKTEST_END_DATE: datetime.date = datetime.date(2025, 5, 31)

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Breakout30D"
        self.market: str = Market.STOCK
        self.position_type: str = PositionType.LONG
        self.init_capital: float = 1000000.0
        self.max_holdings: int = self.DEFAULT_MAX_HOLDINGS
        self.lookback_days: int = self.DEFAULT_LOOKBACK_DAYS
        self.scale: str = Scale.DAY
        self.start_date: datetime.date = self.DEFAULT_BACKTEST_START_DATE
        self.end_date: datetime.date = self.DEFAULT_BACKTEST_END_DATE

        self.setup_apis()

    def setup_account(self, account: StockAccount) -> None:
        """設置虛擬帳戶資訊"""
        self.account: StockAccount = account

    def setup_apis(self) -> None:
        """設置資料 API"""
        if self.scale in (Scale.DAY, Scale.MIX):
            self.price: StockPriceAPI = StockPriceAPI()

    def _get_30d_high_low(
        self, stock_id: str, current_date: datetime.date
    ) -> Optional[Tuple[float, float]]:
        """
        取得過去 N 個交易日的最高價與最低價（不含當日）

        Returns:
            (high_30d, low_30d) 或 None（若資料不足）
        """
        # 前一交易日
        last_trading_date: datetime.date = MarketCalendar.get_last_trading_date(
            api=self.price, date=current_date
        )

        # 取足夠範圍以涵蓋 lookback_days 個交易日（約 45 個日曆日）
        start_date: datetime.date = last_trading_date - datetime.timedelta(days=60)

        prices_df: pd.DataFrame = self.price.get_stock_price(
            stock_id=stock_id,
            start_date=start_date,
            end_date=last_trading_date,
        )

        if prices_df.empty or len(prices_df) < self.lookback_days:
            return None

        # 取最後 lookback_days 筆
        recent_prices: pd.DataFrame = prices_df.tail(self.lookback_days)
        high_30d: float = recent_prices["最高價"].max()
        low_30d: float = recent_prices["最低價"].min()

        return (high_30d, low_30d)

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉：突破過去 30 天最高價 → 做多"""
        open_positions: List[StockQuote] = []

        if self.max_holdings > 0 and self.account.get_position_count() >= self.max_holdings:
            return []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                continue

            result = self._get_30d_high_low(stock_quote.stock_id, stock_quote.date)
            if result is None:
                continue

            high_30d, low_30d = result
            today_close = stock_quote.close

            # 突破過去 30 天最高價 → 做多
            if today_close > high_30d:
                logger.info(
                    f"股票 {stock_quote.stock_id} 突破 30 日高 {high_30d:.2f}，"
                    f"收盤 {today_close:.2f} → 做多"
                )
                open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉：跌破過去 30 天最低價 → 出場"""
        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if not self.account.check_has_position(stock_quote.stock_id):
                continue

            position: Optional[StockPosition] = (
                self.account.get_first_open_position(stock_quote.stock_id)
            )
            if position is None:
                continue

            result = self._get_30d_high_low(stock_quote.stock_id, stock_quote.date)
            if result is None:
                continue

            high_30d, low_30d = result
            today_close = stock_quote.close

            # 跌破過去 30 天最低價 → 出場
            if today_close < low_30d:
                logger.info(
                    f"股票 {stock_quote.stock_id} 跌破 30 日低 {low_30d:.2f}，"
                    f"收盤 {today_close:.2f} → 出場"
                )
                close_positions.append(stock_quote)

        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損策略（本策略不額外設停損，由突破邏輯決定出場）"""
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算 Open or Close 的部位大小"""
        orders: List[StockOrder] = []

        if action == Action.BUY:
            available_position_cnt: int = (
                max(0, self.max_holdings - self.account.get_position_count())
                if self.max_holdings is not None
                else len(stock_quotes)
            )

            if available_position_cnt > 0:
                per_position_size: float = (
                    self.account.balance / available_position_cnt
                )

                for stock_quote in stock_quotes:
                    if available_position_cnt == 0:
                        break

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
