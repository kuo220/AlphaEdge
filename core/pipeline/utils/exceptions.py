"""Pipeline 專用例外類別。

依資料來源／層級分組，避免不同類型例外混在一起：
- PipelineError：Pipeline 通用基底（可選，供未來 Crawler/Loader 等使用）
- FinMind*：FinMind API 專用

Usage:
    from core.pipeline.utils import FinMindQuotaExhaustedError, FinMindError

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

from typing import List, Optional

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


# -----------------------------------------------------------------------------
# Crawler 例外
# -----------------------------------------------------------------------------


class IPBlockedError(PipelineError):
    """連續多次建立 Session 失敗，本機 IP 多半已被交易所封鎖。

    **存在的理由是「被擋」不能長得像「沒資料」**：舊版 `find_best_session()`
    連續失敗後只印三行提示就回 `None`，呼叫端接著把 `None` 當成休市，
    於是整段回補會安靜地跳過每一天，事後才發現資料整片缺失。

    這是需要人介入（換 IP、重開數據機）才能解除的狀態，故用例外表達。
    """

    def __init__(self, url: str, attempts: int, last_error: Optional[str] = None):
        self.url: str = url
        self.attempts: int = attempts
        self.last_error: Optional[str] = last_error
        super().__init__(
            f"連續 {attempts} 次無法建立 Session（{url}），IP 可能已被封鎖"
            + (f"；最後一次錯誤：{last_error}" if last_error else "")
        )


# -----------------------------------------------------------------------------
# Loader 例外
# -----------------------------------------------------------------------------


class DataLoadError(PipelineError):
    """部分或全部檔案入庫失敗。

    **存在的理由是「不讓失敗變成靜默」**：loader 逐檔入庫時，單一檔案失敗
    （撞主鍵、欄位不符、檔案損毀）不應中止整批——其餘檔案仍該入庫。
    但整批跑完後若有任何失敗，就必須讓呼叫端知道，否則行程會以成功狀態結束，
    缺漏要靠事後逐檔對帳才會被發現。

    `failed_files` 保留失敗清單，供呼叫端記錄或重試。
    """

    def __init__(self, source: str, failed_files: List[str], succeeded: int = 0):
        self.source: str = source
        self.failed_files: List[str] = failed_files
        self.succeeded: int = succeeded
        super().__init__(
            f"{source} 入庫未完全成功：成功 {succeeded} 檔、失敗 {len(failed_files)} 檔"
        )
