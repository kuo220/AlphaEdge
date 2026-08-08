import datetime
from pathlib import Path
from typing import Callable, Dict, List

import pandas as pd
import pytest

from core.backtest.analysis.analyzer import StockBacktestAnalyzer
from core.backtest.report.reporter import StockBacktestReporter
from core.models import StockAccount, StockTradeRecord
from core.utils import PositionType

"""權益曲線口徑測試：有 daily_equity 時一律走盯市，沒有時退回已實現（對應 backlog 逐日權益 S2~S5）"""


DAY_1: datetime.date = datetime.date(2024, 1, 2)


@pytest.fixture
def reporter_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[..., StockBacktestReporter]:
    """建立不連資料庫的 reporter（setup 只負責載入 benchmark 價格，本測試用不到）"""

    def _factory(strategy, account: StockAccount) -> StockBacktestReporter:
        monkeypatch.setattr(StockBacktestReporter, "setup", lambda self: None)

        reporter: StockBacktestReporter = StockBacktestReporter(strategy, tmp_path)
        reporter.account = account
        return reporter

    return _factory


def make_closed_record(
    record_id: int, exit_date: datetime.date, realized_pnl: float
) -> StockTradeRecord:
    """建立一筆已平倉的做多交易紀錄"""

    return StockTradeRecord(
        id=record_id,
        stock_id="2330",
        is_closed=True,
        position_type=PositionType.LONG,
        buy_date=DAY_1,
        buy_price=100.0,
        buy_volume=1,
        sell_date=exit_date,
        sell_price=105.0,
        sell_volume=1,
        realized_pnl=realized_pnl,
        roi=1.0,
    )


def test_equity_series_uses_daily_equity_when_available(
    make_strategy, reporter_factory
) -> None:
    """有 daily_equity 時採盯市口徑：節點數等於交易日數（＋起始資金節點）"""

    strategy = make_strategy(
        start_date=DAY_1, end_date=datetime.date(2024, 1, 5)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    # 只有一筆平倉紀錄，但盯市權益有 4 個交易日
    account.trade_records.append(
        make_closed_record(1, datetime.date(2024, 1, 5), 5000.0)
    )

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    reporter.trading_report = reporter.generate_trading_report()
    reporter.daily_equity = [
        {"Date": DAY_1, "Equity": 1000000.0},
        {"Date": datetime.date(2024, 1, 3), "Equity": 990000.0},  # 持倉期間被軋
        {"Date": datetime.date(2024, 1, 4), "Equity": 995000.0},
        {"Date": datetime.date(2024, 1, 5), "Equity": 1005000.0},
    ]

    series: pd.Series
    basis: str
    series, basis = reporter.get_equity_series()

    assert basis == StockBacktestReporter.EQUITY_BASIS_MARK_TO_MARKET

    # 4 個交易日 + 1 個起始資金節點
    assert len(series) == 5
    assert series.iloc[0] == 1000000.0
    assert series.index[0] == reporter.origin_date

    # 持倉期間的逆勢有出現在序列裡（已實現口徑會整段抹平）
    assert series.min() == 990000.0


def test_equity_series_falls_back_to_realized(make_strategy, reporter_factory) -> None:
    """沒有 daily_equity 時退回已實現口徑，行為與逐日權益上線前一致"""

    strategy = make_strategy(
        start_date=DAY_1, end_date=datetime.date(2024, 1, 31)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    account.trade_records.append(
        make_closed_record(1, datetime.date(2024, 1, 5), 5000.0)
    )
    account.trade_records.append(
        make_closed_record(2, datetime.date(2024, 1, 10), -3000.0)
    )

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    reporter.trading_report = reporter.generate_trading_report()
    reporter.daily_equity = None

    series: pd.Series
    basis: str
    series, basis = reporter.get_equity_series()

    assert basis == StockBacktestReporter.EQUITY_BASIS_REALIZED_ONLY

    # 起始資金 + 兩個平倉節點，持倉期間沒有任何節點
    assert len(series) == 3
    assert series.iloc[0] == 1000000.0
    assert series.iloc[1] == 1005000.0
    assert series.iloc[2] == 1002000.0


def test_equity_series_dedups_same_day_trades(make_strategy, reporter_factory) -> None:
    """同一天多筆平倉只取當日最後一筆，避免重複節點"""

    strategy = make_strategy(
        start_date=DAY_1, end_date=datetime.date(2024, 1, 31)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    exit_date: datetime.date = datetime.date(2024, 1, 5)
    account.trade_records.append(make_closed_record(1, exit_date, 5000.0))
    account.trade_records.append(make_closed_record(2, exit_date, -3000.0))

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    reporter.trading_report = reporter.generate_trading_report()

    series: pd.Series = reporter.get_equity_series()[0]

    assert len(series) == 2
    assert series.iloc[-1] == 1002000.0


def test_mark_to_market_mdd_is_deeper_than_realized(
    make_strategy, reporter_factory
) -> None:
    """同一組交易：盯市口徑的 MDD 必須比只認已實現的更深，否則沒修到問題"""

    strategy = make_strategy(
        start_date=DAY_1, end_date=datetime.date(2024, 1, 5)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    # 最終獲利 5000，但持倉期間一度虧到 -10000
    account.trade_records.append(
        make_closed_record(1, datetime.date(2024, 1, 5), 5000.0)
    )

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    reporter.trading_report = reporter.generate_trading_report()

    def mdd_of(series: pd.Series) -> float:
        """以序列算最大回撤（%）"""

        return round(float((series / series.cummax() - 1).min() * 100), 2)

    realized_mdd: float = mdd_of(reporter.get_equity_series()[0])

    reporter.daily_equity = [
        {"Date": DAY_1, "Equity": 1000000.0},
        {"Date": datetime.date(2024, 1, 3), "Equity": 990000.0},
        {"Date": datetime.date(2024, 1, 4), "Equity": 995000.0},
        {"Date": datetime.date(2024, 1, 5), "Equity": 1005000.0},
    ]
    mark_to_market_mdd: float = mdd_of(reporter.get_equity_series()[0])

    # 已實現口徑完全看不到回撤（權益一路向上）
    assert realized_mdd == 0.0
    assert mark_to_market_mdd == -1.0


def test_analyzer_mdd_matches_reporter_series(make_strategy, reporter_factory) -> None:
    """analyzer 與圖表必須同口徑：兩者算出的 MDD 要一致"""

    strategy = make_strategy(
        start_date=DAY_1, end_date=datetime.date(2024, 1, 5)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)
    account.trade_records.append(
        make_closed_record(1, datetime.date(2024, 1, 5), 5000.0)
    )

    daily_equity: List[Dict] = [
        {"Date": DAY_1, "Equity": 1000000.0},
        {"Date": datetime.date(2024, 1, 3), "Equity": 990000.0},
        {"Date": datetime.date(2024, 1, 4), "Equity": 995000.0},
        {"Date": datetime.date(2024, 1, 5), "Equity": 1005000.0},
    ]

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    reporter.trading_report = reporter.generate_trading_report()
    reporter.daily_equity = daily_equity

    series: pd.Series = reporter.get_equity_series()[0]
    reporter_mdd: float = round(float((series / series.cummax() - 1).min() * 100), 2)

    analyzer: StockBacktestAnalyzer = StockBacktestAnalyzer(strategy)

    assert analyzer.compute_mdd(daily_equity) == reporter_mdd

    # analyzer 的曲線同樣以初始資金為第一個節點
    assert analyzer.compute_equity_curve(daily_equity)[0] == 1000000.0
    assert len(analyzer.compute_equity_curve(daily_equity)) == len(series)


def test_everyday_equity_change_skipped_without_daily_equity(
    make_strategy, reporter_factory, monkeypatch: pytest.MonkeyPatch
) -> None:
    """沒有 daily_equity 時不畫盯市差分圖，避免畫出與已實現口徑重複的圖"""

    strategy = make_strategy(
        start_date=DAY_1, end_date=datetime.date(2024, 1, 31)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)
    account.trade_records.append(
        make_closed_record(1, datetime.date(2024, 1, 5), 5000.0)
    )

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    reporter.trading_report = reporter.generate_trading_report()
    reporter.daily_equity = None

    saved: List[str] = []
    monkeypatch.setattr(
        StockBacktestReporter,
        "save_figure",
        lambda self, fig, file_name="": saved.append(file_name),
    )

    reporter.plot_everyday_equity_change()

    assert saved == []
