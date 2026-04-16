from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd

try:
    from config import CHART_FILE_CANDIDATES, CSV_FILE_CANDIDATES
except ModuleNotFoundError:
    from frontend.config import CHART_FILE_CANDIDATES, CSV_FILE_CANDIDATES


@dataclass
class BacktestReport:
    strategy_name: str
    report_dir: Path
    csv_path: Optional[Path]
    chart_paths: Dict[str, Optional[Path]]


def list_strategy_dirs(results_root: Path) -> List[Path]:
    if not results_root.exists() or not results_root.is_dir():
        return []
    return sorted(
        [path for path in results_root.iterdir() if path.is_dir()],
        key=lambda path: path.name.lower(),
    )


def _pick_first_match(base_dir: Path, patterns: List[str]) -> Optional[Path]:
    for pattern in patterns:
        matched = sorted(base_dir.glob(pattern))
        if matched:
            return matched[0]
    return None


def load_backtest_report(strategy_dir: Path) -> BacktestReport:
    csv_path = _pick_first_match(strategy_dir, CSV_FILE_CANDIDATES)
    chart_paths = {
        chart_name: _pick_first_match(strategy_dir, patterns)
        for chart_name, patterns in CHART_FILE_CANDIDATES.items()
    }
    return BacktestReport(
        strategy_name=strategy_dir.name,
        report_dir=strategy_dir,
        csv_path=csv_path,
        chart_paths=chart_paths,
    )


def read_trading_report(csv_path: Path) -> pd.DataFrame:
    # 產出檔多為 UTF-8-SIG，讀取時優先用 utf-8-sig
    return pd.read_csv(csv_path, encoding="utf-8-sig")

