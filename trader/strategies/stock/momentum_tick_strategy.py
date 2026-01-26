# Python standard library
import datetime
from typing import List, Optional

import pandas as pd
from loguru import logger

from trader.api.financial_statement_api import FinancialStatementAPI
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from trader.api.stock_chip_api import StockChipAPI
from trader.api.stock_price_api import StockPriceAPI
from trader.api.stock_tick_api import StockTickAPI
from trader.models import StockAccount, StockOrder, StockPosition, StockQuote
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Action, PositionType, Scale, Units
from trader.utils.market_calendar import MarketCalendar


class MomentumTickStrategy(BaseStockStrategy):
    """Tick 級別動能策略（基於原本 MomentumStrategy 改寫）"""

    def __init__(self):
        super().__init__()
        self.strategy_name: str = "Momentum_Tick"
        self.init_capital: float = 1000000.0
        self.max_holdings: int = 10
        self.scale: Scale = Scale.TICK

        self.start_date: datetime.date = datetime.date(2020, 5, 1)
        self.end_date: datetime.date = datetime.date(2025, 5, 31)

        self.setup_apis()

    def setup_account(self, account: StockAccount):
        """設置虛擬帳戶資訊"""

        self.account = account

    def setup_apis(self):
        """設置資料 API

        - Tick 級別回測仍會使用日 K 價格來取得昨日收盤價
        """

        self.chip = StockChipAPI()
        self.mrr = MonthlyRevenueReportAPI()
        self.fs = FinancialStatementAPI()

        # Tick & Day 都載，方便同時使用
        self.tick: StockTickAPI = StockTickAPI()
        self.price: StockPriceAPI = StockPriceAPI()

    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """開倉策略（Tick 級別）

        規則沿用原 MomentumStrategy：
        1. 當日漲幅 > 9%
        2. 當下這一筆 tick 的成交量 >= 5000 張

        差異：
        - 當前價改用 tick_quote.close
        - 成交量改用 tick_quote.volume（單筆 tick 成交量）
        """

        open_positions: List[StockQuote] = []

        if self.max_holdings == 0 or not stock_quotes:
            return []

        # 取得昨日收盤價（仍用日 K 價）
        base_date: datetime.date = stock_quotes[0].date
        yesterday: datetime.date = MarketCalendar.get_last_trading_date(
            api=self.price, date=base_date
        )

        yesterday_prices: pd.DataFrame = self.price.get(yesterday)

        for stock_quote in stock_quotes:
            if stock_quote.tick_quote is None:
                continue

            tick = stock_quote.tick_quote

            # Condition 1: 當前漲幅 > 9%
            mask: pd.Series = yesterday_prices["stock_id"] == tick.stock_id
            if yesterday_prices.loc[mask, "收盤價"].empty:
                logger.warning(f"股票 {tick.stock_id} {yesterday} 收盤價為空")
                continue

            yesterday_close_price: float = yesterday_prices.loc[mask, "收盤價"].iloc[0]

            if yesterday_close_price == 0:
                logger.warning(f"股票 {tick.stock_id} {yesterday} 收盤價為 0 或 None")
                continue

            price_chg: float = (tick.close / yesterday_close_price - 1) * 100

            if price_chg < 9:
                continue

            logger.info(
                f"[Tick] 股票 {tick.stock_id} 時間 {tick.time} 漲幅 {round(price_chg, 2)}%"
            )

            # Condition 2: 單筆 tick 成交量 >= 5000 張
            if tick.volume < 5000:
                continue

            open_positions.append(stock_quote)

        return self.calculate_position_size(open_positions, Action.BUY)

    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """平倉策略（Tick 級別）

        - 沿用原本邏輯：持有超過 1 個交易日即平倉
        - 使用 tick_quote.time 的日期部分作為當前日期
        """

        close_positions: List[StockQuote] = []

        for stock_quote in stock_quotes:
            if self.account.check_has_position(stock_quote.stock_id):
                position: Optional[StockPosition] = (
                    self.account.get_first_open_position(stock_quote.stock_id)
                )
                if position is None:
                    logger.warning(f"股票 {stock_quote.stock_id} 沒有開倉記錄")
                    continue

                # tick 回測時，StockQuote.date 仍是一整天的 date
                cur_date: datetime.date = stock_quote.date
                if cur_date >= position.date + datetime.timedelta(days=1):
                    close_positions.append(stock_quote)

        return self.calculate_position_size(close_positions, Action.SELL)

    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """停損策略（此版本暫不實作）"""
        return []

    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """計算 Open or Close 的部位大小

        - BUY: 仍用帳戶餘額 / 可用持股數決定張數
        - 價格取用：
            - Tick 模式：tick_quote.close 作為下單價格
        """

        orders: List[StockOrder] = []

        if action == Action.BUY:
            if self.max_holdings is not None:
                available_position_cnt: int = max(
                    0, self.max_holdings - self.account.get_position_count()
                )
            else:
                available_position_cnt = 0

            if available_position_cnt > 0:
                per_position_size: float = self.account.balance / available_position_cnt

                for stock_quote in stock_quotes:
                    if stock_quote.tick_quote is None:
                        continue

                    price: float = stock_quote.tick_quote.close
                    if price <= 0:
                        continue

                    # 計算可買張數：可用資金 / 每張價格
                    open_volume: int = int(per_position_size / (price * Units.LOT))

                    if open_volume >= 1:
                        orders.append(
                            StockOrder(
                                stock_id=stock_quote.stock_id,
                                date=stock_quote.date,
                                action=action,
                                position_type=PositionType.LONG,
                                price=price,
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

                # 出場價格：若有 tick_quote 就用 tick 價，否則退回 0（理論上 tick 回測都會有）
                price: float = (
                    stock_quote.tick_quote.close
                    if stock_quote.tick_quote is not None
                    else 0.0
                )

                orders.append(
                    StockOrder(
                        stock_id=stock_quote.stock_id,
                        date=stock_quote.date,
                        action=action,
                        position_type=position.position_type,
                        price=price,
                        volume=position.volume,
                    )
                )
        return orders
