"""
Overnight lead-signal strategy backtest module.

Uses TSM, ^SOX, and TWD=X as pre-open lead features to forecast same-day
2330.TW return and run a long-or-flat daily backtest.
"""

from __future__ import annotations

import datetime as dt
from pathlib import Path
from typing import Optional, Tuple

import numpy as np
import pandas as pd
import plotly.graph_objects as go
import yfinance as yf
from core.api.stock_price_api import StockPriceAPI
from core.utils import Units
from core.utils.instrument import StockUtils

_PROJECT_ROOT = Path(__file__).resolve().parents[1]

TRAIN_END = dt.date(2020, 12, 31)
VAL_START = dt.date(2021, 1, 1)
VAL_END = dt.date(2021, 12, 31)
TEST_START = dt.date(2022, 1, 1)

FEE_BUY: float = 0.001425
FEE_SELL_PLUS_TAX: float = 0.001425 + 0.003


def _ridge_fit_predict(
    X_train: np.ndarray,
    y_train: np.ndarray,
    X_pred: np.ndarray,
    alpha: float,
) -> Tuple[np.ndarray, np.ndarray]:
    n, p = X_train.shape
    X1 = np.c_[np.ones(n), X_train]
    reg = np.eye(p + 1)
    reg[0, 0] = 0.0
    coef = np.linalg.solve(X1.T @ X1 + alpha * reg, X1.T @ y_train)
    y_hat = np.c_[np.ones(len(X_pred)), X_pred] @ coef
    return coef, y_hat


def fetch_panel(start: dt.date, end: dt.date) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """
    2330 收盤與報酬：與 core/backtest 一致，使用 StockPriceAPI（SQLite）。
    美股特徵：yfinance（TSM、^SOX、TWD=X）。
    """
    tw_id = "2330"
    price_api = StockPriceAPI()
    tw_df = price_api.get_stock_price(tw_id, start, end)
    if tw_df.empty:
        raise RuntimeError(
            f"No DB price rows for {tw_id} between {start} and {end}. "
            "Populate core/database price table to match backtester."
        )
    tw_df = tw_df.sort_values("date").reset_index(drop=True)
    tw_df["date"] = pd.to_datetime(tw_df["date"]).dt.normalize()
    tw_px = tw_df.set_index("date")["收盤價"].astype(float).sort_index()
    tw_px.index = pd.to_datetime(tw_px.index).tz_localize(None).normalize()

    us_tickers = ["TSM", "^SOX", "TWD=X"]
    data = yf.download(
        us_tickers,
        start=start.strftime("%Y-%m-%d"),
        end=end.strftime("%Y-%m-%d"),
        interval="1d",
        auto_adjust=True,
        progress=False,
        threads=True,
    )
    if data.empty:
        raise RuntimeError("yfinance returned empty dataset for US tickers.")
    close_us = data["Close"].copy() if isinstance(data.columns, pd.MultiIndex) else data[["Close"]].copy()
    if not isinstance(data.columns, pd.MultiIndex):
        close_us.columns = us_tickers[:1]
    close_us = close_us.sort_index()
    close_us.index = pd.to_datetime(close_us.index).tz_localize(None).normalize()
    rets = close_us.pct_change()
    us_calendar = close_us["TSM"].dropna().index

    close_df = pd.DataFrame({"2330.TW": tw_px})

    rows = []
    for ts in tw_px.index:
        ts_d = pd.Timestamp(ts).normalize()
        prev_us = us_calendar[us_calendar < ts_d]
        if len(prev_us) == 0:
            continue
        us_d = prev_us.max()
        try:
            r_tsm = float(rets.loc[us_d, "TSM"])
            r_sox = float(rets.loc[us_d, "^SOX"])
            r_fx = float(rets.loc[us_d, "TWD=X"])
        except (KeyError, ValueError):
            continue
        if any(np.isnan([r_tsm, r_sox, r_fx])):
            continue
        loc = tw_px.index.get_indexer([ts_d], method="pad")[0]
        if loc <= 0:
            continue
        r_tw = float(tw_px.iloc[loc] / tw_px.iloc[loc - 1] - 1.0)
        if np.isnan(r_tw):
            continue
        rows.append(
            {
                "date": ts_d.date(),
                "r_tsm_us": r_tsm,
                "r_sox_us": r_sox,
                "r_twd": r_fx,
                "r_2330": r_tw,
                "close_2330": float(tw_px.iloc[loc]),
            }
        )

    panel = pd.DataFrame(rows).dropna()
    panel = panel.drop_duplicates(subset=["date"], keep="last").sort_values("date").reset_index(drop=True)
    return close_df, panel


def tune_alpha(
    X_train: np.ndarray, y_train: np.ndarray, X_val: np.ndarray, y_val: np.ndarray, grid: np.ndarray
) -> float:
    best_alpha = float(grid[0])
    best_mse = np.inf
    for a in grid:
        _, y_hat = _ridge_fit_predict(X_train, y_train, X_val, float(a))
        mse = float(np.mean((y_val - y_hat) ** 2))
        if mse < best_mse:
            best_mse = mse
            best_alpha = float(a)
    return best_alpha


def run_backtest_with_signal(exec_df: pd.DataFrame) -> pd.DataFrame:
    pred = exec_df["pred"].values.astype(float)
    signal = exec_df["signal"].values.astype(int)
    close = exec_df["close_2330"].values.astype(float)
    r = exec_df["r_2330"].values.astype(float)

    # Event-driven aligned simulation: close-price execution, integer lots, TW fee/tax.
    init_capital = 1_000_000.0
    cash = init_capital
    hold_lots = 0
    equity_series = []
    pos_series = []
    strat_r = []

    def max_buyable_lots(balance: float, price: float) -> int:
        lots = int(balance // (price * Units.LOT))
        while lots > 0:
            comm = StockUtils.calculate_transaction_commission(price=price, volume=lots)
            need = lots * price * Units.LOT + comm
            if need <= balance:
                return lots
            lots -= 1
        return 0

    prev_equity = init_capital
    for i in range(len(exec_df)):
        px = close[i]
        sig = signal[i]

        if sig == 1 and hold_lots == 0:
            buy_lots = max_buyable_lots(cash, px)
            if buy_lots > 0:
                buy_comm = StockUtils.calculate_transaction_commission(
                    price=px, volume=buy_lots
                )
                cash -= buy_lots * px * Units.LOT + buy_comm
                hold_lots = buy_lots
        elif sig == 0 and hold_lots > 0:
            sell_comm = StockUtils.calculate_transaction_commission(
                price=px, volume=hold_lots
            )
            sell_tax = StockUtils.calculate_transaction_tax(price=px, volume=hold_lots)
            cash += hold_lots * px * Units.LOT - (sell_comm + sell_tax)
            hold_lots = 0

        equity = cash + hold_lots * px * Units.LOT
        equity_series.append(equity)
        pos_series.append(1.0 if hold_lots > 0 else 0.0)
        day_r = equity / prev_equity - 1.0 if prev_equity > 0 else 0.0
        strat_r.append(day_r)
        prev_equity = equity

    equity_s = np.array(equity_series) / init_capital
    bh_equity = (1.0 + r).cumprod()
    dd_s = equity_s / np.maximum.accumulate(equity_s) - 1.0
    dd_bh = bh_equity / np.maximum.accumulate(bh_equity) - 1.0

    out = exec_df[["date"]].copy()
    out["pred"] = pred
    out["position"] = np.array(pos_series)
    out["r_strategy"] = np.array(strat_r)
    out["r_buyhold"] = r
    out["equity_strategy"] = equity_s
    out["equity_buyhold"] = bh_equity
    out["dd_strategy"] = dd_s
    out["dd_buyhold"] = dd_bh
    return out


def information_coefficient(y: np.ndarray, y_hat: np.ndarray) -> float:
    if len(y) < 3:
        return float("nan")
    return float(np.corrcoef(y, y_hat)[0, 1])


def annualized_sharpe(daily_r: np.ndarray, rf_daily: float = 0.02 / 252) -> float:
    x = daily_r - rf_daily
    s = float(np.std(x, ddof=1))
    if s < 1e-12:
        return float("nan")
    return float(np.sqrt(252) * np.mean(x) / s)


def max_drawdown_pct(dd: np.ndarray) -> float:
    return float(np.min(dd) * 100.0)


def save_fig(fig: go.Figure, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.write_image(str(path), scale=2)
    fig.write_html(str(path.with_suffix(".html")))


def plot_equity_curve(bt: pd.DataFrame, out_dir: Path, title_suffix: str) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bt["date"], y=bt["equity_strategy"], name="Overnight Signal Strategy", line=dict(color="#2563eb", width=2)))
    fig.add_trace(
        go.Scatter(x=bt["date"], y=bt["equity_buyhold"], name="Buy & Hold 2330.TW", line=dict(color="#94a3b8", width=2, dash="dash"))
    )
    fig.update_layout(
        title=f"Equity Curve {title_suffix}",
        xaxis_title="Date",
        yaxis_title="Equity (Start = 1)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(size=14),
    )
    save_fig(fig, out_dir / "equity_curve.png")


def plot_mdd(bt: pd.DataFrame, out_dir: Path, title_suffix: str) -> None:
    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bt["date"], y=bt["dd_strategy"] * 100.0, name="Strategy MDD (%)", fill="tozeroy", line=dict(color="#dc2626")))
    fig.add_trace(
        go.Scatter(x=bt["date"], y=bt["dd_buyhold"] * 100.0, name="2330 B&H MDD (%)", line=dict(color="#cbd5e1", dash="dot"))
    )
    fig.update_layout(
        title=f"Underwater Drawdown {title_suffix}",
        xaxis_title="Date",
        yaxis_title="Drawdown (%)",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(size=14),
    )
    save_fig(fig, out_dir / "mdd_underwater.png")


def plot_rolling_sharpe(bt: pd.DataFrame, out_dir: Path, window: int = 63) -> None:
    rs = bt["r_strategy"].astype(float)
    rb = bt["r_buyhold"].astype(float)

    def roll_sharpe(r: pd.Series) -> pd.Series:
        m = r.rolling(window, min_periods=max(20, window // 3)).mean()
        s = r.rolling(window, min_periods=max(20, window // 3)).std(ddof=1)
        return np.sqrt(252) * m / s

    fig = go.Figure()
    fig.add_trace(go.Scatter(x=bt["date"], y=roll_sharpe(rs), name=f"Strategy Rolling Sharpe ({window}d)", line=dict(color="#2563eb")))
    fig.add_trace(
        go.Scatter(x=bt["date"], y=roll_sharpe(rb), name=f"B&H Rolling Sharpe ({window}d)", line=dict(color="#94a3b8", dash="dash"))
    )
    fig.add_hline(y=0, line_dash="dot", line_color="#ccc")
    fig.update_layout(
        title="Rolling Sharpe Ratio (Annualized, Daily)",
        xaxis_title="Date",
        yaxis_title="Sharpe",
        template="plotly_white",
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        font=dict(size=14),
    )
    save_fig(fig, out_dir / "rolling_sharpe.png")


def plot_rolling_ic(panel_with_pred: pd.DataFrame, out_dir: Path, window: int = 126) -> None:
    """Rolling information coefficient to monitor potential alpha decay."""
    df = panel_with_pred.sort_values("date").reset_index(drop=True)
    ic_roll = df["pred"].rolling(window, min_periods=max(30, window // 4)).corr(df["r_2330"])
    fig = go.Figure(go.Scatter(x=df["date"], y=ic_roll, name="Rolling IC", line=dict(color="#0d9488")))
    fig.add_hline(y=0, line_dash="dot", line_color="#ccc")
    fig.update_layout(title=f"Rolling IC (Pearson, {window} trading days)", xaxis_title="Date", yaxis_title="IC", template="plotly_white", font=dict(size=14))
    save_fig(fig, out_dir / "rolling_ic.png")


def plot_ic_by_year(panel_with_pred: pd.DataFrame, out_dir: Path) -> None:
    """Yearly IC for signal effectiveness by year."""
    df = panel_with_pred.copy()
    df["year"] = pd.to_datetime(df["date"]).dt.year
    ics = []
    for y, g in df.groupby("year"):
        ics.append({"year": y, "IC": information_coefficient(g["r_2330"].values, g["pred"].values)})
    ic_df = pd.DataFrame(ics)
    fig = go.Figure(data=go.Bar(x=ic_df["year"], y=ic_df["IC"], marker_color="#7c3aed"))
    fig.update_layout(title="Information Coefficient (IC): Prediction vs Realized Return by Year", xaxis_title="Year", yaxis_title="IC (Pearson)", template="plotly_white", font=dict(size=14))
    save_fig(fig, out_dir / "ic_by_year.png")
    ic_df.to_csv(out_dir / "ic_by_year.csv", index=False)


def plot_monthly_returns_heatmap(bt: pd.DataFrame, out_dir: Path) -> None:
    d = pd.to_datetime(bt["date"])
    mret = bt.assign(ym=d.dt.to_period("M")).groupby("ym")["r_strategy"].apply(lambda s: (1 + s).prod() - 1)
    pivot = mret.reset_index()
    pivot["year"] = pivot["ym"].dt.year
    pivot["month"] = pivot["ym"].dt.month
    mat = pivot.pivot(index="year", columns="month", values="r_strategy") * 100.0
    fig = go.Figure(data=go.Heatmap(z=mat.values, x=[f"M{m}" for m in mat.columns], y=mat.index.astype(str), colorscale="RdYlGn", zmid=0, colorbar=dict(title="%")))
    fig.update_layout(title="Strategy Monthly Return Heatmap (%)", template="plotly_white", font=dict(size=14))
    save_fig(fig, out_dir / "monthly_returns_heatmap.png")


def summary_metrics(bt: pd.DataFrame) -> pd.Series:
    rs = bt["r_strategy"].values.astype(float)
    rb = bt["r_buyhold"].values.astype(float)
    years = max((bt["date"].max() - bt["date"].min()).days / 365.25, 0.25)
    total_s = float(bt["equity_strategy"].iloc[-1] - 1.0)
    total_b = float(bt["equity_buyhold"].iloc[-1] - 1.0)
    ann_s = (1 + total_s) ** (1 / years) - 1 if years > 0 else np.nan
    ann_b = (1 + total_b) ** (1 / years) - 1 if years > 0 else np.nan
    vol_s = float(np.std(rs, ddof=1) * np.sqrt(252))
    calmar = ann_s / abs(max_drawdown_pct(bt["dd_strategy"].values) / 100.0 + 1e-9)
    win = float(np.mean(rs[bt["position"].values > 0] > 0)) if (bt["position"] > 0).any() else np.nan
    return pd.Series(
        {
            "區間天數": len(bt),
            "策略累積報酬": total_s,
            "B&H累積報酬": total_b,
            "策略年化報酬": ann_s,
            "B&H年化報酬": ann_b,
            "策略年化波動": vol_s,
            "策略Sharpe": annualized_sharpe(rs),
            "B&H_Sharpe": annualized_sharpe(rb),
            "策略最大回撤%": max_drawdown_pct(bt["dd_strategy"].values),
            "B&H最大回撤%": max_drawdown_pct(bt["dd_buyhold"].values),
            "卡瑪比率(估)": calmar,
            "做多日勝率": win,
        }
    )


def main(
    output_dir: Optional[Path] = None,
    data_start: dt.date = dt.date(2020, 1, 1),
    data_end: Optional[dt.date] = None,
) -> Path:
    data_end = data_end or dt.date.today()
    out = Path(output_dir or (_PROJECT_ROOT / "strategy_lab" / "output"))
    out.mkdir(parents=True, exist_ok=True)

    close_df, panel = fetch_panel(data_start, data_end)
    panel = panel[panel["date"] >= data_start].reset_index(drop=True)

    x_cols = ["r_tsm_us", "r_sox_us", "r_twd"]
    train = panel[(panel["date"] <= TRAIN_END)].copy()
    val = panel[(panel["date"] >= VAL_START) & (panel["date"] <= VAL_END)].copy()
    test = panel[panel["date"] >= TEST_START].copy()

    X_tr, y_tr = train[x_cols].values.astype(float), train["r_2330"].values.astype(float)
    X_va, y_va = val[x_cols].values.astype(float), val["r_2330"].values.astype(float)
    alpha = tune_alpha(X_tr, y_tr, X_va, y_va, np.logspace(-4, 3, 30))

    fit_mask = panel["date"] <= VAL_END
    X_fit = panel.loc[fit_mask, x_cols].values.astype(float)
    y_fit = panel.loc[fit_mask, "r_2330"].values.astype(float)
    coef, _ = _ridge_fit_predict(X_fit, y_fit, X_fit, alpha)

    panel_test = test.reset_index(drop=True)
    _, pred_test = _ridge_fit_predict(
        X_fit, y_fit, panel_test[x_cols].values.astype(float), alpha
    )
    signal_df = panel_test[["date", "r_2330", "close_2330"]].copy()
    signal_df["pred"] = pred_test
    signal_df["signal"] = (signal_df["pred"] > 0.0).astype(int)

    # Align with event-driven loop: evaluate every TW trading day.
    tw_px = close_df["2330.TW"].dropna().sort_index()
    tw_ret = tw_px.pct_change()
    exec_df = pd.DataFrame(
        {
            "date": tw_px.index.date,
            "close_2330": tw_px.values,
            "r_2330": tw_ret.values,
        }
    )
    exec_df = exec_df[(exec_df["date"] >= TEST_START) & (exec_df["date"] <= data_end)]
    exec_df = exec_df.dropna(subset=["r_2330", "close_2330"]).copy()
    exec_df = exec_df.merge(
        signal_df[["date", "pred", "signal"]],
        on="date",
        how="left",
    )
    exec_df["pred"] = exec_df["pred"].fillna(0.0)
    exec_df["signal"] = exec_df["signal"].fillna(0).astype(int)

    bt = run_backtest_with_signal(exec_df)

    summary_metrics(bt).to_csv(out / "metrics_summary.csv", header=["value"])
    pd.Series(
        {
            "ridge_alpha": alpha,
            "data_start": str(data_start),
            "data_end": str(data_end),
            "train_end": str(TRAIN_END),
            "val": f"{VAL_START}~{VAL_END}",
            "test_start": str(TEST_START),
            "fee_buy": FEE_BUY,
            "fee_sell_plus_tax": FEE_SELL_PLUS_TAX,
        }
    ).to_csv(out / "run_meta.csv", header=["value"])

    title_suffix = f"(Test {TEST_START} to {bt['date'].max()})"
    plot_equity_curve(bt, out, title_suffix)
    plot_mdd(bt, out, title_suffix)
    plot_rolling_sharpe(bt, out)
    ic_panel = exec_df[["date", "r_2330", "pred"]].copy()
    plot_ic_by_year(ic_panel, out)
    plot_rolling_ic(ic_panel, out)
    plot_monthly_returns_heatmap(bt, out)
    bt.to_csv(out / "backtest_daily.csv", index=False)
    return out


if __name__ == "__main__":
    p = main()
    print(f"Done. Output: {p}")

