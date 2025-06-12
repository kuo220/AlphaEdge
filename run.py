import argparse
from typing import Dict, Type

from trader.strategies.stock import BaseStockStrategy
from trader.strategies import StrategyLoader
from trader.backtest import Backtester

"""
run.py

This is the main entry point of the trading system.
It is responsible for executing either backtesting or live trading based on the selected mode.

Modules and strategy logic are imported from the internal package structure.
Make sure to run this file from the project root to ensure all relative imports work correctly.

Example:
    python run.py          # default behavior (e.g., backtest)
    python run.py live     # switch to live trading mode
"""


def parse_arguments():
    parser = argparse.ArgumentParser(description="Trading System")
    
    parser.add_argument('--mode', choices=["backtest", "live"], default="backtest")
    parser.add_argument('--strategy', type=str, required=True, help='Name of the strategy class')
    
    return parser.parse_args()


def main():
    args = parse_arguments()
    strategy_name = args.strategy
    
    strategies: Dict[str, Type[BaseStockStrategy]] = StrategyLoader.load_all_stock_strategies()
    
    if strategy_name not in strategies:
        print(f"Strategy '{strategy_name}' not found. Please check the spelling or ensure it is registered.")
        print(f"Available strategies: {list(strategies.keys())}")
        return

    # Initialize strategy
    strategy = strategies[strategy_name]()
    
    # Backtest or Live Trading
    if args.mode == "backtest":
        backtester = Backtester(strategy)
        backtester.run()
    elif args.mode == "live":
        pass


if __name__ == "__main__":
    main()