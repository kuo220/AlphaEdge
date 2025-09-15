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
from trader.managers.stock.position.position_manager import StockPositionManager
from trader.models import (
    StockAccount,
    StockOrder,
    StockPosition,
    StockQuote,
    StockTradeRecord,
    TickQuote,
)
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Action, PositionType, Scale, TimeUtils
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

        """ === Position Manager === """
        self.position_manager: StockPositionManager = StockPositionManager(
            self.account
        )  # 設置倉位管理器

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
        BACKTEST_LOGS_DIR_PATH.mkdir(parents=True, exist_ok=True)
        logger.add(f"{BACKTEST_LOGS_DIR_PATH}/{self.strategy.strategy_name}.log")

        # load backtest dataset
        self.load_datasets()

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
    def execute_open_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockPosition]:
        """若倉位數量未達到限制且有開倉訊號，則執行開倉"""

        # Get open orders
        open_orders: List[StockOrder] = self.strategy.check_open_signal(stock_quotes)

        # Execute open orders
        open_positions: List[StockPosition] = []
        for order in open_orders:
            open_position: Optional[StockPosition] = (
                self.position_manager.open_position(order)
            )
            if open_position:
                open_positions.append(open_position)
        return open_positions

    def execute_close_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockTradeRecord]:
        """執行平倉邏輯：先判斷停損訊號，後判斷一般平倉"""

        # Find stocks with existing positions
        positions: List[StockQuote] = [
            sq for sq in stock_quotes if self.account.check_has_position(sq.stock_id)
        ]

        if not positions:
            return

        # Get stop loss orders
        stop_loss_orders: List[StockOrder] = self.strategy.check_stop_loss_signal(
            positions
        )

        # Close records
        close_records: List[StockTradeRecord] = []

        # Execute stop loss orders
        for order in stop_loss_orders:
            close_positions: List[StockTradeRecord] = (
                self.position_manager.close_position(order)
            )
            close_records.extend(close_positions)

        # After executing stop loss, recheck the remaining positions
        remaining_positions: List[StockQuote] = [
            sq for sq in stock_quotes if self.account.check_has_position(sq.stock_id)
        ]

        # Get close orders
        close_orders: List[StockOrder] = self.strategy.check_close_signal(
            remaining_positions
        )

        # Execute close orders
        for order in close_orders:
            close_positions: List[StockTradeRecord] = (
                self.position_manager.close_position(order)
            )
            close_records.extend(close_positions)

        return close_records

    # === Report ===
    def generate_backtest_report(self) -> None:
        """生產回測報告"""

        # Generate Backtest Report (Chart)
        reporter: StockBacktestReporter = StockBacktestReporter(self.strategy, self.strategy_result_dir)
        df: pd.DataFrame = reporter.generate_trading_report()
        reporter.trading_report = df

        reporter.plot_balance_curve()
        reporter.plot_everyday_profit()
        # reporter.plot_equity_and_benchmark_curve()
        # reporter.plot_mdd()
