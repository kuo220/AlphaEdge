import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import pandas as pd
import plotly.graph_objects as go
from loguru import logger

from trader.api.stock_price_api import StockPriceAPI
from trader.backtest.report.base import BaseBacktestReporter
from trader.models.stock.record import StockTradeRecord
from trader.pipeline.utils import FileEncoding
from trader.strategies.stock import BaseStockStrategy
from trader.utils.time import TimeUtils

"""Generates performance reports based on backtest results"""


class StockBacktestReporter(BaseBacktestReporter):
    """Generates visual reports based on backtest results"""

    SPLIT_ADJUSTMENT_WARNING_PCT: float = 5.0  # 分割調整差異超過此 % 發出警告
    CHART_FONT_SIZE: int = 15

    # 股票分割配置：{股票代號: [(分割日期, 分割比例), ...]}
    # 分割比例格式：1:4 表示 1 拆 4（1 股變成 4 股，調整因子為 4）
    # 範例：{"0050": [(datetime.date(2025, 6, 18), 4)]}
    STOCK_SPLITS: Dict[str, List[Tuple[datetime.date, float]]] = {
        "0050": [(datetime.date(2025, 6, 18), 4.0)],  # 2025/06/18 1 拆 4
    }

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
        self.price: Optional[StockPriceAPI] = None  # Price data
        self.benchmark_price: Optional[pd.Series] = None  # Benchmark price

        # Trading report
        self.trading_report: Optional[pd.DataFrame] = None  # Trading report

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
        self.benchmark_price: pd.Series = self.price_df["收盤價"]
        self.benchmark_price.index = pd.to_datetime(self.price_df["date"]).dt.date

    def _get_adjusted_price(self, price_series: pd.Series, stock_id: str) -> pd.Series:
        """
        計算調整後價格（處理股票分割，支援多次分割）

        Args:
            price_series: 原始價格序列（已排序）
            stock_id: 股票代號

        Returns:
            調整後價格序列

        Note:
            對於股票分割（如 1 拆 4），分割日期及之後的價格需要乘以調整因子（4），
            這樣可以確保價格序列的連續性

            範例（單次分割）：
            - 分割前 100 元（保持原樣）
            - 分割後 25 元 → 調整後 100 元（25 × 4）
            - 這樣可以確保價格序列連續：100 → 100，而不是 100 → 25

            範例（多次分割）：
            假設有兩次分割：
            - 2025/06/18: 1 拆 4（調整因子 4）
            - 2025/12/18: 1 拆 2（調整因子 2）

            原始價格：
            - 2025/06/17: 100 元（分割前）
            - 2025/06/18: 25 元（第一次分割後）
            - 2025/12/17: 25 元
            - 2025/12/18: 12.5 元（第二次分割後）

            調整後價格：
            - 2025/06/17: 100 元（不變，累積調整因子 = 1.0）
            - 2025/06/18: 25 × 4 = 100 元（累積調整因子 = 4.0）
            - 2025/12/17: 25 × 4 = 100 元（累積調整因子 = 4.0）
            - 2025/12/18: 12.5 × 4 × 2 = 100 元（累積調整因子 = 8.0）

            實現邏輯：
            1. 對於每個日期，計算其累積調整因子（所有在該日期之前或當天的分割的累積）
            2. 將原始價格乘以對應的累積調整因子
            3. 這樣可以確保不同分割後的日期使用正確的調整因子
        """
        if stock_id not in self.STOCK_SPLITS:
            return price_series

        adjusted_price: pd.Series = price_series.copy()
        splits: List[Tuple[datetime.date, float]] = self.STOCK_SPLITS[stock_id]

        # 確保索引是 date 類型，並排序
        if len(adjusted_price) > 0:
            # 轉換索引為 date 類型（如果還不是）
            if not isinstance(adjusted_price.index[0], datetime.date):
                adjusted_price.index = pd.to_datetime(adjusted_price.index).date  # type: ignore
            # 確保索引是 date 類型的列表
            index_dates: List[datetime.date] = [
                d if isinstance(d, datetime.date) else pd.to_datetime(d).date()
                for d in adjusted_price.index
            ]
            adjusted_price.index = pd.Index(index_dates)

        adjusted_price: pd.Series = adjusted_price.sort_index()

        # 按日期排序（從舊到新）
        splits_sorted: List[Tuple[datetime.date, float]] = sorted(
            splits, key=lambda x: x[0]
        )

        # 標準化分割日期為 date 類型
        splits_normalized: List[Tuple[datetime.date, float]] = []
        for split_date, split_ratio in splits_sorted:
            split_date_normalized: datetime.date
            if isinstance(split_date, datetime.datetime):
                split_date_normalized = split_date.date()
            elif isinstance(split_date, str):
                split_date_normalized = datetime.datetime.strptime(
                    split_date, "%Y-%m-%d"
                ).date()
            else:
                split_date_normalized = split_date  # type: ignore
            splits_normalized.append((split_date_normalized, split_ratio))

        # 方法：為每個日期計算其累積調整因子
        # 這樣可以確保不同分割後的日期使用正確的調整因子
        adjusted_result: pd.Series = adjusted_price.copy()

        for date in adjusted_price.index:
            # 計算該日期的累積調整因子
            cumulative_ratio: float = 1.0
            for split_date, split_ratio in splits_normalized:
                # 如果該日期 >= 分割日期，則應用該分割的調整因子
                if date >= split_date:
                    cumulative_ratio *= split_ratio

            # 應用累積調整因子
            if cumulative_ratio != 1.0:
                adjusted_result.loc[date] = adjusted_price.loc[date] * cumulative_ratio

        # 記錄分割調整信息
        for split_date, split_ratio in splits_normalized:
            # 計算受影響的日期範圍
            mask: pd.Series = adjusted_price.index >= split_date
            num_adjusted: int = mask.sum()

            if num_adjusted > 0:
                # 計算該分割的累積調整因子（用於日誌）
                cumulative_ratio_for_split: float = 1.0
                for sd, sr in splits_normalized:
                    if sd <= split_date:
                        cumulative_ratio_for_split *= sr

                # 記錄分割日期前一天的價格（如果存在），用於驗證調整是否正確
                price_before_split: Optional[float] = None
                dates_before: pd.Index = adjusted_price.index[
                    adjusted_price.index < split_date
                ]
                if len(dates_before) > 0:
                    price_before_split = adjusted_result.loc[dates_before[-1]]

                # 記錄分割日期當天的調整後價格（如果存在）
                price_on_split_date_after: Optional[float] = None
                if split_date in adjusted_result.index:
                    price_on_split_date_after = adjusted_result.loc[split_date]
                else:
                    dates_on_or_after: pd.Index = adjusted_price.index[
                        adjusted_price.index >= split_date
                    ]
                    if len(dates_on_or_after) > 0:
                        price_on_split_date_after = adjusted_result.loc[
                            dates_on_or_after[0]
                        ]

                logger.info(
                    f"股票分割調整: {stock_id} 在 {split_date} 進行 1:{int(split_ratio)} 分割，"
                    f"調整了 {num_adjusted} 筆價格數據（累積調整因子: {cumulative_ratio_for_split:.2f}）"
                )

                # 驗證調整是否正確：分割當天的調整後價格應該接近分割前一天的價格
                if (
                    price_on_split_date_after is not None
                    and price_before_split is not None
                ):
                    diff_pct: float = (
                        abs(price_on_split_date_after - price_before_split)
                        / price_before_split
                        * 100
                    )
                    if diff_pct > self.SPLIT_ADJUSTMENT_WARNING_PCT:
                        logger.warning(
                            f"警告：分割當天調整後價格 ({price_on_split_date_after:.2f}) 與分割前一天價格 ({price_before_split:.2f}) 差異較大 ({diff_pct:.2f}%)，"
                            f"可能表示分割比例配置不正確或數據有問題"
                        )
            else:
                logger.warning(
                    f"股票分割調整: {stock_id} 在 {split_date} 的分割事件沒有找到需要調整的價格數據。"
                    f"可用日期範圍: {adjusted_price.index.min()} ~ {adjusted_price.index.max()}"
                )

        return adjusted_result

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

        # 過濾出已平倉的交易記錄（只有已平倉的記錄才有完整的買賣資訊）
        # 確保交易記錄按 sell_date 排序（對於 tick 級別回測，同一天可能有多筆交易）
        # 排序確保累積值的計算順序正確，以及繪圖時 groupby().last() 能取得正確的最後一筆
        # 此排序邏輯對 tick 和 day 級別回測都適用
        #
        # 排序邏輯：
        # 1. 主要排序：按 sell_date（賣出日期）
        # 2. 次要排序：保持 trade_records 的原始添加順序（使用索引）
        #    原因：trade_records 是按平倉順序添加的，而 id 是按開倉順序生成的
        #    使用原始順序可以確保同一天內的多筆交易按實際平倉時間順序排列
        closed_records_with_index: List[Tuple[int, StockTradeRecord]] = [
            (i, r) for i, r in enumerate(self.account.trade_records) if r.is_closed
        ]
        sorted_records: List[StockTradeRecord] = [
            r
            for _, r in sorted(
                closed_records_with_index,
                key=lambda x: (
                    x[1].sell_date if x[1].sell_date else datetime.date.min,
                    x[0],  # 使用原始索引作為次要排序鍵，保持平倉順序
                ),
            )
        ]

        # Generate trading report
        rows: List[Dict[str, Any]] = []
        for record in sorted_records:
            cumulative_pnl += record.realized_pnl
            cumulative_balance += record.realized_pnl

            row: Dict[str, Any] = {
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
        df: pd.DataFrame = pd.concat([init_row, df], ignore_index=True)

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

        # === 清理 benchmark_price 數據 ===
        # 移除缺失值和 0 值（0 值可能是數據錯誤或停牌），並確保索引唯一且排序
        # 注意：股票收盤價不可能是負數，所以不需要特別檢查負數
        benchmark_price_clean: pd.Series = self.benchmark_price.copy()
        benchmark_price_clean = benchmark_price_clean[
            benchmark_price_clean.notna() & (benchmark_price_clean > 0)
        ]
        benchmark_price_clean = benchmark_price_clean.sort_index()
        benchmark_price_clean = benchmark_price_clean[
            ~benchmark_price_clean.index.duplicated(keep="last")
        ]

        if len(benchmark_price_clean) == 0:
            logger.warning(f"benchmark_price 數據異常，無法繪製 benchmark 曲線")
            return

        # === 計算調整後價格（處理股票分割） ===
        benchmark_price_adjusted: pd.Series = self._get_adjusted_price(
            benchmark_price_clean, self.benchmark
        )

        # === Benchmark 淨值曲線 ===
        benchmark_net_worth: pd.Series = (
            benchmark_price_adjusted
            / benchmark_price_adjusted.iloc[0]
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
        # 使用 benchmark 的所有交易日作為基準日期（確保日期對齊正確）
        # benchmark 的日期通常是完整的交易日曆，所以用它作為基準更合理
        all_dates: pd.Index = benchmark_net_worth.index.sort_values()

        # 將策略數據重新索引到 benchmark 的日期上，使用前向填充處理沒有交易的日期
        cumulative_balance_aligned: pd.Series = cumulative_balance.reindex(
            all_dates
        ).ffill()
        # 如果仍有 NaN（例如在第一次交易之前的日期），用初始資金填充
        if cumulative_balance_aligned.isna().any():
            cumulative_balance_aligned = cumulative_balance_aligned.fillna(
                self.account.init_capital
            )

        # benchmark_net_worth 已經在 all_dates 上（因為 all_dates 就是從它的 index 來的），直接使用即可
        benchmark_net_worth_aligned: pd.Series = benchmark_net_worth

        networth_df: pd.DataFrame = pd.DataFrame(
            {
                "Date": all_dates,
                "Strategy Net Worth": cumulative_balance_aligned.values,
                f"{self.benchmark} Net Worth": benchmark_net_worth_aligned.values,
            }
        )

        # 計算報酬率 (ROI)
        strategy_roi: float = round(
            (cumulative_balance.iloc[-1] / self.account.init_capital - 1) * 100, 2
        )
        benchmark_roi: float = round(
            (benchmark_price_adjusted.iloc[-1] / benchmark_price_adjusted.iloc[0] - 1)
            * 100,
            2,
        )

        roi_text: str = (
            f"Strategy Total ROI(%): {strategy_roi}%\n"
            f"{self.benchmark} Total ROI(%): {benchmark_roi}%"
        )

        # === 繪製圖表 ===
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

        # === 清理 benchmark_price 數據 ===
        # 移除缺失值和 0 值（0 值可能是數據錯誤或停牌），並確保索引唯一且排序
        # 注意：股票收盤價不可能是負數，所以不需要特別檢查負數
        benchmark_price_clean: pd.Series = self.benchmark_price.copy()
        benchmark_price_clean = benchmark_price_clean[
            benchmark_price_clean.notna() & (benchmark_price_clean > 0)
        ]
        benchmark_price_clean = benchmark_price_clean.sort_index()
        benchmark_price_clean = benchmark_price_clean[
            ~benchmark_price_clean.index.duplicated(keep="last")
        ]

        if len(benchmark_price_clean) == 0:
            logger.warning(f"benchmark_price 數據異常，無法繪製 benchmark MDD")
            return

        # === 計算調整後價格（處理股票分割） ===
        benchmark_price_adjusted: pd.Series = self._get_adjusted_price(
            benchmark_price_clean, self.benchmark
        )

        # === 計算 Benchmark 的 MDD (%) ===
        # 使用調整後價格計算 MDD，這樣可以正確處理股票分割
        mdd_benchmark: pd.Series = (
            benchmark_price_adjusted / benchmark_price_adjusted.cummax() - 1
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

        # === 整理 DataFrame 用來繪圖 ===
        # 使用 benchmark 的所有交易日作為基準日期（確保日期對齊正確）
        # benchmark 的日期通常是完整的交易日曆，所以用它作為基準更合理
        all_dates: pd.Index = mdd_benchmark.index.sort_values()

        # 將策略數據重新索引到 benchmark 的日期上，使用前向填充處理沒有交易的日期
        cumulative_balance_aligned: pd.Series = cumulative_balance.reindex(
            all_dates
        ).ffill()
        # 如果仍有 NaN（例如在第一次交易之前的日期），用初始資金填充
        if cumulative_balance_aligned.isna().any():
            cumulative_balance_aligned = cumulative_balance_aligned.fillna(
                self.account.init_capital
            )

        # 在對齊後的日期上計算策略的 MDD
        mdd_balance: pd.Series = (
            cumulative_balance_aligned / cumulative_balance_aligned.cummax() - 1
        ) * 100

        # mdd_benchmark 已經在 all_dates 上（因為 all_dates 就是從它的 index 來的），直接使用即可
        mdd_benchmark_aligned: pd.Series = mdd_benchmark

        mdd_df: pd.DataFrame = pd.DataFrame(
            {
                "Date": all_dates,
                "Strategy MDD": mdd_balance.values,
                f"{self.benchmark} MDD": mdd_benchmark_aligned.values,
            }
        )

        # === 繪製圖表 ===
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
                    size=self.CHART_FONT_SIZE,
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
            save_path: Path = self.output_dir / file_name
        else:
            save_path: Path = Path(file_name)

        # 確保資料夾存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 輸出 CSV 檔案
        df.to_csv(save_path, index=False, encoding=FileEncoding.UTF8_SIG.value)
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
            save_path: Path = self.output_dir / file_name
        else:
            save_path: Path = Path(file_name)

        # 確保資料夾存在
        save_path.parent.mkdir(parents=True, exist_ok=True)

        # 輸出圖片
        fig.write_image(str(save_path))
        logger.info(f"* Figure saved to: {save_path}")
