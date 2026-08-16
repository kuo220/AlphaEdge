import sqlite3
from pathlib import Path
from typing import List

import pandas as pd
import pytest

from core.pipeline.loaders.base import BaseDataLoader
from core.pipeline.utils import DataLoadError

"""loader 入庫失敗不得被降級成 warning 後仍回報成功

2026-08-16 的 margin 回補實際中招：2 個 CSV 入庫失敗只留下 warning，
行程照樣印 `✅ Database Update Completed` 且結束碼為 0，缺的 1,553 列
是事後逐日比對列數才發現的。
"""


MARGIN_COLUMNS: List[str] = [
    "date",
    "stock_id",
    "證券名稱",
    "融資買進",
    "融資賣出",
    "融資現金償還",
    "融資前日餘額",
    "融資今日餘額",
    "融資限額",
    "融券買進",
    "融券賣出",
    "融券現券償還",
    "融券前日餘額",
    "融券今日餘額",
    "融券限額",
    "資券互抵",
    "券資比",
    "註記",
]


def make_margin_row(stock_id: str = "2330", date: str = "2024-01-02") -> pd.DataFrame:
    """建立一列最小可用的 margin 資料"""

    values = [date, stock_id, "台積電"] + [0] * 12 + [0, 0.0, ""]
    return pd.DataFrame([values], columns=MARGIN_COLUMNS)


# === finish_load 的行為 ===
def test_finish_load_raises_when_any_file_failed() -> None:
    """有任何失敗即拋出，呼叫端無法當作沒發生"""

    with pytest.raises(DataLoadError) as exc_info:
        BaseDataLoader.finish_load(
            source="margin", succeeded=6630, failed_files=["a.csv", "b.csv"]
        )

    error: DataLoadError = exc_info.value
    assert error.source == "margin"
    assert error.succeeded == 6630
    assert error.failed_files == ["a.csv", "b.csv"]
    # 訊息必須同時帶出成功與失敗數，否則看 log 的人無從判斷缺多少
    assert "6630" in str(error) and "2" in str(error)


def test_finish_load_is_silent_on_full_success() -> None:
    """全部成功時不得拋出，否則正常路徑會被誤判為失敗"""

    BaseDataLoader.finish_load(source="margin", succeeded=10, failed_files=[])


def test_finish_load_keeps_source_files_when_failed(tmp_path: Path) -> None:
    """有失敗時**不可**刪除來源目錄，否則連重試的機會都沒有"""

    downloads: Path = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "kept.csv").write_text("x")

    with pytest.raises(DataLoadError):
        BaseDataLoader.finish_load(
            source="margin",
            succeeded=1,
            failed_files=["broken.csv"],
            remove_files=True,
            downloads_path=downloads,
        )

    assert downloads.exists(), "有失敗檔案時來源目錄不應被刪除"
    assert (downloads / "kept.csv").exists()


def test_finish_load_removes_source_files_on_success(tmp_path: Path) -> None:
    """全部成功且要求刪除時才真的刪，維持原有行為"""

    downloads: Path = tmp_path / "downloads"
    downloads.mkdir()
    (downloads / "done.csv").write_text("x")

    BaseDataLoader.finish_load(
        source="margin",
        succeeded=1,
        failed_files=[],
        remove_files=True,
        downloads_path=downloads,
    )

    assert not downloads.exists()


# === 端到端：重跑與衝突的分辨 ===
def make_margin_rows(date: str, pairs: List[tuple]) -> pd.DataFrame:
    """建立多列 margin 資料；pairs 為 (stock_id, 證券名稱)"""

    return pd.DataFrame(
        [[date, sid, name] + [0] * 12 + [0, 0.0, ""] for sid, name in pairs],
        columns=MARGIN_COLUMNS,
    )


def make_loader(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """建立指向暫存 DB 與暫存 downloads 目錄的 margin loader"""

    import core.pipeline.loaders.stock_margin_loader as loader_module

    downloads: Path = tmp_path / "margin"
    downloads.mkdir(exist_ok=True)
    monkeypatch.setattr(loader_module, "DB_PATH", str(tmp_path / "test.db"))
    monkeypatch.setattr(loader_module, "MARGIN_DOWNLOADS_PATH", downloads)

    loader = loader_module.StockMarginLoader()
    loader.margin_dir = downloads
    return loader, downloads


def test_reloading_same_files_is_not_a_failure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    loader 每次都掃整個 downloads 目錄，重跑必然重送已入庫的檔案

    這**不是**失敗——若當成失敗，日常更新每天都會以非零狀態結束。
    """

    loader, downloads = make_loader(tmp_path, monkeypatch)
    make_margin_rows("2024-01-02", [("2330", "台積電")]).to_csv(
        downloads / "twse_20240102.csv", index=False
    )
    loader.add_to_db()

    # 隔日：新增一個新檔，舊檔仍在目錄裡
    make_margin_rows("2024-01-03", [("2330", "台積電")]).to_csv(
        downloads / "twse_20240103.csv", index=False
    )
    loader2, _ = make_loader(tmp_path, monkeypatch)
    loader2.add_to_db()  # 不得拋出

    conn = sqlite3.connect(tmp_path / "test.db")
    assert conn.execute("select count(*) from margin").fetchone()[0] == 2
    conn.close()


def test_partial_collision_loads_the_rest(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    重現 2026-08-16 事故的形狀：整檔中只有一列撞鍵

    當時整個 625 列的檔案被判定失敗、資料全數遺失。現在撞鍵的那列跳過、
    其餘照常入庫，並以 partial 警告把衝突浮上來。
    """

    loader, downloads = make_loader(tmp_path, monkeypatch)
    make_margin_rows(
        "2017-09-07", [("2330", "台積電"), ("4739", "康普"), ("2317", "鴻海")]
    ).to_csv(downloads / "twse_20170907.csv", index=False)
    loader.add_to_db()

    # tpex 檔的 4739 與 twse 撞鍵（轉市過渡期兩邊都收錄）
    make_margin_rows(
        "2017-09-07", [("6201", "元大富櫃50"), ("4739", "康普"), ("5483", "中美晶")]
    ).to_csv(downloads / "tpex_20170907.csv", index=False)

    loader2, _ = make_loader(tmp_path, monkeypatch)
    loader2.add_to_db()  # 不得拋出

    conn = sqlite3.connect(tmp_path / "test.db")
    # 3 ＋ 2（6201、5483）＝ 5；撞鍵的 4739 只留一筆
    assert conn.execute("select count(*) from margin").fetchone()[0] == 5
    assert (
        conn.execute("select count(*) from margin where stock_id='4739'").fetchone()[0]
        == 1
    )
    conn.close()


def test_broken_file_still_fails_loudly(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """真正的錯誤（欄位不符）仍必須拋出，不可被「跳過」的寬鬆語意吃掉"""

    loader, downloads = make_loader(tmp_path, monkeypatch)
    pd.DataFrame([{"unexpected_column": 1}]).to_csv(
        downloads / "twse_20240104.csv", index=False
    )

    with pytest.raises(DataLoadError) as exc_info:
        loader.add_to_db()

    assert len(exc_info.value.failed_files) == 1


# === CLI 層：失敗必須反映在結束碼上 ===
def test_update_db_exits_non_zero_when_a_target_fails(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """
    單一 target 失敗時，行程須以非零狀態結束且不得印出成功訊息

    這是 2026-08-16 事故的核心：舊行為是結束碼 0 ＋ `✅ Database Update Completed`。
    """

    import tasks.update_db as update_db

    class ExplodingUpdater:
        """模擬 loader 拋出 DataLoadError 的 updater"""

        def update(self, **kwargs) -> None:
            raise DataLoadError("margin", ["broken.csv"], succeeded=6630)

    monkeypatch.setattr(update_db, "StockMarginUpdater", ExplodingUpdater)
    monkeypatch.setattr(
        update_db, "parse_arguments", lambda: _FakeArgs(target=["margin"])
    )

    with pytest.raises(SystemExit) as exc_info:
        update_db.main()

    assert exc_info.value.code == 1


def test_target_guard_isolates_failure() -> None:
    """一個 target 失敗不得中斷其餘 target——否則是拿可用性換可見度"""

    from tasks.update_db import target_guard

    failed: List[str] = []

    with target_guard("margin", failed):
        raise DataLoadError("margin", ["a.csv"], succeeded=1)

    # 沒有往外拋，後續 target 仍可繼續
    with target_guard("price", failed):
        pass

    assert failed == ["margin"]


class _FakeArgs:
    """取代 argparse.Namespace 的最小替身"""

    def __init__(self, target: List[str]):
        self.target: List[str] = target
