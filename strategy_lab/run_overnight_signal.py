#!/usr/bin/env python3
"""
台積電跨市場隔夜訊號回測入口。

請於 AlphaEdge 專案根目錄執行：
    .venv/bin/python strategy_lab/run_overnight_signal.py

輸出目錄：`strategy_lab/output/`（資產曲線、MDD、滾動 Sharpe、月報酬熱圖、IC 等）。
"""

from __future__ import annotations

import datetime as dt
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from strategy_lab.overnight_signal_pipeline import main  # noqa: E402


if __name__ == "__main__":
    output_path = main(
        data_start=dt.date(2020, 1, 1),
        data_end=dt.date(2026, 4, 25),
    )
    print(f"輸出已寫入：{output_path}")

