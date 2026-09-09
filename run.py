import argparse
from typing import Dict, Type

from core.backtest.backtester import Backtester
from core.backtest.factory import build_backtester
from core.config import SHOW_FIGURES_ENV_VAR, resolve_show_figures
from core.strategies.base import BaseStrategy
from core.strategies.strategy_loader import StrategyLoader

"""Main entry point of the trading system: run backtest or live trading from project root"""


# -----------------------------------------------------------------------
# run.py 使用方式說明
# -----------------------------------------------------------------------
# Description: 本檔案為交易系統主程式入口，用於執行指定策略的回測或實盤
# Parameters: --mode (backtest | live), --strategy (策略類別名稱，必填)
# Example: python run.py --strategy MeanReversion
# Notes: Strategy Name 為 Class 名稱
#


def parse_arguments() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Trading System"
    )

    parser.add_argument("--mode", choices=["backtest", "live"], default="backtest")
    parser.add_argument(
        "--strategy", type=str, required=True, help="Name of the strategy class"
    )
    # 回測畫完的五張圖要不要在瀏覽器開起來（健檢 F-067）。**預設不開**：
    # 舊版寫死開啟，每跑一次回測就彈出 5 個分頁，批次掃參數時一次開幾十個，
    # 在無頭環境（CI、容器、nohup）更是直接失敗。圖本來就會存成 PNG。
    show_group = parser.add_mutually_exclusive_group()
    show_group.add_argument(
        "--show",
        dest="show",
        action="store_true",
        default=None,
        help="回測結束後在瀏覽器開啟圖表",
    )
    show_group.add_argument(
        "--no-show",
        dest="show",
        action="store_false",
        help=f"不開啟圖表（未指定時依環境變數 {SHOW_FIGURES_ENV_VAR}，預設不開）",
    )

    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = parse_arguments()
    strategy_name: str = args.strategy

    strategies: Dict[str, Type[BaseStrategy]] = StrategyLoader.load_strategies()

    if strategy_name not in strategies:
        print(
            f"Strategy '{strategy_name}' not found. Please check the spelling or ensure it is registered."
        )
        print(f"Available strategies: {list(strategies.keys())}")
        return

    # Initialize strategy
    strategy: BaseStrategy = strategies[strategy_name]()

    # Backtest or Live Trading
    if args.mode == "backtest":
        backtester: Backtester = build_backtester(strategy)
        # 命令列旗標優先於環境變數；兩者都沒給就是不開圖
        backtester.show_figures = (
            resolve_show_figures() if args.show is None else args.show
        )
        backtester.run()
    elif args.mode == "live":
        pass


if __name__ == "__main__":
    main()
