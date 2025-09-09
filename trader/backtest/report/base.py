from abc import ABC, abstractmethod
from pathlib import Path
from typing import Optional

import pandas as pd

from trader.models import StockAccount
from trader.strategies.stock import BaseStockStrategy


class BaseBacktestReporter(ABC):
    """Backtest Performance Reporter Framework (Base Template)"""

    def __init__(self, strategy: BaseStockStrategy, output_dir: Optional[Path] = None):
        self.strategy: BaseStockStrategy = strategy  # Backtest strategy
        self.account: StockAccount = self.strategy.account  # Account
        self.output_dir: Optional[Path] = output_dir  # Output directory

    @abstractmethod
    def setup(self) -> None:
        """Set Up the Config of Reporter"""
        pass

    @abstractmethod
    def generate_trading_report(self) -> pd.DataFrame:
        """生成回測報告 DataFrame"""
        pass

    @abstractmethod
    def plot_balance_curve(self) -> None:
        """計算並繪製總資金曲線（總資金隨時間變化）"""
        pass

    @abstractmethod
    def plot_balance_and_benchmark_curve(self) -> None:
        """計算並繪製總資金 & benchmark 曲線圖"""
        pass

    @abstractmethod
    def plot_balance_mdd(self) -> None:
        """計算並繪製總資金 Max Drawdown"""
        pass

    @abstractmethod
    def set_figure_config(self) -> None:
        """設置繪圖配置"""
        pass

    @abstractmethod
    def save_figure(self) -> None:
        """儲存回測報告圖表"""
        pass
