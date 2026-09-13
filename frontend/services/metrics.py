from __future__ import annotations

from typing import List, Optional, Tuple

import pandas as pd

from core.backtest.analysis.risk_metrics import (
    TRADING_DAYS_PER_YEAR,
    compute_annualized_sharpe,
    compute_annualized_sortino,
)

"""
前端的指標計算

**與 reporter 共用同一份公式**：Sharpe 與 Sortino 直接 import
`core/backtest/analysis/risk_metrics.py` 的純函式，不在前端另寫一份。
同一個指標算兩次、寫在兩個地方，最後一定會出現「報表說 1.2、前端說 0.8」
而沒有人知道哪個對。

舊版 `app.py` 自己寫的那份正好是 `risk_metrics` 開頭列的四個缺陷：
以 `ddof=0` 取標準差、沒有扣無風險利率、Sortino 對「低於門檻的那幾期」
取標準差（那是它們**彼此之間**的離散度，不是相對門檻的偏差）。

本模組不含任何 Streamlit 呼叫，這樣才測得到——`frontend/app.py` 在 import 時
就會執行 Streamlit 的版面設定，無法在測試裡 import（所以指標函式才獨立成本模組）。

---

⚠️ **這是前端唯一 import `core` 的地方**，且只用得到 `risk_metrics`——
它是只相依 `math` 與 `typing` 的純函式檔。`core/backtest/analysis/__init__.py`
因此刻意不 eager import analyzer（否則會拉進 shioaji 與 sqlite3，
實測 1,164 個模組），`frontend/Dockerfile` 也只 COPY 這條最小鏈。
`tests/test_frontend_metrics.py` 有一條測試盯住這個 import 不會變重。
"""

# 回測區間取自進出場日；`Sell Date` 對 SHORT 是開倉日，單獨用它定義不出區間
DATE_COLUMNS: List[str] = [
    "Entry Date",
    "Exit Date",
    "Buy Date",
    "Sell Date",
    "Date",
]


def _to_float_list(daily_returns: pd.Series) -> List[float]:
    """把 pandas 的日報酬轉成純 float list（`risk_metrics` 只吃序列，不吃 pandas）"""

    return [float(value) for value in daily_returns.dropna().to_numpy()]


def calc_sharpe_ratio(
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> Optional[float]:
    """
    - Description:
        年化 Sharpe ratio；公式見 `risk_metrics.compute_annualized_sharpe()`
    - Parameters:
        - daily_returns: pd.Series
            日報酬序列（小數，非百分比）
        - risk_free_rate: float
            年化無風險利率（小數）
    - Return:
        - Optional[float]
            年化 Sharpe；樣本不足時為 None
    """

    return compute_annualized_sharpe(
        _to_float_list(daily_returns), risk_free_rate=risk_free_rate
    )


def calc_sortino_ratio(
    daily_returns: pd.Series,
    risk_free_rate: float = 0.0,
) -> Optional[float]:
    """
    - Description:
        年化 Sortino ratio；公式見 `risk_metrics.compute_annualized_sortino()`
    - Parameters:
        - daily_returns: pd.Series
            日報酬序列（小數，非百分比）
        - risk_free_rate: float
            年化無風險利率（小數）
    - Return:
        - Optional[float]
            年化 Sortino；樣本不足或沒有下檔波動時為 None
    """

    return compute_annualized_sortino(
        _to_float_list(daily_returns), risk_free_rate=risk_free_rate
    )


def extract_backtest_date_range(
    df: pd.DataFrame,
) -> Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]:
    """
    - Description:
        由交易明細取回測區間

        取**所有**進出場日欄位的極值：只看 `Sell Date` 對 SHORT 是開倉日，
        區間的右端會提早。
    - Parameters:
        - df: pd.DataFrame
            交易明細
    - Return:
        - Tuple[Optional[pd.Timestamp], Optional[pd.Timestamp]]
            起訖日；沒有任何日期欄位時為 `(None, None)`
    """

    parsed_dates: List[pd.Series] = []
    for column in DATE_COLUMNS:
        if column in df.columns:
            dates: pd.Series = pd.to_datetime(df[column], errors="coerce").dropna()
            if not dates.empty:
                parsed_dates.append(dates)

    if not parsed_dates:
        return None, None

    merged: pd.Series = pd.concat(parsed_dates, ignore_index=True)
    if merged.empty:
        return None, None
    return pd.Timestamp(merged.min()), pd.Timestamp(merged.max())


__all__ = [
    "DATE_COLUMNS",
    "TRADING_DAYS_PER_YEAR",
    "calc_sharpe_ratio",
    "calc_sortino_ratio",
    "extract_backtest_date_range",
]
