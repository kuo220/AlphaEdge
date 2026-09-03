import os
from typing import Any, Dict, Optional

import pandas as pd
import requests
import shioaji as sj
from loguru import logger

from .account import ShioajiAccount
from .constant import Action, StockPriceType

"""
LINE 推播通知

**LINE Notify 已於 2025-03-31 停止服務**（健檢 F-017）。舊實作打的
`https://notify-api.line.me/api/notify` 現在不會成功，而且原本連
`raise_for_status()` 都沒有——所有通知早就默默地送不出去，卻沒有任何跡象。

現改用 **LINE Messaging API** 的 push message 端點，需要兩個設定：

| 環境變數 | 意義 |
|----------|------|
| `LINE_CHANNEL_ACCESS_TOKEN` | Messaging API channel 的長期存取權杖 |
| `LINE_PUSH_TARGET_ID` | 推播對象的 userId／groupId／roomId |

兩者任一缺少時**只警告一次**並跳過推播——盤中不該因為通知沒設定而中斷下單；
但送出失敗一定會記 `logger.error`，不再是靜默的。
"""


class Notification:
    """執行 LINE 推播通知"""

    COLUMN_PADDING: int = 10  # 報表欄位寬度 padding

    # LINE Messaging API 的 push message 端點（LINE Notify 已於 2025-03-31 停服）
    PUSH_MESSAGE_URL: str = "https://api.line.me/v2/bot/message/push"
    REQUEST_TIMEOUT_SECONDS: int = 10

    # 未設定時只警告一次，避免盤中每一筆成交都刷一行
    _missing_config_warned: bool = False

    @classmethod
    def get_push_target(cls) -> Optional[str]:
        """推播對象 ID；未設定時回 None"""

        return os.getenv("LINE_PUSH_TARGET_ID")

    @classmethod
    def post_line_notify(cls, token: str, msg: str) -> None:
        """
        - Description:
            以 LINE Messaging API 推播一則文字訊息

            **不拋例外**：通知失敗不該讓下單流程中斷。但失敗一定會記
            `logger.error`——舊版連回應狀態都不看，訊息送不出去毫無跡象。
        - Parameters:
            - token: str
                Messaging API 的 channel access token
            - msg: str
                訊息內容
        """

        target: Optional[str] = cls.get_push_target()
        if not token or not target:
            if not cls._missing_config_warned:
                logger.warning(
                    "未設定 LINE_CHANNEL_ACCESS_TOKEN／LINE_PUSH_TARGET_ID，"
                    "本次執行的 LINE 推播全部跳過"
                )
                cls._missing_config_warned = True
            return

        headers: Dict[str, str] = {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json",
        }
        payload: Dict[str, Any] = {
            "to": target,
            "messages": [{"type": "text", "text": msg}],
        }

        try:
            response: requests.Response = requests.post(
                cls.PUSH_MESSAGE_URL,
                headers=headers,
                json=payload,
                timeout=cls.REQUEST_TIMEOUT_SECONDS,
            )
        except Exception as error:
            logger.error(f"LINE 推播失敗：{type(error).__name__}: {error}")
            return

        if not response.ok:
            logger.error(
                f"LINE 推播失敗：HTTP {response.status_code}；{response.text[:200]}"
            )

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
        msg += "【Today's Stock Info】\n"
        msg += (
            "".join(
                f"{title:<{len(title) + 5}}" for title in info.columns if title != "pnl"
            )
            + "\n"
        )
        msg += (
            "\n".join(
                f"{row['code']:<{len(info['code'].name) + 5}}"
                f"{row['quantity']:<{len(info['quantity'].name) + Notification.COLUMN_PADDING}}"
                f"{row['chg_rate']:<{len(info['chg_rate'].name) + 5}}"
                for _, row in info.iterrows()
            )
            + "\n"
        )
        msg += f"\nTotal realized pnl: {ShioajiAccount.get_realized_pnl(api)}"
        msg += f"\nTotal unrealized pnl: {info['pnl'].sum():.0f}"

        Notification.post_line_notify(token, msg)
