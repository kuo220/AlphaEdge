import sys
import os
from pathlib import Path
import requests
import numpy as np
import pandas as pd
import datetime
import plotly.express as px
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import (Data, Market, Scale, PositionType,
                   Market, Scale, PositionType)
from models import StockAccount, StockQuote, StockOrder, StockTradeRecord


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
    
    
