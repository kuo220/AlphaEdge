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

        # Tick 級別的當日累計高低點（TickQuote 沒有 OHLC，成交價驗證需自行維護）
        self.intraday_range: Dict[str, Tuple[float, float]] = {}

        # 前一交易日收盤價，作為漲跌停判定基準
        self.prev_close: Dict[str, float] = {}

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

        self.setup()

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
        """依成本設定補上放空管道與當沖旗標，策略不需自行填寫（見 backlog §4.6）"""

        for order in orders:
            if order.position_type != PositionType.SHORT:
                continue

            if order.short_method is None:
                order.short_method = self.cost_model.config.short_method
            if not order.is_day_trade:
                order.is_day_trade = self.cost_model.config.is_day_trade

        return orders

    def validate_fill_price(self, order: StockOrder, quote: StockQuote) -> bool:
        """
        - Description:
            成交價合理性檢查（前視偏誤與不可能成交的擋板）
        - Parameters:
            - order: StockOrder
                待驗證的訂單
            - quote: StockQuote
                同一標的的當日報價
        - Return:
            - is_valid: bool
                False 時呼叫端應拒單
        - Notes:
            - DAY 級別以當日 high/low 為界；TICK 級別以當日「已發生」的累計高低點為界
            - 漲跌停以前一交易日收盤為基準；尚未取得前收時跳過該項檢查
            - 檔位未對齊僅記錄警告，不拒單（避免既有資料的價格精度問題擋掉正常回測）
        """

        low, high = self.get_price_range(quote)
        if low is not None and high is not None and not (low <= order.price <= high):
            logger.warning(
                f"[Validate Fill] {order.stock_id} 成交價 {order.price} 超出當日區間 "
                f"[{low}, {high}]，拒單"
            )
            self.event_counts["rejected_fill_price"] += 1
            return False

        prev_close: Optional[float] = self.prev_close.get(order.stock_id)
        if prev_close:
            limit_up: float = StockUtils.round_to_tick(
                prev_close * (1 + PRICE_LIMIT_RATIO), "down"
            )
            limit_down: float = StockUtils.round_to_tick(
                prev_close * (1 - PRICE_LIMIT_RATIO), "up"
            )
            if not (limit_down <= order.price <= limit_up):
                logger.warning(
                    f"[Validate Fill] {order.stock_id} 成交價 {order.price} 超出漲跌停 "
                    f"[{limit_down}, {limit_up}]，拒單"
                )
                self.event_counts["rejected_fill_price"] += 1
                return False

        if StockUtils.round_to_tick(order.price, "nearest") != order.price:
            logger.warning(
                f"[Validate Fill] {order.stock_id} 成交價 {order.price} 未對齊檔位"
            )

        return True

    def get_price_range(
        self, quote: StockQuote
    ) -> Tuple[Optional[float], Optional[float]]:
        """取得該報價可成交的價格區間：日 K 用 OHLC，Tick 用當日累計高低點"""

        if quote.scale == Scale.TICK:
            return self.intraday_range.get(quote.stock_id, (None, None))

        if quote.high and quote.low:
            return (quote.low, quote.high)

        return (None, None)

    def update_intraday_range(self, stock_quotes: List[StockQuote]) -> None:
        """更新 Tick 級別的當日累計高低點（只納入已發生的報價，本身即防前視）"""

        for quote in stock_quotes:
            price: float = quote.cur_price or quote.close
            if not price:
                continue

            low, high = self.intraday_range.get(quote.stock_id, (price, price))
            self.intraday_range[quote.stock_id] = (min(low, price), max(high, price))

    def update_prev_close(self, stock_quotes: List[StockQuote]) -> None:
        """收盤後記錄當日收盤價，作為次一交易日的漲跌停基準"""

        for quote in stock_quotes:
            close: float = quote.close or quote.cur_price
            if close:
                self.prev_close[quote.stock_id] = close

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

        self.intraday_range = {}
        self.update_intraday_range(stock_quotes)
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

        # 當沖：日終仍未回補的放空部位
        self.enforce_day_trade_cover(date, stock_quotes)

        # 留倉：借券費計提與維持率／強制回補檢查
        self.execute_daily_position_check(date, stock_quotes)

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

    # === Daily Position Check ===
    def enforce_day_trade_cover(
        self, date: datetime.date, stock_quotes: List[StockQuote]
    ) -> None:
        """
        - Description:
            當沖放空於日終仍未回補時的處理（見 backlog §7.1）

            現行引擎不會自己發現這件事，若放著不管，回測會出現實務上不存在的
            「當沖單留倉」；因此一律依 day_trade_uncovered_policy 明確處理並計數。
        - Parameters:
            - date: datetime.date
                當前交易日
            - stock_quotes: List[StockQuote]
                當日報價
        """

        quote_map: Dict[str, StockQuote] = {sq.stock_id: sq for sq in stock_quotes}
        policy: DayTradeUncoveredPolicy = self.strategy.day_trade_uncovered_policy

        for position in self.account.get_positions(position_type=PositionType.SHORT):
            if not position.is_day_trade:
                continue

            quote: Optional[StockQuote] = quote_map.get(position.stock_id)
            if quote is None:
                logger.warning(
                    f"[Day Trade Cover] {position.stock_id} 當日無報價，無法強制回補"
                )
                continue

            # 漲停鎖死無法回補：轉為融券留倉，並單獨計數（放空最致命的尾部風險）
            if self.check_limit_up_locked(quote):
                logger.warning(
                    f"[Day Trade Cover] {position.stock_id} 全日鎖漲停無法回補，轉為融券留倉"
                )
                self.event_counts["limit_up_cover_failed"] += 1
                self.convert_to_margin_position(position)
                continue

            if policy == DayTradeUncoveredPolicy.RAISE:
                raise ValueError(
                    f"[Day Trade Cover] {position.stock_id} 當沖放空於 {date} 日終未回補"
                )

            if policy == DayTradeUncoveredPolicy.CONVERT_TO_MARGIN:
                logger.warning(
                    f"[Day Trade Cover] {position.stock_id} 未回補，依政策轉為融券留倉"
                )
                self.convert_to_margin_position(position)
                continue

            logger.warning(
                f"[Day Trade Cover] {position.stock_id} 未回補，以收盤價 {quote.close} 強制回補"
            )
            self.event_counts["forced_cover_day_trade"] += 1
            self.force_cover_position(position, date, quote.close)

    def check_limit_up_locked(self, quote: StockQuote) -> bool:
        """判定是否全日鎖漲停（開高低收皆等於漲停價），此時放空無法回補"""

        prev_close: Optional[float] = self.prev_close.get(quote.stock_id)
        if not prev_close:
            return False

        limit_up: float = StockUtils.round_to_tick(
            prev_close * (1 + PRICE_LIMIT_RATIO), "down"
        )
        return (
            quote.close == limit_up
            and quote.high == limit_up
            and quote.low == limit_up
        )

    def convert_to_margin_position(self, position: StockPosition) -> None:
        """將無法當日回補的當沖空單轉為融券留倉：補收保證金與融券手續費"""

        margin: int = self.cost_model.margin_required(
            price=position.price,
            volume=position.volume,
            short_method=ShortMethod.MARGIN,
        )
        borrow_fee: int = self.cost_model.borrow_fee(
            price=position.price,
            volume=position.volume,
            short_method=ShortMethod.MARGIN,
        )

        position.is_day_trade = False
        position.short_method = ShortMethod.MARGIN
        position.margin += margin
        position.borrow_fee += borrow_fee
        position.transaction_cost += borrow_fee

        self.account.balance -= margin + borrow_fee
        self.account.margin_used += margin

    def force_cover_position(
        self,
        position: StockPosition,
        date: datetime.date,
        price: float,
    ) -> List[StockTradeRecord]:
        """以指定價格強制回補放空部位（當沖日終、維持率追繳、超過持有天數共用）"""

        order: StockOrder = StockOrder(
            stock_id=position.stock_id,
            date=date,
            action=Action.BUY,
            position_type=PositionType.SHORT,
            price=price,
            volume=position.volume,
            short_method=position.short_method,
            is_day_trade=position.is_day_trade,
        )
        return self.position_manager.close_position(order)

    def execute_daily_position_check(
        self, date: datetime.date, stock_quotes: List[StockQuote]
    ) -> None:
        """
        - Description:
            每日收盤後對未平倉放空部位的檢查（做多部位直接略過）
        - Parameters:
            - date: datetime.date
                當前交易日
            - stock_quotes: List[StockQuote]
                當日報價；停牌無報價時沿用前一交易日收盤價
        """

        short_positions: List[StockPosition] = self.account.get_positions(
            position_type=PositionType.SHORT
        )
        if not short_positions:
            return

        quote_map: Dict[str, StockQuote] = {sq.stock_id: sq for sq in stock_quotes}

        self.accrue_holding_cost(date, quote_map)
        self.check_margin_call(date, quote_map)

    def accrue_holding_cost(
        self, date: datetime.date, quote_map: Dict[str, StockQuote]
    ) -> None:
        """
        - Description:
            逐日計提持有成本並更新持有天數

            只有 SBL 借券費在此逐日累加；MARGIN 的融券手續費在開倉時一次收取、
            融券利息於平倉時依日期差一次計算（見 backlog §4.3 計算時點表），
            在此重複計算會造成雙重計費。
        """

        for position in self.account.get_positions(position_type=PositionType.SHORT):
            position.holding_days += 1

            if position.short_method != ShortMethod.SBL:
                continue

            price: float = self.get_mark_price(position, quote_map)
            position.accrued_borrow_fee += self.cost_model.borrow_fee(
                price=price,
                volume=position.volume,
                holding_days=1,
                short_method=ShortMethod.SBL,
            )

    def check_margin_call(
        self, date: datetime.date, quote_map: Dict[str, StockQuote]
    ) -> None:
        """
        - Description:
            維持率追繳與強制回補檢查

            現行引擎沒有跨日的委託佇列，無法模擬「次一交易日開盤成交」，
            因此一律以觸發當日收盤價立即回補（見 backlog §7.2）。
        """

        for position in list(
            self.account.get_positions(position_type=PositionType.SHORT)
        ):
            price: float = self.get_mark_price(position, quote_map)

            # 超過最長持有天數：強制回補
            if (
                self.strategy.max_holding_days is not None
                and position.holding_days >= self.strategy.max_holding_days
            ):
                logger.warning(
                    f"[Force Cover] {position.stock_id} 持有 {position.holding_days} 天"
                    f"已達上限，以 {price} 強制回補"
                )
                self.event_counts["forced_cover_max_holding"] += 1
                self.force_cover_position(position, date, price)
                continue

            # 停券強制回補日
            force_cover_dates: List[datetime.date] = (
                self.cost_model.config.short_constraint.get_force_cover_dates(
                    position.stock_id
                )
            )
            if date in force_cover_dates:
                logger.warning(
                    f"[Force Cover] {position.stock_id} 於 {date} 停券，以 {price} 強制回補"
                )
                self.event_counts["forced_cover_max_holding"] += 1
                self.force_cover_position(position, date, price)
                continue

            # 維持率追繳
            if position.short_method != ShortMethod.MARGIN:
                continue

            if not self.cost_model.check_margin_call(
                proceeds=position.short_proceeds,
                margin=position.margin,
                cur_price=price,
                volume=position.volume,
            ):
                continue

            if self.strategy.margin_call_policy == MarginCallPolicy.WARN_ONLY:
                logger.warning(
                    f"[Margin Call] {position.stock_id} 維持率已低於門檻（僅記錄不回補）"
                )
                continue

            logger.warning(
                f"[Margin Call] {position.stock_id} 維持率不足，以 {price} 強制回補（斷頭）"
            )
            self.event_counts["forced_cover_margin_call"] += 1
            self.force_cover_position(position, date, price)

    def get_mark_price(
        self, position: StockPosition, quote_map: Dict[str, StockQuote]
    ) -> float:
        """取得盯市價格：優先用當日收盤，停牌時沿用前收，再無資料則退回開倉價"""

        quote: Optional[StockQuote] = quote_map.get(position.stock_id)
        if quote is not None and (quote.close or quote.cur_price):
            return quote.close or quote.cur_price

        logger.warning(
            f"[Mark Price] {position.stock_id} 當日無報價，沿用前一交易日收盤價盯市"
        )
        return self.prev_close.get(position.stock_id, position.price)

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
            price: float = self.get_mark_price(position, quote_map)
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
