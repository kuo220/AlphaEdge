import sys
import os
from pathlib import Path
import numpy as np
import pandas as pd
import datetime
import plotly.express as px
from plotly.graph_objs import Figure
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
sys.path.append(str(Path(__file__).resolve().parents[2]))
from data import Data, Chip, Tick, QXData
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
    
    def __init__(self, account: StockAccount, start_date: datetime.date, end_date: datetime.date):
        self.account: StockAccount = account                # Account
        self.start_date: datetime.date = start_date         # Backtest start date
        self.end_date: datetime.date = end_date             # Backtest end date
        self.benchmark: str = '0050'                        # Benchmark stock
        self.qxData = QXData()                              # QuantX data (for benchmark)
        
    
    def plot_equity_curve(self):
        """ 繪製權益曲線圖圖（淨資產隨時間變化）"""
        cumulative_capital: List[float] = [self.account.init_capital]
        dates: List[datetime.datetime] = [self.start_date]
        
        for record in self.account.trade_records:
            cumulative_capital.append(cumulative_capital[-1] + record.realized_pnl)
            
        
        
    
    
    def plot_equity_and_benchmark_curve(self):
        """ 繪製權益 & benchmark 曲線圖 """
        pass
    
    
    def plot_mdd(self):
        """ 繪製 Max Drawdown """
        pass
    
    
    def _set_figure_config(self, fig: Figure, title: str="", 
                          xaxis_title: str="", yaxis_title: str="",
                          info_context: str=""):
        """ 設置繪圖配置 """
        
        fig.update_layout(
            title = title,
            xaxis_title = xaxis_title,
            yaxis_title = yaxis_title
        )
        
        fig.add_annotation(
            xref = 'paper',
            yref = 'paper',
            x = 1,
            y = 1,
            text = info_context.replace("\n", "<br>"),
            showarrow = False,
            font = dict(
                size = 15,
                color = 'white',
            ),
            align = 'left',
            bordercolor = 'black',
            borderwidth = 1,
            borderpad = 5,
            bgcolor = 'black',
            opacity = 0.5
        )
        
        
    def _save_figure_to_dir(self, file_name: str=""):
        """ 儲存回測報告 """
        pass