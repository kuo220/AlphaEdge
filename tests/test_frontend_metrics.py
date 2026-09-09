import ast
import math
import subprocess
import sys
from pathlib import Path
from typing import List, Set

import pandas as pd
import pytest

from core.backtest.analysis.risk_metrics import (
    TRADING_DAYS_PER_YEAR,
    compute_annualized_sharpe,
    compute_annualized_sortino,
)
from frontend.services.metrics import (
    calc_sharpe_ratio,
    calc_sortino_ratio,
    extract_backtest_date_range,
)
from frontend.services.report_loader import (
    build_equity_series,
    compute_daily_returns,
    compute_max_drawdown,
)

"""
前端與 reporter 用同一份公式（F-085、F-068）

舊版 `frontend/app.py` 自己寫了一份 Sharpe／Sortino，而且**寫在模組層級的
Streamlit 呼叫之後**——測試連 import 都做不到，於是那份公式從來沒有被驗證過。
它正好踩中 `risk_metrics` 開頭列的缺陷：以 `ddof=0` 取標準差、沒有扣無風險
利率、Sortino 對「低於門檻的那幾期」取標準差（那是它們**彼此之間**的離散度，
不是相對於門檻的偏差）。

本檔盯住三件事：

1. 前端的 Sharpe／Sortino 與 `core/backtest/analysis/risk_metrics.py` **逐值相同**。
2. 公式本身對得上**手算**，不是「兩邊都錯得一樣」。
3. `app.py` 不再定義任何計算函式，且前端 import `core` 的成本沒有變重。
"""


_PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
_APP_PATH: Path = _PROJECT_ROOT / "frontend" / "app.py"


# === 與 core 共用同一份公式 ===
def test_sharpe_matches_core_implementation() -> None:
    """前端算出來的就是 `risk_metrics` 算出來的，沒有第二份實作"""

    returns: List[float] = [0.01, -0.005, 0.012, 0.003, -0.008, 0.006]
    series: pd.Series = pd.Series(returns)

    assert calc_sharpe_ratio(series) == compute_annualized_sharpe(returns)
    assert calc_sortino_ratio(series) == compute_annualized_sortino(returns)


def test_sharpe_matches_hand_calculation() -> None:
    """
    手算對照：報酬率 [1%, 2%, 1%, 2%]、無風險利率 0

    `(平均 / 標準差(ddof=1)) × √252`。舊版用 `ddof=0`，樣本少時偏差最大。
    """

    returns: List[float] = [0.01, 0.02, 0.01, 0.02]
    mean: float = sum(returns) / len(returns)
    variance: float = sum((r - mean) ** 2 for r in returns) / (len(returns) - 1)
    expected: float = round(
        mean / math.sqrt(variance) * math.sqrt(TRADING_DAYS_PER_YEAR), 4
    )

    assert calc_sharpe_ratio(pd.Series(returns)) == expected


def test_sortino_downside_uses_full_sample_count() -> None:
    """
    下檔標準差的分母是**全樣本**筆數，不是虧損那幾期的筆數

    舊版對「低於門檻的那幾期」取標準差，四期裡只有一期為負時，
    那一期與自己的離散度是 0，Sortino 會變成無限大或 NaN。
    """

    returns: List[float] = [0.01, 0.02, 0.01, -0.01]
    downside: float = math.sqrt(sum(min(r, 0.0) ** 2 for r in returns) / len(returns))
    mean: float = sum(returns) / len(returns)
    expected: float = round(mean / downside * math.sqrt(TRADING_DAYS_PER_YEAR), 4)

    assert calc_sortino_ratio(pd.Series(returns)) == expected


def test_ratios_are_none_without_samples() -> None:
    """
    樣本不足時回 None 而不是 NaN 或 0

    「沒有資料可算」與「風險調整後報酬為零」是兩件完全不同的事。
    """

    assert calc_sharpe_ratio(pd.Series(dtype=float)) is None
    assert calc_sortino_ratio(pd.Series(dtype=float)) is None


def test_no_downside_returns_none_not_infinity() -> None:
    """全部獲利時 Sortino 沒有定義，回 None 而不是無限大"""

    assert calc_sortino_ratio(pd.Series([0.01, 0.02, 0.015])) is None


# === MDD 手算 ===
def test_max_drawdown_matches_hand_calculation() -> None:
    """
    手算對照：100 → 120 → 90 → 110

    峰值 120、谷底 90，回撤 ＝ 90 / 120 − 1 ＝ −25%。
    最後回到 110 不影響**最大**回撤。
    """

    equity: pd.Series = pd.Series([100.0, 120.0, 90.0, 110.0])

    assert compute_max_drawdown(equity) == pytest.approx(-25.0)


def test_max_drawdown_is_zero_when_monotonic() -> None:
    """只漲不跌時回撤為 0；這與「沒有資料」（None）是兩件事"""

    assert compute_max_drawdown(pd.Series([100.0, 110.0, 120.0])) == 0.0
    assert compute_max_drawdown(pd.Series(dtype=float)) is None


# === 回測區間 ===
def test_date_range_covers_entry_and_exit() -> None:
    """
    區間要涵蓋進場與出場

    只看 `Sell Date` 對 SHORT 是開倉日，右端會提早——本例的 `Exit Date`
    比 `Sell Date` 晚，區間右端必須是 `Exit Date`。
    """

    df: pd.DataFrame = pd.DataFrame(
        {
            "Entry Date": ["2024-01-05", "2024-02-01"],
            "Exit Date": ["2024-01-10", "2024-03-15"],
            "Sell Date": ["2024-01-05", "2024-02-01"],
        }
    )

    start, end = extract_backtest_date_range(df)

    assert start == pd.Timestamp("2024-01-05")
    assert end == pd.Timestamp("2024-03-15")


def test_date_range_is_none_without_date_columns() -> None:
    """沒有任何日期欄位時回 `(None, None)`，不要猜"""

    assert extract_backtest_date_range(pd.DataFrame({"X": [1]})) == (None, None)


# === 端到端：由 daily_equity 算到指標 ===
def test_pipeline_from_daily_equity_to_ratios() -> None:
    """
    `daily_equity` → 權益序列 → 日報酬 → Sharpe，整條接得起來

    這條是前端實際走的路徑；任何一段的口徑換掉，這裡就會變。
    """

    daily_equity: pd.DataFrame = pd.DataFrame(
        {
            "Date": pd.date_range("2024-01-02", periods=6, freq="D"),
            "Equity": [1010000.0, 1005000.0, 1020000.0, 1015000.0, 1030000, 1025000],
        }
    )

    equity: pd.Series = build_equity_series(daily_equity, 1000000.0)
    returns: pd.Series = compute_daily_returns(equity)

    assert len(equity) == 7
    assert len(returns) == 6
    assert calc_sharpe_ratio(returns) is not None
    assert compute_max_drawdown(equity) is not None


# === F-085：app.py 不再定義計算函式 ===
def test_app_defines_no_calculation_functions() -> None:
    """
    `app.py` 只剩渲染函式

    計算留在 `app.py` 就等於**不可能被測試**：它在模組層級呼叫
    `st.set_page_config()`，測試 import 它就會炸。
    """

    tree: ast.Module = ast.parse(_APP_PATH.read_text(encoding="utf-8"))
    top_level: List[str] = [
        node.name
        for node in tree.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    ]

    assert top_level, "app.py 應該還有渲染函式"
    calculation_like: List[str] = [
        name
        for name in top_level
        if name.startswith(("_calc_", "_extract_", "_compute_", "_summarise_"))
    ]
    assert calculation_like == []
    assert all(
        name.startswith("_render_") or name.startswith("_get_") for name in top_level
    ), top_level


def test_frontend_imports_core_only_for_risk_metrics() -> None:
    """
    前端只准 import `core` 的 `risk_metrics`

    多 import 一個 `core` 模組，`frontend/Dockerfile` 那條最小 COPY 鏈就不夠了，
    而症狀會是容器啟動時才 ImportError。
    """

    imported: Set[str] = set()
    for path in (_PROJECT_ROOT / "frontend").rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.ImportFrom) and (node.module or "").startswith(
                "core"
            ):
                imported.add(node.module or "")
            elif isinstance(node, ast.Import):
                imported.update(
                    alias.name for alias in node.names if alias.name.startswith("core")
                )

    assert imported == {"core.backtest.analysis.risk_metrics"}


def test_importing_risk_metrics_stays_cheap() -> None:
    """
    import 共用公式不得拉進 pandas／numpy／shioaji

    `core/backtest/analysis/__init__.py` 一旦又 eager import analyzer，
    這條就會紅——那代表前端映像得裝進整個後端才跑得起來。
    以子行程量測，避免被本測試檔自己已經 import 的模組汙染。
    """

    script: str = (
        "import sys;"
        "from core.backtest.analysis.risk_metrics import compute_annualized_sharpe;"
        "heavy={'pandas','numpy','shioaji','sqlite3','loguru','requests'};"
        "print(','.join(sorted(heavy & {m.split('.')[0] for m in sys.modules})))"
    )
    result = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True,
        text=True,
        cwd=_PROJECT_ROOT,
    )

    assert result.returncode == 0, result.stderr
    assert result.stdout.strip() == ""
