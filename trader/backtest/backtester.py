import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from loguru import logger

from trader.adapters import StockQuoteAdapter
from trader.api import (
    FinancialStatementAPI,
    MonthlyRevenueReportAPI,
    StockChipAPI,
    StockPriceAPI,
    StockTickAPI,
)
from trader.models import (
    StockAccount,
    StockOrder,
    StockQuote,
    StockTradeRecord,
    TickQuote,
)
from trader.strategies.stock import BaseStockStrategy
from trader.utils import (
    Commission,
    Market,
    MarketCalendar,
    PositionType,
    Scale,
    StockUtils,
    TimeUtils,
    Units,
)

"""
Backtesting engine that simulates trading based on strategy signals.

Includes:
- Tick/day backtest flow
- Position and account management
- Order execution logic
- Strategy integration for various financial instruments
"""


class Backtester:
    """
    Backtest Framework
    - Time Interval：
        1. Ticks
        2. Daily price
    """

    # === Init & Data Loading ===
    def __init__(self, strategy: BaseStockStrategy):
        """=== Strategy & Account Information ==="""
        self.strategy: BaseStockStrategy = strategy  # 要回測的策略
        self.account: StockAccount = StockAccount(
            self.strategy.init_capital
        )  # 虛擬帳戶資訊
        self.strategy.set_account(self.account)  # 設置虛擬帳戶資訊

        """ === Datasets === """
        self.tick: Optional[StockTickAPI] = None  # Ticks data
        self.chip: Optional[StockChipAPI] = None  # Chips data
        self.price: Optional[StockPriceAPI] = None  # Price data
        self.mrr: Optional[MonthlyRevenueReportAPI] = (
            None  # Monthly Revenue Report data
        )
        self.fs: Optional[FinancialStatementAPI] = None  # Financial Statement data

        """ === Backtest Parameters === """
        self.scale: str = self.strategy.scale  # 回測 KBar 級別
        self.max_holdings: Optional[int] = self.strategy.max_holdings  # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date  # 回測起始日
        self.cur_date: datetime.date = self.strategy.start_date  # 回測當前日
        self.end_date: datetime.date = self.strategy.end_date  # 回測結束日

    def load_datasets(self) -> None:
        """從資料庫載入資料"""

        self.chip = StockChipAPI()
        self.mrr = MonthlyRevenueReportAPI()
        self.fs = FinancialStatementAPI()

        if self.scale == Scale.TICK:
            self.tick = StockTickAPI()

        elif self.scale == Scale.DAY:
            self.price = StockPriceAPI()

        elif self.scale == Scale.MIX:
            self.tick = StockTickAPI()
            self.price = StockPriceAPI()

    # === Main Backtest Loop ===
    def run(self) -> None:
        """執行 Backtest (目前只有全tick回測)"""

        logger.info("========== Backtest Start ==========")
        logger.info(f"* Strategy Name: {self.strategy.strategy_name}")
        logger.info(
            f"* Backtest Period: {self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')}"
        )
        logger.info(f"* Initial Capital: {self.strategy.init_capital}")
        logger.info(f"* Backtest Scale: {self.scale}")

        # load backtest dataset
        self.load_datasets()
        # load backtest period
        dates: List[datetime.date] = TimeUtils.generate_date_range(
            start_date=self.start_date, end_date=self.end_date
        )

        for date in dates:
            logger.info(f"--- {date.strftime('%Y/%m/%d')} ---")

            if not MarketCalendar().check_stock_market_open(date):
                logger.info("* Stock Market Close\n")
                continue

            if self.scale == Scale.TICK:
                self.run_tick_backtest(date)

            elif self.scale == Scale.DAY:
                self.run_day_backtest(date)

            elif self.scale == Scale.MIX:
                self.run_mix_backtest(date)

        self.account.update_account_status()

    def run_tick_backtest(self, date: datetime.date) -> None:
        """Tick 級別的回測架構"""

        # Stock Quotes
        stock_quotes: List[StockQuote] = StockQuoteAdapter.convert_to_tick_quotes(
            self.tick, date
        )

        if not stock_quotes:
            return

        self.execute_close_signal(stock_quotes)
        self.execute_open_signal(stock_quotes)

    def run_day_backtest(self, date: datetime.date) -> None:
        """Day 級別的回測架構"""

        # Stock Quotes
        stock_quotes: List[StockQuote] = StockQuoteAdapter.convert_to_day_quotes(
            self.price, date
        )

        if not stock_quotes:
            return

        self.execute_close_signal(stock_quotes)
        self.execute_open_signal(stock_quotes)

    def run_mix_backtest(self, date: datetime.date) -> None:
        """Tick & Day 級別的回測架構"""
        pass

    # === Signal Execution ===
    def execute_open_signal(self, stock_quotes: List[StockQuote]) -> None:
        """若倉位數量未達到限制且有開倉訊號，則執行開倉"""

        # Step 1: Get open orders
        open_orders: List[StockOrder] = self.strategy.check_open_signal(stock_quotes)
        if self.max_holdings is not None:
            remaining_holding: int = max(
                0, self.max_holdings - self.account.get_position_count()
            )
            open_orders = open_orders[:remaining_holding]

        # Step 2: Execute open orders
        for order in open_orders:
            self.place_open_order(order)

    def execute_close_signal(self, stock_quotes: List[StockQuote]) -> None:
        """執行平倉邏輯：先判斷停損訊號，後判斷一般平倉"""

        # Step 1:find stocks with existing positions
        positions: List[StockQuote] = [
            sq for sq in stock_quotes if self.account.check_has_position(sq.code)
        ]

        if not positions:
            return

        # Step 2: Get stop loss orders
        stop_loss_orders: List[StockOrder] = self.strategy.check_stop_loss_signal(
            positions
        )

        # Step 3: Execute stop loss orders
        for order in stop_loss_orders:
            self.place_close_order(order)

        # After executing stop loss, recheck the remaining positions
        remaining_positions: List[StockQuote] = [
            sq for sq in stock_quotes if self.account.check_has_position(sq.code)
        ]

        # Step 4: Get close orders
        close_orders: List[StockOrder] = self.strategy.check_close_signal(
            remaining_positions
        )

        # Step 5: Execute close orders
        for order in close_orders:
            self.place_close_order(order)

    # === Order Placement ===
    def place_open_order(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """
        - Description: 開倉下單股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """

        # Step 1: Calculate position value and open cost
        position_value: float = stock.price * stock.volume
        open_cost: float = StockUtils.calculate_transaction_commission(
            buy_price=stock.price, volume=stock.volume
        )

        # Step 2: Create position
        position: Optional[StockTradeRecord] = None

        # Step 3: Execute open order & update account
        if stock.position_type == PositionType.LONG:
            if self.account.balance >= (position_value + open_cost):
                logger.info(f"* Place Open Order: {stock.stock_id}")

                self.account.trade_id_counter += 1
                self.account.balance -= position_value + open_cost

                position = StockTradeRecord(
                    id=self.account.trade_id_counter,
                    stock_id=stock.stock_id,
                    date=stock.date,
                    position_type=stock.position_type,
                    buy_price=stock.price,
                    volume=stock.volume,
                    commission=open_cost,
                    transaction_cost=open_cost,
                    position_value=position_value,
                )

                self.account.positions.append(position)
                self.account.trade_records[position.id] = position

        return position

    def place_close_order(self, stock: StockOrder) -> Optional[StockTradeRecord]:
        """
        - Description: 下單平倉股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """

        # Step 1: Calculate position value and close cost
        position_value: float = stock.price * stock.volume
        close_cost: float = StockUtils.calculate_transaction_commission(
            sell_price=stock.price, volume=stock.volume
        )

        # Step 2: Find the first open position of the stock (FIFO)
        position: Optional[StockTradeRecord] = self.account.get_first_open_position(
            stock.stock_id
        )

        # Step 3: Execute close order & update account
        if position is not None and not position.is_closed:
            logger.info(f"* Place Close Order: {stock.stock_id}")

            if position.position_type == PositionType.LONG:
                position.date = stock.date
                position.is_closed = True
                position.sell_price = stock.price
                position.commission += close_cost
                position.tax = StockUtils.calculate_transaction_tax(
                    stock.price, stock.volume
                )
                position.transaction_cost = position.commission + position.tax
                position.realized_pnl = StockUtils.calculate_net_profit(
                    position.buy_price, position.sell_price, position.volume
                )
                position.roi = StockUtils.calculate_roi(
                    position.buy_price, position.sell_price, position.volume
                )

                self.account.balance += position_value - close_cost
                self.account.trade_records[position.id] = (
                    position  # 根據 position.id 更新 trade_records 中對應到的 position
                )
                self.account.positions = [
                    p for p in self.account.positions if p.id != position.id
                ]  # 每一筆開倉的部位都會記錄一個 id，因此這邊只會刪除對應到 id 的部位

        return position

    # === Report ===
    def generate_backtest_report(self) -> None:
        """生產回測報告"""
        pass
