from typing import Any, Dict

import shioaji as sj

from .constant import OrderState
from .notify import Notification


class Callback:
    """Order callback"""

    @staticmethod
    def order_callback(api: sj.Shioaji, token: str) -> None:
        """
        設置委託 or 成交回報的輸出格式

        Parameters
        - api: 永豐API
        - token: Line notify token
        """
        print("* Setting order callback...")

        # `stat` 實際收到的是 `shioaji.constant.OrderState`，這裡標的是專案自己那份。
        # 兩者是**值相同的 `str` Enum**，故 `==` 比得起來（比的是字串值）；
        # 由 `tests/test_order_state_parity.py` 盯住兩邊不會漂開。
        # 舊版兩個 `OrderState` 都 import（後者覆蓋前者，F811），
        # 讀的人無從得知實際用的是哪一個
        def order_cb(stat: OrderState, msg: Dict[str, Any]) -> None:
            if stat == OrderState.StockDeal:
                print(
                    f"【Order Deal】 Stock: {msg['code']} | Volume: {msg['quantity']} | Price: {msg['price']} | Action: {msg['action']}"
                )

                # Notify
                deal_info: Dict[str, Any] = {
                    "code": msg["code"],
                    "volume": msg["quantity"],
                    "price": msg["price"],
                    "action": msg["action"],
                }
                Notification.post_deal_notify(token, deal_info)

        api.set_order_callback(order_cb)

        print("* Setting order callback successfully!")
