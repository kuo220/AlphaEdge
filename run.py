import argparse
from typing import Dict, Type

from trader.backtest import Backtester
from trader.strategies import StrategyLoader
from trader.strategies.stock import BaseStockStrategy


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
        backtester: Backtester = Backtester(strategy)
        backtester.run()
    elif args.mode == "live":
        pass


if __name__ == "__main__":
    main()
