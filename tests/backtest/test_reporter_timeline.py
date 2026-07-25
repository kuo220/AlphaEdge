import datetime
from pathlib import Path
from typing import Callable, List

import pandas as pd
import pytest

from core.backtest.report.reporter import StockBacktestReporter
from core.models import StockAccount, StockTradeRecord
from core.utils import PositionType

"""報表時間軸測試：SHORT 的損益必須落在回補日而非開倉日（對應 backlog §2.6、§5.9）"""


@pytest.fixture
def reporter_factory(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> Callable[..., StockBacktestReporter]:
    """建立不連資料庫的 reporter（setup 只負責載入 benchmark 價格，測試用不到）"""

    def _factory(strategy, account: StockAccount) -> StockBacktestReporter:
        monkeypatch.setattr(StockBacktestReporter, "setup", lambda self: None)

        reporter: StockBacktestReporter = StockBacktestReporter(strategy, tmp_path)
        reporter.account = account
        return reporter

    return _factory


def test_report_timeline_uses_exit_date(make_strategy, reporter_factory) -> None:
    """跨月放空的損益要出現在回補日（5 月），不是放空開倉日（3 月）"""

    strategy = make_strategy(
        start_date=datetime.date(2024, 3, 1),
        end_date=datetime.date(2024, 5, 31),
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    # 3 月放空、5 月回補
    account.trade_records.append(
        StockTradeRecord(
            id=1,
            stock_id="2330",
            is_closed=True,
            position_type=PositionType.SHORT,
            sell_date=datetime.date(2024, 3, 1),
            sell_price=100.0,
            sell_volume=1,
            buy_date=datetime.date(2024, 5, 1),
            buy_price=95.0,
            buy_volume=1,
            realized_pnl=4548.0,
            roi=4.53,
        )
    )

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    df: pd.DataFrame = reporter.generate_trading_report()

    assert df.loc[0, "Exit Date"] == datetime.date(2024, 5, 1)
    assert df.loc[0, "Entry Date"] == datetime.date(2024, 3, 1)

    # 累積餘額掛在回補日，不是開倉日
    assert df.loc[0, "Cumulative Balance"] == 1004548.0
    assert df.loc[0, "Exit Date"] != df.loc[0, "Entry Date"]


def test_report_sorted_by_exit_date(make_strategy, reporter_factory) -> None:
    """報表排序依平倉日；先開倉的放空若較晚回補，應排在後面"""

    strategy = make_strategy(
        start_date=datetime.date(2024, 3, 1),
        end_date=datetime.date(2024, 6, 30),
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    # 3 月開、6 月回補的放空
    account.trade_records.append(
        StockTradeRecord(
            id=1,
            stock_id="2330",
            is_closed=True,
            position_type=PositionType.SHORT,
            sell_date=datetime.date(2024, 3, 1),
            sell_price=100.0,
            buy_date=datetime.date(2024, 6, 1),
            buy_price=95.0,
            realized_pnl=1000.0,
        )
    )
    # 4 月買、4 月賣的做多
    account.trade_records.append(
        StockTradeRecord(
            id=2,
            stock_id="2317",
            is_closed=True,
            position_type=PositionType.LONG,
            buy_date=datetime.date(2024, 4, 1),
            buy_price=50.0,
            sell_date=datetime.date(2024, 4, 10),
            sell_price=55.0,
            realized_pnl=2000.0,
        )
    )

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    df: pd.DataFrame = reporter.generate_trading_report()

    exit_dates: List[datetime.date] = list(df["Exit Date"])
    assert exit_dates == [datetime.date(2024, 4, 10), datetime.date(2024, 6, 1)]

    # 累積損益依平倉順序累加
    assert list(df["Cumulative PnL"]) == [2000.0, 3000.0]


def test_long_record_timeline_unchanged(make_strategy, reporter_factory) -> None:
    """LONG 的 exit_date 等於 sell_date，報表時間軸與修改前一致"""

    strategy = make_strategy(
        start_date=datetime.date(2024, 1, 1),
        end_date=datetime.date(2024, 1, 31),
    )
    account: StockAccount = StockAccount(1000000.0)
    strategy.setup_account(account)

    account.trade_records.append(
        StockTradeRecord(
            id=1,
            stock_id="2330",
            is_closed=True,
            position_type=PositionType.LONG,
            buy_date=datetime.date(2024, 1, 2),
            buy_price=100.0,
            sell_date=datetime.date(2024, 1, 10),
            sell_price=110.0,
            realized_pnl=9581.0,
        )
    )

    reporter: StockBacktestReporter = reporter_factory(strategy, account)
    df: pd.DataFrame = reporter.generate_trading_report()

    assert df.loc[0, "Exit Date"] == df.loc[0, "Sell Date"]
    assert df.loc[0, "Entry Date"] == df.loc[0, "Buy Date"]
