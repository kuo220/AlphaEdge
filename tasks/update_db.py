import argparse
import datetime
from typing import Dict, Set, Union

from loguru import logger

from core.pipeline.updaters.financial_statement_updater import (
    FinancialStatementUpdater,
)
from core.pipeline.updaters.finmind_updater import FinMindUpdater
from core.pipeline.updaters.monthly_revenue_report_updater import (
    MonthlyRevenueReportUpdater,
)
from core.pipeline.updaters.stock_chip_updater import StockChipUpdater
from core.pipeline.updaters.stock_price_updater import StockPriceUpdater
from core.pipeline.updaters.stock_tick_updater import StockTickUpdater
from core.config import (
    DEFAULT_CHIP_PRICE_START_DATE,
    DEFAULT_END_MONTH,
    DEFAULT_START_YEAR,
    FINMIND_BROKER_TRADING_END_DATE,
    FINMIND_BROKER_TRADING_START_DATE,
    TICK_UPDATE_START_DATE,
)
from core.pipeline.utils import DataType, FinMindDataType

"""
資料更新任務主程式 (update_db)

本模組為資料更新系統的入口，依 --target 參數選擇要更新的資料類型，
可單一更新或一次指定多個目標。預設為 no_tick（更新所有資料但不含 tick）。

================================================================================
參考：財報申報期限（一般行業）
================================================================================
  Q1    5月15日
  Q2    8月14日
  Q3    11月14日
  年報  3月31日

================================================================================
參考：Shioaji 台股 ticks 資料時間
================================================================================
  可取得區間  2020/03/02 ~ 今日
  目前 DB    2020/04/01 ~ 2024/05/10（依實際維護為準）

================================================================================
參數說明
================================================================================

  --target  <target> [<target> ...]
      欲更新的資料類型，可多選。未指定時預設為 no_tick。
      選項見下方「Target 對照表」。

================================================================================
Target 對照表
================================================================================

  選項                        說明
  -------------------------  -----------------------------------------------
  tick                        逐筆成交 (Shioaji ticks)
  chip                        三大法人籌碼
  price                       收盤價
  fs                          財報 (Financial Statement)
  mrr                         月營收報表 (Monthly Revenue Report)
  finmind                     全部 FinMind（台股總覽 + 證券商 + 券商分點）
  stock_info                  FinMind 台股總覽（不含權證）
  stock_info_with_warrant     FinMind 台股總覽（含權證）
  broker_info                 FinMind 證券商資訊
  broker_trading              FinMind 券商分點統計
  all                         全部資料（含 tick）
  no_tick                     全部資料（不含 tick，預設）

================================================================================
各資料更新指令（單一 target）
================================================================================

  # 逐筆成交
  python -m tasks.update_db --target tick

  # 三大法人籌碼
  python -m tasks.update_db --target chip

  # 收盤價
  python -m tasks.update_db --target price

  # 財報
  python -m tasks.update_db --target fs

  # 月營收報表
  python -m tasks.update_db --target mrr

  # 全部 FinMind（台股總覽 + 證券商 + 券商分點）
  python -m tasks.update_db --target finmind

  # FinMind 台股總覽（不含權證）
  python -m tasks.update_db --target stock_info

  # FinMind 台股總覽（含權證）
  python -m tasks.update_db --target stock_info_with_warrant

  # FinMind 證券商資訊
  python -m tasks.update_db --target broker_info

  # FinMind 券商分點統計
  python -m tasks.update_db --target broker_trading

  # 全部資料（含 tick）
  python -m tasks.update_db --target all

  # 全部資料（不含 tick，等同預設）
  python -m tasks.update_db --target no_tick
  或
  python -m tasks.update_db

================================================================================
組合更新範例（多個 target）
================================================================================

  python -m tasks.update_db --target chip price
  python -m tasks.update_db --target chip price tick
  python -m tasks.update_db --target stock_info broker_trading
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
        return {
            "start_date": TICK_UPDATE_START_DATE,
            "end_date": datetime.date.today(),
        }
    elif data_type == DataType.CHIP or data_type == DataType.PRICE:
        return {
            "start_date": DEFAULT_CHIP_PRICE_START_DATE,
            "end_date": datetime.date.today(),
        }
    elif data_type == DataType.FS:
        return {
            "start_year": DEFAULT_START_YEAR,
            "end_year": datetime.date.today().year,
            "start_season": 1,
            "end_season": 4,
        }
    elif data_type == DataType.MRR:
        return {
            "start_year": DEFAULT_START_YEAR,
            "end_year": datetime.date.today().year,
            "start_month": 1,
            "end_month": DEFAULT_END_MONTH,
        }
    elif data_type == DataType.FINMIND:
        return {
            "start_date": FINMIND_BROKER_TRADING_START_DATE,
            "end_date": FINMIND_BROKER_TRADING_END_DATE,
        }
    elif data_type == FinMindDataType.BROKER_TRADING or (
        isinstance(data_type, str)
        and data_type.lower() == FinMindDataType.BROKER_TRADING.value.lower()
    ):
        return {
            "start_date": FINMIND_BROKER_TRADING_START_DATE,
            "end_date": FINMIND_BROKER_TRADING_END_DATE,
        }
    else:
        return {
            "start_date": DEFAULT_CHIP_PRICE_START_DATE,
            "end_date": datetime.date.today(),
            "start_year": DEFAULT_START_YEAR,
            "end_year": datetime.date.today().year,
            "start_month": 1,
            "end_month": DEFAULT_END_MONTH,
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
