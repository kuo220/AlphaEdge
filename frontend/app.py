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
st.markdown(
    """
    <style>
        :root {
            --ae-bg: var(--background-color);
            --ae-surface: var(--secondary-background-color);
            --ae-surface-2: color-mix(in srgb, var(--secondary-background-color) 80%, var(--text-color) 20%);
            --ae-sidebar: var(--secondary-background-color);
            --ae-border: color-mix(in srgb, var(--text-color) 20%, transparent 80%);
            --ae-text: var(--text-color);
            --ae-muted: color-mix(in srgb, var(--text-color) 60%, transparent 40%);
            --ae-accent: var(--primary-color);
            --ae-accent-hover: color-mix(in srgb, var(--primary-color) 85%, #000000 15%);
        }

        [data-testid="stAppViewContainer"] {
            background: var(--ae-bg);
            color: var(--ae-text);
        }

        [data-testid="stSidebar"] {
            background: var(--ae-sidebar);
            border-right: 1px solid var(--ae-border);
        }

        [data-testid="stSidebar"] * {
            color: var(--ae-text);
        }

        [data-testid="stHeader"] {
            background: transparent;
        }

        .stMarkdown h1, .stMarkdown h2, .stMarkdown h3, .stMarkdown h4,
        .stMarkdown h5, .stMarkdown h6, p, label, span {
            color: var(--ae-text) !important;
        }

        [data-baseweb="select"] > div,
        [data-baseweb="input"] > div,
        .stTextInput > div > div,
        .stNumberInput > div > div {
            background: var(--ae-surface);
            border-color: var(--ae-border);
            color: var(--ae-text);
        }

        [data-baseweb="tab-list"] {
            gap: 0.4rem;
        }

        button[kind="secondary"] {
            background: var(--ae-surface);
            border: 1px solid var(--ae-border);
            border-radius: 10px;
            color: var(--ae-text);
        }

        button[data-baseweb="tab"] {
            background: transparent;
            border: none;
            border-radius: 0;
            color: var(--ae-muted);
            box-shadow: none;
        }

        button[data-baseweb="tab"][aria-selected="true"] {
            background: transparent;
            border: none;
            color: var(--ae-text);
        }

        .stButton button,
        .stDownloadButton button {
            background: var(--ae-accent);
            color: #ffffff;
            border: none;
            border-radius: 10px;
        }

        .stButton button:hover,
        .stDownloadButton button:hover {
            background: var(--ae-accent-hover);
        }

        [data-testid="stMetric"] {
            background: var(--ae-surface);
            border: 1px solid var(--ae-border);
            border-radius: 12px;
            padding: 0.8rem;
        }

        [data-testid="stDataFrame"] {
            border: 1px solid var(--ae-border);
            border-radius: 12px;
            overflow: hidden;
        }

        [data-testid="stPlotlyChart"] {
            border: 1px solid var(--ae-border);
            border-radius: 16px;
            overflow: hidden;
            background: var(--ae-surface);
            padding: 0.25rem;
        }

        [data-testid="stImage"] img {
            border-radius: 16px;
            border: 1px solid var(--ae-border);
        }

        .stCaption {
            color: var(--ae-muted) !important;
        }

        .ae-info-card {
            background: var(--ae-surface);
            border: 1px solid var(--ae-border);
            border-radius: 14px;
            padding: 0.9rem 1rem;
            min-height: 96px;
            display: flex;
            flex-direction: column;
            justify-content: center;
            gap: 0.35rem;
        }

        .ae-info-label {
            font-size: 0.82rem;
            color: var(--ae-muted);
            letter-spacing: 0.02em;
        }

        .ae-info-value {
            font-size: 1.05rem;
            font-weight: 600;
            color: var(--ae-text);
            word-break: break-word;
        }
    </style>
    """,
    unsafe_allow_html=True,
)
st.title("Backtest Report")


def _to_numeric(df: pd.DataFrame, column: str) -> pd.Series:
    if column not in df.columns:
        return pd.Series(dtype=float)
    return pd.to_numeric(df[column], errors="coerce")


def _extract_daily_returns(df: pd.DataFrame) -> pd.Series:
    if "Sell Date" not in df.columns or "Cumulative Balance" not in df.columns:
        return pd.Series(dtype=float)

    work_df = df[["Sell Date", "Cumulative Balance"]].copy()
    work_df["Sell Date"] = pd.to_datetime(work_df["Sell Date"], errors="coerce")
    work_df["Cumulative Balance"] = pd.to_numeric(
        work_df["Cumulative Balance"], errors="coerce"
    )
    work_df = work_df.dropna(subset=["Sell Date", "Cumulative Balance"])
    if work_df.empty:
        return pd.Series(dtype=float)

    daily_balance = (
        work_df.groupby(work_df["Sell Date"].dt.date)["Cumulative Balance"]
        .last()
        .astype(float)
    )
    if daily_balance.empty:
        return pd.Series(dtype=float)

    daily_returns = daily_balance.pct_change().dropna()
    return daily_returns.replace([float("inf"), float("-inf")], pd.NA).dropna()


def _calc_sharpe_ratio(daily_returns: pd.Series, annualization: int = 252) -> float:
    if daily_returns.empty:
        return float("nan")
    std = daily_returns.std(ddof=0)
    if std == 0 or pd.isna(std):
        return float("nan")
    return float((daily_returns.mean() / std) * (annualization**0.5))


def _calc_sortino_ratio(daily_returns: pd.Series, annualization: int = 252) -> float:
    if daily_returns.empty:
        return float("nan")
    downside = daily_returns[daily_returns < 0]
    if downside.empty:
        return float("nan")
    downside_std = downside.std(ddof=0)
    if downside_std == 0 or pd.isna(downside_std):
        return float("nan")
    return float((daily_returns.mean() / downside_std) * (annualization**0.5))


def _extract_benchmark_returns(df: pd.DataFrame) -> pd.Series:
    benchmark_candidates = [
        "Benchmark Return",
        "Benchmark Daily Return",
        "Benchmark ROI",
    ]
    for column in benchmark_candidates:
        if column in df.columns:
            return pd.to_numeric(df[column], errors="coerce").dropna()
    return pd.Series(dtype=float)


def _calc_information_ratio(
    daily_returns: pd.Series, benchmark_returns: pd.Series, annualization: int = 252
) -> float:
    if daily_returns.empty or benchmark_returns.empty:
        return float("nan")

    min_len = min(len(daily_returns), len(benchmark_returns))
    if min_len == 0:
        return float("nan")

    strategy = daily_returns.tail(min_len).reset_index(drop=True)
    benchmark = benchmark_returns.tail(min_len).reset_index(drop=True)
    active_returns = strategy - benchmark
    tracking_error = active_returns.std(ddof=0)
    if tracking_error == 0 or pd.isna(tracking_error):
        return float("nan")
    return float((active_returns.mean() / tracking_error) * (annualization**0.5))


def _extract_starting_capital(df: pd.DataFrame) -> tuple[float | None, bool]:
    explicit_columns = [
        "Starting Capital",
        "Initial Capital",
        "Initial Balance",
        "起始資金",
        "本金",
    ]
    for column in explicit_columns:
        if column in df.columns:
            values = pd.to_numeric(df[column], errors="coerce").dropna()
            if not values.empty:
                return float(values.iloc[0]), False

    if "Cumulative Balance" in df.columns:
        values = pd.to_numeric(df["Cumulative Balance"], errors="coerce").dropna()
        if not values.empty:
            return float(values.iloc[0]), True
    return None, False


def _extract_backtest_date_range(df: pd.DataFrame) -> tuple[pd.Timestamp | None, pd.Timestamp | None]:
    date_columns = ["Buy Date", "Sell Date", "Date", "Trade Date", "交易日期", "買進日期", "賣出日期"]
    parsed_dates: list[pd.Series] = []
    for column in date_columns:
        if column in df.columns:
            dates = pd.to_datetime(df[column], errors="coerce").dropna()
            if not dates.empty:
                parsed_dates.append(dates)

    if not parsed_dates:
        return None, None

    merged = pd.concat(parsed_dates, ignore_index=True)
    if merged.empty:
        return None, None
    return pd.Timestamp(merged.min()), pd.Timestamp(merged.max())


def _render_info_card(label: str, value: str) -> None:
    st.markdown(
        f"""
        <div class="ae-info-card">
            <div class="ae-info-label">{label}</div>
            <div class="ae-info-value">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def _render_strategy_overview(report: BacktestReport, df: pd.DataFrame) -> None:
    starting_capital, is_estimated = _extract_starting_capital(df)
    start_date, end_date = _extract_backtest_date_range(df)

    if start_date is not None and end_date is not None:
        date_range = f"{start_date.date()} ~ {end_date.date()}"
    else:
        date_range = "N/A"

    if starting_capital is None:
        starting_capital_text = "N/A"
    else:
        starting_capital_text = f"{starting_capital:,.2f}"
        if is_estimated:
            starting_capital_text += "（估算）"

    c1, c2, c3 = st.columns(3)
    with c1:
        _render_info_card("策略名稱", report.strategy_name)
    with c2:
        _render_info_card("策略起始資金", starting_capital_text)
    with c3:
        _render_info_card("回測日期區間", date_range)


def _render_metrics(df: pd.DataFrame) -> None:
    realized_pnl = _to_numeric(df, "Realized PnL")
    roi = _to_numeric(df, "ROI")
    cumulative_balance = _to_numeric(df, "Cumulative Balance")
    daily_returns = _extract_daily_returns(df)
    benchmark_returns = _extract_benchmark_returns(df)

    trade_count = int(len(df))
    win_count = int((realized_pnl > 0).sum())
    loss_count = int((realized_pnl < 0).sum())
    win_rate = (win_count / trade_count * 100) if trade_count > 0 else 0.0
    total_pnl = float(realized_pnl.sum()) if not realized_pnl.empty else 0.0
    avg_roi = float(roi.mean() * 100) if not roi.empty else 0.0
    last_balance = float(cumulative_balance.iloc[-1]) if not cumulative_balance.empty else 0.0
    sharpe_ratio = _calc_sharpe_ratio(daily_returns)
    sortino_ratio = _calc_sortino_ratio(daily_returns)
    information_ratio = _calc_information_ratio(daily_returns, benchmark_returns)

    def _fmt_ratio(value: float) -> str:
        return f"{value:.3f}" if pd.notna(value) else "N/A"

    st.markdown("##### 交易概況")
    r1c1, r1c2, r1c3 = st.columns(3)
    r1c1.metric("總交易數", trade_count)
    r1c2.metric("勝率", f"{win_rate:.2f}%")
    r1c3.metric("獲利筆數 / 虧損筆數", f"{win_count} / {loss_count}")

    st.divider()

    st.markdown("##### 損益與資產")
    r2c1, r2c2, r2c3 = st.columns(3)
    r2c1.metric("總已實現損益", f"{total_pnl:,.2f}")
    r2c2.metric("平均 ROI", f"{avg_roi:.2f}%")
    r2c3.metric("最後累積資產", f"{last_balance:,.2f}")

    st.divider()

    st.markdown("##### 風險調整報酬")
    r3c1, r3c2, r3c3 = st.columns(3)
    r3c1.metric("Sharpe Ratio", _fmt_ratio(sharpe_ratio))
    r3c2.metric("Sortino Ratio", _fmt_ratio(sortino_ratio))
    r3c3.metric("Information Ratio", _fmt_ratio(information_ratio))


def _get_chart_theme() -> dict[str, str]:
    return {
        "paper_bg": "rgba(0,0,0,0)",
        "plot_bg": "rgba(0,0,0,0)",
        "grid": "var(--ae-border)",
        "text": "var(--ae-text)",
    }


def _render_interactive_charts(df: pd.DataFrame) -> None:
    if df.empty:
        st.info("目前沒有交易資料可畫圖。")
        return

    chart_df = df.copy()
    if "Sell Date" in chart_df.columns:
        chart_df["Sell Date"] = pd.to_datetime(chart_df["Sell Date"], errors="coerce")
        chart_df = chart_df.sort_values("Sell Date")

    chart_theme = _get_chart_theme()

    if "Cumulative Balance" in chart_df.columns and "Sell Date" in chart_df.columns:
        chart_df["Cumulative Balance"] = pd.to_numeric(
            chart_df["Cumulative Balance"], errors="coerce"
        )
        line_fig = px.line(
            chart_df,
            x="Sell Date",
            y="Cumulative Balance",
            markers=True,
            title="資產曲線",
        )
        line_fig.update_layout(
            paper_bgcolor=chart_theme["paper_bg"],
            plot_bgcolor=chart_theme["plot_bg"],
            font=dict(color=chart_theme["text"]),
            margin=dict(l=20, r=20, t=56, b=20),
            xaxis=dict(showgrid=True, gridcolor=chart_theme["grid"], gridwidth=1),
            yaxis=dict(showgrid=True, gridcolor=chart_theme["grid"], gridwidth=1),
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
        bar_fig = px.bar(
            daily,
            x="Date",
            y="Daily PnL",
            title="每日損益",
        )
        bar_fig.update_layout(
            paper_bgcolor=chart_theme["paper_bg"],
            plot_bgcolor=chart_theme["plot_bg"],
            font=dict(color=chart_theme["text"]),
            margin=dict(l=20, r=20, t=56, b=20),
            xaxis=dict(showgrid=True, gridcolor=chart_theme["grid"], gridwidth=1),
            yaxis=dict(showgrid=True, gridcolor=chart_theme["grid"], gridwidth=1),
        )
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
    ["總覽", "交易明細", "圖表", "圖片", "下載"]
)

with overview_tab:
    st.subheader("策略摘要")
    _render_strategy_overview(report, df)
    st.divider()
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
    st.subheader("圖表")
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
