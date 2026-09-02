import sys
from pathlib import Path

import pytest

_PROJECT_ROOT: Path = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(_PROJECT_ROOT))

from core import config

"""
防護測試：設定的路徑錨點與產物／原始碼分界

這裡擋的是**靜默錯置**：錨點層數算錯時不會有任何例外，只會安靜地在錯的地方
建目錄，等到有人發現 `core/` 底下又長出 `data/` 才知道。`core/config.py`
拆成 `core/config/` 套件時就踩過一次——`Path(__file__).parent` 沒跟著加一層，
`PROJECT_ROOT` 變成 `core/`，全部產物退回套件內。
"""


def test_base_dir_is_core_package() -> None:
    """`BASE_DIR_PATH` 必須指向 `core/` 本身，不是它的子目錄或父目錄"""

    assert config.BASE_DIR_PATH == _PROJECT_ROOT / "core"


def test_project_root_is_repo_root() -> None:
    """`PROJECT_ROOT` 必須指向專案根（有 pyproject.toml 的那一層）"""

    assert config.PROJECT_ROOT == _PROJECT_ROOT
    assert (config.PROJECT_ROOT / "pyproject.toml").exists()


@pytest.mark.parametrize(
    "name",
    ["DATA_DIR_PATH", "RESULTS_DIR_PATH", "LOGS_DIR_PATH"],
)
def test_artifact_roots_live_outside_core(name: str) -> None:
    """
    三個產物根一律在 `core/` 之外

    分界見 `docs/dev/runtime-artifacts.md`：`core/` 是被讀的，產物根是被寫的。
    """

    path: Path = getattr(config, name)
    assert config.BASE_DIR_PATH not in path.parents
    assert path.parent == config.PROJECT_ROOT


@pytest.mark.parametrize(
    "name",
    [
        "DATABASE_DIR_PATH",
        "PIPELINE_DOWNLOADS_PATH",
        "TW_STOCK_DOWNLOADS_PATH",
        "TW_FUTURES_DOWNLOADS_PATH",
        "TW_STOCK_DB_PATH",
        "TW_FUTURES_DB_PATH",
        "API_LOGS_DIR_PATH",
        "PIPELINE_LOGS_DIR_PATH",
        "BACKTEST_LOGS_DIR_PATH",
        "BACKTEST_RESULT_DIR_PATH",
        "DOWNLOADS_METADATA_DIR_PATH",
    ],
)
def test_derived_artifact_paths_stay_outside_core(name: str) -> None:
    """掛在產物根底下的每一個常數都不得落回 `core/`"""

    assert config.BASE_DIR_PATH not in getattr(config, name).parents


def test_cleaner_schema_is_package_data() -> None:
    """
    相反方向：欄位定義是**設定**，必須留在 `core/` 內並隨套件發佈

    它一旦被移進產物目錄就會整批掉出版控，而缺檔只會 warning 後靜默降級清洗。
    """

    assert config.BASE_DIR_PATH in config.CLEANER_SCHEMA_DIR_PATH.parents
    assert config.CLEANER_SCHEMA_DIR_PATH.exists()

    for name in ("financial_statement", "monthly_revenue_report"):
        assert list((config.CLEANER_SCHEMA_DIR_PATH / name).rglob("*.json"))


def test_importing_config_creates_no_directories(tmp_path: Path) -> None:
    """
    import 設定模組不得有檔案系統副作用

    否則任何只是要讀常數的測試都會被動生出 data/ results/ logs/。
    目錄一律由實際要寫檔的呼叫端惰性建立。
    """

    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os;"
            f"os.environ['ALPHAEDGE_DATA_DIR']=r'{tmp_path / 'd'}';"
            f"os.environ['ALPHAEDGE_RESULTS_DIR']=r'{tmp_path / 'r'}';"
            f"os.environ['ALPHAEDGE_LOGS_DIR']=r'{tmp_path / 'l'}';"
            "from core import config",
        ],
        cwd=_PROJECT_ROOT,
        capture_output=True,
    )

    assert result.returncode == 0, result.stderr.decode()
    assert not list(tmp_path.iterdir()), (
        f"import 期間建立了目錄：{list(tmp_path.iterdir())}"
    )


def test_env_override_is_honoured(tmp_path: Path) -> None:
    """三個產物根可由環境變數覆寫（容器掛載 volume 用）"""

    import subprocess

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            "import os;"
            f"os.environ['ALPHAEDGE_DATA_DIR']=r'{tmp_path}';"
            "from core import config;"
            "print(config.TW_STOCK_DB_PATH)",
        ],
        cwd=_PROJECT_ROOT,
        capture_output=True,
        text=True,
    )

    assert result.returncode == 0, result.stderr
    assert str(tmp_path / "db" / "tw_stock.db") in result.stdout


def test_config_facade_exposes_all_three_modules() -> None:
    """
    `from core.config import X` 在拆成套件後仍要能取到三個模組的所有常數

    門面用 star import 正是為了這件事——逐一列出會在新增常數卻忘了補進門面時，
    以一個指不到原因的 ImportError 收場。
    """

    assert config.DATA_DIR_PATH  # paths
    assert config.PRICE_TABLE_NAME == "price"  # schema
    assert config.FUTURES_TARGET_PRODUCTS  # settings


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
