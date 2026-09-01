from typing import Dict

import pandas as pd
import pytest

from frontend.services.futures_metrics import (
    DATE_COLUMN,
    LOTS_COLUMN,
    MARGIN_COLUMN,
    build_exposure_series,
    is_futures_report,
    summarise_margin,
)

"""
前端的期貨專屬指標測試（Phase5-2）

**期貨的風險視角與股票不同**：股票看「投入多少錢、值多少錢」，期貨看
「**佔用多少保證金、留了幾口**」——契約價值本身不佔用資金。

本檔釘住三件事：

1. **以欄位判斷是不是期貨報表**，不是以策略名稱（名稱可以任意取）。
2. **曝險看「峰值」不是「總和」**：把每筆交易的保證金加起來會得到一個沒有意義
   的巨大數字（同一筆錢用了幾十次）。
3. **曝險曲線由交易明細「走」出來**：每筆在進場日佔用、出場日釋放，疊起來即為
   逐日曝險——不需要回測引擎多輸出一份檔案，舊報表也能直接看。
"""


def make_futures_report() -> pd.DataFrame:
    """兩筆重疊 ＋ 一筆未平倉的期貨交易明細"""

    return pd.DataFrame(
        [
            {
                "Contract ID": "TX202403",
                "Multiplier": 200,
                "Entry Date": "2024-03-01",
                "Exit Date": "2024-03-05",
                "Buy Volume": 2,
                "Margin": 400000.0,
                "ROI": 5.0,
                "Realized PnL": 20000.0,
                "Settled PnL": 12000.0,
            },
            {
                "Contract ID": "TX202403",
                "Multiplier": 200,
                "Entry Date": "2024-03-04",
                "Exit Date": "2024-03-06",
                "Buy Volume": 1,
                "Margin": 200000.0,
                "ROI": -2.0,
                "Realized PnL": -4000.0,
                "Settled PnL": -1000.0,
            },
            {
                "Contract ID": "TX202404",
                "Multiplier": 200,
                "Entry Date": "2024-03-08",
                "Exit Date": None,  # 尚未平倉
                "Buy Volume": 3,
                "Margin": 600000.0,
                "ROI": 0.0,
                "Realized PnL": 0.0,
                "Settled PnL": 0.0,
            },
        ]
    )


def make_stock_report() -> pd.DataFrame:
    """台股交易明細（沒有 Contract ID／Multiplier／Margin 三欄）"""

    return pd.DataFrame(
        [
            {
                "Stock ID": "2330",
                "Entry Date": "2024-03-01",
                "Exit Date": "2024-03-05",
                "Buy Volume": 2,
                "Realized PnL": 20000.0,
                "ROI": 5.0,
            }
        ]
    )


# === 判斷報表類型 ===
def test_futures_report_is_detected_by_columns() -> None:
    """以欄位判斷，不是以策略名稱——名稱可以任意取，欄位由報表產生器決定"""

    assert is_futures_report(make_futures_report()) is True
    assert is_futures_report(make_stock_report()) is False
    assert is_futures_report(pd.DataFrame()) is False


# === 曝險曲線 ===
def test_exposure_accumulates_overlapping_positions() -> None:
    """
    重疊的部位要**疊加**

    3/4 那天兩筆同時在倉：保證金 400,000 ＋ 200,000、口數 2 ＋ 1。
    """

    exposure: pd.DataFrame = build_exposure_series(make_futures_report())
    by_date: Dict[str, tuple] = {
        str(row[DATE_COLUMN].date()): (row[MARGIN_COLUMN], row[LOTS_COLUMN])
        for _, row in exposure.iterrows()
    }

    assert by_date["2024-03-01"] == (400000.0, 2)
    assert by_date["2024-03-04"] == (600000.0, 3)
    assert by_date["2024-03-05"] == (200000.0, 1)  # 第一筆平倉，釋放 400,000
    assert by_date["2024-03-06"] == (0.0, 0)


def test_open_position_is_never_released() -> None:
    """尚未平倉的部位（`Exit Date` 為空）一路留到序列末端"""

    exposure: pd.DataFrame = build_exposure_series(make_futures_report())

    assert exposure.iloc[-1][MARGIN_COLUMN] == 600000.0
    assert exposure.iloc[-1][LOTS_COLUMN] == 3


def test_exposure_is_empty_without_required_columns() -> None:
    """欄位不足時回空表，不可猜 0——那會畫出一條「完全沒有曝險」的假曲線"""

    assert build_exposure_series(make_stock_report()).empty
    assert build_exposure_series(pd.DataFrame()).empty


# === 摘要指標 ===
def test_peak_margin_is_not_the_sum() -> None:
    """
    **資金使用率看峰值不是總和**

    三筆保證金相加是 1,200,000，但同時佔用的最高只有 600,000——
    用總和會得到「使用率 120%」這種沒有意義的數字。
    """

    summary: Dict = summarise_margin(make_futures_report(), starting_capital=1000000.0)

    assert summary["峰值佔用保證金"] == 600000.0
    assert summary["峰值未平倉口數"] == 3
    assert summary["資金使用率"] == 60.0


def test_summary_handles_missing_capital() -> None:
    """沒有初始資金時使用率為 None，不可用 0 或猜一個數字"""

    summary: Dict = summarise_margin(make_futures_report(), starting_capital=None)

    assert summary["資金使用率"] is None
    assert summary["峰值佔用保證金"] == 600000.0


def test_summary_reports_margin_based_roi() -> None:
    """期貨的 ROI 分母是保證金，這個平均值才是「資金效率」"""

    summary: Dict = summarise_margin(make_futures_report(), starting_capital=1000000.0)

    assert summary["平均保證金報酬率"] == pytest.approx(1.0)
    assert summary["總交易口數"] == 6
    assert summary["逐日結算損益"] == 11000.0
