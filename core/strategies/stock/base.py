import datetime
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from core.api.financial_statement_api import FinancialStatementAPI
from core.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from core.api.stock_chip_api import StockChipAPI
from core.api.stock_price_api import StockPriceAPI
from core.api.stock_tick_api import StockTickAPI
from core.models import StockAccount, StockOrder, StockQuote
from core.utils import (
    Action,
    BarExecutionOrder,
    DayTradeUncoveredPolicy,
    MarginCallPolicy,
    Market,
    PositionType,
    Scale,
    ShortMethod,
)
from core.utils.cost_model import CostConfig, ShortConstraint


class BaseStockStrategy(ABC):
    """Stock Strategy Framework (Base Template)"""

    def __init__(self):
        """=== Account Setting ==="""
        self.account: StockAccount = None  # 虛擬帳戶資訊

        """ === Strategy Setting === """
        self.strategy_name: str = ""  # Strategy name
        self.market: str = Market.STOCK  # Stock or Futures
        self.position_type: str = PositionType.LONG  # 策略主要方向（推導預設值用）
        self.enable_intraday: bool = True  # Allow day trade or not
        self.init_capital: float = 0  # Initial capital
        self.max_holdings: Optional[int] = 0  # Maximum number of holdings allowed

        """
        === Short Setting ===

        方向的責任分工（見 backlog §4.4）：
        - position_type 只用來推導預設值，不參與記帳
        - allowed_directions 是訂單方向的白名單，None 時等同 {position_type}
        - 實際記帳與成本路徑一律看每一張 order 的 position_type
        """
        self.allowed_directions: Optional[Set[PositionType]] = None  # 允許的訂單方向
        self.short_method: ShortMethod = ShortMethod.MARGIN  # 放空管道
        self.cost_config: Optional[CostConfig] = None  # 成本參數（None 用預設）
        self.short_constraint: Optional[ShortConstraint] = None  # 放空可成交限制
        self.max_holding_days: Optional[int] = None  # 留倉放空的最長持有曆日數
        self.bar_execution_order: Optional[BarExecutionOrder] = (
            None  # 單根 K 棒內的執行順序（None 由引擎推導）
        )
        self.day_trade_uncovered_policy: DayTradeUncoveredPolicy = (
            DayTradeUncoveredPolicy.FORCE_COVER_AT_CLOSE  # 當沖日終未回補的處理
        )
        self.margin_call_policy: MarginCallPolicy = (
            MarginCallPolicy.FORCE_COVER  # 維持率追繳的處理
        )

        """ === Backtest Setting === """
        self.is_backtest: bool = True  # Whether it's used for backtest or not
        self.scale: str = Scale.DAY  # Backtest scale: Day/Tick/ALL
        self.start_date: datetime.date = (
            None  # Optional: if is_backtest == True, then set start date in backtest
        )
        self.end_date: datetime.date = (
            None  # Optional: if is_backtest == True, then set end date in backtest
        )

        """ === Datasets Setting=== """
        self.tick: Optional[StockTickAPI] = None  # Ticks data (Optional)
        self.price: Optional[StockPriceAPI] = None  # Day price data (Optional)
        self.chip: Optional[StockChipAPI] = None  # Chips data (Optional)
        self.mrr: Optional[MonthlyRevenueReportAPI] = (
            None  # Monthly Revenue Report data (Optional)
        )
        self.fs: Optional[FinancialStatementAPI] = (
            None  # Financial Statement data (Optional)
        )

    @abstractmethod
    def setup_account(self, account: StockAccount):
        """
        - Description:
            載入虛擬帳戶資訊
        """
        pass

    @abstractmethod
    def setup_apis(self):
        """
        - Description:
            載入資料 API
        """
        pass

    @abstractmethod
    def check_open_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """
        - Description:
            開倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
        - Return:
            - position: List[StockQuote]
                開倉訂單
        """
        pass

    @abstractmethod
    def check_close_signal(self, stock_quotes: List[StockQuote]) -> List[StockOrder]:
        """
        - Description:
            平倉策略（Long & Short） ，需要包含買賣的標的、價位和數量
        - Parameter:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
        - Return:
            - position: List[StockQuote]
                平倉訂單
        """
        pass

    @abstractmethod
    def check_stop_loss_signal(
        self, stock_quotes: List[StockQuote]
    ) -> List[StockOrder]:
        """
        - Description:
            設定停損機制
        - Parameter:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
        - Return:
            - position: List[StockOrder]
                停損（平倉）訂單
        """
        pass

    @abstractmethod
    def calculate_position_size(
        self, stock_quotes: List[StockQuote], action: Action
    ) -> List[StockOrder]:
        """
        - Description:
            計算下單股數，依據當前資金、價格、風控規則決定部位大小
        - Parameters:
            - account: StockAccount
                交易帳戶資訊
            - stock_quotes: List[StockQuote]
                目標股票的報價資訊
            - action: Action
                動作類型，例如 Action.OPEN 或 Action.CLOSE
        - Return:
            - List[StockOrder]
                建議下單的股數
        """
        pass
