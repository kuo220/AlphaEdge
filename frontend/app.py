from __future__ import annotations

from pathlib import Path
from typing import Dict

import pandas as pd
import plotly.express as px
import streamlit as st

try:
    from config import RESULTS_ROOT
    from services.report_loader import (
        BacktestReport,
        list_strategy_dirs,
        load_backtest_report,
        read_trading_report,
    )
except ModuleNotFoundError:
    from frontend.config import RESULTS_ROOT
    from frontend.services.report_loader import (
        BacktestReport,
        list_strategy_dirs,
        load_backtest_report,
        read_trading_report,
    )


st.set_page_config(page_title="AlphaEdge Backtest Viewer", layout="wide")
st.title("Backtest Report")


def _to_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _render_metrics(df: pd.DataFrame) -> None:
    realized_pnl = _to_numeric(df, "Realized PnL")
    roi = _to_numeric(df, "ROI")
    cumulative_balance = _to_numeric(df, "Cumulative Balance")

    trade_count = int(len(df))
    win_count = int((realized_pnl > 0).sum())
    loss_count = int((realized_pnl < 0).sum())
    win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0.0
    total_pnl = float(realized_pnl.sum()) if not realized_pnl.empty else 0.0
    avg_roi = float(roi.mean() * 100) if not roi.empty else 0.0
    last_balance = float(cumulative_balance.iloc[-1]) if not cumulative_balance.empty else 0.0

    col1, col2, col3, col4, col5, col6 = st.columns(6)
    col1.metric("總交易數", trade_count)
    col2.metric("勝率", f"{win_rate:.2f}%")
    col3.metric("獲利筆數 / 虧損筆數", f"{win_count} / {loss_count}")
    col4.metric("總已實現損益", f"{total_pnl:,.2f}")
    col5.metric("平均 ROI", f"{avg_roi:.2f}%")
    col6.metric("最後累積資產", f"{last_balance:,.2f}")


def _render_interactive_charts(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("目前沒有交易資料可畫圖。")
        return

    chart_df = df.copy()
    if "Sell Date" in chart_df.columns:
        chart_df["Sell Date"] = pd.to_datetime(chart_df["Sell Date"], errors="coerce")
        chart_df = chart_df.sort_values("Sell Date")

    if "Cumulative Balance" in chart_df.columns and "Sell Date" in chart_df.columns:
        chart_df["Cumulative Balance"] = pd.to_numeric(
            chart_df["Cumulative Balance"], errors="coerce"
        )
        line_fig = px.line(
            chart_df,
            x="Sell Date",
            y="Cumulative Balance",
            markers=True,
            title="互動資產曲線（可縮放、框選）",
        )
        st.plotly_chart(line_fig, use_container_width=True)

    if "Realized PnL" in chart_df.columns and "Sell Date" in chart_df.columns:
        chart_df["Realized PnL"] = pd.to_numeric(chart_df["Realized PnL"], errors="coerce")
        daily = (
            chart_df.dropna(subset=["Sell Date"])
            .groupby(chart_df["Sell Date"].dt.date)["Realized PnL"]
            .sum()
            .reset_index()
            .rename(columns={"Sell Date": "Date", "Realized PnL": "Daily PnL"})
        )
        bar_fig = px.bar(daily, x="Date", y="Daily PnL", title="每日損益（互動）")
        st.plotly_chart(bar_fig, use_container_width=True)


def _render_chart_images(chart_paths: Dict[str, Path | None]) -> None:
    for chart_name, chart_path in chart_paths.items():
        st.subheader(chart_name)
        if chart_path is None:
            st.warning(f"找不到 `{chart_name}` 圖檔。")
            continue
        st.image(str(chart_path), caption=chart_path.name, use_container_width=True)


strategy_dirs = list_strategy_dirs(RESULTS_ROOT)
if not strategy_dirs:
    st.error(
        f"找不到任何回測結果資料夾。請確認路徑 `{RESULTS_ROOT}` 是否存在，"
        "或設定環境變數 `ALPHAEDGE_BACKTEST_RESULTS`。"
    )
    st.stop()

with st.sidebar:
    st.header("設定")
    selected = st.selectbox(
        "策略資料夾",
        options=strategy_dirs,
        format_func=lambda path: path.name,
        index=0,
    )
    st.caption(f"結果根目錄：`{RESULTS_ROOT}`")

report: BacktestReport = load_backtest_report(selected)

if report.csv_path is None:
    st.error(f"`{selected.name}` 中找不到 trading report CSV。")
    st.stop()

df = read_trading_report(report.csv_path)

overview_tab, detail_tab, chart_tab, image_tab, download_tab = st.tabs(
    ["總覽", "交易明細", "互動圖表", "圖片", "下載"]
)

with overview_tab:
    st.subheader("關鍵指標")
    _render_metrics(df)
    st.caption(f"報表檔案：`{report.csv_path.name}`")

with detail_tab:
    st.subheader("交易報表")
    stock_col = "Stock ID" if "Stock ID" in df.columns else None
    if stock_col:
        stock_ids = sorted(df[stock_col].dropna().astype(str).unique().tolist())
        selected_stock = st.multiselect("依股票代號篩選", options=stock_ids)
        filtered_df = (
            df[df[stock_col].astype(str).isin(selected_stock)] if selected_stock else df
        )
    else:
        filtered_df = df
    st.dataframe(filtered_df, use_container_width=True, height=480)

with chart_tab:
    st.subheader("互動圖表")
    _render_interactive_charts(df)

with image_tab:
    st.subheader("回測輸出圖片")
    _render_chart_images(report.chart_paths)

with download_tab:
    st.subheader("下載")
    st.download_button(
        label="下載 trading report CSV",
        data=report.csv_path.read_bytes(),
        file_name=report.csv_path.name,
        mime="text/csv",
    )
    for chart_name, chart_path in report.chart_paths.items():
        if chart_path is None:
            continue
        st.download_button(
            label=f"下載 {chart_name}",
            data=chart_path.read_bytes(),
            file_name=chart_path.name,
            mime="image/png",
            key=f"download-{chart_name}",
        )
