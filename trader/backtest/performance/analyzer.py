"""
analyzer.py

Provides analytical tools for evaluating trading strategy performance during backtesting.

This module includes methods for calculating key performance metrics such as:
- Equity curve
- Maximum drawdown (MDD)
- Cumulative return
- Sharpe ratio

Designed to work with backtest results stored in StockAccount and StockTradeRecord objects.

Intended for use in strategy evaluation, portfolio optimization, and performance monitoring.
"""


class StockBacktestAnalyzer:
    """ 
    Analyzes backtest results to compute key metrics like 
    equity curve, MDD, and ROI
    """
    
    
