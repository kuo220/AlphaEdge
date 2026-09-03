import sys
from pathlib import Path
from typing import List

import pytest

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from core.pipeline.utils.constant import ChipColumn, PriceColumn

"""防護測試：策略層不得出現資料庫欄位字面值

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


# === 策略層的三道防線（健檢 F-072、F-073、F-075、F-076）===
def test_momentum_strategy_rejects_tick_scale() -> None:
    """
    TICK 級別要當場擋下，不是等到第一根 bar 才崩（F-075）

    本策略的訊號建立在「前一交易日收盤」上，TICK 路徑只會掛 `self.tick`、
    `self.price` 維持 None，第一根 bar 就會撞 `ValueError("Invalid API type")`。
    """

    import pytest

    from core.strategies.stock.momentum_strategy_1 import MomentumStrategy1
    from core.utils import Scale

    strategy: MomentumStrategy1 = MomentumStrategy1()
    strategy.scale = Scale.TICK

    class _Feed:
        chip = mrr = fs = price = tick = None

    with pytest.raises(NotImplementedError, match="只支援日線"):
        strategy.setup_apis(_Feed())


def test_max_holdings_defaults_to_unlimited() -> None:
    """
    `BaseStrategy.max_holdings` 預設 None ＝ 不限制（F-076）

    舊版預設 0，而 `Backtester.check_max_holdings()` 只把 None 當成不限制
    ——忘記設定的新策略，每一張開倉單都被引擎剔除，回測跑完是零筆交易、
    零錯誤訊息。
    """

    from core.strategies.base import BaseStrategy

    class _Bare(BaseStrategy):
        def setup_account(self, account) -> None: ...

        def setup_apis(self, feed) -> None: ...

        def check_open_signal(self, quotes): ...

        def check_close_signal(self, quotes): ...

        def check_stop_loss_signal(self, positions): ...

        def calculate_position_size(self, *args, **kwargs): ...

    assert _Bare().max_holdings is None


def test_overnight_lead_event_strategy_can_be_constructed() -> None:
    """
    建構本身不可觸網、不可依賴尚未注入的 API（F-072）

    舊版在 `__init__()` 末尾就呼叫 `_build_signals()`，而它要用
    `self.price`——那是 `setup_apis()` 才掛上去的，於是這一行本身就
    `AttributeError`。引擎的 factory 是先建策略再 `setup_apis()`，
    順序反了就沒有任何方法救得回來。
    """

    from core.strategies.stock.overnight_lead_event_strategy import (
        OvernightLeadEventStrategy,
    )

    strategy: OvernightLeadEventStrategy = OvernightLeadEventStrategy()

    assert strategy.signal_by_date == {}


def test_strategy_loader_isolates_a_broken_module(monkeypatch) -> None:
    """
    單一模組壞掉不該讓所有策略都列不出來（F-073）

    舊版一路 `import_module()` 到底，任何一支策略有 import 錯誤，
    `run.py --strategy` 連「有哪些策略可用」都印不出來。
    """

    import importlib

    from core.strategies.strategy_loader import StrategyLoader

    original = importlib.import_module

    def explode_on_one(name: str, *args, **kwargs):
        if name.endswith("momentum_strategy_1"):
            raise ImportError("boom")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(importlib, "import_module", explode_on_one)

    strategies = StrategyLoader.load_strategies()

    assert "MomentumStrategy1" not in strategies
    assert "ForeignSellShortDayTradeStrategy" in strategies, "其餘策略仍要載得到"


def test_strategy_loader_rejects_duplicate_class_names() -> None:
    """
    同名類別要當場拋出，不可靜默覆蓋（F-073）

    key 是類別名，覆蓋之後「跑的到底是哪一支」要看掃描順序，比模組壞掉更難查。
    """

    import types

    import pytest

    from core.strategies.base import BaseStrategy
    from core.strategies.strategy_loader import StrategyLoader

    def make_module(module_name: str):
        module = types.ModuleType(module_name)

        class Duplicated(BaseStrategy):
            def setup_account(self, account) -> None: ...

            def setup_apis(self, feed) -> None: ...

            def check_open_signal(self, quotes): ...

            def check_close_signal(self, quotes): ...

            def check_stop_loss_signal(self, positions): ...

            def calculate_position_size(self, *args, **kwargs): ...

        Duplicated.__module__ = module_name
        module.Duplicated = Duplicated
        return module

    collected = {}
    StrategyLoader.collect_from_module(make_module("pkg.first"), collected)

    with pytest.raises(ValueError, match="策略類別名稱重複"):
        StrategyLoader.collect_from_module(make_module("pkg.second"), collected)
