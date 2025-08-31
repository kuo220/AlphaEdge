import argparse
from typing import Dict, Type

from trader.backtest import Backtester
from trader.strategies import StrategyLoader
from trader.strategies.stock import BaseStockStrategy

"""
run.py

This is the main entry point of the trading system.
It is responsible for executing either backtesting or live trading based on the selected mode.

Modules and strategy logic are imported from the internal package structure.
Make sure to run this file from the project root to ensure all relative imports work correctly.
"""


"""
* run.py 使用方式說明 *

- Description:
    本檔案為交易系統的主程式入口，用於執行指定策略的回測或實盤操作。

- Parameters:
    - --mode: str
        執行模式，可選 "backtest" 或 "live"，預設為 "backtest"
    - --strategy: str
        指定要使用的策略類別名稱（必填）

- Usage Example:
    - 執行回測模式，使用名為 "MeanReversion" 的策略：
        python run.py --strategy MeanReversion

    - 執行實盤模式，使用名為 "Momentum" 的策略：
        python run.py --mode live --strategy Momentum
"""


def parse_arguments() -> argparse.Namespace:
    parser: argparse.ArgumentParser = argparse.ArgumentParser(
        description="Trading System"
    )

    parser.add_argument("--mode", choices=["backtest", "live"], default="backtest")
    parser.add_argument(
        "--strategy", type=str, required=True, help="Name of the strategy class"
    )

    return parser.parse_args()


def main() -> None:
    args: argparse.Namespace = parse_arguments()
    strategy_name: str = args.strategy

    strategies: Dict[str, Type[BaseStockStrategy]] = (
        StrategyLoader.load_stock_strategies()
    )

    if strategy_name not in strategies:
        print(
            f"Strategy '{strategy_name}' not found. Please check the spelling or ensure it is registered."
        )
        print(f"Available strategies: {list(strategies.keys())}")
        return

    # Initialize strategy
    strategy: BaseStockStrategy = strategies[strategy_name]()

    # Backtest or Live Trading
    if args.mode == "backtest":
        backtester = Backtester(strategy)
        backtester.run()
    elif args.mode == "live":
        pass


if __name__ == "__main__":
    main()
