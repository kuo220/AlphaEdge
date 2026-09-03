import math
from typing import List, Optional

import pytest

from core.backtest.analysis.risk_metrics import (
    TRADING_DAYS_PER_YEAR,
    compute_annualized_sharpe,
    compute_annualized_sortino,
    compute_period_returns,
)

"""
風險調整後報酬的公式（健檢 F-068）

舊版的四個問題都會讓數字看起來合理但實際錯誤：分子用百分比、分母用小數；
沒有年化；以「每筆交易」為樣本；Sortino 的下檔標準差算的是低於門檻那幾期
**彼此之間**的離散度。
"""


def test_period_returns_from_equity_curve() -> None:
    """逐期報酬率是小數，不是百分比"""

    returns: List[float] = compute_period_returns([100.0, 110.0, 99.0])

    assert returns == pytest.approx([0.1, -0.1])


def test_period_returns_skip_non_positive_base() -> None:
    """前一期權益為 0 或負數時該期沒有定義；補 0 會讓破產的帳戶看起來很平穩"""

    assert compute_period_returns([0.0, 100.0, 110.0]) == pytest.approx([0.1])


def test_sharpe_matches_hand_calculation() -> None:
    """
    手算對照：報酬率 [1%, -1%, 1%, -1%]、無風險利率 0

    平均 0、標準差 0.0115470…（ddof=1）→ Sharpe 恰為 0。
    """

    returns: List[float] = [0.01, -0.01, 0.01, -0.01]

    assert compute_annualized_sharpe(returns, risk_free_rate=0.0) == 0.0


def test_sharpe_is_annualized() -> None:
    """年化係數是 √252；未年化的數字無法與任何外部參考比較"""

    returns: List[float] = [0.01, 0.02, 0.01, 0.02]

    mean: float = sum(returns) / len(returns)
    variance: float = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    expected: float = round(
        mean / math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR), 4
    )

    assert compute_annualized_sharpe(returns, risk_free_rate=0.0) == expected


def test_risk_free_rate_is_converted_to_a_single_period() -> None:
    """
    無風險利率與報酬率同為小數，且先換算成單期再相減

    舊版分子是百分比（例如 2.31）、分母的無風險利率是 0.02，兩者差 100 倍，
    等於幾乎沒有扣無風險利率。
    """

    returns: List[float] = [0.01, 0.02, 0.01, 0.02]

    with_rf: Optional[float] = compute_annualized_sharpe(returns, risk_free_rate=0.02)
    without_rf: Optional[float] = compute_annualized_sharpe(returns, risk_free_rate=0.0)

    assert with_rf is not None and without_rf is not None
    assert with_rf < without_rf, "扣掉無風險利率之後應該變小"


def test_sharpe_returns_none_without_enough_samples() -> None:
    """
    零筆／一筆時回 None，不可回 0

    「沒有資料」與「風險調整後報酬為零」是兩件完全不同的事；
    舊版在零筆交易時是 `np.mean([])` → nan ＋ RuntimeWarning。
    """

    assert compute_annualized_sharpe([]) is None
    assert compute_annualized_sharpe([0.01]) is None


def test_sharpe_returns_none_when_there_is_no_variance() -> None:
    """報酬率完全不動時標準差為 0，Sharpe 無定義"""

    assert compute_annualized_sharpe([0.01, 0.01, 0.01]) is None


def test_sortino_only_penalises_downside() -> None:
    """上檔波動不進分母：同樣的平均報酬，正向波動大的 Sortino 應較高"""

    calm_upside: Optional[float] = compute_annualized_sortino(
        [0.01, 0.01, 0.01, -0.01], risk_free_rate=0.0
    )
    wild_upside: Optional[float] = compute_annualized_sortino(
        [0.05, -0.03, 0.01, -0.01], risk_free_rate=0.0
    )

    assert calm_upside is not None and wild_upside is not None
    assert calm_upside > wild_upside


def test_sortino_divides_by_the_full_sample() -> None:
    """
    分母是「低於門檻的偏差平方和 ÷ **全樣本**筆數」再開根號

    舊版對低於門檻的那幾期取 `np.std`，算的是它們彼此之間的離散度，與門檻無關。
    """

    returns: List[float] = [0.02, 0.02, 0.02, -0.02]

    mean: float = sum(returns) / len(returns)
    downside: float = math.sqrt(((-0.02) ** 2) / len(returns))
    expected: float = round(mean / downside * math.sqrt(TRADING_DAYS_PER_YEAR), 4)

    assert compute_annualized_sortino(returns, risk_free_rate=0.0) == expected


def test_sortino_returns_none_without_downside() -> None:
    """完全沒有下檔波動時 Sortino 無定義，回 None 而不是無限大"""

    assert compute_annualized_sortino([0.01, 0.02, 0.03], risk_free_rate=0.0) is None


def test_analyzer_metrics_are_none_without_trades() -> None:
    """零筆交易時 analyzer 的三個指標都回 None，不會噴 RuntimeWarning"""

    from core.backtest.analysis.analyzer import StockBacktestAnalyzer

    analyzer: StockBacktestAnalyzer = StockBacktestAnalyzer.__new__(
        StockBacktestAnalyzer
    )

    class _Account:
        init_capital = 1000000.0
        trade_records: List = []

    analyzer.account = _Account()
    analyzer.trade_records = []
    analyzer.risk_free_rate = 0.02

    assert analyzer.compute_sharpe_ratio() is None
    assert analyzer.compute_sortino_ratio() is None
    assert analyzer.compute_volatility() is None


def test_analyzer_refuses_to_annualize_per_trade_returns() -> None:
    """
    沒有逐日權益時回 None，**不可退回逐筆交易的曲線**

    `compute_equity_curve()` 的 fallback 是「每平倉一筆一個節點」，那是每筆
    交易的報酬而不是日報酬。拿它去乘 √252 等於宣稱「一年有 252 筆交易」——
    正是本模組說明裡列的第 2、3 個缺陷，只是換成從可選參數溜進來。
    """

    from core.backtest.analysis.analyzer import StockBacktestAnalyzer

    class _Record:
        def __init__(self, pnl: float, day: int):
            self.realized_pnl = pnl
            self.exit_date = None
            self.roi = pnl / 10000

    analyzer: StockBacktestAnalyzer = StockBacktestAnalyzer.__new__(
        StockBacktestAnalyzer
    )

    class _Account:
        init_capital = 1000000.0

    analyzer.account = _Account()
    analyzer.trade_records = [_Record(1000.0, i) for i in range(20)]
    analyzer.risk_free_rate = 0.02

    assert analyzer.compute_daily_returns() is None
    assert analyzer.compute_sharpe_ratio() is None
    assert analyzer.compute_sortino_ratio() is None


def test_analyzer_computes_metrics_from_daily_equity() -> None:
    """有逐日權益時照常算得出來"""

    from core.backtest.analysis.analyzer import StockBacktestAnalyzer

    analyzer: StockBacktestAnalyzer = StockBacktestAnalyzer.__new__(
        StockBacktestAnalyzer
    )

    class _Account:
        init_capital = 1000000.0

    analyzer.account = _Account()
    analyzer.trade_records = []
    analyzer.risk_free_rate = 0.0

    daily_equity = [
        {"Equity": 1010000.0},
        {"Equity": 1005000.0},
        {"Equity": 1020000.0},
        {"Equity": 1015000.0},
    ]

    returns = analyzer.compute_daily_returns(daily_equity)

    assert returns is not None and len(returns) == 4
    assert analyzer.compute_sharpe_ratio(daily_equity) is not None
