from abc import ABC, abstractmethod
from typing import Optional

from core.models import BaseAccount
from core.strategies.base import BaseStrategy


class BaseBacktestAnalyzer(ABC):
    """
    Backtest Performance Analyzer Framework (Base Template)

    定位：Analyzer 供測試與研究驗算指標，正式回測輸出走 `report/reporter.py`
    （雙軌關係見 `core/backtest/README.md`〈績效指標〉）。
    """

    def __init__(self, strategy: BaseStrategy):
        self.strategy: BaseStrategy = strategy  # Backtest strategy
        self.account: BaseAccount = self.strategy.account  # Account

    @abstractmethod
    def setup(self) -> None:
        """Set Up the Config of Analyzer"""
        pass

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
    def compute_volatility(self, *args, **kwargs) -> Optional[float]:
        """年化波動度（%）；樣本不足或沒有逐日權益時為 None"""
        pass

    @abstractmethod
    def compute_sharpe_ratio(self, *args, **kwargs) -> Optional[float]:
        """計算 Sharpe Ratio"""
        pass

    @abstractmethod
    def compute_sortino_ratio(self, *args, **kwargs) -> Optional[float]:
        """計算 Sortino Ratio"""
        pass

    @abstractmethod
    def compute_information_ratio(self, *args, **kwargs) -> Optional[float]:
        """年化 Information Ratio（相對基準的超額報酬穩定性）；資料不足時為 None"""
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
