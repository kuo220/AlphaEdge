# Standard library imports
import sys
import os
import datetime
from pathlib import Path
from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any
import numpy as np
import pandas as pd
import plotly.express as px

from trader.data import Data, Chip, Tick, QXData
from trader.utils import Market, Scale, PositionType
from trader.models import (
    StockAccount,
    StockQuote,
    StockOrder,
    StockTradeRecord
)
from .base import BaseBacktestAnalyzer
from .report import StockBacktestReporter
from trader.config import BACKTEST_RESULT_DIR_PATH


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


class StockBacktestAnalyzer(BaseBacktestAnalyzer):
    """ 
    Analyzes backtest results to compute key metrics like 
    equity curve, MDD, and ROI
    """
    def __init__(self, account: StockAccount):
        # Account
        super().__init__(account)
        
        # Trade Record List
        self.trade_records: List[StockTradeRecord] = [record for record in self.account.trade_records.values() if record.is_closed]
        
        # Statistics
        self.benchmark: str = '0050'
        self.risk_free_rate: float  = 0         # 無風險利率（暫定0）

    
    # ===== Risk-Adjusted Metrics =====
    def compute_volatility(self) -> float:
        """ 計算報酬率的標準差（可視為風險程度）"""
        return np.std([record.roi for record in self.trade_records])
    
    
    def compute_sharpe_ratio(self) -> Optional[float]:
        """ 計算 Sharpe Ratio """
        
        std_dev: float = self.compute_volatility()
        roi_mean: float = np.mean([record.roi for record in self.trade_records])
        
        if std_dev > 0:
            return (roi_mean - self.risk_free_rate) / std_dev
        return None
    
    
    def compute_sortino_ratio(self) -> Optional[float]:
        """ 計算 Sortino Ratio"""
        
        downside_dev: float = np.std([record.roi for record in self.trade_records if record.roi < self.risk_free_rate])
        roi_mean: float = np.mean([record.roi for record in self.trade_records])
        
        if downside_dev > 0:
            return (roi_mean - self.risk_free_rate) / downside_dev
        return None


    # ===== Trade Statistics =====
    def compute_win_rate(self) -> float:
        """ 計算勝率（獲利交易次數/總交易次數）"""
        return self.compute_num_winning_trades() / self.compute_num_trades()
    
    
    def compute_win_lose_rate(self) -> float:
        """ 計算勝敗比（獲利交易次數/虧損交易次數） """
        
        win_cnt: int = self.compute_num_winning_trades()
        lose_cnt: int = self.compute_num_losing_trades()
        return win_cnt / lose_cnt
    
    
    def compute_profit_factor(self) -> float:
        """ 計算利潤因子（總獲利/總虧損）"""
        
        profit: float = sum(record.realized_pnl for record in self.trade_records if record.realized_pnl >= 0)
        loss: float = sum(abs(record.realized_pnl) for record in self.trade_records if record.realized_pnl < 0)
        
        return profit / loss
    
    
    def compute_average_return(self) -> float:
        """ 計算每筆交易平均報酬 """
        
        total_roi: float = sum(record.roi for record in self.trade_records)
        return total_roi / self.compute_num_trades()
    
    
    def compute_num_trades(self) -> int:
        """ 計算總交易次數（開倉+平倉 = 1次交易）"""
        return len(self.trade_records)
    
    
    def compute_num_winning_trades(self) -> int:
        """ 計算獲利筆數（可用於 win rate）"""
        
        win_cnt: int = sum(1 for record in self.trade_records if record.realized_pnl > 0)
        return win_cnt

    
    def compute_num_losing_trades(self) -> int:
        """ 計算虧損筆數（可用於 win rate）"""
        
        lose_cnt: int = sum(1 for record in self.trade_records if record.realized_pnl < 0)
        return lose_cnt