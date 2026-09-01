from typing import Dict, List

from core.models.base.account import BaseAccount
from core.models.futures.position import FuturesPosition
from core.utils import PositionType

"""FuturesAccount: 期貨帳戶（保證金佔用與口數曝險）"""


class FuturesAccount(BaseAccount):
    """
    期貨帳戶

    **與 `StockAccount` 的差異在資金佔用方式**：股票買進是把錢換成股票（部位價值
    離開餘額）；期貨開倉只凍結**保證金**，契約價值本身不動用資金。因此
    - `balance` 是**可動用餘額**（已扣除保證金與交易成本、已加計逐日結算損益）；
    - `margin_used` 是被部位佔用的保證金，平倉時全額釋回；
    - `equity` ＝ `balance` ＋ `margin_used`，才是帳戶總權益。

    逐日盯市的損益由 `FuturesPositionManager.settle_daily()` 直接進出 `balance`，
    不等到平倉才實現——這是期貨與股票在記帳上最根本的不同。
    """

    def __init__(self, init_capital: float = 0.0):
        super().__init__(init_capital=init_capital)

        # Margin
        self.margin_used: float = 0.0  # 未平倉部位佔用的原始保證金總額

    @property
    def equity(self) -> float:
        """帳戶總權益 ＝ 可動用餘額 ＋ 被佔用的保證金"""

        return self.balance + self.margin_used

    def get_open_lots(self, contract_id: str = None) -> Dict[str, int]:
        """
        - Description:
            取得未平倉口數；`contract_id` 為 None 時回傳所有契約

            方向以正負表示：多單為正、空單為負，同一契約的多空**相抵後**回傳
            （net position）。要看毛部位請直接走 `get_positions()`。
        - Parameters:
            - contract_id: str
                契約代號（`{product}{expiry}`）；None 表示全部
        - Return:
            - Dict[str, int]
                {契約代號: 淨口數}
        """

        lots: Dict[str, int] = {}
        positions: List[FuturesPosition] = [
            p
            for p in self.positions
            if not p.is_closed and (contract_id is None or p.symbol == contract_id)
        ]

        for position in positions:
            sign: int = 1 if position.position_type == PositionType.LONG else -1
            lots[position.symbol] = (
                lots.get(position.symbol, 0) + sign * position.volume
            )

        return lots

    def update_transaction_cost(self) -> None:
        """更新交易成本；期貨沒有持有期間的計提費用，故與基底相同"""

        super().update_transaction_cost()
