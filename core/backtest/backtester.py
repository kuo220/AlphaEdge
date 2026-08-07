import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple, Union

import numpy as np
import pandas as pd
from loguru import logger

from core.adapters import StockQuoteAdapter
from core.api.financial_statement_api import FinancialStatementAPI
from core.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from core.api.stock_chip_api import StockChipAPI
from core.api.stock_price_api import StockPriceAPI
from core.api.stock_tick_api import StockTickAPI
from core.backtest.analysis.analyzer import StockBacktestAnalyzer
from core.backtest.models.fill_model import BaseFillModel, TwStockFillModel
from core.backtest.models.instrument_spec import InstrumentSpec, TwStockSpec
from core.backtest.models.settlement_model import (
    BaseSettlementModel,
    TwStockSettlementModel,
)
from core.backtest.report.reporter import StockBacktestReporter
from core.config import BACKTEST_RESULT_DIR_PATH
from core.utils.log_manager import LogManager
from core.managers.stock.position.position_manager import StockPositionManager
from core.models import (
    StockAccount,
    StockOrder,
    StockPosition,
    StockQuote,
    StockTradeRecord,
    TickQuote,
)
from core.strategies.stock import BaseStockStrategy
from core.utils import (
    PRICE_LIMIT_RATIO,
    Action,
    BarExecutionOrder,
    DayTradeUncoveredPolicy,
    MarginCallPolicy,
    PositionType,
    Scale,
    ShortMethod,
    TimeUtils,
)
from core.utils.cost_model import CostConfig, StockCostModel
from core.utils.instrument import StockUtils
from core.utils.market_calendar import MarketCalendar

"""Backtesting engine that simulates trading based on strategy signals"""


class Backtester:
    """Backtest Framework: Tick and Daily price intervals"""

    # === Init & Data Loading ===
    def __init__(self, strategy: BaseStockStrategy):
        self.strategy: BaseStockStrategy = strategy  # 要回測的策略
        self.account: StockAccount = StockAccount(
            self.strategy.init_capital
        )  # 虛擬帳戶資訊
        self.strategy.setup_account(self.account)  # 設置虛擬帳戶資訊

        # 成本模型：由策略宣告的放空管道與是否當沖決定參數組合
        self.cost_model: StockCostModel = StockCostModel(self.build_cost_config())

        # 倉位管理器
        self.position_manager: StockPositionManager = StockPositionManager(
            self.account, self.cost_model
        )  # 設置倉位管理器

        # 資料集
        self.tick: Optional[StockTickAPI] = None  # Ticks data
        self.chip: Optional[StockChipAPI] = None  # Chips data
        self.price: Optional[StockPriceAPI] = None  # Price data
        self.mrr: Optional[MonthlyRevenueReportAPI] = (
            None  # Monthly Revenue Report data
        )
        self.fs: Optional[FinancialStatementAPI] = None  # Financial Statement data

        # 回測參數
        self.scale: str = self.strategy.scale  # 回測 KBar 級別
        self.max_holdings: Optional[int] = self.strategy.max_holdings  # 最大持倉檔數
        self.start_date: datetime.date = self.strategy.start_date  # 回測起始日
        self.cur_date: datetime.date = self.strategy.start_date  # 回測當前日
        self.end_date: datetime.date = self.strategy.end_date  # 回測結束日

        # 回測結果輸出目錄
        self.strategy_result_dir: Optional[Path] = None  # 策略回測結果資料夾

        # 含未實現損益的每日權益序列（只認已實現損益會低估留倉放空的 MDD）
        self.daily_equity: List[Dict[str, Any]] = []

        # 事件統計：放空策略的尾部風險不能被平均掉，需單獨計數
        self.event_counts: Dict[str, int] = {
            "rejected_direction": 0,  # 方向不合法被剔除的訂單
            "rejected_fill_price": 0,  # 成交價不合理被拒的訂單
            "forced_cover_day_trade": 0,  # 當沖日終強制回補
            "forced_cover_margin_call": 0,  # 維持率追繳強制回補
            "forced_cover_max_holding": 0,  # 超過最長持有天數強制回補
            "limit_up_cover_failed": 0,  # 漲停鎖死無法回補
        }

        # 商品規格與成交價模型（Phase3-1 之後改由 factory 注入）
        self.instrument: InstrumentSpec = TwStockSpec()
        self.fill_model: BaseFillModel = TwStockFillModel(
            instrument=self.instrument, event_counts=self.event_counts
        )

        # 結算模型：一根 bar 收盤後的市場強制動作（Phase3-1 之後改由 factory 注入）
        self.settlement: BaseSettlementModel = TwStockSettlementModel(
            position_manager=self.position_manager,
            cost_model=self.cost_model,
            prev_close=self.fill_model.prev_close,
            instrument=self.instrument,
            day_trade_uncovered_policy=self.strategy.day_trade_uncovered_policy,
            margin_call_policy=self.strategy.margin_call_policy,
            max_holding_days=self.strategy.max_holding_days,
        )

        self.setup()

    @property
    def intraday_range(self) -> Dict[str, Tuple[float, float]]:
        """Tick 級別的當日累計高低點；狀態由 FillModel 持有"""

        return self.fill_model.intraday_range

    @property
    def prev_close(self) -> Dict[str, float]:
        """前一交易日收盤價；狀態由 FillModel 持有"""

        return self.fill_model.prev_close

    def setup(self) -> None:
        """Set Up the Config of Backtester"""

        # 確保每個 strategy 有獨立的結果資料夾
        self.strategy_result_dir: Path = (
            Path(BACKTEST_RESULT_DIR_PATH) / self.strategy.strategy_name
        )
        self.strategy_result_dir.mkdir(parents=True, exist_ok=True)

        # Set Log File Path
        LogManager.setup_backtest_logger(self.strategy.strategy_name)

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

    # === Direction & Cost Setting ===
    def build_cost_config(self) -> CostConfig:
        """
        - Description:
            依策略宣告推導成本設定：放空且允許當沖時一律走現股當沖沖賣
        - Return:
            - config: CostConfig
                本次回測使用的成本參數
        """

        is_day_trade: bool = (
            self.strategy.position_type == PositionType.SHORT
            and self.strategy.enable_intraday
        )
        short_method: ShortMethod = (
            ShortMethod.DAY_TRADE if is_day_trade else self.strategy.short_method
        )

        config: CostConfig = self.strategy.cost_config or CostConfig.default(
            short_method, is_day_trade
        )

        if self.strategy.short_constraint is not None:
            config.short_constraint = self.strategy.short_constraint

        return config

    def get_allowed_directions(self) -> Set[PositionType]:
        """取得允許的訂單方向白名單；策略未指定時等同其宣告方向"""

        return self.strategy.allowed_directions or {self.strategy.position_type}

    def get_execution_order(self) -> BarExecutionOrder:
        """
        - Description:
            決定單根 K 棒內的執行順序；策略顯式指定時一律以策略為準

            放空當沖必須「先開後平」才可能同日結清，其餘情境維持既有的「先平後開」
        - Return:
            - order: BarExecutionOrder
        """

        if self.strategy.bar_execution_order is not None:
            return self.strategy.bar_execution_order

        if (
            self.strategy.position_type == PositionType.SHORT
            and self.strategy.enable_intraday
        ):
            return BarExecutionOrder.OPEN_THEN_CLOSE

        return BarExecutionOrder.CLOSE_THEN_OPEN

    @staticmethod
    def resolve_open_action(position_type: PositionType) -> Action:
        """開倉動作：LONG 為買進、SHORT 為賣出（依訂單方向，不看策略）"""

        return Action.BUY if position_type == PositionType.LONG else Action.SELL

    @staticmethod
    def resolve_close_action(position_type: PositionType) -> Action:
        """平倉動作：LONG 為賣出、SHORT 為買進回補"""

        return Action.SELL if position_type == PositionType.LONG else Action.BUY

    # === Order Validation ===
    def validate_orders(
        self, orders: List[StockOrder], stage: str
    ) -> List[StockOrder]:
        """
        - Description:
            檢查訂單方向是否合法，不合法者剔除並記錄，禁止靜默丟棄
        - Parameters:
            - orders: List[StockOrder]
                策略回傳的訂單
            - stage: str
                "open" 或 "close"，決定期望的動作
        - Return:
            - valid_orders: List[StockOrder]
                通過檢查的訂單
        """

        allowed: Set[PositionType] = self.get_allowed_directions()
        valid_orders: List[StockOrder] = []

        for order in orders:
            if order.position_type not in allowed:
                logger.warning(
                    f"[Validate Order] {order.stock_id} 方向 {order.position_type} "
                    f"不在策略允許的 {allowed} 內，已剔除"
                )
                self.event_counts["rejected_direction"] += 1
                continue

            expected_action: Action = (
                self.resolve_open_action(order.position_type)
                if stage == "open"
                else self.resolve_close_action(order.position_type)
            )
            if order.action != expected_action:
                logger.warning(
                    f"[Validate Order] {order.stock_id} {stage} 動作應為 {expected_action}，"
                    f"實際為 {order.action}，已剔除"
                )
                self.event_counts["rejected_direction"] += 1
                continue

            valid_orders.append(order)

        return valid_orders

    def enrich_orders(self, orders: List[StockOrder]) -> List[StockOrder]:
        """補上市場專屬的訂單欄位；規則由 CostModel 實作（見 backlog Phase2-4）"""

        return self.cost_model.enrich_orders(orders)

    def validate_fill_price(self, order: StockOrder, quote: StockQuote) -> bool:
        """成交價合理性檢查；規則由 FillModel 實作（見 backlog Phase2-2）"""

        return self.fill_model.validate(order, quote)

    def get_price_range(
        self, quote: StockQuote
    ) -> Tuple[Optional[float], Optional[float]]:
        """取得該報價可成交的價格區間；規則由 FillModel 實作"""

        return self.fill_model.get_price_range(quote)

    def update_intraday_range(self, stock_quotes: List[StockQuote]) -> None:
        """累計 Tick 級別的當日高低點；狀態由 FillModel 持有"""

        self.fill_model.update_intraday_range(stock_quotes)

    def update_prev_close(self, stock_quotes: List[StockQuote]) -> None:
        """收盤後記錄當日收盤價；狀態由 FillModel 持有"""

        self.fill_model.on_bar_close(stock_quotes)

    # === Main Backtest Loop ===
    def run(self) -> None:
        """Execute Backtest"""

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

        logger.info(f"""
            1. Initial Capital: {int(self.account.init_capital)}
            2. Balance: {int(self.account.balance)}
            3. Total realized pnl: {int(self.account.realized_pnl)}
            4. ROI: {round(self.account.roi, 2)}%
            """)

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

        self.fill_model.on_bar_open(stock_quotes)
        self.execute_bar(date, stock_quotes)

    def run_day_backtest(self, date: datetime.date) -> None:
        """日 K 級別的回測架構"""

        # Stock Quotes
        stock_quotes: List[StockQuote] = StockQuoteAdapter.convert_to_day_quotes(
            self.price, date
        )

        if not stock_quotes:
            return

        self.execute_bar(date, stock_quotes)

    def run_mix_backtest(self, date: datetime.date) -> None:
        """Tick 與日 K 級別的回測架構"""
        pass

    def execute_bar(
        self, date: datetime.date, stock_quotes: List[StockQuote]
    ) -> None:
        """
        - Description:
            單一時間切片的完整流程：依設定的執行順序開平倉，再做收盤後的部位檢查
        - Parameters:
            - date: datetime.date
                當前交易日
            - stock_quotes: List[StockQuote]
                當日報價
        """

        if self.get_execution_order() == BarExecutionOrder.OPEN_THEN_CLOSE:
            self.execute_open_signal(stock_quotes)
            self.execute_close_signal(stock_quotes)
        else:
            self.execute_close_signal(stock_quotes)
            self.execute_open_signal(stock_quotes)

        # 一根 bar 收盤後由市場規則強制執行的動作
        # 台股：當沖強制回補 ＋ 借券費計提 ＋ 維持率追繳
        # 期貨：每日結算 ＋ 保證金追繳 ＋ 到期換月
        self.settlement.on_bar_close(
            date, stock_quotes, self.account, self.event_counts
        )

        self.snapshot_daily_equity(date, stock_quotes)
        self.update_prev_close(stock_quotes)

    # === Signal Execution ===
    def execute_open_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockPosition]:
        """若倉位數量未達到限制且有開倉訊號，則執行開倉"""

        # Get open orders
        open_orders: List[StockOrder] = self.strategy.check_open_signal(stock_quotes)

        # 方向驗證 → 補值 → 成交價驗證，最後才進倉位管理器
        open_orders = self.enrich_orders(self.validate_orders(open_orders, "open"))
        quote_map: Dict[str, StockQuote] = {sq.stock_id: sq for sq in stock_quotes}

        # Execute open orders
        open_positions: List[StockPosition] = []
        for order in open_orders:
            quote: Optional[StockQuote] = quote_map.get(order.stock_id)
            if quote and not self.validate_fill_price(order, quote):
                continue

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
        stop_loss_orders = self.validate_orders(stop_loss_orders, "close")

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
        close_orders = self.validate_orders(close_orders, "close")

        # Execute close orders
        for order in close_orders:
            close_positions: List[StockTradeRecord] = (
                self.position_manager.close_position(order)
            )
            close_records.extend(close_positions)

        return close_records

    # === Daily Equity ===
    def snapshot_daily_equity(
        self, date: datetime.date, stock_quotes: List[StockQuote]
    ) -> float:
        """
        - Description:
            記錄含未實現損益的每日權益，並更新各部位的未實現損益

            只認已實現損益的權益曲線會把「持倉期間的逆勢」完全抹平，
            而那正是放空最大的風險來源（見 backlog §7.7 註）。
        - Parameters:
            - date: datetime.date
                當前交易日
            - stock_quotes: List[StockQuote]
                當日報價
        - Return:
            - equity: float
                當日權益（現金 + 部位價值）
        """

        quote_map: Dict[str, StockQuote] = {sq.stock_id: sq for sq in stock_quotes}
        position_value: float = 0.0

        for position in self.account.get_positions():
            price: float = self.settlement.get_mark_price(position, quote_map)
            shares: int = StockUtils.convert_lot_to_share(position.volume)

            if position.position_type == PositionType.SHORT:
                # 開倉時只扣了保證金與成本，賣出價款留作擔保品
                position.unrealized_pnl = round((position.price - price) * shares, 2)
                position_value += position.margin + position.unrealized_pnl
            else:
                position.unrealized_pnl = round((price - position.price) * shares, 2)
                position_value += price * shares

            cost_basis: float = position.price * shares
            position.unrealized_roi = (
                round(position.unrealized_pnl / cost_basis * 100, 2)
                if cost_basis
                else 0.0
            )

        equity: float = round(self.account.balance + position_value, 2)
        self.daily_equity.append({"Date": date, "Equity": equity})
        return equity

    # === Report ===
    def generate_backtest_report(self) -> None:
        """Generate backtest report"""

        # Generate Backtest Report (Chart)
        reporter: StockBacktestReporter = StockBacktestReporter(
            self.strategy, self.strategy_result_dir
        )
        reporter.trading_report = reporter.generate_trading_report()

        # 多空分開統計與事件計數（放空的尾部風險不可被平均掉）
        reporter.generate_direction_summary()
        reporter.generate_event_report(self.event_counts)

        if self.daily_equity:
            reporter.save_report(
                pd.DataFrame(self.daily_equity),
                f"{self.strategy.strategy_name}_daily_equity.csv",
            )

        reporter.plot_balance_curve()
        reporter.plot_balance_and_benchmark_curve()
        reporter.plot_balance_mdd()
        reporter.plot_everyday_profit()
