"""Pipeline 專用例外類別。

依資料來源／層級分組，避免不同類型例外混在一起：
- PipelineError：Pipeline 通用基底（可選，供未來 Crawler/Loader 等使用）
- FinMind*：FinMind API 專用

Usage:
    from trader.pipeline.utils import FinMindQuotaExhaustedError, FinMindError

    try:
        df = crawler.crawl_broker_trading_daily_report(...)
    except FinMindQuotaExhaustedError:
        # 配額用盡：等待重置或稍後重試
        ...
    except FinMindError as e:
        # 其他 FinMind 錯誤
        ...

    if FinMindError.is_quota_error(some_exception):
        # 判斷是否為配額相關（含 HTTP 402、KeyError('data') 等）
        ...
"""

from typing import Optional


# -----------------------------------------------------------------------------
# Pipeline 通用（未來可擴充 CrawlerError, LoaderError 等）
# -----------------------------------------------------------------------------


class PipelineError(Exception):
    """Pipeline 相關錯誤的共通基底，方便與其他模組的 Exception 區隔。"""

    pass


# -----------------------------------------------------------------------------
# FinMind 例外階層（業界常見：Base -> 具體錯誤類型）
# -----------------------------------------------------------------------------


class FinMindError(PipelineError):
    """FinMind 相關錯誤的基底類別。"""

    @classmethod
    def is_quota_error(cls, exc: BaseException) -> bool:
        """判斷例外是否為 FinMind API 配額用盡相關錯誤。

        辨識條件（依序）：
        1. KeyError('data')：配額用盡時 FinMind API 常回傳無 "data" 的 JSON，套件內會拋出 KeyError。
        2. HTTP 402：FinMind API 配額用盡時回傳 402 (Payment Required / 用量超出上限)。
        3. 訊息關鍵字：402、quota、rate limit、exceeded、配額（含 __cause__ 鏈）。

        Args:
            exc: 要檢查的例外（可為鏈狀 __cause__ 的根）。

        Returns:
            True 若判定為配額相關錯誤，否則 False。
        """
        err: Optional[BaseException] = exc
        seen: set[int] = set()

        while err is not None and id(err) not in seen:
            seen.add(id(err))

            # FinMind 配額用盡時常回傳無 "data" 的 JSON，套件內 pd.DataFrame(response["data"]) 會拋 KeyError
            if (
                isinstance(err, KeyError)
                and len(err.args) > 0
                and err.args[0] == "data"
            ):
                return True

            # HTTP 402 (FinMind 配額用盡／用量超出上限)
            if hasattr(err, "response") and getattr(err, "response", None) is not None:
                status = getattr(err.response, "status_code", None)
                if status == 402:
                    return True

            # 訊息或內容含配額相關關鍵字
            msg: str = ""
            if getattr(err, "args", ()):
                msg = str(err.args[0]) if err.args else ""
            if not msg:
                msg = str(err)
            msg_lower: str = msg.lower()
            if any(
                k in msg_lower
                for k in (
                    "402",
                    "quota",
                    "rate limit",
                    "rate_limit",
                    "exceeded",
                    "配額",
                )
            ):
                return True

            err = getattr(err, "__cause__", None)

        return False


class FinMindQuotaExhaustedError(FinMindError):
    """FinMind API 配額用盡。

    可能情境：
    - HTTP 402（用量超出上限，依 FinMind API 說明）
    - API 回傳 JSON 無 "data" 鍵（FinMind 套件會拋出 KeyError('data')）
    - 回應內容含 quota / rate limit / exceeded 等關鍵字
    """

    pass
