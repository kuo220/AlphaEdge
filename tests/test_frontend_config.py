import warnings
from pathlib import Path

import pytest

from frontend.config import (
    DEFAULT_RESULTS_ROOT,
    LEGACY_RESULTS_ENV_VAR,
    PROJECT_ROOT,
    RESULTS_ENV_VAR,
    resolve_results_root,
)

"""
前端的結果根目錄必須與後端同一個地方（F-083）

舊版有兩個問題，兩個都只在**本機不設環境變數**時發作，而那正是新人第一次
跑起來的情境：預設指向 `core/backtest/results`（該目錄在 2026-08「執行期產物
移出 `core/`」時就消失了），環境變數名也與後端的 `ALPHAEDGE_RESULTS_DIR` 不同。
Docker 內因為 compose 與 Dockerfile 各自寫死 `/results` 才看起來一致。

`frontend/config.py` 刻意不 import `core`（前端映像只 COPY `frontend/`），
所以「兩邊算出同一個路徑」這件事沒有型別或 import 可以保證，只能靠本檔盯住。
"""


def test_default_results_root_exists() -> None:
    """
    預設路徑必須真的存在

    這是 F-083 最直接的症狀：預設指向一個不存在的目錄，本機不設環境變數
    就整頁「找不到任何回測結果資料夾」。
    """

    assert DEFAULT_RESULTS_ROOT == PROJECT_ROOT / "results"
    assert DEFAULT_RESULTS_ROOT.is_dir()


def test_default_matches_backend_results_dir() -> None:
    """
    與後端 `core/config` 的 `RESULTS_DIR_PATH` 指向同一個目錄

    後端寫哪、前端就得讀哪。兩邊各算一次是為了讓前端映像不必帶 `core/`，
    代價就是要有這條測試——否則下次有人改後端，前端會安靜地繼續讀舊的地方。
    """

    from core.config import RESULTS_DIR_PATH

    assert DEFAULT_RESULTS_ROOT == RESULTS_DIR_PATH


def test_env_var_name_matches_backend() -> None:
    """前端與後端讀的是**同一個**環境變數名，不必各設一次"""

    assert RESULTS_ENV_VAR == "ALPHAEDGE_RESULTS_DIR"


def test_new_env_var_wins(tmp_path: Path) -> None:
    """設了新名就用新名"""

    target: Path = tmp_path / "custom"
    assert resolve_results_root({RESULTS_ENV_VAR: str(target)}) == target


def test_legacy_env_var_still_works_but_warns(tmp_path: Path) -> None:
    """舊名保留一版相容，但要讓人知道該改了"""

    target: Path = tmp_path / "legacy"

    with pytest.warns(DeprecationWarning, match=LEGACY_RESULTS_ENV_VAR):
        resolved: Path = resolve_results_root({LEGACY_RESULTS_ENV_VAR: str(target)})

    assert resolved == target


def test_new_env_var_takes_precedence_over_legacy(tmp_path: Path) -> None:
    """兩個都設時以新名為準，且不該再警告（使用者已經改好了）"""

    new_target: Path = tmp_path / "new"
    old_target: Path = tmp_path / "old"

    with warnings.catch_warnings():
        warnings.simplefilter("error", DeprecationWarning)
        resolved: Path = resolve_results_root(
            {
                RESULTS_ENV_VAR: str(new_target),
                LEGACY_RESULTS_ENV_VAR: str(old_target),
            }
        )

    assert resolved == new_target


def test_falls_back_to_default_without_env() -> None:
    """兩個都沒設就用預設值，不是回 None 讓呼叫端自己猜"""

    assert resolve_results_root({}) == DEFAULT_RESULTS_ROOT


# === 前端映像的相依（健檢 F-093）===
def test_frontend_requirements_cover_every_third_party_import() -> None:
    """
    `frontend/requirements.txt` 必須涵蓋 `frontend/` 實際 import 的每個第三方套件

    前端映像**不安裝本專案**（只 COPY `frontend/` 與 risk_metrics 那條最小鏈），
    所以 `pyproject.toml` 的相依完全不生效，那一份 requirements 是唯一來源。
    漏一個的症狀是**映像裝得起來、一開頁就 ModuleNotFoundError**——
    F-093 就是這樣來的（漏了 plotly）。
    """

    import ast
    import sys

    frontend_dir: Path = PROJECT_ROOT / "frontend"
    requirements: Path = frontend_dir / "requirements.txt"
    assert requirements.is_file(), (
        "缺 frontend/requirements.txt，映像會退回只裝 streamlit pandas"
    )

    declared: set[str] = {
        line.split("=")[0].split(">")[0].split("<")[0].strip().lower()
        for line in requirements.read_text(encoding="utf-8").splitlines()
        if line.strip() and not line.strip().startswith("#")
    }

    # 本地模組（同層 import 與專案自己的套件）不算第三方
    local: set[str] = {"config", "services", "frontend", "core"}
    imported: set[str] = set()
    for path in frontend_dir.rglob("*.py"):
        if "__pycache__" in path.parts:
            continue
        for node in ast.walk(ast.parse(path.read_text(encoding="utf-8"))):
            if isinstance(node, ast.Import):
                imported.update(alias.name.split(".")[0] for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.level == 0 and node.module:
                imported.add(node.module.split(".")[0])

    third_party: set[str] = {
        name for name in imported if name not in sys.stdlib_module_names
    } - local

    missing: set[str] = {name for name in third_party if name.lower() not in declared}
    assert not missing, f"frontend/requirements.txt 缺少：{sorted(missing)}"
