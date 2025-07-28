import pandas as pd
import requests
import shioaji as sj
from typing import Dict, Any

from .account import ShioajiAccount
from .constant import Action, StockPriceType


class Notification:
    """執行 Line 通知"""

    @staticmethod
    def post_line_notify(token: str, msg: str) -> None:
        """Line notify"""

        url: str = "https://notify-api.line.me/api/notify"
        headers: Dict[str, str] = {"Authorization": "Bearer " + token}
        data: Dict[str, str] = {"message": msg}
        requests.post(url, headers=headers, data=data)

    @staticmethod
    def post_order_notify(token: str, order: Dict[str, Any]) -> None:
        """
        買or賣下單委託通知
        order 格式
        order = {
            'code': '2330',
            'volume': 3,
            'price': 0,
            'price_change': 5%,
            'action': Action.BUY,
            'price_type': StockPriceType.MKT,
            'order_type': OrderType.IOC,
            'order_lot': StockOrderLot.Common,
        }
        """

        msg: str = "\n"
        msg += f"【{order['action']} Order Submit】\n"
        msg += f"Stock ID: {order['code']}\n"
        msg += f"Volume: {order['volume']}\n"
        msg += f"Stock Price: {order['price_type'] if order['price_type'] == StockPriceType.MKT else order['price']}\n"
        msg += (
            f"Price Change: {order['price_change']}%"
            if order["action"] == Action.BUY
            else ""
        )  # 只有買單才會輸出

        Notification.post_line_notify(token, msg)

    @staticmethod
    def post_deal_notify(token: str, order: Dict[str, Any]) -> None:
        """委託成交通知"""

        msg: str = "\n"
        msg += f"【{order['action']} Order Deal】\n"
        msg += f"Stock ID: {order['code']}\n"
        msg += f"Volume: {order['volume']}\n"
        msg += f"Price: {order['price']}"

        Notification.post_line_notify(token, msg)

    @staticmethod
    def post_account_info(
        api: sj.Shioaji,
        token: str,
        info: pd.DataFrame,
    ) -> None:
        """每日帳戶資訊"""

        msg: str = "\n"
        msg += f"【Today's Stock Info】\n"
        msg += (
            "".join(
                f"{title:<{len(title) + 5}}" for title in info.columns if title != "pnl"
            )
            + "\n"
        )
        msg += (
            "\n".join(
                f"{row['code']:<{len(info['code'].name) + 5}}"
                f"{row['quantity']:<{len(info['quantity'].name) + 10}}"
                f"{row['chg_rate']:<{len(info['chg_rate'].name) + 5}}"
                for _, row in info.iterrows()
            )
            + "\n"
        )
        msg += f"\nTotal realized pnl: {ShioajiAccount.get_realized_pnl(api)}"
        msg += f"\nTotal unrealized pnl: {info['pnl'].sum():.0f}"

        Notification.post_line_notify(token, msg)
