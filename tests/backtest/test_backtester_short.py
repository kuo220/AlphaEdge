import datetime
from typing import Callable, List

import pytest

from core.backtest.backtester import Backtester
from core.backtest.factory import build_backtester
from core.backtest.models.fill_model import TwStockFillModel
from core.models import StockOrder, StockPosition, StockQuote, StockTradeRecord
from core.utils import (
    Action,
    BarExecutionOrder,
    DayTradeUncoveredPolicy,
    MarginCallPolicy,
    PositionType,
    Scale,
    ShortMethod,
)

"""回測引擎的方向驅動、成交價驗證與每日部位檢查測試（對應 backlog §4.5、§7.1、§7.2、§7.6）"""


DAY_1: datetime.date = datetime.date(2024, 1, 2)
DAY_2: datetime.date = datetime.date(2024, 1, 3)


@pytest.fixture
def make_backtester(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Backtester]:
    """建立不載入資料庫的 Backtester（setup 只負責建立目錄與載入 API）"""

    def _make_backtester(strategy) -> Backtester:
        monkeypatch.setattr(Backtester, "setup", lambda self: None)
        return build_backtester(strategy)

    return _make_backtester


def short_strategy(make_strategy, **overrides):
    """建立放空策略的捷徑；預設為留倉融券"""

    params: dict = dict(
        position_type=PositionType.SHORT,
        enable_intraday=False,
        short_method=ShortMethod.MARGIN,
    )
    params.update(overrides)
    return make_strategy(**params)


# === 方向驅動 ===
def test_resolve_actions() -> None:
    """開平倉動作依訂單方向推導"""

    assert Backtester.resolve_open_action(PositionType.LONG) == Action.BUY
    assert Backtester.resolve_open_action(PositionType.SHORT) == Action.SELL
    assert Backtester.resolve_close_action(PositionType.LONG) == Action.SELL
    assert Backtester.resolve_close_action(PositionType.SHORT) == Action.BUY


def test_execution_order_derivation(make_strategy, make_backtester) -> None:
    """當沖放空預設先開後平，其餘維持先平後開；策略顯式指定時以策略為準"""

    day_trade = make_backtester(
        short_strategy(make_strategy, enable_intraday=True)
    )
    assert day_trade.get_execution_order() == BarExecutionOrder.OPEN_THEN_CLOSE

    swing = make_backtester(short_strategy(make_strategy, enable_intraday=False))
    assert swing.get_execution_order() == BarExecutionOrder.CLOSE_THEN_OPEN

    long_strategy = make_backtester(make_strategy(position_type=PositionType.LONG))
    assert long_strategy.get_execution_order() == BarExecutionOrder.CLOSE_THEN_OPEN

    explicit = make_backtester(
        make_strategy(
            position_type=PositionType.LONG,
            bar_execution_order=BarExecutionOrder.OPEN_THEN_CLOSE,
        )
    )
    assert explicit.get_execution_order() == BarExecutionOrder.OPEN_THEN_CLOSE


def test_order_enrichment(make_strategy, make_backtester, make_order) -> None:
    """策略未填放空管道與當沖旗標時，由引擎依成本設定補值"""

    backtester: Backtester = make_backtester(
        short_strategy(make_strategy, enable_intraday=True)
    )

    orders: List[StockOrder] = backtester.enrich_orders(
        [
            make_order(action=Action.SELL, position_type=PositionType.SHORT),
            make_order(action=Action.BUY, position_type=PositionType.LONG),
        ]
    )

    assert orders[0].short_method == ShortMethod.DAY_TRADE
    assert orders[0].is_day_trade is True

    # LONG 不受影響
    assert orders[1].short_method is None
    assert orders[1].is_day_trade is False


def test_wrong_direction_order_rejected(
    make_strategy, make_backtester, make_order
) -> None:
    """方向不在白名單、或動作與方向不符的訂單一律剔除並計數"""

    backtester: Backtester = make_backtester(short_strategy(make_strategy))

    orders: List[StockOrder] = backtester.validate_orders(
        [
            make_order(action=Action.SELL, position_type=PositionType.SHORT),  # 合法
            make_order(action=Action.BUY, position_type=PositionType.LONG),  # 方向不允許
            make_order(action=Action.BUY, position_type=PositionType.SHORT),  # 動作錯誤
        ],
        "open",
    )

    assert len(orders) == 1
    assert backtester.event_counts["rejected_direction"] == 2


def test_allowed_directions_whitelist(
    make_strategy, make_backtester, make_order
) -> None:
    """放寬白名單後即可同時接受多空訂單，引擎不需修改"""

    backtester: Backtester = make_backtester(
        make_strategy(
            position_type=PositionType.LONG,
            allowed_directions={PositionType.LONG, PositionType.SHORT},
        )
    )

    orders: List[StockOrder] = backtester.validate_orders(
        [
            make_order(action=Action.BUY, position_type=PositionType.LONG),
            make_order(action=Action.SELL, position_type=PositionType.SHORT),
        ],
        "open",
    )

    assert len(orders) == 2
    assert backtester.event_counts["rejected_direction"] == 0


# === 成交價驗證（規則已下沉至 FillModel，故直接打 model）===
def test_fill_price_out_of_range_rejected(make_order, make_quote) -> None:
    """成交價超出當日高低區間即拒單"""

    fill_model: TwStockFillModel = TwStockFillModel()
    quote: StockQuote = make_quote(cur_price=100.0, high=105.0, low=98.0)

    assert fill_model.validate(make_order(price=100.0), quote) is True
    assert fill_model.validate(make_order(price=110.0), quote) is False
    assert fill_model.validate(make_order(price=95.0), quote) is False
    assert fill_model.event_counts["rejected_fill_price"] == 2


def test_fill_price_limit_rejected(make_order, make_quote) -> None:
    """超出漲跌停區間即拒單（漲跌停以前一交易日收盤為基準）"""

    fill_model: TwStockFillModel = TwStockFillModel()
    fill_model.prev_close["2330"] = 100.0

    # 漲停 110、跌停 90
    in_range: StockQuote = make_quote(cur_price=112.0, high=130.0, low=90.0)
    assert fill_model.validate(make_order(price=112.0), in_range) is False
    assert fill_model.event_counts["rejected_fill_price"] == 1


def test_fill_price_tick_scale(make_order, make_quote) -> None:
    """§7.6：Tick 級別以當日累計高低點為界，且只納入已發生的報價"""

    fill_model: TwStockFillModel = TwStockFillModel()

    quotes: List[StockQuote] = [
        make_quote(cur_price=100.0, scale=Scale.TICK),
        make_quote(cur_price=102.0, scale=Scale.TICK),
    ]
    fill_model.update_intraday_range(quotes)

    tick_quote: StockQuote = make_quote(cur_price=102.0, scale=Scale.TICK)
    assert fill_model.validate(make_order(price=101.0), tick_quote) is True

    # 105 尚未出現在當日成交中，不可成交
    assert fill_model.validate(make_order(price=105.0), tick_quote) is False


def test_fill_model_wired_into_engine(
    make_strategy, make_backtester, make_order, make_quote
) -> None:
    """引擎的拒單計數必須反映到共用的 event_counts（model 與引擎共用同一個 dict）"""

    backtester: Backtester = make_backtester(short_strategy(make_strategy))
    quote: StockQuote = make_quote(cur_price=100.0, high=105.0, low=98.0)

    assert backtester.validate_fill_price(make_order(price=110.0), quote) is False
    assert backtester.event_counts["rejected_fill_price"] == 1
    assert backtester.fill_model.event_counts is backtester.event_counts


def test_fill_model_state_shared_with_engine(
    make_strategy, make_backtester, make_quote
) -> None:
    """引擎的 prev_close／intraday_range 為 FillModel 狀態的視圖，兩邊寫入互通"""

    backtester: Backtester = make_backtester(short_strategy(make_strategy))

    backtester.prev_close["2330"] = 100.0
    assert backtester.fill_model.prev_close["2330"] == 100.0

    backtester.fill_model.on_bar_close([make_quote(cur_price=105.0, close=105.0)])
    assert backtester.prev_close["2330"] == 105.0


# === 同日開平倉 ===
def test_same_day_short_cover(make_strategy, make_backtester, make_order, make_quote) -> None:
    """§4.5：OPEN_THEN_CLOSE 下，當沖放空可在同一天完成開倉與回補"""

    strategy = short_strategy(
        make_strategy,
        enable_intraday=True,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
        close_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.BUY,
                    position_type=PositionType.SHORT,
                    price=95.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    backtester.execute_bar(DAY_1, [make_quote(date=DAY_1, cur_price=97.0, high=101.0, low=94.0)])

    records: List[StockTradeRecord] = backtester.account.trade_records
    assert len(records) == 1
    assert records[0].realized_pnl == 4768.0  # §6.1 當沖手算值
    assert records[0].holding_days == 0
    assert backtester.account.positions == []


def test_close_then_open_cannot_cover_same_day(
    make_strategy, make_backtester, make_quote
) -> None:
    """對照組：維持 CLOSE_THEN_OPEN 時，同日開的空單不可能在當日被平掉"""

    strategy = short_strategy(
        make_strategy,
        enable_intraday=True,
        bar_execution_order=BarExecutionOrder.CLOSE_THEN_OPEN,
        day_trade_uncovered_policy=DayTradeUncoveredPolicy.CONVERT_TO_MARGIN,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
        close_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.BUY,
                    position_type=PositionType.SHORT,
                    price=95.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    backtester.execute_bar(DAY_1, [make_quote(date=DAY_1, cur_price=97.0, high=101.0, low=94.0)])

    # 平倉訊號先於開倉執行，因此當日不會產生交易紀錄
    assert backtester.account.trade_records == []


# === 當沖日終未回補 ===
def test_uncovered_day_trade_forced(make_strategy, make_backtester, make_quote) -> None:
    """§7.1：當沖放空日終未回補，以收盤價強制回補並計數"""

    strategy = short_strategy(
        make_strategy,
        enable_intraday=True,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    backtester.execute_bar(
        DAY_1, [make_quote(date=DAY_1, cur_price=98.0, high=101.0, low=97.0, close=98.0)]
    )

    assert backtester.event_counts["forced_cover_day_trade"] == 1
    assert backtester.account.positions == []
    assert len(backtester.account.trade_records) == 1
    assert backtester.account.trade_records[0].exit_price == 98.0


def test_limit_up_cannot_cover(make_strategy, make_backtester, make_quote) -> None:
    """§7.1：全日鎖漲停無法回補，轉為融券留倉並單獨計數"""

    strategy = short_strategy(
        make_strategy,
        enable_intraday=True,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=110.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)
    backtester.prev_close["2330"] = 100.0  # 漲停價 110

    backtester.execute_bar(
        DAY_1,
        [make_quote(date=DAY_1, cur_price=110.0, high=110.0, low=110.0, close=110.0)],
    )

    assert backtester.event_counts["limit_up_cover_failed"] == 1
    assert backtester.event_counts["forced_cover_day_trade"] == 0

    positions: List[StockPosition] = backtester.account.get_positions()
    assert len(positions) == 1
    assert positions[0].is_day_trade is False
    assert positions[0].short_method == ShortMethod.MARGIN
    assert positions[0].margin > 0


# === 留倉的每日檢查 ===
def test_margin_call_force_cover(make_strategy, make_backtester, make_quote) -> None:
    """§7.2：維持率跌破 130% 時，以當日收盤價強制回補並記為斷頭"""

    strategy = short_strategy(
        make_strategy,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    backtester.execute_bar(DAY_1, [make_quote(date=DAY_1, cur_price=100.0, high=101.0, low=99.0)])
    assert len(backtester.account.get_positions()) == 1

    # 股價漲到 150：維持率 190000 / 150000 = 126.7% < 130%
    backtester.execute_bar(DAY_2, [make_quote(date=DAY_2, cur_price=150.0, high=151.0, low=149.0)])

    assert backtester.event_counts["forced_cover_margin_call"] == 1
    assert backtester.account.positions == []
    assert backtester.account.trade_records[0].realized_pnl < 0


def test_margin_call_warn_only(make_strategy, make_backtester, make_quote) -> None:
    """WARN_ONLY 政策下只記錄不回補，適合研究純訊號績效"""

    strategy = short_strategy(
        make_strategy,
        margin_call_policy=MarginCallPolicy.WARN_ONLY,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    backtester.execute_bar(DAY_1, [make_quote(date=DAY_1, cur_price=100.0, high=101.0, low=99.0)])
    backtester.execute_bar(DAY_2, [make_quote(date=DAY_2, cur_price=150.0, high=151.0, low=149.0)])

    assert backtester.event_counts["forced_cover_margin_call"] == 0
    assert len(backtester.account.get_positions()) == 1


def test_borrow_fee_not_double_counted(
    make_strategy, make_backtester, make_quote
) -> None:
    """§4.3：MARGIN 的券費只在開倉收一次，逐日計提的 accrued_borrow_fee 必須維持 0"""

    strategy = short_strategy(
        make_strategy,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    backtester.execute_bar(DAY_1, [make_quote(date=DAY_1, cur_price=100.0, high=101.0, low=99.0)])

    # 連續持有 10 天，期間沒有任何訊號
    for offset in range(1, 11):
        date: datetime.date = DAY_1 + datetime.timedelta(days=offset)
        backtester.execute_bar(
            date, [make_quote(date=date, cur_price=100.0, high=101.0, low=99.0)]
        )

    position: StockPosition = backtester.account.get_positions()[0]
    assert position.accrued_borrow_fee == 0  # MARGIN 不逐日計提
    assert position.borrow_fee == 80  # 開倉時一次收取
    assert position.holding_days == 11


def test_sbl_borrow_fee_accrued_daily(
    make_strategy, make_backtester, make_quote
) -> None:
    """對照組：SBL 借券費才需要逐日計提"""

    strategy = short_strategy(
        make_strategy,
        short_method=ShortMethod.SBL,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    backtester.execute_bar(DAY_1, [make_quote(date=DAY_1, cur_price=100.0, high=101.0, low=99.0)])
    backtester.execute_bar(DAY_2, [make_quote(date=DAY_2, cur_price=100.0, high=101.0, low=99.0)])

    position: StockPosition = backtester.account.get_positions()[0]
    # 每日 100000 × 3% / 365 = 8.21 → 捨去為 8，兩天共 16
    assert position.accrued_borrow_fee == 16


def test_max_holding_days_force_cover(
    make_strategy, make_backtester, make_quote
) -> None:
    """§7.3：超過最長持有天數的保險絲會強制回補"""

    strategy = short_strategy(
        make_strategy,
        max_holding_days=3,
        open_script={
            DAY_1: [
                StockOrder(
                    stock_id="2330",
                    date=DAY_1,
                    action=Action.SELL,
                    position_type=PositionType.SHORT,
                    price=100.0,
                    volume=1,
                )
            ]
        },
    )
    backtester: Backtester = make_backtester(strategy)

    for offset in range(5):
        date: datetime.date = DAY_1 + datetime.timedelta(days=offset)
        backtester.execute_bar(
            date, [make_quote(date=date, cur_price=100.0, high=101.0, low=99.0)]
        )

    assert backtester.event_counts["forced_cover_max_holding"] == 1
    assert backtester.account.positions == []
