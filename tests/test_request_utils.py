import time

import pytest
import requests

from core.pipeline.shared.request_utils import RequestUtils

"""
共用 HTTP 工具的重試行為

**本檔存在的唯一理由是一個會打死長時間爬蟲的坑**：
`requests.exceptions.ConnectionError` **不是**內建 `ConnectionError` 的子類——
兩者是 `OSError` 底下的兄弟。`except ConnectionError` 若抓的是內建那個，
requests 拋的連線中斷就完全沒被攔到，行程當場結束。

2026-09-01 實測：台期貨歷史回補跑到第 9 年（2024-10-29）時因 `RemoteDisconnected`
整個中止，前面 23,599 列雖已入庫，但中斷點要人工找。
"""


def test_requests_connection_error_is_not_a_builtin_connection_error() -> None:
    """
    釘住這個反直覺的事實本身

    日後有人「簡化」成只寫 `except ConnectionError` 時，本測試會說明為什麼不行。
    """

    assert not issubclass(requests.exceptions.ConnectionError, ConnectionError)


def test_retryable_exceptions_cover_requests_connection_error() -> None:
    """重試清單必須涵蓋 requests 版本的連線錯誤"""

    assert issubclass(
        requests.exceptions.ConnectionError, RequestUtils.RETRYABLE_EXCEPTIONS
    )


def test_retryable_exceptions_cover_the_builtin_too() -> None:
    """底層 socket 也可能直接拋內建版本，兩個都要攔"""

    assert issubclass(ConnectionError, RequestUtils.RETRYABLE_EXCEPTIONS)


@pytest.mark.parametrize(
    "exception",
    [
        requests.exceptions.ConnectionError("boom"),
        requests.exceptions.ReadTimeout("boom"),
        requests.exceptions.ChunkedEncodingError("boom"),
    ],
)
def test_get_retries_then_returns_none(
    monkeypatch: pytest.MonkeyPatch, exception: Exception
) -> None:
    """
    重試耗盡後回傳 None，**不可讓例外往外炸**

    上層一律以「回傳 None」表示這次取不到，由 updater 決定要跳過還是中止。
    """

    class FailingSession:
        def get(self, *args, **kwargs):
            raise exception

        def post(self, *args, **kwargs):
            raise exception

    monkeypatch.setattr(RequestUtils, "ses", FailingSession())
    monkeypatch.setattr(
        RequestUtils, "find_best_session", classmethod(lambda cls, url: None)
    )
    monkeypatch.setattr(RequestUtils, "HTTP_RETRY_DELAY_SECONDS", 0)
    monkeypatch.setattr(time, "sleep", lambda *_: None)

    assert RequestUtils.requests_get("https://example.com") is None
    assert RequestUtils.requests_post("https://example.com") is None
