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

        # Benchmark
        self.benchmark: str = "0050"  # Benchmark stock

        # Price data
        self.price: StockPriceAPI = None  # Price data

        # Trading report
        self.trading_report: pd.DataFrame = None  # Trading report
        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Reporter"""

        # Price data
        self.price: StockPriceAPI = StockPriceAPI()
        self.trading_report: pd.DataFrame = self.generate_trading_report()

    def generate_trading_report_2(self) -> pd.DataFrame:
        """生成回測報告 DataFrame"""

        # Step 1: 產生完整日期清單
        dates: List[datetime.date] = TimeUtils.generate_date_range(
            start_date=self.start_date, end_date=self.end_date
        )

        # Step 2: 把交易紀錄轉成 dict {date: pnl}
        pnl_dict: Dict[datetime.date, float] = {}
        for record in self.account.trade_records.values():
            pnl_dict[record.date] = pnl_dict.get(record.date, 0.0) + record.realized_pnl

        # Step 3: 逐日累積 PnL 與資金餘額
        daily_pnl_list: List[float] = []  # 每日損益
        cumulative_pnl_value: float = 0.0  # 累計損益（暫存值）
        cumulative_pnl_list: List[float] = []  # 每日累積損益
        balance_value: float = self.account.init_capital  # 資金餘額（暫存值）
        balance_list: List[float] = []  # 每日總資金（含已實現損益）

        for date in dates:
            daily_pnl = pnl_dict.get(date, 0.0)
            cumulative_pnl_value += daily_pnl
            balance_value += daily_pnl

            daily_pnl_list.append(daily_pnl)
            cumulative_pnl_list.append(cumulative_pnl_value)
            balance_list.append(balance_value)

        # Step 4: 建立 DataFrame（方便之後擴展）
        df = pd.DataFrame(
            {
                "date": dates,
                "pnl": daily_pnl_list,
                "cumulative_pnl": cumulative_pnl_list,
                "balance": balance_list,
            }
        )
        df = df.set_index("date")
        return df

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
        df = pd.DataFrame(rows, columns=report_columns)
        self.save_report(df, f"{self.strategy.strategy_name}_trading_report.csv")
        return df

    def plot_balance_curve(self) -> None:
        """繪製總資金曲線圖（總資金隨時間變化）"""

        df: pd.DataFrame = self.generate_trading_report()

        # TODO: 需處理日期顯示過於密集的問題
        # Plot Balance Curve
        fig_title: str = "Balance Curve"
        fig: go.Figure = go.Figure()
        fig.add_trace(
            go.Scatter(
                x=df.index,
                y=df["balance"],
                mode="lines",
                line=dict(color="blue", width=2),
            )
        )

        self.set_figure_config(
            fig, title=fig_title, xaxis_title="Date", yaxis_title="Balance"
        )
        self.save_figure(fig, f"{self.strategy.strategy_name}_balance_curve.png")

    def plot_balance_and_benchmark_curve(self) -> None:
        """繪製總資金 & benchmark 曲線圖"""
        pass

    def plot_balance_mdd(self) -> None:
        """繪製總資金 Max Drawdown"""
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

        # Show figure
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
