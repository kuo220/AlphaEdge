import datetime
from pathlib import Path
from typing import Callable, Dict

import pandas as pd
import pytest

from core.backtest.backtester import Backtester
from core.backtest.factory import build_backtester
from core.backtest.report.reporter import StockBacktestReporter
from core.models import StockAccount, StockOrder, StockTradeRecord
from core.utils import Action, PositionType, ShortMethod

"""每日權益、多空分開統計與事件報表的測試"""


DAY_1: datetime.date = datetime.date(2024, 1, 2)


@pytest.fixture
def make_backtester(monkeypatch: pytest.MonkeyPatch) -> Callable[..., Backtester]:
    """建立不載入資料庫的 Backtester"""

    def _make_backtester(strategy) -> Backtester:
        monkeypatch.setattr(Backtester, "setup", lambda self: None)
        return build_backtester(strategy)

    return _make_backtester


def test_snapshot_daily_equity_includes_unrealized(
    make_strategy, make_backtester, make_quote
) -> None:
    """留倉放空的帳面虧損必須反映在每日權益，不能等到平倉才出現"""

    strategy = make_strategy(
        position_type=PositionType.SHORT,
        enable_intraday=False,
        short_method=ShortMethod.MARGIN,
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
        DAY_1, [make_quote(date=DAY_1, cur_price=100.0, high=101.0, low=99.0)]
    )

    # 開倉當日：現金 1000000 − 90422 + 部位（保證金 90000 + 未實現 0）
    assert backtester.daily_equity[0]["Equity"] == 999578.0

    # 次日股價上漲 5 元，未實現虧損 5000 應立刻反映在權益上
    day_2: datetime.date = datetime.date(2024, 1, 3)
    backtester.execute_bar(
        day_2, [make_quote(date=day_2, cur_price=105.0, high=106.0, low=104.0)]
    )

    assert backtester.account.get_positions()[0].unrealized_pnl == -5000.0
    assert backtester.daily_equity[1]["Equity"] == 994578.0
    assert backtester.account.realized_pnl == 0.0  # 尚未平倉，已實現損益仍為 0


def test_trading_report_columns_and_symbol(
    make_strategy, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """
    報表的欄位名與識別欄位取值

    引擎內部改用 symbol 之後，輸出欄位名必須維持 `Stock ID`——
    改名會讓 915 筆 LONG baseline 失效。但回歸雙線是自行從 trade_records 組表的，
    完全不經過 reporter，故欄位名與取值只能靠本測試把關。
    """

    monkeypatch.setattr(StockBacktestReporter, "setup", lambda self: None)

    strategy = make_strategy(
        start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 3, 31)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    account.trade_records.append(
        StockTradeRecord(
            id=1,
            stock_id="2330",
            is_closed=True,
            position_type=PositionType.LONG,
            buy_date=DAY_1,
            buy_price=100.0,
            buy_volume=1,
            sell_date=datetime.date(2024, 1, 5),
            sell_price=105.0,
            sell_volume=1,
            realized_pnl=4548.0,
            roi=4.53,
        )
    )

    reporter: StockBacktestReporter = StockBacktestReporter(strategy, tmp_path)
    reporter.account = account
    report: pd.DataFrame = reporter.generate_trading_report()

    # 欄位名維持台股語意，且順序不變（baseline 逐欄比對依賴此順序）
    assert list(report.columns)[:3] == ["Stock ID", "Position Type", "Entry Date"]
    assert "Symbol" not in report.columns

    # 取值來自 model 的 symbol，不是空字串
    assert report.loc[0, "Stock ID"] == "2330"
    assert report.loc[0, "Stock ID"] == account.trade_records[0].symbol


def test_direction_summary_and_event_report(
    make_strategy, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    """多空分開統計與事件計數需正確輸出"""

    monkeypatch.setattr(StockBacktestReporter, "setup", lambda self: None)

    strategy = make_strategy(
        start_date=datetime.date(2024, 1, 1), end_date=datetime.date(2024, 3, 31)
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    account.trade_records.append(
        StockTradeRecord(
            id=1,
            stock_id="2330",
            is_closed=True,
            position_type=PositionType.SHORT,
            short_method=ShortMethod.MARGIN,
            sell_date=DAY_1,
            sell_price=100.0,
            buy_date=datetime.date(2024, 1, 12),
            buy_price=95.0,
            commission=82.0,
            tax=300.0,
            borrow_fee=80.0,
            interest=10.0,
            margin=90000.0,
            holding_days=10,
            realized_pnl=4548.0,
            roi=4.53,
            roi_on_capital=5.03,
        )
    )
    account.trade_records.append(
        StockTradeRecord(
            id=2,
            stock_id="2317",
            is_closed=True,
            position_type=PositionType.LONG,
            buy_date=DAY_1,
            buy_price=50.0,
            sell_date=datetime.date(2024, 1, 5),
            sell_price=48.0,
            commission=40.0,
            tax=144.0,
            realized_pnl=-2184.0,
            roi=-4.37,
        )
    )

    reporter: StockBacktestReporter = StockBacktestReporter(strategy, tmp_path)
    reporter.account = account
    reporter.trading_report = reporter.generate_trading_report()

    summary: pd.DataFrame = reporter.generate_direction_summary()
    short_row: pd.Series = summary[summary["Position Type"] == "SHORT"].iloc[0]
    long_row: pd.Series = summary[summary["Position Type"] == "LONG"].iloc[0]

    assert short_row["Trades"] == 1
    assert short_row["Win Rate (%)"] == 100.0
    assert short_row["Total Borrow Fee"] == 80.0
    assert short_row["Total Interest"] == 10.0
    assert short_row["Avg Holding Days"] == 10.0
    assert long_row["Total PnL"] == -2184.0
    assert long_row["Total Borrow Fee"] == 0.0

    events: Dict[str, int] = {"forced_cover_day_trade": 3, "limit_up_cover_failed": 1}
    event_df: pd.DataFrame = reporter.generate_event_report(events)

    assert set(event_df["Event"]) == set(events.keys())
    assert event_df[event_df["Event"] == "limit_up_cover_failed"]["Count"].iloc[0] == 1


def test_analyzer_direction_metrics(make_strategy) -> None:
    """analyzer 的多空分開指標與放空成本統計"""

    from core.backtest.analysis.analyzer import StockBacktestAnalyzer

    strategy = make_strategy()
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    account.trade_records.append(
        StockTradeRecord(
            id=1,
            stock_id="2330",
            is_closed=True,
            position_type=PositionType.SHORT,
            sell_date=DAY_1,
            sell_price=100.0,
            buy_date=datetime.date(2024, 1, 12),
            buy_price=95.0,
            borrow_fee=80.0,
            interest=10.0,
            holding_days=10,
            realized_pnl=4548.0,
            roi=4.53,
        )
    )
    account.trade_records.append(
        StockTradeRecord(
            id=2,
            stock_id="2317",
            is_closed=True,
            position_type=PositionType.LONG,
            buy_date=DAY_1,
            buy_price=50.0,
            sell_date=datetime.date(2024, 1, 5),
            sell_price=48.0,
            realized_pnl=-2184.0,
            roi=-4.37,
        )
    )

    analyzer: StockBacktestAnalyzer = StockBacktestAnalyzer(strategy)

    assert analyzer.compute_trade_count_by_direction() == {"SHORT": 1, "LONG": 1}
    assert analyzer.compute_pnl_by_direction() == {"SHORT": 4548.0, "LONG": -2184.0}
    assert analyzer.compute_short_cost() == {
        "borrow_fee": 80.0,
        "interest": 10.0,
        "dividend_compensation": 0.0,
    }
    assert analyzer.compute_average_holding_days() == 5.0


# === 分割調整：reporter 與 analyzer 必須共用同一份 ===
def test_split_adjustment_removes_the_fake_gap() -> None:
    """
    0050 在 2025-06-18 一拆四，調整後序列不可出現假跳空

    `stock_dividend` 只記除權息、**不含分割**，所以還原價的累積因子在分割日
    前後完全相同（實測皆為 1.4545），原始收盤價卻由 188.65 掉到 47.57。
    少了這道調整，任何跨過該日的序列都會多出一天 −75% 的假跌幅。
    """

    from core.api.tw.stock_split import apply_split_adjustment

    raw: pd.Series = pd.Series(
        [188.65, 47.57, 47.10],
        index=[
            datetime.date(2025, 6, 10),
            datetime.date(2025, 6, 18),
            datetime.date(2025, 6, 19),
        ],
    )

    adjusted: pd.Series = apply_split_adjustment(raw, "0050")

    assert adjusted.loc[datetime.date(2025, 6, 10)] == pytest.approx(188.65)
    assert adjusted.loc[datetime.date(2025, 6, 18)] == pytest.approx(47.57 * 4)
    # 調整後跨分割日的單日變動回到常態（原本是 −74.8%）
    change: float = (
        adjusted.loc[datetime.date(2025, 6, 18)]
        / adjusted.loc[datetime.date(2025, 6, 10)]
        - 1
    )
    assert abs(change) < 0.05


def test_split_adjustment_leaves_unlisted_stocks_alone() -> None:
    """沒有分割紀錄的個股原樣回傳，不做任何調整"""

    from core.api.tw.stock_split import apply_split_adjustment

    raw: pd.Series = pd.Series([100.0, 101.0], index=[DAY_1, datetime.date(2024, 1, 3)])

    assert apply_split_adjustment(raw, "2330").equals(raw)


def test_reporter_delegates_split_adjustment_to_the_shared_table() -> None:
    """
    reporter 不可自留一份分割表

    分割表寫在誰身上，另一邊就得再抄一次；抄漏一次分割的代價是整段序列
    從那天起錯 N 倍（F-087 的教訓）。這條測試釘住「只有一份」。
    """

    from core.api.tw import stock_split

    assert not hasattr(StockBacktestReporter, "STOCK_SPLITS")

    raw: pd.Series = pd.Series(
        [188.65, 47.57],
        index=[datetime.date(2025, 6, 10), datetime.date(2025, 6, 18)],
    )
    reporter: StockBacktestReporter = StockBacktestReporter.__new__(
        StockBacktestReporter
    )

    assert reporter._get_adjusted_price(raw, "0050").equals(
        stock_split.apply_split_adjustment(raw, "0050")
    )
