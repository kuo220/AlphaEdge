import argparse
import datetime
import sys
from pathlib import Path
from typing import List

import pandas as pd

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.backtest.backtester import Backtester
from core.strategies.stock.momentum_strategy_1 import MomentumStrategy1
from core.utils import TimeUtils
from core.utils.market_calendar import MarketCalendar

"""產生 LONG 策略的回歸 baseline：放空框架動程式碼前的第一步（見 backlog §9.0）"""


SNAPSHOT_DIR: Path = Path(__file__).resolve().parent / "snapshots"
BASELINE_FILE_NAME: str = "momentum_strategy_1_baseline.csv"

# baseline 期間：固定短區間即可達成回歸保護目的，不需跑完策略預設的五年
BASELINE_START_DATE: datetime.date = datetime.date(2024, 1, 1)
BASELINE_END_DATE: datetime.date = datetime.date(2024, 6, 30)


def run_backtest_without_report(strategy: MomentumStrategy1) -> Backtester:
    """跑完回測主迴圈但不產生圖表報告（繪圖與回歸比對無關且耗時）"""

    backtester: Backtester = Backtester(strategy)

    dates: List[datetime.date] = TimeUtils.generate_date_range(
        start_date=backtester.start_date, end_date=backtester.end_date
    )

    for date in dates:
        if not MarketCalendar.check_stock_market_open(api=backtester.price, date=date):
            continue

        backtester.run_day_backtest(date)

    backtester.account.update_account_status()
    return backtester


def generate_baseline() -> pd.DataFrame:
    """跑 MomentumStrategy1 並輸出交易明細，作為 LONG 路徑的回歸基準"""

    strategy: MomentumStrategy1 = MomentumStrategy1()
    strategy.start_date = BASELINE_START_DATE
    strategy.end_date = BASELINE_END_DATE

    backtester: Backtester = run_backtest_without_report(strategy)

    # 直接由 trade_records 組表，避免依賴 reporter（reporter 在 P1-5 會被改動）
    rows: List[dict] = [
        {
            "Stock ID": record.stock_id,
            "Position Type": record.position_type.value,
            "Buy Date": record.buy_date,
            "Buy Price": record.buy_price,
            "Buy Volume": record.buy_volume,
            "Sell Date": record.sell_date,
            "Sell Price": record.sell_price,
            "Sell Volume": record.sell_volume,
            "Commission": record.commission,
            "Tax": record.tax,
            "Transaction Cost": record.transaction_cost,
            "Realized PnL": record.realized_pnl,
            "ROI": record.roi,
        }
        for record in backtester.account.trade_records
        if record.is_closed
    ]

    df: pd.DataFrame = pd.DataFrame(rows)

    SNAPSHOT_DIR.mkdir(parents=True, exist_ok=True)
    df.to_csv(SNAPSHOT_DIR / BASELINE_FILE_NAME, index=False)

    print(f"* Baseline saved: {SNAPSHOT_DIR / BASELINE_FILE_NAME}")
    print(f"* Trades: {len(df)}")
    print(f"* Balance: {backtester.account.balance}")
    print(f"* Realized PnL: {backtester.account.realized_pnl}")
    return df


if __name__ == "__main__":
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Generate LONG regression baseline"
    )
    parser.parse_args()

    generate_baseline()
