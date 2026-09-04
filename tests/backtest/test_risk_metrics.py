import math
from typing import List, Optional

import pytest

from core.backtest.analysis.risk_metrics import (
    TRADING_DAYS_PER_YEAR,
    compute_annualized_information_ratio,
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


# === Information Ratio（F-068 漏掉的第四個指標）===
def test_information_ratio_matches_hand_calculation() -> None:
    """
    手算對照：策略 [2%, -1%, 3%, 0%]、基準 [1%, -1%, 1%, 1%]

    主動報酬 [1%, 0%, 2%, -1%]，平均 0.5%、樣本標準差（ddof=1）
    √(((0.005)² + (0.005)² + (0.015)² + (0.015)²) / 3)，再乘 √252。
    """

    returns: List[float] = [0.02, -0.01, 0.03, 0.0]
    benchmark: List[float] = [0.01, -0.01, 0.01, 0.01]

    active: List[float] = [0.01, 0.0, 0.02, -0.01]
    mean: float = sum(active) / len(active)
    variance: float = sum((value - mean) ** 2 for value in active) / (len(active) - 1)
    expected: float = round(
        mean / math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR), 4
    )

    assert compute_annualized_information_ratio(returns, benchmark) == expected


def test_information_ratio_actually_depends_on_the_benchmark() -> None:
    """
    換一條基準就要換一個數字——這正是舊版做不到的事

    舊版的基準是寫死的常數 `0.0`，而**從每個樣本減去同一個常數不會改變分母**，
    分子則平移了同一個量，算出來恆等於 `mean(ROI) / std(ROI)`。所以只要基準的
    **波動型態**不同（不只是平均值不同），IR 就必須跟著變；若兩者仍相等，
    代表基準又被當成常數處理了。
    """

    returns: List[float] = [0.03, -0.01, 0.04, 0.02]
    flat: List[float] = [0.01, 0.01, 0.01, 0.01]  # 常數基準
    volatile: List[float] = [-0.01, 0.02, 0.0, 0.03]  # 同平均、但有波動

    assert sum(flat) == pytest.approx(sum(volatile))
    ir_flat: Optional[float] = compute_annualized_information_ratio(returns, flat)
    ir_volatile: Optional[float] = compute_annualized_information_ratio(
        returns, volatile
    )

    assert ir_flat != ir_volatile

    # 常數基準的追蹤誤差與策略自身的標準差相同（舊版恆等式的來源）
    assert ir_flat == compute_annualized_sharpe(returns, risk_free_rate=0.01 * 252)


def test_information_ratio_refuses_misaligned_series() -> None:
    """長度湊得起來不代表日期對得起來，長度不同一律拒絕而不是截頭去尾"""

    with pytest.raises(ValueError, match="長度不同"):
        compute_annualized_information_ratio([0.01, 0.02, 0.03], [0.01, 0.02])


def test_information_ratio_returns_none_without_tracking_error() -> None:
    """策略與基準完全同步時追蹤誤差為 0，IR 無定義"""

    assert compute_annualized_information_ratio([0.01, 0.02], [0.01, 0.02]) is None
    assert compute_annualized_information_ratio([0.01], [0.02]) is None


def make_ir_analyzer() -> "object":
    """建一個不連資料庫的 analyzer（IR 測試只餵自備的基準序列）"""

    from core.backtest.analysis.analyzer import StockBacktestAnalyzer

    analyzer = StockBacktestAnalyzer.__new__(StockBacktestAnalyzer)

    class _Account:
        init_capital = 1000000.0

    analyzer.account = _Account()
    analyzer.trade_records = []
    analyzer.risk_free_rate = 0.0
    analyzer.benchmark = "0050"
    analyzer.price = None
    return analyzer


def test_analyzer_information_ratio_uses_daily_returns() -> None:
    """
    analyzer 的 IR 與 Sharpe 同源：樣本是日報酬、依日期與基準對齊

    策略首日的報酬（初始資金 → 首日權益）沒有對應的基準報酬——基準首日要
    前一交易日的收盤價才算得出來——故落在交集之外，兩邊仍然同期。
    """

    import datetime

    analyzer = make_ir_analyzer()

    dates: List[datetime.date] = [datetime.date(2025, 1, day) for day in (2, 3, 6, 7)]
    daily_equity = [
        {"Date": dates[0], "Equity": 1010000.0},
        {"Date": dates[1], "Equity": 1005000.0},
        {"Date": dates[2], "Equity": 1020000.0},
        {"Date": dates[3], "Equity": 1015000.0},
    ]
    # 基準沒有首日（2025-01-02）
    benchmark = {dates[1]: 0.002, dates[2]: 0.01, dates[3]: -0.004}

    strategy_returns = analyzer.compute_daily_returns_by_date(daily_equity)
    assert list(strategy_returns) == dates

    ir: Optional[float] = analyzer.compute_information_ratio(daily_equity, benchmark)

    expected: Optional[float] = compute_annualized_information_ratio(
        [strategy_returns[date] for date in dates[1:]],
        [benchmark[date] for date in dates[1:]],
    )
    assert ir == expected
    assert ir is not None


def test_analyzer_information_ratio_is_none_without_daily_equity() -> None:
    """沒有逐日權益就沒有日報酬，IR 與 Sharpe 一樣回 None 而不是拿逐筆交易硬算"""

    analyzer = make_ir_analyzer()

    assert analyzer.compute_daily_returns_by_date(None) is None
    assert analyzer.compute_information_ratio() is None
