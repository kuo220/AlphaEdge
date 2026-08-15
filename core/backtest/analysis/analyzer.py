import datetime
from typing import Dict, List, Optional

import numpy as np

from core.backtest.analysis.base import BaseBacktestAnalyzer
from core.models import StockTradeRecord
from core.strategies.stock import BaseStockStrategy

"""Provides analytical tools for evaluating trading strategy performance during backtesting"""


class StockBacktestAnalyzer(BaseBacktestAnalyzer):
    """Analyzes backtest results to compute key metrics like equity curve, MDD, and ROI"""

    def __init__(self, strategy: BaseStockStrategy):
        # Account
        super().__init__(strategy)

        # Trade Record List
        self.trade_records: List[StockTradeRecord] = [
            record for record in self.account.trade_records if record.is_closed
        ]

        # Statistics
        self.benchmark: Optional[str] = None  # Benchmark stock
        self.risk_free_rate: Optional[float] = None  # 無風險利率（暫定0.02）
        self.benchmark_return: Optional[float] = (
            None  # 基準報酬率（用於 Information Ratio）
        )

    def setup(self) -> None:
        """Set Up the Config of Analyzer"""
        self.benchmark: str = "0050"
        self.risk_free_rate: float = 0.02  # 無風險利率（暫定0.02）
        self.benchmark_return: float = 0.0  # 基準報酬率（可依回測期間調整）

    # ===== Equity-based Metrics =====
    def compute_equity_curve(
        self, daily_equity: Optional[List[Dict]] = None
    ) -> List[float]:
        """
        - Description:
            計算權益曲線

            優先使用 Backtester 產出的每日權益（含未實現損益）；
            未提供時退回「初始資金 + 累積已實現損益」，此時留倉部位的
            帳面波動看不見，放空的回撤會被低估（見 backlog §7.7）。

            兩條路徑都以**初始資金**為第一個節點，與
            `StockBacktestReporter.get_equity_series()` 的口徑一致——
            否則 analyzer 算出的 MDD 會與 `plot_balance_mdd` 的圖對不上。
        - Parameters:
            - daily_equity: Optional[List[Dict]]
                Backtester.daily_equity
        - Return:
            - curve: List[float]
                權益序列，第一筆為初始資金
        """

        curve: List[float] = [round(float(self.account.init_capital), 2)]

        if daily_equity:
            curve.extend(float(row["Equity"]) for row in daily_equity)
            return curve

        equity: float = self.account.init_capital
        for record in sorted(
            self.trade_records,
            key=lambda r: r.exit_date if r.exit_date else datetime.date.min,
        ):
            equity += record.realized_pnl
            curve.append(round(equity, 2))
        return curve

    def compute_mdd(self, daily_equity: Optional[List[Dict]] = None) -> float:
        """計算最大回撤（%）；資料來源與 compute_equity_curve 一致"""

        curve: List[float] = self.compute_equity_curve(daily_equity)
        if not curve:
            return 0.0

        peak: float = curve[0]
        mdd: float = 0.0
        for equity in curve:
            peak = max(peak, equity)
            if peak > 0:
                mdd = min(mdd, equity / peak - 1)

        return round(mdd * 100, 2)

    # ===== Risk-Adjusted Metrics =====
    def compute_volatility(self) -> float:
        """計算報酬率的標準差（可視為風險程度）"""
        return np.std([record.roi for record in self.trade_records])

    def compute_sharpe_ratio(self) -> Optional[float]:
        """Compute Sharpe Ratio"""

        std_dev: float = self.compute_volatility()
        roi_mean: float = np.mean([record.roi for record in self.trade_records])

        if std_dev > 0:
            return (roi_mean - self.risk_free_rate) / std_dev
        return None

    def compute_sortino_ratio(self) -> Optional[float]:
        """Compute Sortino Ratio"""

        downside_dev: float = np.std(
            [
                record.roi
                for record in self.trade_records
                if record.roi < self.risk_free_rate
            ]
        )
        roi_mean: float = np.mean([record.roi for record in self.trade_records])

        if downside_dev > 0:
            return (roi_mean - self.risk_free_rate) / downside_dev
        return None

    def compute_information_ratio(self) -> Optional[float]:
        """Compute Information Ratio（策略超額報酬相對於基準的穩定性）

        IR = mean(active_returns) / std(active_returns)
        active_returns = strategy_roi - benchmark_return
        """
        if not self.trade_records:
            return None
        benchmark: float = self.benchmark_return or 0.0
        active_returns: np.ndarray = np.array(
            [record.roi - benchmark for record in self.trade_records]
        )
        tracking_error: float = np.std(active_returns)
        if tracking_error > 0:
            return float(np.mean(active_returns) / tracking_error)
        return None

    # ===== Trade Statistics =====
    def compute_win_rate(self) -> float:
        """計算勝率（獲利交易次數/總交易次數）"""
        return self.compute_num_winning_trades() / self.compute_num_trades()

    def compute_win_lose_rate(self) -> float:
        """計算勝敗比（獲利交易次數/虧損交易次數）"""

        win_cnt: int = self.compute_num_winning_trades()
        lose_cnt: int = self.compute_num_losing_trades()
        return win_cnt / lose_cnt

    def compute_profit_factor(self) -> float:
        """計算利潤因子（總獲利/總虧損）"""

        profit: float = sum(
            record.realized_pnl
            for record in self.trade_records
            if record.realized_pnl >= 0
        )
        loss: float = sum(
            abs(record.realized_pnl)
            for record in self.trade_records
            if record.realized_pnl < 0
        )

        return profit / loss

    def compute_average_return(self) -> float:
        """計算每筆交易平均報酬"""

        total_roi: float = sum(record.roi for record in self.trade_records)
        return total_roi / self.compute_num_trades()

    def compute_num_trades(self) -> int:
        """計算總交易次數（開倉+平倉 = 1次交易）"""
        return len(self.trade_records)

    def compute_num_winning_trades(self) -> int:
        """計算獲利筆數（可用於 win rate）"""

        win_cnt: int = sum(
            1 for record in self.trade_records if record.realized_pnl > 0
        )
        return win_cnt

    def compute_trade_count_by_direction(self) -> Dict[str, int]:
        """依部位方向統計交易筆數（多空的風險型態不同，需分開檢視）"""

        counts: Dict[str, int] = {}
        for record in self.trade_records:
            key: str = record.position_type.value
            counts[key] = counts.get(key, 0) + 1
        return counts

    def compute_pnl_by_direction(self) -> Dict[str, float]:
        """依部位方向統計已實現損益"""

        pnl: Dict[str, float] = {}
        for record in self.trade_records:
            key: str = record.position_type.value
            pnl[key] = round(pnl.get(key, 0.0) + record.realized_pnl, 2)
        return pnl

    def compute_short_cost(self) -> Dict[str, float]:
        """統計放空專屬成本：借券費支出與融券利息收入"""

        return {
            "borrow_fee": round(
                sum(record.borrow_fee for record in self.trade_records), 2
            ),
            "interest": round(sum(record.interest for record in self.trade_records), 2),
        }

    def compute_average_holding_days(self) -> float:
        """計算平均持有曆日數（留倉放空的成本與持有天數直接相關）"""

        if not self.trade_records:
            return 0.0

        total_days: int = sum(record.holding_days for record in self.trade_records)
        return round(total_days / len(self.trade_records), 2)

    def compute_num_losing_trades(self) -> int:
        """計算虧損筆數（可用於 win rate）"""

        lose_cnt: int = sum(
            1 for record in self.trade_records if record.realized_pnl < 0
        )
        return lose_cnt
