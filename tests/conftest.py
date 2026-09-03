import pytest

from core.utils.log_manager import LogManager

"""
測試期間不寫 `logs/`

`LogManager.setup_logger()` 會 `logger.add()` 一個檔案 sink，而 `core/api/`、
`core/pipeline/` 的每個類別都在 `setup()` 裡呼叫它。跑一次測試就會在專案下
產生一整片 `logs/pipeline/*.log`、`logs/api/*.log`——那是**測試的副作用**，
不是測試的產物（健檢 F-017 相鄰的 F-097 桶問題同源）。

以 `pytest_sessionstart` 換成 no-op，是因為它在 collection 之前執行；
用 fixture 來不及——模組層級就會有類別被實例化。
"""


def _noop(*args, **kwargs) -> None:
    """測試期間的 `setup_logger` 替身：什麼都不做"""


def pytest_sessionstart(session: pytest.Session) -> None:
    """整個測試 session 開始前，把日誌檔案 sink 的設定換成 no-op"""

    LogManager.setup_logger = staticmethod(_noop)
    LogManager.setup_backtest_logger = staticmethod(_noop)
