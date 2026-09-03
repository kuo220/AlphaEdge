"""
Log Manager：以 loguru 統一設定日誌

**loguru 的 sink 預設收下整個行程的每一行**（健檢 F-001）：本專案有 33 個
`setup_logger()` 呼叫端，少了 `filter=` 的話，`core/api/` 的一次查詢會同時寫進
`logs/api/`、`logs/pipeline/`、`logs/backtest/` 底下的**每一個**檔案。
`logs/api/` 每天長約 100 MB（F-097）大部分不是 api 自己的日誌，是別人的。

修法是**依「記錄從哪個套件發出」分桶**：api 桶只收 `core.api.*`、
backtest 桶只收回測相關套件、pipeline 桶收其餘。這樣不需要改動任何一個
`logger.info()` 呼叫端——若改用 `logger.bind(module=...)` 過濾，
沒有 bind 的模組會**整批消失**，那比寫太多更糟。

⚠️ **同一個桶內的檔案仍會互收**（例如 `update_price.log` 也會收到
`update_chip.log` 的內容）。要做到逐檔隔離必須讓每個呼叫端 bind 自己的名字，
屬另一階段的工作；本次先把跨桶的重複拿掉，那是量體的主要來源。
"""

from pathlib import Path
from typing import Callable, Dict, Optional, Set, Tuple

from loguru import logger

from core.config import (
    BACKTEST_LOGS_DIR_PATH,
    PIPELINE_LOGS_DIR_PATH,
)


class LogManager:
    """Unified Log Manager for the application"""

    _configured_logs: Set[str] = set()
    """Track which log files have been configured to prevent duplicates"""

    # 每個日誌桶收哪些套件發出的記錄（比對 `record["name"]` 的前綴）。
    # pipeline 桶不列前綴，代表「其餘全收」——新增的模組不會憑空消失。
    BUCKET_PREFIXES: Dict[str, Tuple[str, ...]] = {
        "api": ("core.api",),
        "backtest": (
            "core.backtest",
            "core.strategies",
            "core.managers",
            "core.models",
            "core.adapters",
            "strategy_lab",
        ),
    }

    @classmethod
    def build_bucket_filter(cls, log_dir: Path) -> Callable:
        """
        - Description:
            依日誌桶產生 `filter`，讓 sink 只收自己那一桶的記錄

            桶名取自目錄名（`logs/api` → `api`）。三個桶構成一個**分割**：

            - `api`／`backtest`：只收 `BUCKET_PREFIXES` 列出的套件。
            - 其餘（含 `pipeline` 與自訂目錄）：收**沒有被其他桶認領**的記錄。

            後者刻意是「排除法」而不是白名單：新增一個套件時它會自動落進
            pipeline 桶，而不是**整批消失**。日誌設定的預設值該偏向多收，
            少收是查不出來的。
        - Parameters:
            - log_dir: Path
                sink 的目錄
        - Return:
            - Callable
                loguru 的 filter
        """

        owned: Optional[Tuple[str, ...]] = cls.BUCKET_PREFIXES.get(log_dir.name)

        if owned:

            def accept_owned(record) -> bool:
                return str(record["name"]).startswith(owned)

            return accept_owned

        claimed: Tuple[str, ...] = tuple(
            prefix for prefixes in cls.BUCKET_PREFIXES.values() for prefix in prefixes
        )

        def accept_rest(record) -> bool:
            return not str(record["name"]).startswith(claimed)

        return accept_rest

    @staticmethod
    def setup_logger(
        log_file: str,
        log_dir: Optional[Path] = None,
        rotation: str = "10 MB",
        retention: str = "30 days",
        level: str = "INFO",
        format: str = "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
    ) -> None:
        """
        Set up a logger with specified configuration.

        Args:
            log_file: Name of the log file (e.g., "update_tick.log")
            log_dir: Directory to store log files. Defaults to PIPELINE_LOGS_DIR_PATH.
            rotation: When to rotate log files (e.g., "10 MB", "1 day")
            retention: How long to keep log files (e.g., "30 days", "10 files")
            level: Logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR")
            format: Log message format string

        Example:
            LogManager.setup_logger("update_tick.log")
            LogManager.setup_logger("backtest.log", log_dir=BACKTEST_LOGS_DIR_PATH)
        """
        # 未指定時落在 pipeline 桶：29 個呼叫端裡多數是爬取／清洗／入庫，
        # 這樣改動面最小。`core/api/` 一律自行帶入 API_LOGS_DIR_PATH（見 config.py）
        if log_dir is None:
            log_dir: Path = PIPELINE_LOGS_DIR_PATH

        # Ensure log directory exists
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create full log file path
        log_path: Path = log_dir / log_file

        # Check if this log file has already been configured
        log_path_str: str = str(log_path)
        if log_path_str in LogManager._configured_logs:
            # Logger already configured, skip to avoid duplicates
            return

        # Add logger with specified configuration
        logger.add(
            log_path_str,
            rotation=rotation,
            retention=retention,
            level=level,
            format=format,
            enqueue=True,  # Thread-safe logging
            # 沒有 filter 的話，這個 sink 會收下整個行程的每一行（F-001）
            filter=LogManager.build_bucket_filter(log_dir),
        )

        # Track this log file as configured
        LogManager._configured_logs.add(log_path_str)

    @staticmethod
    def setup_backtest_logger(
        strategy_name: str,
        rotation: str = "10 MB",
        retention: str = "30 days",
        level: str = "INFO",
    ) -> None:
        """
        Set up a logger specifically for backtest results.

        Args:
            strategy_name: Name of the strategy (used as log file name)
            rotation: When to rotate log files
            retention: How long to keep log files
            level: Logging level

        Example:
            LogManager.setup_backtest_logger("momentum_strategy_1")
        """
        log_file: str = f"{strategy_name}.log"
        LogManager.setup_logger(
            log_file=log_file,
            log_dir=BACKTEST_LOGS_DIR_PATH,
            rotation=rotation,
            retention=retention,
            level=level,
        )

    @staticmethod
    def remove_default_handler() -> None:
        """Remove the default loguru handler (console output)"""
        logger.remove()

    @staticmethod
    def add_console_handler(
        level: str = "INFO",
        format: str = "{message}",
    ) -> None:
        """
        Add a console handler for logging to stdout.

        Args:
            level: Logging level for console output
            format: Log message format string

        Example:
            LogManager.add_console_handler(level="DEBUG")
        """
        logger.add(
            lambda msg: print(msg, end=""),
            format=format,
            level=level,
        )

    @staticmethod
    def get_logger():
        """Get the loguru logger instance"""
        return logger
