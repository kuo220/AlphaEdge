import datetime
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from core.models import BaseAccount, BaseOrder, BaseQuote
from core.utils import BarExecutionOrder, PositionType, Scale

"""BaseStrategy: 市場無關的策略骨架（market 欄位為 factory 的分派鍵）"""


class BaseStrategy(ABC):
    """Strategy Framework (Market-agnostic Base Template)"""

    def __init__(self):
        """=== Account Setting ==="""
        self.account: Optional[BaseAccount] = None  # 虛擬帳戶資訊

        """ === Strategy Setting === """
        self.strategy_name: str = ""  # Strategy name
        self.market: Optional[str] = None  # 市場別；由各市場的策略基底填入，是 factory 的分派鍵
        self.position_type: str = PositionType.LONG  # 策略主要方向（推導預設值用）
        self.enable_intraday: bool = True  # Allow day trade or not
        self.init_capital: float = 0  # Initial capital
        self.max_holdings: Optional[int] = 0  # Maximum number of holdings allowed

        """
        === Direction Setting ===

        方向的責任分工（見 backlog §4.4）：
        - position_type 只用來推導預設值，不參與記帳
        - allowed_directions 是訂單方向的白名單，None 時等同 {position_type}
        - 實際記帳與成本路徑一律看每一張 order 的 position_type

        方向（LONG／SHORT）與市場（股票／期貨）是兩條獨立的軸，故本區塊屬市場無關。
        """
        self.allowed_directions: Optional[Set[PositionType]] = None  # 允許的訂單方向
        self.bar_execution_order: Optional[BarExecutionOrder] = (
            None  # 單根 K 棒內的執行順序（None 由引擎推導）
        )

        """ === Backtest Setting === """
        self.scale: str = Scale.DAY  # Backtest scale: Day/Tick/ALL
        self.start_date: datetime.date = None  # Optional: 回測起始日
        self.end_date: datetime.date = None  # Optional: 回測結束日

    @abstractmethod
    def setup_account(self, account: BaseAccount) -> None:
        """
        - Description:
            載入虛擬帳戶資訊
        """
        pass

    @abstractmethod
    def check_open_signal(self, quotes: List[BaseQuote]) -> List[BaseOrder]:
        """
        - Description:
            開倉策略（Long & Short），需要包含買賣的標的、價位和數量
        - Parameter:
            - quotes: List[BaseQuote]
                目標商品的報價資訊
        - Return:
            - List[BaseOrder]
                開倉訂單
        """
        pass

    @abstractmethod
    def check_close_signal(self, quotes: List[BaseQuote]) -> List[BaseOrder]:
        """
        - Description:
            平倉策略（Long & Short），需要包含買賣的標的、價位和數量
        - Parameter:
            - quotes: List[BaseQuote]
                目標商品的報價資訊
        - Return:
            - List[BaseOrder]
                平倉訂單
        """
        pass

    @abstractmethod
    def check_stop_loss_signal(self, quotes: List[BaseQuote]) -> List[BaseOrder]:
        """
        - Description:
            設定停損機制
        - Parameter:
            - quotes: List[BaseQuote]
                目標商品的報價資訊
        - Return:
            - List[BaseOrder]
                停損（平倉）訂單
        """
        pass
