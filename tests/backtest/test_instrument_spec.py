from typing import Optional, Tuple

import pytest

from core.backtest.models.instrument_spec import InstrumentSpec, TwStockSpec
from core.utils.instrument import StockUtils

"""InstrumentSpec 測試：台股規格的三個介面必須與既有 StockUtils 逐值相同（backlog Phase2-1）"""


@pytest.fixture
def spec() -> TwStockSpec:
    """台股商品規格"""

    return TwStockSpec()


def test_spec_is_instrument_spec(spec: TwStockSpec) -> None:
    """TwStockSpec 必須實作抽象介面，期貨才有對稱的落點"""

    assert isinstance(spec, InstrumentSpec)


@pytest.mark.parametrize("lots, expected", [(0, 0), (1, 1000), (5, 5000), (100, 100000)])
def test_to_units(spec: TwStockSpec, lots: int, expected: int) -> None:
    """張 → 股：1 張 ＝ 1000 股"""

    assert spec.to_units(lots) == expected
    assert spec.to_units(lots) == StockUtils.convert_lot_to_share(lots)


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
def test_round_to_tick(
    spec: TwStockSpec, price: float, direction: str, expected: float
) -> None:
    """六段檔位的邊界取整：沿用 test_cost_model 的既有 15 組測資"""

    assert spec.round_to_tick(price, direction) == expected


def test_round_to_tick_default_direction(spec: TwStockSpec) -> None:
    """未指定方向時預設就近取整，與 StockUtils 的預設一致"""

    assert spec.round_to_tick(100.3) == StockUtils.round_to_tick(100.3, "nearest")


@pytest.mark.parametrize(
    "prev_close, expected",
    [
        (100.0, (90.0, 110.0)),  # 前收 100 → 跌停 90、漲停 110
        (9.99, (9.0, 10.95)),  # 跨檔位：漲停落在 0.05 檔、跌停落在 0.01 檔
        (1000.0, (900.0, 1100.0)),
    ],
)
def test_get_price_limits(
    spec: TwStockSpec, prev_close: float, expected: Tuple[float, float]
) -> None:
    """漲跌停為前收 ±10%，並各自往內對齊檔位（漲停捨去、跌停進位）"""

    assert spec.get_price_limits(prev_close) == expected


def test_get_price_limits_rounds_inward(spec: TwStockSpec) -> None:
    """對齊方向不可對調：漲停必須 ≤ 理論值、跌停必須 ≥ 理論值"""

    prev_close: float = 33.3
    limit_down, limit_up = spec.get_price_limits(prev_close)

    assert limit_up <= prev_close * 1.1
    assert limit_down >= prev_close * 0.9


@pytest.mark.parametrize("prev_close", [0.0, None])
def test_get_price_limits_without_prev_close(
    spec: TwStockSpec, prev_close: Optional[float]
) -> None:
    """尚未取得前收時不做漲跌停判定，維持既有的「跳過該項檢查」行為"""

    assert spec.get_price_limits(prev_close) == (None, None)
