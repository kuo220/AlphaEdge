import sqlite3
from pathlib import Path
from typing import List, Set

import pytest

"""
入口與日誌的四個坑，共通點是**平常不會有人發現**

1. F-078：預設 `no_tick` 仍包含 `futures_tick`，沒有 Shioaji 金鑰的機器每晚紅燈。
2. F-079：`delete_price_data` 沒有預覽也沒有確認，打錯日期就少一整天行情。
3. F-015：`.env` 缺 `DDB_PATH` 時路徑被拼成 `"NonetickDB"`。
4. F-097：`logs/api/` 每天長約 100 MB。
"""


# === F-078：no_tick 要排除所有 tick ===
def test_no_tick_excludes_futures_tick() -> None:
    """
    預設的 `python -m tasks.update_db` 不可去跑期貨 tick

    那需要 Shioaji 金鑰與 `[tick]` 選用相依，沒有的機器每晚都以結束碼 1 收場，
    久了就沒人在看那個紅燈了。
    """

    from core.pipeline.utils import DataType
    from tasks.update_db import TICK_DATA_TYPES

    expanded: Set[str] = {
        dt.name.lower() for dt in DataType if dt not in TICK_DATA_TYPES
    }

    assert DataType.FUTURES_TICK.name.lower() not in expanded
    assert DataType.TICK.name.lower() not in expanded
    # 其餘 target 一個都不能少
    assert DataType.PRICE.name.lower() in expanded
    assert DataType.FUTURES_PRICE.name.lower() in expanded


def test_all_still_includes_every_tick_target() -> None:
    """`--target all` 仍要涵蓋兩種 tick，否則就沒有「全部」了"""

    from core.pipeline.utils import DataType

    expanded: Set[str] = {dt.name.lower() for dt in DataType}

    assert DataType.TICK.name.lower() in expanded
    assert DataType.FUTURES_TICK.name.lower() in expanded


# === F-079：delete_price_data 預設不刪 ===
def make_price_db(tmp_path: Path) -> Path:
    """建一個只有 price 表的暫存 DB"""

    db_path: Path = tmp_path / "test.db"
    conn = sqlite3.connect(db_path)
    conn.execute("CREATE TABLE price (date TEXT, stock_id TEXT)")
    conn.executemany(
        "INSERT INTO price VALUES (?, ?)",
        [("2025-07-13", "2330"), ("2025-07-13", "2317"), ("2025-07-14", "2330")],
    )
    conn.commit()
    conn.close()
    return db_path


def test_delete_price_data_defaults_to_preview(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """沒有 --apply 時一列都不能刪"""

    import tasks.delete_price_data as module

    db_path: Path = make_price_db(tmp_path)
    monkeypatch.setattr(module, "TW_STOCK_DB_PATH", str(db_path))

    module.delete_price_data_by_date("2025-07-13")

    conn = sqlite3.connect(db_path)
    assert conn.execute("select count(*) from price").fetchone()[0] == 3
    conn.close()


def test_delete_price_data_requires_confirmation(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--apply 但沒有 --yes 且無法互動時不可刪除"""

    import tasks.delete_price_data as module

    db_path: Path = make_price_db(tmp_path)
    monkeypatch.setattr(module, "TW_STOCK_DB_PATH", str(db_path))
    monkeypatch.setattr(module.sys.stdin, "isatty", lambda: False)

    module.delete_price_data_by_date("2025-07-13", apply=True)

    conn = sqlite3.connect(db_path)
    assert conn.execute("select count(*) from price").fetchone()[0] == 3
    conn.close()


def test_delete_price_data_applies_with_yes(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """--apply --yes 才真的刪，且只刪指定那天"""

    import tasks.delete_price_data as module

    db_path: Path = make_price_db(tmp_path)
    monkeypatch.setattr(module, "TW_STOCK_DB_PATH", str(db_path))

    module.delete_price_data_by_date("2025-07-13", apply=True, assume_yes=True)

    conn = sqlite3.connect(db_path)
    remaining: List[tuple] = conn.execute("select date from price").fetchall()
    assert remaining == [("2025-07-14",)]
    conn.close()


def test_delete_price_data_parser_has_the_two_flags() -> None:
    """`--apply` 與 `--yes` 必須存在，否則使用說明會與行為不符"""

    import tasks.delete_price_data as module

    source: str = Path(module.__file__).read_text(encoding="utf-8")

    assert '"--apply"' in source
    assert '"--yes"' in source


# === F-015：DDB_PATH 缺值要當場拋出 ===
def test_require_tick_db_path_raises_when_unset(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    缺 `DDB_PATH` 時不可拼出 `"NonetickDB"`

    那是一個看起來像路徑的字串，DolphinDB 會拿它去查一個永遠不存在的位置，
    錯誤訊息完全指不到真正的原因。
    """

    import core.config.schema as schema

    monkeypatch.setattr(schema, "TICK_DB_PATH", None)

    with pytest.raises(RuntimeError, match="DDB_PATH"):
        schema.require_tick_db_path()


def test_tick_db_path_is_none_rather_than_none_string() -> None:
    """設定值缺漏時是 None，不是字面上的 'None...' 字串"""

    import core.config.schema as schema

    assert schema.TICK_DB_PATH is None or not str(schema.TICK_DB_PATH).startswith(
        "None"
    )


# === F-097：api 桶的檔案 sink 只留 WARNING ===
def test_api_log_file_level_is_warning() -> None:
    """
    `core/api/` 每次查詢都寫一行，回測一跑就是數十萬次

    console 不受影響，開發時照樣看得到 INFO。
    """

    from core.config import API_LOG_FILE_LEVEL

    assert API_LOG_FILE_LEVEL == "WARNING"


def test_every_api_module_uses_the_shared_level() -> None:
    """12 支 API 都要用同一份常數，不可各自寫死"""

    api_dir: Path = Path("core/api/tw")
    modules: List[Path] = [
        path
        for path in sorted(api_dir.glob("*.py"))
        if "API_LOGS_DIR_PATH" in path.read_text(encoding="utf-8")
    ]

    assert modules, "找不到任何使用 API_LOGS_DIR_PATH 的模組"
    for path in modules:
        source: str = path.read_text(encoding="utf-8")
        assert "API_LOG_FILE_LEVEL" in source, f"{path.name} 沒有指定 api 桶日誌等級"
