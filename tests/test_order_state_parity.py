from enum import Enum
from pathlib import Path
from typing import Dict, Type

import pytest

from core.utils.constant import OrderState

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]

"""
專案自訂的 `OrderState` 必須與 Shioaji 那份一致

`core/utils/callback.py` 的 `order_cb(stat, msg)` 由 Shioaji 回呼，`stat` 是
`shioaji.constant.OrderState`；而函式裡拿來比較的是專案自己那份。兩者都是
`str` Enum，`==` 比的是字串值，**值一樣就成立、不一樣就永遠不成立**——
不成立時不會拋錯，只是實盤成交回報安靜地不發出通知。

舊版把兩個 `OrderState` 都 import（後者覆蓋前者），
於是「用的是哪一份」連讀程式碼都看不出來。已刪掉被覆蓋的那行，
兩份是否同步改由本測試盯住。

**本檔量的是 `requirements.txt` 鎖定的 shioaji 版本**（CI 也裝同一份）。
shioaji 1.7 起 `OrderState` 改由原生模組提供、不再是 Python Enum——升版時本檔會紅，
那是在提醒 `order_cb` 的比較前提變了，不是測試寫錯。
"""


def _load_shioaji_order_state() -> Type[Enum]:
    """
    - Description:
        取得 Shioaji 的 `OrderState`，並確認它仍是 Python Enum

        不先檢查的話，升版後會在迭代時丟出 `TypeError: 'type' object is not iterable`，
        完全看不出是 shioaji 換了實作。
    - Return:
        - Type[Enum]
            Shioaji 的 `OrderState`
    """

    from shioaji.constant import OrderState as ShioajiOrderState

    if not (
        isinstance(ShioajiOrderState, type) and issubclass(ShioajiOrderState, Enum)
    ):
        import shioaji

        pytest.fail(
            f"shioaji {getattr(shioaji, '__version__', '?')} 的 OrderState 已不是 "
            "Python Enum。`core/utils/callback.py` 的 `order_cb` 以 `==` 比對字串值的"
            "前提需要重新確認；不要只改這條測試讓它通過。"
        )
    return ShioajiOrderState


def test_order_state_matches_shioaji() -> None:
    """成員名稱與字串值都要與 Shioaji 那份逐一相同"""

    shioaji_order_state: Type[Enum] = _load_shioaji_order_state()

    ours: Dict[str, str] = {member.name: member.value for member in OrderState}
    theirs: Dict[str, str] = {
        member.name: member.value for member in shioaji_order_state
    }

    assert ours == theirs


def test_order_state_compares_across_both_enums() -> None:
    """
    跨兩份 Enum 的 `==` 必須成立

    這是 `order_cb` 實際做的事：拿 Shioaji 傳進來的值比對專案自己的成員。
    任何一邊改成非 `str` 的 Enum，這個比較會安靜地變成永遠 False。
    """

    shioaji_order_state: Type[Enum] = _load_shioaji_order_state()

    assert shioaji_order_state.StockDeal == OrderState.StockDeal
    assert shioaji_order_state.FuturesDeal == OrderState.FuturesDeal
