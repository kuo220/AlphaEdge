from .base import BaseStrategy

"""Main entry point for strategy modules, including stocks, futures, etc"""

# 刻意不在此 eager import StrategyLoader：它會拉進整個 stock 套件，
# 而策略基底需要 import core.backtest.datafeed 的型別，形成循環
# （與 core/backtest/__init__.py 同一類問題，見 backlog Phase2-4、Phase2-7）。
