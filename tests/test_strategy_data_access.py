import sys
from pathlib import Path
from typing import List

import pytest

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.pipeline.utils.constant import ChipColumn, PriceColumn

"""防護測試：策略層不得出現資料庫欄位字面值
（「策略層資料欄位抽象化」S6 的產出，該工作已於 2026-08 完成並移出 `backlog/`）

現況的失效模式是**靜默**的：欄位名一旦更名，部分策略會走進既有的 `continue`
分支而安靜地不開倉，回測報表上只表現為「訊號變少」，極難察覺。本測試讓這件事
在 CI 就變紅，而不是等到換資料源才爆。
"""


STRATEGY_DIR: Path = _PROJECT_ROOT / "core" / "strategies"

# 例外清單刻意留空。若日後真有必要保留，須在此明列檔案並註明理由
ALLOWED_FILES: List[str] = []


def db_column_names() -> List[str]:
    """所有資料庫欄位名（策略層一律不得直接引用）"""

    return [column.value for column in PriceColumn] + [
        column.value for column in ChipColumn
    ]


def strategy_source_files() -> List[Path]:
    """`core/strategies/` 下的所有策略原始碼"""

    return sorted(
        path
        for path in STRATEGY_DIR.rglob("*.py")
        if "__pycache__" not in path.parts and path.name not in ALLOWED_FILES
    )


def test_strategy_dir_has_source_files() -> None:
    """掃描範圍不得為空，否則本測試會永遠通過而失去意義"""

    assert len(strategy_source_files()) >= 6


@pytest.mark.parametrize("column", db_column_names())
def test_no_db_column_literal_in_strategies(column: str) -> None:
    """策略層出現任一資料庫欄位字面值即失敗"""

    offenders: List[str] = []

    for path in strategy_source_files():
        source: str = path.read_text(encoding="utf-8")
        for line_no, line in enumerate(source.splitlines(), start=1):
            # 只擋字面值取值（帶引號），中文註解與 docstring 說明不在此限
            if f'"{column}"' in line or f"'{column}'" in line:
                offenders.append(f"{path.relative_to(_PROJECT_ROOT)}:{line_no}")

    assert not offenders, (
        f"策略層不得直接引用資料庫欄位 {column!r}，請改用 core/api/ 的具名查詢方法："
        f"{offenders}"
    )
