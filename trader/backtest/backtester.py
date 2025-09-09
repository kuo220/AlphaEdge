import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple, Union

import numpy as np
import pandas as pd
from loguru import logger

from trader.adapters import StockQuoteAdapter
from trader.api.financial_statement_api import FinancialStatementAPI
from trader.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from trader.api.stock_chip_api import StockChipAPI
from trader.api.stock_price_api import StockPriceAPI
from trader.api.stock_tick_api import StockTickAPI
from trader.backtest.analysis.analyzer import StockBacktestAnalyzer
from trader.backtest.report.reporter import StockBacktestReporter
from trader.config import BACKTEST_LOGS_DIR_PATH, BACKTEST_RESULT_DIR_PATH
from trader.models import (
    StockAccount,
    StockOrder,
    StockQuote,
    StockTradeRecord,
    TickQuote,
)
from trader.strategies.stock import BaseStockStrategy
from trader.utils import PositionType, Scale, TimeUtils
from trader.utils.instrument import StockUtils
from trader.utils.market_calendar import MarketCalendar

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
        self.strategy.setup_account(self.account)  # 設置虛擬帳戶資訊

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

        """ === Backtest Result Directory === """
        self.strategy_result_dir: Optional[Path] = None  # 策略回測結果資料夾

        self.setup()

    def setup(self):
        """Set Up the Config of Backtester"""

        # 確保每個 strategy 有獨立的結果資料夾
        self.strategy_result_dir = (
            Path(BACKTEST_RESULT_DIR_PATH) / self.strategy.strategy_name
        )
        self.strategy_result_dir.mkdir(parents=True, exist_ok=True)

        # Set Log File Path
        logger.add(f"{BACKTEST_LOGS_DIR_PATH}/{self.strategy.strategy_name}.log")

    def load_datasets(self) -> None:
        """從資料庫載入資料"""

        self.chip = StockChipAPI()
        self.mrr = MonthlyRevenueReportAPI()
        self.fs = FinancialStatementAPI()
        self.price = StockPriceAPI()

        if self.scale == Scale.TICK or self.scale == Scale.MIX:
            self.tick = StockTickAPI()

    # === Main Backtest Loop ===
    def run(self) -> None:
        """執行 Backtest"""

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

            if not MarketCalendar.check_stock_market_open(api=self.price, date=date):
                logger.info("* Stock Market Close\n")
                continue

            if self.scale == Scale.TICK:
                self.run_tick_backtest(date)

            elif self.scale == Scale.DAY:
                self.run_day_backtest(date)

            elif self.scale == Scale.MIX:
                self.run_mix_backtest(date)

        self.account.update_account_status()

        logger.info(
            f"""
            1. Initial Capital: {int(self.account.init_capital)}
            2. Balance: {int(self.account.balance)}
            3. Total realized pnl: {int(self.account.realized_pnl)}
            4. ROI: {round(self.account.roi, 2)}%
            """
        )

        # Generate Backtest Report
        self.generate_backtest_report()

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

        # Step 2: Execute open orders
        for order in open_orders:
            self.place_open_order(order)

    def execute_close_signal(self, stock_quotes: List[StockQuote]) -> None:
        """執行平倉邏輯：先判斷停損訊號，後判斷一般平倉"""

        # Step 1:find stocks with existing positions
        positions: List[StockQuote] = [
            sq for sq in stock_quotes if self.account.check_has_position(sq.stock_id)
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
            sq for sq in stock_quotes if self.account.check_has_position(sq.stock_id)
        ]

        # Step 4: Get close orders
        close_orders: List[StockOrder] = self.strategy.check_close_signal(
            remaining_positions
        )

        # Step 5: Execute close orders
        for order in close_orders:
            self.place_close_order(order)

    # === Order Placement ===
    def place_open_order(self, stock_order: StockOrder) -> Optional[StockTradeRecord]:
        """
        - Description: 開倉下單股票
        - Parameters:
            - stock: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """

        # Step 1: Calculate position value and open cost
        position_value: float = stock_order.price * stock_order.volume
        open_cost: float = StockUtils.calculate_transaction_commission(
            price=stock_order.price, volume=stock_order.volume
        )

        # Step 2: Create position
        position: Optional[StockTradeRecord] = None

        # Step 3: Execute open order & update account
        if stock_order.position_type == PositionType.LONG:
            if self.account.balance >= (position_value + open_cost):
                logger.info(f"* Place Open Order: {stock_order.stock_id}")

                position = StockTradeRecord(
                    id=self.account.trade_id_counter,
                    stock_id=stock_order.stock_id,
                    position_type=stock_order.position_type,
                    buy_date=stock_order.date,
                    buy_price=stock_order.price,
                    buy_volume=stock_order.volume,
                    commission=open_cost,
                    transaction_cost=open_cost,
                )

                self.account.trade_id_counter += 1
                self.account.balance -= position_value + open_cost
                self.account.positions.append(position)
                self.account.trade_records[position.id] = position

        return position

    def place_close_order(self, stock_order: StockOrder) -> Optional[StockTradeRecord]:
        """
        - Description: 下單平倉股票
        - Parameters:
            - stock_order: StockOrder
                目標股票的訂單資訊
        - Return:
            - position: StockTradeRecord
        """

        # Step 1: Calculate position value and close cost
        position_value: float = stock_order.price * stock_order.volume
        close_cost: float = StockUtils.calculate_transaction_commission(
            price=stock_order.price, volume=stock_order.volume
        )

        # Step 2: Find the first open position of the stock (FIFO)
        position: Optional[StockTradeRecord] = self.account.get_first_open_position(
            stock_order.stock_id
        )

        # Step 3: Execute close order & update account
        if position is not None and not position.is_closed:
            logger.info(f"* Place Close Order: {stock_order.stock_id}")

            if position.position_type == PositionType.LONG:
                position.is_closed = True
                position.sell_date = stock_order.date
                position.sell_price = stock_order.price
                position.sell_volume = stock_order.volume
                position.commission += close_cost
                position.tax = StockUtils.calculate_transaction_tax(
                    stock_order.price, stock_order.volume
                )
                position.transaction_cost = position.commission + position.tax
                position.realized_pnl = StockUtils.calculate_net_profit(
                    position.buy_price, position.sell_price, position.sell_volume
                )

                logger.info(f"Realized PnL: {position.realized_pnl}")

                position.roi = StockUtils.calculate_roi(
                    position.buy_price, position.sell_price, position.sell_volume
                )

                self.account.balance += position_value - close_cost
                self.account.realized_pnl += position.realized_pnl
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

        # Generate Backtest Report (Chart)
        reporter = StockBacktestReporter(self.strategy, self.strategy_result_dir)
        reporter.plot_balance_curve()
        # reporter.plot_equity_and_benchmark_curve()
        # reporter.plot_mdd()
