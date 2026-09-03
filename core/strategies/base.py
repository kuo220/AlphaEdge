import datetime
from abc import ABC, abstractmethod
from typing import List, Optional, Set

from core.models import BaseAccount, BaseOrder, BaseQuote
from core.utils import BarExecutionOrder, InstrumentType, Market, PositionType, Scale

"""BaseStrategy: 市場與商品皆無關的策略骨架（market ＋ instrument_type 為 factory 的分派鍵）"""


class BaseStrategy(ABC):
    """Strategy Framework (Market/Instrument-agnostic Base Template)"""

    def __init__(self):
        """=== Account Setting ==="""
        self.account: Optional[BaseAccount] = None  # 虛擬帳戶資訊

        """ === Strategy Setting === """
        self.strategy_name: str = ""  # Strategy name
        # 市場（地區）與商品類別是兩條正交的軸，兩者的**組合**才是 factory 的分派鍵：
        # model 組合本來就是按組合實作的（`TwStockSpec` ＝ TW ＋ STOCK）。
        # 兩者皆由各市場的策略基底填入，策略本身不需設定。
        self.market: Optional[Market] = None  # 市場（地區）
        self.instrument_type: Optional[InstrumentType] = None  # 商品類別
        # 策略主要方向（推導預設值用）
        self.position_type: PositionType = PositionType.LONG
        # 策略是否為當沖：只是**推導預設值的輸入**，不是硬性開關。
        # 真正決定同一根 bar 能否開平同一標的的是 bar_execution_order（見下方區塊）
        self.enable_intraday: bool = True  # Allow day trade or not
        self.init_capital: float = 0  # Initial capital
        # 同時可持有的最大檔數；**預設 None ＝ 不限制**（健檢 F-076）。
        #
        # 舊版預設 0，而 `Backtester.check_max_holdings()` 只把 None 當成不限制
        # ——於是**忘記設定的新策略，每一張開倉單都被引擎剔除**，回測跑完是
        # 零筆交易、零錯誤訊息。寧可預設不限制（策略自己的 sizer 仍會把關），
        # 也不要用一個看起來像「還沒設定」的值去無聲地擋掉所有交易。
        self.max_holdings: Optional[int] = None

        """
        === Direction Setting ===

        方向的責任分工：
        - position_type 只用來推導預設值，不參與記帳
        - allowed_directions 是訂單方向的白名單，None 時等同 {position_type}
        - 實際記帳與成本路徑一律看每一張 order 的 position_type

        方向（LONG／SHORT）與商品類別（股票／期貨）是兩條獨立的軸，故本區塊與商品無關。

        執行順序的推導（`Backtester.get_execution_order()`，完整對照表在該處）：

        | position_type | enable_intraday | 推導出的預設 bar_execution_order |
        |---------------|-----------------|----------------------------------|
        | LONG          | 任意            | `CLOSE_THEN_OPEN`                |
        | SHORT         | True            | `OPEN_THEN_CLOSE`                |
        | SHORT         | False           | `CLOSE_THEN_OPEN`                |

        **推導出的只是預設建議，一旦策略在 `__init__` 填了 `bar_execution_order`，
        引擎一律以策略宣告為準。** 做多當沖要在同一根 bar 內開平同一標的，
        必須自己宣告 `OPEN_THEN_CLOSE`——`enable_intraday=True` 不會自動切換，
        因為它的預設值就是 True，既有做多策略沒有一支是刻意宣告當沖的，
        自動切換等於在無人宣告的情況下改掉所有做多策略的回測結果。
        """
        self.allowed_directions: Optional[Set[PositionType]] = None  # 允許的訂單方向
        self.bar_execution_order: Optional[BarExecutionOrder] = (
            None  # 單根 K 棒內的執行順序（None 由引擎推導，見上表；非 None 時一律以策略為準）
        )

        """ === Backtest Setting === """
        self.scale: str = Scale.DAY  # Backtest scale: DAY / TICK
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
