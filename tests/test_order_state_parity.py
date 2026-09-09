import sys
from pathlib import Path
from typing import Dict

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.utils.constant import OrderState

"""
專案自訂的 `OrderState` 必須與 Shioaji 那份一致（健檢 F-011）

`core/utils/callback.py` 的 `order_cb(stat, msg)` 由 Shioaji 回呼，`stat` 是
`shioaji.constant.OrderState`；而函式裡拿來比較的是專案自己那份。兩者都是
`str` Enum，`==` 比的是字串值，**值一樣就成立、不一樣就永遠不成立**——
不成立時不會拋錯，只是實盤成交回報安靜地不發出通知。

舊版把兩個 `OrderState` 都 import（後者覆蓋前者，F811），
於是「用的是哪一份」連讀程式碼都看不出來。已刪掉被覆蓋的那行，
兩份是否同步改由本測試盯住。
"""


def test_order_state_matches_shioaji() -> None:
    """成員名稱與字串值都要與 Shioaji 那份逐一相同"""

    from shioaji.constant import OrderState as ShioajiOrderState

    ours: Dict[str, str] = {member.name: member.value for member in OrderState}
    theirs: Dict[str, str] = {member.name: member.value for member in ShioajiOrderState}

    assert ours == theirs


def test_order_state_compares_across_both_enums() -> None:
    """
    跨兩份 Enum 的 `==` 必須成立

    這是 `order_cb` 實際做的事：拿 Shioaji 傳進來的值比對專案自己的成員。
    任何一邊改成非 `str` 的 Enum，這個比較會安靜地變成永遠 False。
    """

    from shioaji.constant import OrderState as ShioajiOrderState

    assert ShioajiOrderState.StockDeal == OrderState.StockDeal
    assert ShioajiOrderState.FuturesDeal == OrderState.FuturesDeal
