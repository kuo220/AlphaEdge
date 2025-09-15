import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

import pandas as pd
import plotly.graph_objects as go
from loguru import logger

from trader.api.stock_price_api import StockPriceAPI
from trader.backtest.report.base import BaseBacktestReporter
from trader.strategies.stock import BaseStockStrategy
from trader.utils.time import TimeUtils

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

        # Backtest date
        self.start_date: datetime.date = self.strategy.start_date  # Backtest start date
        self.end_date: datetime.date = self.strategy.end_date  # Backtest end date

        # 起始前一天，用來當作初始資金節點
        self.origin_date: datetime.date = self.start_date - datetime.timedelta(days=1)

        # Benchmark
        self.benchmark: str = "0050"  # Benchmark stock

        # Price data
        self.price: StockPriceAPI = None  # Price data
        self.benchmark_price: pd.Series = None  # Benchmark price

        # Trading report
        self.trading_report: pd.DataFrame = None  # Trading report

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Reporter"""

        # Price data
        self.price: StockPriceAPI = StockPriceAPI()

        # Benchmark price
        self.price_df: pd.DataFrame = self.price.get_stock_price(
            stock_id=self.benchmark,
            start_date=self.start_date,
            end_date=self.end_date,
        )
        self.benchmark_price = self.price_df["收盤價"]
        self.benchmark_price.index = pd.to_datetime(self.price_df["date"]).dt.date

    def generate_trading_report(self) -> pd.DataFrame:
        """生成回測報告"""

        report_columns: List[str] = [
            "Stock ID",
            "Position Type",
            "Buy Date",
            "Buy Price",
            "Buy Volume",
            "Sell Date",
            "Sell Price",
            "Sell Volume",
            "Commission",
            "Tax",
            "Transaction Cost",
            "Realized PnL",
            "ROI",
            "Cumulative PnL",
            "Cumulative Balance",
        ]

        # Initialize cumulative values for PnL and Balance
        cumulative_pnl: float = 0.0
        cumulative_balance: float = self.account.init_capital

        # Generate trading report
        rows: List[Dict[str, Any]] = []
        for record in self.account.trade_records:
            cumulative_pnl += record.realized_pnl
            cumulative_balance += record.realized_pnl

            row = {
                "Stock ID": record.stock_id,
                "Position Type": record.position_type.value,
                "Buy Date": record.buy_date,
                "Buy Price": record.buy_price,
                "Buy Volume": record.buy_volume,
                "Sell Date": record.sell_date,
                "Sell Price": record.sell_price,
                "Sell Volume": record.sell_volume,
                "Commission": record.commission,
                "Tax": record.tax,
                "Transaction Cost": record.transaction_cost,
                "Realized PnL": record.realized_pnl,
                "ROI": record.roi,
                "Cumulative PnL": cumulative_pnl,
                "Cumulative Balance": cumulative_balance,
            }
            rows.append(row)

        # Convert to DataFrame
        df: pd.DataFrame = pd.DataFrame(rows, columns=report_columns)
        self.save_report(df, f"{self.strategy.strategy_name}_trading_report.csv")
        return df

    def plot_balance_curve(self) -> None:
        """繪製總資金曲線圖（總資金隨時間變化）"""

        df: pd.DataFrame = self.trading_report.copy()

        # Add a row for the initial capital
        init_row: pd.DataFrame = pd.DataFrame(
            [
                {
                    "Sell Date": self.origin_date,
                    "Cumulative PnL": 0.0,
                    "Cumulative Balance": self.account.init_capital,
                }
            ]
        )

        # Concatenate initial row
        df = pd.concat([init_row, df], ignore_index=True)

        # Plot Balance Curve
        fig_title: str = "Balance Curve"
        fig: go.Figure = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df["Sell Date"],
                y=df["Cumulative Balance"],
                mode="lines",
                line=dict(color="blue", width=2),
            )
        )

        self.set_figure_config(
            fig,
            title=fig_title,
            xaxis_title="Sell Date",
            yaxis_title="Cumulative Balance",
        )
        self.save_figure(fig, f"{self.strategy.strategy_name}_balance_curve.png")

    def plot_balance_and_benchmark_curve(self) -> None:
        """繪製總資金 & benchmark 曲線圖"""

        # === Benchmark 淨值曲線 ===
        benchmark_net_worth: pd.Series = (
            self.benchmark_price
            / self.benchmark_price.iloc[0]
            * self.account.init_capital
        )
        # 加入初始資金節點
        benchmark_net_worth = pd.concat(
            [
                pd.Series(self.account.init_capital, index=[self.origin_date]),
                benchmark_net_worth,
            ]
        )

        # === 策略累積資金資料 ===
        balance_df: pd.DataFrame = self.trading_report[
            ["Sell Date", "Cumulative Balance"]
        ].copy()
        balance_df["Sell Date"] = pd.to_datetime(balance_df["Sell Date"])

        cumulative_balance: pd.Series = (
            balance_df.groupby(balance_df["Sell Date"].dt.date)["Cumulative Balance"]
            .last()
            .astype(float)
        )
        init_row: pd.Series = pd.Series(
            self.account.init_capital, index=[self.origin_date]
        )
        # 加入初始資金節點
        cumulative_balance = pd.concat([init_row, cumulative_balance])

        # === 整理 DataFrame 用來繪圖 ===
        networth_df: pd.DataFrame = pd.DataFrame(
            {
                "Date": cumulative_balance.index,
                "Strategy Net Worth": cumulative_balance.values,
                f"{self.benchmark} Net Worth": benchmark_net_worth.loc[
                    cumulative_balance.index
                ].values,
            }
        )

        # 計算報酬率 (ROI)
        strategy_roi: float = round(
            (cumulative_balance.iloc[-1] / self.account.init_capital - 1) * 100, 2
        )
        benchmark_roi: float = round(
            (self.benchmark_price.iloc[-1] / self.benchmark_price.iloc[0] - 1) * 100, 2
        )

        roi_text: str = (
            f"Strategy Total ROI(%): {strategy_roi}%\n"
            f"{self.benchmark} Total ROI(%): {benchmark_roi}%"
        )

        # 畫圖
        fig: go.Figure = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=networth_df["Date"],
                y=networth_df["Strategy Net Worth"],
                mode="lines",
                name="Strategy Net Worth",
                line=dict(color="blue", width=2),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=networth_df["Date"],
                y=networth_df[f"{self.benchmark} Net Worth"],
                mode="lines",
                name=f"{self.benchmark} Net Worth",
                line=dict(color="red", width=2),
            )
        )

        self.set_figure_config(
            fig,
            title=f"Strategy vs {self.benchmark} Net Worth "
            f"({self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')})",
            xaxis_title="Date",
            yaxis_title="Net Worth",
            fig_text=roi_text,
        )
        self.save_figure(fig, f"{self.strategy.strategy_name}_networth.png")

    def plot_balance_mdd(self) -> None:
        """繪製總資金 Max Drawdown"""

        # === 計算 Benchmark 的 MDD (%) ===
        mdd_benchmark: pd.Series = (
            self.benchmark_price / self.benchmark_price.cummax() - 1
        ) * 100

        # 加入初始資金節點
        mdd_benchmark = pd.concat(
            [pd.Series(0.0, index=[self.origin_date]), mdd_benchmark]  # 起點 MDD 為 0%
        )

        # === 累積資金資料 ===
        balance_df: pd.DataFrame = self.trading_report[
            ["Sell Date", "Cumulative Balance"]
        ].copy()
        balance_df["Sell Date"] = pd.to_datetime(balance_df["Sell Date"])

        # 依日期取每日最後一筆 balance（避免一天多筆交易造成重複）
        cumulative_balance: pd.Series = (
            balance_df.groupby(balance_df["Sell Date"].dt.date)["Cumulative Balance"]
            .last()
            .astype(float)
        )
        init_row: pd.Series = pd.Series(
            self.account.init_capital, index=[self.origin_date]
        )
        # 加入初始資金節點
        cumulative_balance = pd.concat([init_row, cumulative_balance])
        mdd_balance = (cumulative_balance / cumulative_balance.cummax() - 1) * 100

        # === 整理 DataFrame 用來繪圖 ===
        mdd_df: pd.DataFrame = pd.DataFrame(
            {
                "Date": cumulative_balance.index,
                "Strategy MDD": mdd_balance.values,
                f"{self.benchmark} MDD": mdd_benchmark.loc[
                    cumulative_balance.index
                ].values,
            }
        )

        # 畫圖
        fig: go.Figure = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=mdd_df["Date"],
                y=mdd_df["Strategy MDD"],
                mode="lines",
                name="Strategy MDD",
                line=dict(color="blue", width=2),
            )
        )
        fig.add_trace(
            go.Scatter(
                x=mdd_df["Date"],
                y=mdd_df[f"{self.benchmark} MDD"],
                mode="lines",
                name=f"{self.benchmark} MDD",
                line=dict(color="red", width=2),
            )
        )

        # 設置圖表配置 (MDD)
        self.set_figure_config(
            fig,
            title=f"MDD ({self.start_date.strftime('%Y/%m/%d')} ~ {self.end_date.strftime('%Y/%m/%d')})",
            xaxis_title="Date",
            yaxis_title="MDD (%)",
        )
        self.save_figure(fig, f"{self.strategy.strategy_name}_mdd.png")

    def plot_everyday_profit(self) -> None:
        """繪製每天的利潤"""

        # 轉換 Sell Date 為 datetime 格式
        profit_df: pd.DataFrame = self.trading_report[
            ["Sell Date", "Realized PnL"]
        ].copy()
        profit_df["Sell Date"] = pd.to_datetime(profit_df["Sell Date"])

        # 群組並計算每日總損益
        daily_profit: pd.DataFrame = (
            profit_df.groupby(profit_df["Sell Date"].dt.date)["Realized PnL"]
            .sum()
            .reset_index()
            .rename(columns={"Sell Date": "Date", "Realized PnL": "Daily PnL"})
        )

        # 建立 bar chart
        fig: go.Figure = go.Figure()
        fig.add_trace(
            go.Bar(
                x=daily_profit["Date"],
                y=daily_profit["Daily PnL"],
                marker_color="green",
                name="Daily Profit",
            )
        )

        # 設置圖表配置
        self.set_figure_config(
            fig,
            title="Everyday Profit",
            xaxis_title="Date",
            yaxis_title="Daily PnL",
        )
        self.save_figure(fig, f"{self.strategy.strategy_name}_everyday_profit.png")

    def set_figure_config(
        self,
        fig: go.Figure,
        title: str = "",
        xaxis_title: str = "",
        yaxis_title: str = "",
        fig_text: str = "",
        show: bool = True,
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

        # Show figure
        if show:
            fig.show(renderer="browser")

    def save_report(self, df: pd.DataFrame, file_name: str = "") -> None:
        """儲存回測報告"""
        if not file_name:
            raise ValueError("file_name 不能是空字串")

        # 決定輸出路徑
        if self.output_dir is not None:
            save_path = self.output_dir / file_name
        else:
            save_path = Path(file_name)

        # 確保資料夾存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 輸出 CSV 檔案
        df.to_csv(save_path, index=False, encoding="utf-8-sig")
        logger.info(f"* Report saved to: {save_path}")

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
