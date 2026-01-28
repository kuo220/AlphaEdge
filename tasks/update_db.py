import argparse
import datetime
from typing import Dict, Set, Union

from loguru import logger

from trader.pipeline.updaters.financial_statement_updater import (
    FinancialStatementUpdater,
)
from trader.pipeline.updaters.finmind_updater import FinMindUpdater
from trader.pipeline.updaters.monthly_revenue_report_updater import (
    MonthlyRevenueReportUpdater,
)
from trader.pipeline.updaters.stock_chip_updater import StockChipUpdater
from trader.pipeline.updaters.stock_price_updater import StockPriceUpdater
from trader.pipeline.updaters.stock_tick_updater import StockTickUpdater
from trader.pipeline.utils import DataType, FinMindDataType

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
            - finmind: 更新所有 FinMind 資料（台股總覽、證券商資訊、券商分點統計）
            - stock_info: 僅更新 FinMind 台股總覽（不含權證）
            - stock_info_with_warrant: 僅更新 FinMind 台股總覽（含權證）
            - broker_info: 僅更新 FinMind 證券商資訊
            - broker_trading: 僅更新 FinMind 券商分點統計
            - all: 更新所有資料（包含 tick）
            - no_tick: 更新所有資料（不包含 tick）

        預設為 no_tick，可同時指定多個目標
        E.g. python -m tasks.update_db --target chip price tick

- Usage Example:
    - 僅更新 tick：
        python -m tasks.update_db --target tick

    - 更新三大法人與收盤價：
        python -m tasks.update_db --target chip price

    - 更新所有 FinMind 資料：
        python -m tasks.update_db --target finmind

    - 僅更新 FinMind 台股總覽（不含權證）：
        python -m tasks.update_db --target stock_info

    - 僅更新 FinMind 台股總覽（含權證）：
        python -m tasks.update_db --target stock_info_with_warrant

    - 僅更新 FinMind 券商分點統計：
        python -m tasks.update_db --target broker_trading

    - 更新所有資料（不含 tick）：
        python -m tasks.update_db --target no_tick
        or
        python -m tasks.update_db

    - 更新所有資料（含 tick）：
        python -m tasks.update_db --target all
"""


def parse_arguments() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Update stock-related databases"
    )

    parser.add_argument(
        "--target",
        nargs="+",
        choices=[dt.name.lower() for dt in DataType]
        + [
            "all",
            "no_tick",
        ]
        + [dt.value.lower() for dt in FinMindDataType],
        default=["no_tick"],
        help="Targets to update (default: no_tick)",
    )
    return parser.parse_args()


def get_update_time_config(
    data_type: Union[DataType, str, None] = None,
) -> Dict[str, datetime.date | int]:
    """
    根據不同的資料類型返回對應的時間區間設定

    Args:
        data_type: 資料類型，如果為 None 則返回通用設定

    Returns:
        包含時間區間設定的字典
    """
    if data_type == DataType.TICK:
        # TICK 資料：從 2020/03/02 開始
        return {
            "start_date": datetime.date(2024, 5, 10),
            "end_date": datetime.date.today(),
        }
    elif data_type == DataType.CHIP or data_type == DataType.PRICE:
        # CHIP 和 PRICE 資料：從 2013/1/1 開始
        return {
            "start_date": datetime.date(2013, 1, 1),
            "end_date": datetime.date.today(),
        }
    elif data_type == DataType.FS:
        # 財報資料：使用年份和季度
        return {
            "start_year": 2013,
            "end_year": datetime.date.today().year,
            "start_season": 1,
            "end_season": 4,
        }
    elif data_type == DataType.MRR:
        # 月營收報表：使用年份和月份
        return {
            "start_year": 2013,
            "end_year": datetime.date.today().year,
            "start_month": 1,
            "end_month": 12,
        }
    elif data_type == DataType.FINMIND:
        # FinMind 所有資料：券商分點統計從 2021/6/30 開始
        return {
            "start_date": datetime.date(2021, 6, 30),
            "end_date": datetime.date(2026, 1, 23),
        }
    elif data_type == FinMindDataType.BROKER_TRADING or (
        isinstance(data_type, str)
        and data_type.lower() == FinMindDataType.BROKER_TRADING.value.lower()
    ):
        # FinMind 券商分點統計：從 2021/6/30 開始
        return {
            "start_date": datetime.date(2021, 6, 30),
            "end_date": datetime.date.today(),
        }
    else:
        # 預設通用設定（向後兼容）
        return {
            "start_date": datetime.date(2013, 1, 1),
            "end_date": datetime.date.today(),
            "start_year": 2013,
            "end_year": datetime.date.today().year,
            "start_month": 1,
            "end_month": 12,
            "start_season": 1,
            "end_season": 4,
        }


def main() -> None:
    args: argparse.Namespace = parse_arguments()
    targets: Set[str] = set(args.target)

    # all = 所有資料類型（包含 tick 和 finmind）
    if "all" in targets:
        targets.update(dt.name.lower() for dt in DataType)

    # no_tick = 所有資料類型 - tick（包含 finmind）
    if "no_tick" in targets:
        targets.update(dt.name.lower() for dt in DataType if dt != DataType.TICK)

    if DataType.TICK.name.lower() in targets:
        time_config: Dict[str, datetime.date | int] = get_update_time_config(
            DataType.TICK
        )
        stock_tick_updater: StockTickUpdater = StockTickUpdater()
        stock_tick_updater.update(
            start_date=time_config["start_date"], end_date=time_config["end_date"]
        )

    if DataType.CHIP.name.lower() in targets:
        time_config: Dict[str, datetime.date | int] = get_update_time_config(
            DataType.CHIP
        )
        stock_chip_updater: StockChipUpdater = StockChipUpdater()
        stock_chip_updater.update(
            start_date=time_config["start_date"], end_date=time_config["end_date"]
        )

    if DataType.PRICE.name.lower() in targets:
        time_config: Dict[str, datetime.date | int] = get_update_time_config(
            DataType.PRICE
        )
        stock_price_updater: StockPriceUpdater = StockPriceUpdater()
        stock_price_updater.update(
            start_date=time_config["start_date"], end_date=time_config["end_date"]
        )

    if DataType.FS.name.lower() in targets:
        time_config: Dict[str, datetime.date | int] = get_update_time_config(
            DataType.FS
        )
        fs_updater: FinancialStatementUpdater = FinancialStatementUpdater()
        fs_updater.update(
            start_year=time_config["start_year"],
            end_year=time_config["end_year"],
            start_season=time_config["start_season"],
            end_season=time_config["end_season"],
        )

    if DataType.MRR.name.lower() in targets:
        time_config: Dict[str, datetime.date | int] = get_update_time_config(
            DataType.MRR
        )
        mrr_updater: MonthlyRevenueReportUpdater = MonthlyRevenueReportUpdater()
        mrr_updater.update(
            start_year=time_config["start_year"],
            end_year=time_config["end_year"],
            start_month=time_config["start_month"],
            end_month=time_config["end_month"],
        )

    # FinMind 資料更新
    if DataType.FINMIND.name.lower() in targets:
        time_config: Dict[str, datetime.date | int] = get_update_time_config(
            DataType.FINMIND
        )
        finmind_updater: FinMindUpdater = FinMindUpdater()
        finmind_updater.update_all(
            start_date=time_config["start_date"], end_date=time_config["end_date"]
        )

    # FinMind 子類型更新
    if FinMindDataType.STOCK_INFO.value.lower() in targets:
        finmind_updater: FinMindUpdater = FinMindUpdater()
        finmind_updater.update(data_type=FinMindDataType.STOCK_INFO)

    if FinMindDataType.STOCK_INFO_WITH_WARRANT.value.lower() in targets:
        finmind_updater: FinMindUpdater = FinMindUpdater()
        finmind_updater.update(data_type=FinMindDataType.STOCK_INFO_WITH_WARRANT)

    if FinMindDataType.BROKER_INFO.value.lower() in targets:
        finmind_updater: FinMindUpdater = FinMindUpdater()
        finmind_updater.update(data_type=FinMindDataType.BROKER_INFO)

    if FinMindDataType.BROKER_TRADING.value.lower() in targets:
        time_config: Dict[str, datetime.date | int] = get_update_time_config(
            FinMindDataType.BROKER_TRADING.value.lower()
        )
        finmind_updater: FinMindUpdater = FinMindUpdater()
        finmind_updater.update_broker_trading_daily_report(
            start_date=time_config["start_date"],
            end_date=time_config["end_date"],
        )

    logger.info(f"✅ Database Update Completed. Updated: {', '.join(sorted(targets))}")


if __name__ == "__main__":
    main()
