import datetime
from pathlib import Path
from typing import List, Optional

import plotly.graph_objects as go
from loguru import logger

from trader.backtest.report.base import BaseBacktestReporter
from trader.api.stock_price_api import StockPriceAPI
from trader.models import StockAccount
from trader.strategies.stock import BaseStockStrategy

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


class StockBacktestReporter(BaseBacktestReporter):
    """Generates visual reports based on backtest results"""

    def __init__(self, strategy: BaseStockStrategy, output_dir: Optional[Path] = None):
        super().__init__(strategy, output_dir)
        self.output_dir: Optional[Path] = output_dir  # Output directory

        self.start_date: datetime.date = self.strategy.start_date  # Backtest start date
        self.end_date: datetime.date = self.strategy.end_date  # Backtest end date

        self.benchmark: str = "0050"  # Benchmark stock
        self.price: StockPriceAPI = None  # Price data
        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Reporter"""

        self.price: StockPriceAPI = StockPriceAPI()

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
        self.save_figure(fig, f"{self.strategy.strategy_name}_equity_curve.png")

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

    def save_figure(self, fig: go.Figure, file_name: str = "") -> None:
        """
        - Description: 儲存回測報告
        - Parameters:
            - fig: go.Figure
                要儲存的圖表
            - file_name: str
                儲存檔案的名稱
        """

        if not file_name:
            raise ValueError("file_name 不能是空字串")

        # 決定輸出路徑
        if self.output_dir is not None:
            save_path = self.output_dir / file_name
        else:
            save_path = Path(file_name)

        # 確保資料夾存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 輸出圖片
        fig.write_image(str(save_path))
        logger.info(f"* Figure saved to: {save_path}")
