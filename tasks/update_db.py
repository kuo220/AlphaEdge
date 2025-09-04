import argparse
import datetime
from typing import Dict

from loguru import logger

from trader.pipeline.updaters.financial_statement_updater import (
    FinancialStatementUpdater,
)
from trader.pipeline.updaters.monthly_revenue_report_updater import (
    MonthlyRevenueReportUpdater,
)
from trader.pipeline.updaters.stock_chip_updater import StockChipUpdater
from trader.pipeline.updaters.stock_price_updater import StockPriceUpdater
# from trader.pipeline.updaters.stock_tick_updater import StockTickUpdater
from trader.pipeline.utils import DataType

"""
* 所有資料爬蟲起始日（除了 Tick）
- From: 2013 (ROC: 102)/1/1 ~ present

* 財報申報期限
一般行業：
- Q1：5月15日
- Q2：8月14日
- Q3：11月14日
- 年報：3月31日


* Shioaji 台股 ticks 資料時間表：
- From: 2020/03/02 ~ Today
- 目前資料庫資料時間：
- From 2020/04/01 ~ 2024/05/10

"""

"""
* update_all.py 使用方式說明 *

- Description:
    本檔案為資料更新系統的主程式入口，可根據參數選擇要更新的資料類型（如 tick, chip, price 等）。

- Parameters:
    - --target: List[str]
        欲更新的資料類型，可選：
            - tick: 僅更新 tick 資料
            - chip: 僅更新三大法人籌碼資料
            - price: 僅更新收盤價資料
            - fs: 僅更新財報資料
            - mrr: 僅更新月營收報表
            - all: 更新所有資料（包含 tick）
            - no_tick: 更新所有資料（不包含 tick）

        預設為 no_tick，可同時指定多個目標
        E.g. python -m tasks.update_db --target chip price tick

- Usage Example:
    - 僅更新 tick：
        python -m tasks.update_db.py --target tick

    - 更新三大法人與收盤價：
        python -m tasks.update_db.py --target chip price

    - 更新所有資料（不含 tick）：
        python -m tasks.update_db.py --target no_tick
        or
        python -m tasks.update_db.py

    - 更新所有資料（含 tick）：
        python -m tasks.update_db.py --target all
"""


def parse_arguments() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Update stock-related databases"
    )

    parser.add_argument(
        "--target",
        nargs="+",
        choices=[dt.name.lower() for dt in DataType] + ["all", "no_tick"],
        default=["no_tick"],
        help="Targets to update (default: no_tick)",
    )
    return parser.parse_args()


def get_update_time_config() -> Dict[str, datetime.date | int]:
    return {
        "start_date": datetime.date(2013, 1, 1),
        # "end_date": datetime.date.today(),
        "end_date": datetime.date(2025, 9, 1),
        "start_year": 2013,
        "end_year": 2025,
        "start_month": 1,
        "end_month": 12,
        "start_season": 1,
        "end_season": 4,
    }


def main() -> None:
    args: argparse.Namespace = parse_arguments()
    targets: set[str] = set(args.target)

    # no_tick = 所有資料類型 - tick
    if "no_tick" in targets:
        targets.update(dt.name.lower() for dt in DataType if dt != DataType.TICK)

    # Time Config
    time_config: Dict[str, datetime.date | int] = get_update_time_config()

    if DataType.TICK.name.lower() in targets:
        stock_tick_updater = StockTickUpdater()
        stock_tick_updater.update(
            start_date=time_config["start_date"], end_date=time_config["end_date"]
        )

    if DataType.CHIP.name.lower() in targets:
        stock_chip_updater = StockChipUpdater()
        stock_chip_updater.update(
            start_date=time_config["start_date"], end_date=time_config["end_date"]
        )

    if DataType.PRICE.name.lower() in targets:
        stock_price_updater = StockPriceUpdater()
        stock_price_updater.update(
            start_date=time_config["start_date"], end_date=time_config["end_date"]
        )

    if DataType.FS.name.lower() in targets:
        fs_updater = FinancialStatementUpdater()
        fs_updater.update(
            start_year=time_config["start_year"],
            end_year=time_config["end_year"],
            start_season=time_config["start_season"],
            end_season=time_config["end_season"],
        )

    if DataType.MRR.name.lower() in targets:
        mrr_updater = MonthlyRevenueReportUpdater()
        mrr_updater.update(
            start_year=time_config["start_year"],
            end_year=time_config["end_year"],
            start_month=time_config["start_month"],
            end_month=time_config["end_month"],
        )

    logger.info(f"✅ Database Update Completed. Updated: {', '.join(sorted(targets))}")


if __name__ == "__main__":
    main()
