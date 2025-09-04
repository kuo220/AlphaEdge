import datetime
from typing import List

import plotly.graph_objects as go

from trader.api import StockPriceAPI
from trader.backtest.report.base import BaseBacktestReporter
from trader.config import BACKTEST_RESULT_DIR_PATH
from trader.models import StockAccount
from trader.strategies.stock import BaseStockStrategy
from trader.utils import Market, PositionType, Scale

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
    """Generates visual reports based on backtest results"""

    def __init__(self, strategy: BaseStockStrategy):
        self.strategy: BaseStockStrategy = strategy  # Backtest strategy
        self.account: StockAccount = self.strategy.account  # Account

        self.start_date: datetime.date = self.strategy.start_date  # Backtest start date
        self.end_date: datetime.date = self.strategy.end_date  # Backtest end date

        self.benchmark: str = "0050"  # Benchmark stock
        self.price: StockPriceAPI = StockPriceAPI()  # Price data

    def plot_equity_curve(self) -> None:
        """繪製權益曲線圖（淨資產隨時間變化）"""

        dates: List[datetime.date] = [self.start_date]
        cumulative_equity: List[float] = [self.account.init_capital]
        fig_title: str = "Equity Curve"

        for record in self.account.trade_records.values():
            dates.append(record.date)
            cumulative_equity.append(cumulative_equity[-1] + record.realized_pnl)

        # TODO: 需處理日期顯示過於密集的問題
        fig: go.Figure = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=dates,
                y=cumulative_equity,
                mode="lines",
                line=dict(color="blue", width=2),
            )
        )

        self.set_figure_config(
            fig, title=fig_title, xaxis_title="Date", yaxis_title="Equity"
        )
        fig.show(renderer="browser")

    def plot_equity_and_benchmark_curve(self) -> None:
        """繪製權益 & benchmark 曲線圖"""
        pass

    def plot_mdd(self) -> None:
        """繪製 Max Drawdown"""
        pass

    def set_figure_config(
        self,
        fig: go.Figure,
        title: str = "",
        xaxis_title: str = "",
        yaxis_title: str = "",
        fig_text: str = "",
    ) -> None:
        """設置繪圖配置"""

        # Layout setting
        fig.update_layout(
            title=title,
            xaxis_title=xaxis_title,
            yaxis_title=yaxis_title,
            xaxis=dict(
                showgrid=True,
                gridcolor="lightgrey",  # 黑色格線
                gridwidth=0.5,  # 可微調線條粗細
                zeroline=False,
            ),
            yaxis=dict(
                showgrid=True, gridcolor="lightgrey", gridwidth=0.5, zeroline=False
            ),
            plot_bgcolor="#f9f9f9",
            paper_bgcolor="white",
        )

        # Annotation setting
        if fig_text != "":
            fig.add_annotation(
                xref="paper",
                yref="paper",
                x=1,
                y=1,
                text=fig_text.replace("\n", "<br>"),
                showarrow=False,
                font=dict(
                    size=15,
                    color="white",
                ),
                align="left",
                bordercolor="black",
                borderwidth=1,
                borderpad=5,
                bgcolor="black",
                opacity=0.5,
            )

    def save_figure(self, file_name: str = "") -> None:
        """儲存回測報告"""
        pass
