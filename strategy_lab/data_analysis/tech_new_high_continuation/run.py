#!/usr/bin/env python3
"""
台股科技業「創高後續上行機率」分析入口。

請於 AlphaEdge 專案根目錄執行：
    .venv/bin/python strategy_lab/data_analysis/tech_new_high_continuation/run.py

輸出目錄：strategy_lab/data_analysis/tech_new_high_continuation/output/
"""

from __future__ import annotations

import sys
from pathlib import Path

_PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(_PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(_PROJECT_ROOT))

from strategy_lab.data_analysis.tech_new_high_continuation.analysis import (  # noqa: E402
    run_analysis,
    write_outputs,
)


def main() -> Path:
    events, by_stock, summary = run_analysis()
    return write_outputs(events, by_stock, summary)


if __name__ == "__main__":
    output_dir = main()
    print(f"輸出已寫入：{output_dir}")
