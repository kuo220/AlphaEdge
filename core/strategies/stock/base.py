from abc import abstractmethod
from typing import List, Optional

from core.api.financial_statement_api import FinancialStatementAPI
from core.api.monthly_revenue_report_api import MonthlyRevenueReportAPI
from core.api.stock_chip_api import StockChipAPI
from core.api.stock_price_api import StockPriceAPI
from core.api.stock_tick_api import StockTickAPI
from core.models import StockAccount, StockOrder, StockQuote
from core.strategies.base import BaseStrategy
from core.utils import (
    Action,
    DayTradeUncoveredPolicy,
    MarginCallPolicy,
    Market,
    ShortMethod,
)
from core.utils.cost_model import CostConfig, ShortConstraint

"""BaseStockStrategy: 台股策略基底，補上信用交易設定與五個資料集"""


class BaseStockStrategy(BaseStrategy):
    """Stock Strategy Framework (Base Template)"""

    def __init__(self):
        super().__init__()

        """ === Strategy Setting === """
        self.market: str = Market.STOCK  # 市場別：台股

        """
        === Short Setting ===

        台股信用交易專屬；方向白名單與執行順序屬市場無關，已上移至 BaseStrategy。
        """
        self.short_method: ShortMethod = ShortMethod.MARGIN  # 放空管道
        self.cost_config: Optional[CostConfig] = None  # 成本參數（None 用預設）
        self.short_constraint: Optional[ShortConstraint] = None  # 放空可成交限制
        self.max_holding_days: Optional[int] = None  # 留倉放空的最長持有曆日數
        self.day_trade_uncovered_policy: DayTradeUncoveredPolicy = (
            DayTradeUncoveredPolicy.FORCE_COVER_AT_CLOSE  # 當沖日終未回補的處理
        )
        self.margin_call_policy: MarginCallPolicy = (
            MarginCallPolicy.FORCE_COVER  # 維持率追繳的處理
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
