from abc import ABC, abstractmethod
from typing import Optional

from trader.models import StockAccount
from trader.strategies.stock import BaseStockStrategy


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