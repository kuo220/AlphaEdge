import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
import datetime
import plotly.express as px
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
sys.path.append(str(Path(__file__).resolve().parents[2]))
from utils import (Market, Scale, PositionType,
                   Market, Scale, PositionType)
from models import StockAccount, StockQuote, StockOrder, StockTradeRecord
from .base import BaseBacktestAnalyzer
from config import BACKTEST_RESULT_DIR_PATH


"""
report.py

Generates performance reports based on backtest results.

This module summarizes key performance metrics—such as cumulative return, maximum drawdown (MDD),
and Sharpe ratio—based on trading records and equity curves. It also provides optional tools for
visualizing and exporting results.

Features:
- Aggregate key backtest metrics
- Generate equity curve plots
- Export performance reports to Excel or other formats

Intended for use in strategy evaluation and performance review.
"""


class StockBacktestReporter:
    """ Generates visual reports based on backtest results. """
    
    def __init__(self, account: StockAccount):
        self.benchmark: str = '0050'           # Benchmark stock
    
    
    def set_figure_config(self):
        """ 設置繪圖配置 """
        pass
    
    
    def plot_equity_curve(self):
        """ 繪製權益曲線圖圖（淨資產隨時間變化）"""
        pass
    
    
    def plot_equity_and_benchmark_curve(self):
        """ 繪製權益 & benchmark 曲線圖 """
        pass
    
    
    def plot_mdd(self):
        """ 繪製 Max Drawdown """
        pass