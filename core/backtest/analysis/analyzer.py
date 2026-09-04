import datetime
from typing import Dict, List, Optional

import numpy as np
import pandas as pd
from loguru import logger

from core.api.tw.stock_price_api import StockPriceAPI
from core.api.tw.stock_split import apply_split_adjustment
from core.backtest.analysis.base import BaseBacktestAnalyzer
from core.backtest.analysis.risk_metrics import (
    TRADING_DAYS_PER_YEAR,
    compute_annualized_information_ratio,
    compute_annualized_sharpe,
    compute_annualized_sortino,
    compute_period_returns,
)
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

        # 取基準還原價用（Information Ratio），首次取用時才連資料庫
        self.price: Optional[StockPriceAPI] = None

    def setup(self) -> None:
        """Set Up the Config of Analyzer"""
        self.benchmark: str = "0050"
        self.risk_free_rate: float = 0.02  # 無風險利率（暫定0.02）

    # ===== Equity-based Metrics =====
    def compute_equity_curve(
        self, daily_equity: Optional[List[Dict]] = None
    ) -> List[float]:
        """
        - Description:
            計算權益曲線

            優先使用 Backtester 產出的每日權益（含未實現損益）；
            未提供時退回「初始資金 + 累積已實現損益」，此時留倉部位的
            帳面波動看不見，放空的回撤會被低估。

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
    def compute_daily_returns(
        self, daily_equity: Optional[List[Dict]] = None
    ) -> Optional[List[float]]:
        """
        - Description:
            由權益曲線算出**日報酬**序列（風險指標的樣本）

            **沒有 `daily_equity` 就回 `None`，不退回逐筆交易的曲線**：
            `compute_equity_curve()` 的 fallback 是「每平倉一筆一個節點」，
            那是**每筆交易**的報酬而不是日報酬。拿它去乘 √252 年化，
            等於宣稱「一年有 252 筆交易」——正是 `risk_metrics` 模組說明裡
            列的第 2、3 個缺陷，只是換成從這個可選參數溜進來。

            年化指標寧可算不出來，也不要算出一個看起來合理的錯數字。
        - Parameters:
            - daily_equity: Optional[List[Dict]]
                Backtester.daily_equity
        - Return:
            - Optional[List[float]]
                日報酬序列；沒有逐日權益時為 None
        """

        if not daily_equity:
            logger.warning(
                "[Analyzer] 沒有逐日權益（daily_equity），風險指標無法年化，"
                "本次回傳 None——逐筆交易的報酬不是日報酬，乘 √252 只會得到假數字"
            )
            return None

        return compute_period_returns(self.compute_equity_curve(daily_equity))

    def compute_volatility(
        self, daily_equity: Optional[List[Dict]] = None
    ) -> Optional[float]:
        """
        - Description:
            年化波動度（%）

            **樣本是日報酬而不是每筆交易的 ROI**（健檢 F-068）：交易筆數與時間
            無關，一年交易 5 次與 500 次算出的「波動度」不可比，也無從年化。
        - Parameters:
            - daily_equity: Optional[List[Dict]]
                Backtester.daily_equity
        - Return:
            - Optional[float]
                年化波動度（%）；樣本不足兩期時為 None
        """

        returns: Optional[List[float]] = self.compute_daily_returns(daily_equity)
        if returns is None or len(returns) < 2:
            return None

        return round(
            float(np.std(returns, ddof=1)) * np.sqrt(TRADING_DAYS_PER_YEAR) * 100, 2
        )

    def compute_sharpe_ratio(
        self, daily_equity: Optional[List[Dict]] = None
    ) -> Optional[float]:
        """
        - Description:
            年化 Sharpe ratio；公式見 `risk_metrics.compute_annualized_sharpe()`

            舊版的分子是 `record.roi`（百分比）、分母的無風險利率是 `0.02`
            （小數），兩者差 100 倍，等於幾乎沒有扣無風險利率；而且沒有年化。
        - Parameters:
            - daily_equity: Optional[List[Dict]]
                Backtester.daily_equity
        - Return:
            - Optional[float]
                年化 Sharpe；資料不足時為 None
        """

        returns: Optional[List[float]] = self.compute_daily_returns(daily_equity)
        if returns is None:
            return None

        return compute_annualized_sharpe(
            returns, risk_free_rate=self.risk_free_rate or 0.0
        )

    def compute_sortino_ratio(
        self, daily_equity: Optional[List[Dict]] = None
    ) -> Optional[float]:
        """
        - Description:
            年化 Sortino ratio；公式見 `risk_metrics.compute_annualized_sortino()`

            舊版對「低於門檻的那些報酬」取 `np.std`，那是它們**彼此之間**的
            離散度；正確定義是相對於門檻的偏差平方，除以**全樣本**筆數再開根號。
        - Parameters:
            - daily_equity: Optional[List[Dict]]
                Backtester.daily_equity
        - Return:
            - Optional[float]
                年化 Sortino；資料不足時為 None
        """

        returns: Optional[List[float]] = self.compute_daily_returns(daily_equity)
        if returns is None:
            return None

        return compute_annualized_sortino(
            returns, risk_free_rate=self.risk_free_rate or 0.0
        )

    def compute_daily_returns_by_date(
        self, daily_equity: Optional[List[Dict]] = None
    ) -> Optional[Dict[datetime.date, float]]:
        """
        - Description:
            與 `compute_daily_returns()` 同一組數字，但**保留每一期的日期**

            `compute_period_returns()` 在前一期權益 ≤ 0 時會跳過該期，序列長度
            因此不必然等於天數；要與基準逐日相減就不能靠位置索引對齊，
            必須帶著日期。
        - Parameters:
            - daily_equity: Optional[List[Dict]]
                Backtester.daily_equity
        - Return:
            - Optional[Dict[datetime.date, float]]
                {日期: 當日報酬率}；沒有逐日權益時為 None
        """

        if not daily_equity:
            return None

        curve: List[float] = self.compute_equity_curve(daily_equity)
        returns: Dict[datetime.date, float] = {}

        # curve[0] 是初始資金，curve[i + 1] 對應 daily_equity[i]，
        # 故第 i 期報酬掛在 daily_equity[i] 的日期上
        for i, row in enumerate(daily_equity):
            previous: float = curve[i]
            if previous > 0:
                returns[row["Date"]] = curve[i + 1] / previous - 1
        return returns

    def compute_benchmark_daily_returns(
        self, start_date: datetime.date, end_date: datetime.date
    ) -> Optional[Dict[datetime.date, float]]:
        """
        - Description:
            取基準（`self.benchmark`，預設 0050）的**還原價**日報酬

            除權息由 `StockPriceAPI.get_adjusted_close_series()` 的累積因子處理，
            分割則**必須另外補**——`stock_dividend` 只記除權息，不含分割：
            實測 0050 在 2025-06-17 與 2025-06-18 的累積因子完全相同（1.4545），
            而原始收盤價由 188.65 掉到 47.57（一拆四）。少了這道調整，
            任何跨過分割日的回測，IR 都會被一天 −74.8% 的假跌幅整段汙染。

            分割表與 reporter 共用 `core/api/tw/stock_split.py` 同一份，
            不各留一份（F-087 的教訓）。
        - Parameters:
            - start_date: datetime.date
                起始日（含）
            - end_date: datetime.date
                結束日（含）
        - Return:
            - Optional[Dict[datetime.date, float]]
                {日期: 當日報酬率}；查無資料或不足兩筆時為 None
        """

        if self.price is None:
            self.price = StockPriceAPI()

        series: pd.Series = apply_split_adjustment(
            self.price.get_adjusted_close_series(self.benchmark, start_date, end_date),
            self.benchmark,
        )
        if series.empty or len(series) < 2:
            logger.warning(
                f"[Analyzer] 基準 {self.benchmark} 在 {start_date}~{end_date} "
                "取不到足夠的還原價，Information Ratio 回傳 None"
            )
            return None

        dates: List[datetime.date] = [
            StockPriceAPI.to_date(index_value) for index_value in series.index
        ]
        prices: List[float] = [float(value) for value in series.to_list()]

        returns: Dict[datetime.date, float] = {}
        for i in range(1, len(prices)):
            if prices[i - 1] > 0:
                returns[dates[i]] = prices[i] / prices[i - 1] - 1
        return returns

    def compute_information_ratio(
        self,
        daily_equity: Optional[List[Dict]] = None,
        benchmark_returns: Optional[Dict[datetime.date, float]] = None,
    ) -> Optional[float]:
        """
        - Description:
            年化 Information ratio；公式見
            `risk_metrics.compute_annualized_information_ratio()`

            與 Sharpe／Sortino／Volatility 同一口徑（健檢 F-068 漏掉的第四個
            指標）：樣本是**日報酬**、以 √252 年化、基準是**真的基準序列**。
            舊版以每筆交易的 `record.roi` 為樣本，且從每個樣本減去寫死的
            `benchmark_return = 0.0`——減去常數不改變分母，等於算出
            `mean(每筆 ROI) / std(每筆 ROI)`，與相對基準的超額報酬無關。

            策略與基準**依日期取交集**再相減。回測首日的基準報酬需要前一個
            交易日的收盤價，區間內取不到，故該日自然落在交集之外——
            策略首日（初始資金 → 首日權益）也一併被排除，兩邊仍然同期。
        - Parameters:
            - daily_equity: Optional[List[Dict]]
                Backtester.daily_equity；沒有時回 None（理由同
                `compute_daily_returns()`）
            - benchmark_returns: Optional[Dict[datetime.date, float]]
                自備的基準日報酬；不給就由 `self.benchmark` 查還原價
        - Return:
            - Optional[float]
                年化 IR；缺逐日權益、缺基準序列或共同日期不足兩期時為 None
        """

        strategy_returns: Optional[Dict[datetime.date, float]] = (
            self.compute_daily_returns_by_date(daily_equity)
        )
        if not strategy_returns:
            logger.warning(
                "[Analyzer] 沒有逐日權益（daily_equity），Information Ratio 無法年化，"
                "本次回傳 None——逐筆交易的報酬不是日報酬"
            )
            return None

        if benchmark_returns is None:
            benchmark_returns = self.compute_benchmark_daily_returns(
                min(strategy_returns), max(strategy_returns)
            )
        if not benchmark_returns:
            return None

        common_dates: List[datetime.date] = sorted(
            set(strategy_returns) & set(benchmark_returns)
        )
        if len(common_dates) < 2:
            logger.warning(
                f"[Analyzer] 策略與基準 {self.benchmark} 的共同交易日只有 "
                f"{len(common_dates)} 天，Information Ratio 回傳 None"
            )
            return None

        return compute_annualized_information_ratio(
            [strategy_returns[date] for date in common_dates],
            [benchmark_returns[date] for date in common_dates],
        )

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
        """統計放空專屬成本：借券費支出、融券利息收入與股利補償"""

        return {
            "borrow_fee": round(
                sum(record.borrow_fee for record in self.trade_records), 2
            ),
            "interest": round(sum(record.interest for record in self.trade_records), 2),
            "dividend_compensation": round(
                sum(record.dividend_compensation for record in self.trade_records), 2
            ),
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
