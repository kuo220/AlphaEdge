import datetime

import pytest

from core.backtest.models.cost_model import CostConfig, ShortConstraint, StockCostModel
from core.models import StockTradeRecord
from core.utils import Action, PositionType, ShortMethod
from core.utils.instrument import StockUtils

"""成本模型與數值處理規則的單元測試"""


# === 手算驗收範例 ===
def test_cost_model_day_trade() -> None:
    """§6.1：100 元放空 1 張、95 元回補的當沖，各項成本與損益需與手算一致"""

    model: StockCostModel = StockCostModel(
        CostConfig.default(ShortMethod.DAY_TRADE, is_day_trade=True)
    )

    open_commission: int = model.commission(price=100.0, volume=1)
    open_tax: int = model.tax(price=100.0, volume=1, action=Action.SELL)
    close_commission: int = model.commission(price=95.0, volume=1)

    assert open_commission == 42  # 100000 × 0.001425 × 0.3 = 42.75 → 捨去
    assert open_tax == 150  # 100000 × 0.0015（當沖減半）
    assert close_commission == 40  # 95000 × 0.001425 × 0.3 = 40.6125 → 捨去

    # 當沖無保證金、無借券費、無利息
    assert model.margin_required(price=100.0, volume=1) == 0
    assert model.borrow_fee(price=100.0, volume=1, holding_days=0) == 0
    assert model.short_interest(proceeds=100000.0, margin=0.0, holding_days=0) == 0

    entry_cost: int = open_commission + open_tax
    pnl: float = model.realized_pnl(
        position_type=PositionType.SHORT,
        entry_price=100.0,
        exit_price=95.0,
        volume=1,
        entry_cost=entry_cost,
        exit_cost=close_commission,
    )
    assert pnl == 4768.0

    roi: float = model.roi(
        position_type=PositionType.SHORT,
        entry_price=100.0,
        exit_price=95.0,
        volume=1,
        entry_cost=entry_cost,
        exit_cost=close_commission,
    )
    assert roi == 4.76  # 4768 / 100192

    roi_on_capital: float = model.roi_on_capital(
        position_type=PositionType.SHORT,
        entry_price=100.0,
        exit_price=95.0,
        volume=1,
        entry_cost=entry_cost,
        exit_cost=close_commission,
        margin=0.0,
    )
    assert roi_on_capital == 2483.33  # 4768 / 192


def test_cost_model_margin_short() -> None:
    """§6.2：100 元融券放空 1 張、持有 10 天後 95 元回補"""

    model: StockCostModel = StockCostModel(CostConfig.default(ShortMethod.MARGIN))

    open_commission: int = model.commission(price=100.0, volume=1)
    open_tax: int = model.tax(price=100.0, volume=1, action=Action.SELL)
    borrow_fee: int = model.borrow_fee(price=100.0, volume=1)
    margin: int = model.margin_required(price=100.0, volume=1)
    close_commission: int = model.commission(price=95.0, volume=1)
    interest: int = model.short_interest(
        proceeds=100000.0, margin=90000.0, holding_days=10
    )

    assert open_commission == 42
    assert open_tax == 300  # 非當沖，0.3%
    assert borrow_fee == 80  # 100000 × 0.08%
    assert margin == 90000  # 100000 × 90%
    assert close_commission == 40
    assert interest == 10  # 190000 × 0.002 × 10 / 365 = 10.41 → 捨去

    entry_cost: int = open_commission + open_tax + borrow_fee
    pnl: float = model.realized_pnl(
        position_type=PositionType.SHORT,
        entry_price=100.0,
        exit_price=95.0,
        volume=1,
        entry_cost=entry_cost,
        exit_cost=close_commission,
        carry_cost=-interest,  # 利息為收入，故為負的持有成本
    )
    assert pnl == 4548.0

    assert (
        model.roi(
            position_type=PositionType.SHORT,
            entry_price=100.0,
            exit_price=95.0,
            volume=1,
            entry_cost=entry_cost,
            exit_cost=close_commission,
            carry_cost=-interest,
        )
        == 4.53
    )
    assert (
        model.roi_on_capital(
            position_type=PositionType.SHORT,
            entry_price=100.0,
            exit_price=95.0,
            volume=1,
            entry_cost=entry_cost,
            exit_cost=close_commission,
            carry_cost=-interest,
            margin=margin,
        )
        == 5.03
    )


def test_maintenance_ratio() -> None:
    """§6.2：維持率 =（擔保價款 + 保證金）/ 市值，146 元時剛好觸及 130%"""

    model: StockCostModel = StockCostModel(CostConfig.default(ShortMethod.MARGIN))

    assert round(model.maintenance_ratio(100000.0, 90000.0, 130.0, 1), 4) == 1.4615
    assert model.check_margin_call(100000.0, 90000.0, 130.0, 1) is False
    assert model.check_margin_call(100000.0, 90000.0, 146.5, 1) is True


def test_long_pnl_direction() -> None:
    """做多方向的損益必須與放空相反，且與既有 StockUtils 結果一致"""

    model: StockCostModel = StockCostModel(CostConfig.default())

    pnl: float = model.realized_pnl(
        position_type=PositionType.LONG,
        entry_price=100.0,
        exit_price=110.0,
        volume=1,
        entry_cost=42,
        exit_cost=47 + 330,
    )
    legacy_pnl: float = StockUtils.calculate_net_profit(
        buy_price=100.0, sell_price=110.0, volume=1
    )

    # 與既有 LONG 公式完全一致（買 42、賣 47 + 稅 330）
    assert pnl == legacy_pnl == 9581.0


# === 數值處理規則 ===
def test_rounding_rules() -> None:
    """§6.0：費用一律無條件捨去、保證金無條件進位"""

    model: StockCostModel = StockCostModel(CostConfig.default(ShortMethod.MARGIN))

    # 手續費 42.75 → 42（若用 round() 會得到 43）
    assert model.commission(price=100.0, volume=1) == 42

    # 最低手續費 20 元
    assert model.commission(price=10.0, volume=1) == 20

    # 證交稅最低 1 元
    assert model.tax(price=0.1, volume=1, action=Action.SELL) == 1

    # 買進不課稅
    assert model.tax(price=100.0, volume=1, action=Action.BUY) == 0

    # 保證金無條件進位：100.005 × 1000 × 0.9 = 90004.5 → 90005
    assert model.margin_required(price=100.005, volume=1) == 90005
    # 浮點尾數不應造成多進一元：33.33 × 1000 × 0.9 實際為 29996.999999999996
    assert model.margin_required(price=33.33, volume=1) == 29997


def test_sbl_borrow_fee_accrues_by_day() -> None:
    """SBL 借券費依持有天數年化計算，MARGIN 則與天數無關"""

    sbl: StockCostModel = StockCostModel(CostConfig.default(ShortMethod.SBL))
    margin: StockCostModel = StockCostModel(CostConfig.default(ShortMethod.MARGIN))

    # 100000 × 3% × 30 / 365 = 246.57 → 捨去
    assert sbl.borrow_fee(price=100.0, volume=1, holding_days=30) == 246
    assert sbl.borrow_fee(price=100.0, volume=1, holding_days=0) == 0

    # MARGIN 一次性收取，持有天數不影響
    assert margin.borrow_fee(price=100.0, volume=1, holding_days=30) == 80
    assert margin.borrow_fee(price=100.0, volume=1, holding_days=0) == 80

    # SBL 不給付融券保證金利息
    assert sbl.short_interest(proceeds=100000.0, margin=90000.0, holding_days=30) == 0


def test_tax_rate_switch() -> None:
    """is_day_trade 切換 0.15% / 0.3%，且 StockUtils 的預設行為不變"""

    model: StockCostModel = StockCostModel(CostConfig.default(ShortMethod.MARGIN))

    assert model.tax(100.0, 1, Action.SELL, is_day_trade=True) == 150
    assert model.tax(100.0, 1, Action.SELL, is_day_trade=False) == 300

    # 既有函式不帶參數時維持原本的 0.3%
    assert StockUtils.calculate_transaction_tax(100.0, 1) == 300
    assert StockUtils.calculate_transaction_tax(100.0, 1, is_day_trade=True) == 150


@pytest.mark.parametrize(
    "price, direction, expected",
    [
        (9.993, "down", 9.99),
        (9.991, "up", 10.0),
        (10.02, "down", 10.0),
        (10.02, "up", 10.05),
        (49.99, "up", 50.0),
        (50.02, "down", 50.0),
        (99.95, "up", 100.0),
        (100.2, "down", 100.0),
        (100.2, "up", 100.5),
        (499.6, "up", 500.0),
        (500.5, "down", 500.0),
        (999.5, "up", 1000.0),
        (1002.0, "down", 1000.0),
        (1002.0, "up", 1005.0),
        (100.3, "nearest", 100.5),
    ],
)
def test_round_to_tick(price: float, direction: str, expected: float) -> None:
    """§3.5：六段檔位的邊界取整"""

    assert StockUtils.round_to_tick(price, direction) == expected


# === 資料模型 ===
def test_record_entry_exit_semantics() -> None:
    """§2.6：SHORT 的 entry 是放空賣出、exit 是回補買進；LONG 相反"""

    short_record: StockTradeRecord = StockTradeRecord(
        position_type=PositionType.SHORT,
        sell_date=datetime.date(2024, 3, 1),
        sell_price=100.0,
        buy_date=datetime.date(2024, 5, 1),
        buy_price=95.0,
    )
    assert short_record.entry_date == datetime.date(2024, 3, 1)
    assert short_record.entry_price == 100.0
    assert short_record.exit_date == datetime.date(2024, 5, 1)
    assert short_record.exit_price == 95.0

    long_record: StockTradeRecord = StockTradeRecord(
        position_type=PositionType.LONG,
        buy_date=datetime.date(2024, 3, 1),
        buy_price=100.0,
        sell_date=datetime.date(2024, 5, 1),
        sell_price=110.0,
    )
    assert long_record.entry_date == long_record.buy_date
    assert long_record.exit_date == long_record.sell_date


def test_short_constraint_defaults() -> None:
    """未提供資料時，各項限制檢查一律放行"""

    constraint: ShortConstraint = ShortConstraint()

    assert constraint.check_day_tradable("2330", datetime.date(2024, 1, 2)) is True
    assert constraint.get_force_cover_dates("2330") == []

    limited: ShortConstraint = ShortConstraint(
        day_trade_whitelist={datetime.date(2024, 1, 2): {"2317"}}
    )
    assert limited.check_day_tradable("2330", datetime.date(2024, 1, 2)) is False
    assert limited.check_day_tradable("2317", datetime.date(2024, 1, 2)) is True
