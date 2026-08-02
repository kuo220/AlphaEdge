import datetime
from typing import Dict, List

from core.models import StockAccount, StockPosition
from core.utils import PositionType, ShortMethod

"""StockAccount 方向感知查詢與保證金欄位的測試（對應 backlog §5.4）"""


def build_account() -> StockAccount:
    """建立同時持有多單與空單的帳戶"""

    account: StockAccount = StockAccount(1000000.0)
    account.positions.append(
        StockPosition(
            id=1,
            stock_id="2330",
            position_type=PositionType.LONG,
            date=datetime.date(2024, 1, 2),
            price=600.0,
            volume=1,
        )
    )
    account.positions.append(
        StockPosition(
            id=2,
            stock_id="2317",
            position_type=PositionType.SHORT,
            short_method=ShortMethod.MARGIN,
            date=datetime.date(2024, 1, 3),
            price=100.0,
            volume=2,
            margin=180000.0,
            short_proceeds=200000.0,
        )
    )
    return account


def test_account_direction_aware() -> None:
    """check_has_position 不帶方向時維持既有行為，帶方向時只認同向部位"""

    account: StockAccount = build_account()

    # 既有呼叫方式（不分方向）
    assert account.check_has_position("2330") is True
    assert account.check_has_position("2317") is True
    assert account.check_has_position("1101") is False

    # 方向感知查詢
    assert account.check_has_position("2330", PositionType.LONG) is True
    assert account.check_has_position("2330", PositionType.SHORT) is False
    assert account.check_has_position("2317", PositionType.SHORT) is True
    assert account.check_has_position("2317", PositionType.LONG) is False


def test_get_positions_filter() -> None:
    """get_positions 可依股票代號與方向過濾，且排除已平倉部位"""

    account: StockAccount = build_account()

    assert len(account.get_positions()) == 2
    assert len(account.get_positions(position_type=PositionType.SHORT)) == 1
    assert len(account.get_positions(stock_id="2330")) == 1
    assert account.get_positions(stock_id="2330", position_type=PositionType.SHORT) == []

    account.positions[0].is_closed = True
    assert len(account.get_positions()) == 1


def test_get_short_market_value() -> None:
    """空頭市值依傳入價格計算；缺價時退回開倉價"""

    account: StockAccount = build_account()

    prices: Dict[str, float] = {"2317": 110.0}
    assert account.get_short_market_value(prices) == 220000.0

    # 未提供價格時以開倉價估算
    assert account.get_short_market_value({}) == 200000.0


def test_margin_used_default() -> None:
    """新帳戶的保證金佔用為 0"""

    account: StockAccount = StockAccount(1000000.0)
    assert account.margin_used == 0.0
