from abc import ABC, abstractmethod
from typing import Optional

from trader.models import StockAccount
from trader.strategies.stock import BaseStockStrategy

"""
base.py

Defines abstract base classes for performance-related modules.

This file provides reusable interfaces for backtest performance analysis and report generation.
Typical use cases include customizing analyzers or reports for different financial instruments
(e.g. stocks, futures, options).

Classes:
- BaseAnalyzer: Interface for computing backtest metrics
- BaseReport: Interface for generating performance reports
"""


class BaseBacktestAnalyzer(ABC):
    """Backtest Performance Analyzer Framework (Base Template)"""

    # TODO: 計算 Cumulative Capital (Equity Curve), MDD, ROI, Sharpe Ratio

    def __init__(self, strategy: BaseStockStrategy):
        self.strategy: BaseStockStrategy = strategy  # Backtest strategy
        self.account: StockAccount = self.strategy.account  # Account

    # ===== Equity-based Metrics =====
    @abstractmethod
    def compute_equity_curve(self) -> None:
        """計算並繪製權益曲線（淨資產隨時間變化）"""
        pass

    @abstractmethod
    def compute_mdd(self) -> None:
        """計算並繪製 Max Drawdown"""
        pass

    # ===== Risk-Adjusted Metrics =====
    @abstractmethod
    def compute_volatility(self) -> float:
        """計算報酬率的標準差（可視為風險程度）"""
        pass

    @abstractmethod
    def compute_sharpe_ratio(self) -> Optional[float]:
        """計算 Sharpe Ratio"""
        pass

    @abstractmethod
    def compute_sortino_ratio(self) -> Optional[float]:
        """計算 Sortino Ratio"""
        pass

    # ===== Trade Statistics =====
    @abstractmethod
    def compute_win_rate(self) -> float:
        """計算勝率（獲利交易次數/總交易次數）"""
        pass

    @abstractmethod
    def compute_win_lose_rate(self) -> float:
        """計算勝敗比（獲利交易次數/虧損交易次數）"""
        pass

    @abstractmethod
    def compute_profit_factor(self) -> float:
        """計算利潤因子（總獲利/總虧損）"""
        pass

    @abstractmethod
    def compute_average_return(self) -> float:
        """計算每筆交易平均報酬"""
        pass

    @abstractmethod
    def compute_num_trades(self) -> int:
        """計算總交易次數（開倉+平倉 = 1次交易）"""
        pass

    @abstractmethod
    def compute_num_winning_trades(self) -> int:
        """計算獲利筆數（可用於 win rate）"""
        pass

    @abstractmethod
    def compute_num_losing_trades(self) -> int:
        """計算虧損筆數（可用於 win rate）"""
        pass


class BaseBacktestReporter(ABC):
    """Backtest Performance Reporter Framework (Base Template)"""

    def __init__(self, strategy: BaseStockStrategy):
        self.strategy: BaseStockStrategy = strategy  # Backtest strategy
        self.account: StockAccount = self.strategy.account  # Account

    @abstractmethod
    def plot_equity_curve(self) -> None:
        """計算並繪製權益曲線（淨資產隨時間變化）"""
        pass

    @abstractmethod
    def plot_equity_and_benchmark_curve(self) -> None:
        """計算並繪製權益 & benchmark 曲線圖"""
        pass

    @abstractmethod
    def plot_mdd(self) -> None:
        """計算並繪製 Max Drawdown"""
        pass

    @abstractmethod
    def set_figure_config(self) -> None:
        """設置繪圖配置"""
        pass

    @abstractmethod
    def save_figure(self) -> None:
        """儲存回測報告"""
        pass