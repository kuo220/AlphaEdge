"""
Log Manager for unified logging configuration.

This module provides a centralized logging management system using loguru.
It ensures consistent logging configuration across the entire application.
"""

from pathlib import Path
from typing import Optional

from loguru import logger

from trader.config import BACKTEST_LOGS_DIR_PATH, LOGS_DIR_PATH


class LogManager:
    """
    Unified Log Manager for the application.

    This class provides centralized logging configuration and management.
    It prevents duplicate logger configurations and ensures consistent
    logging behavior across all modules.
    """

    _configured_logs: set[str] = set()
    """Track which log files have been configured to prevent duplicates."""

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
            log_dir: Directory to store log files. Defaults to LOGS_DIR_PATH.
            rotation: When to rotate log files (e.g., "10 MB", "1 day")
            retention: How long to keep log files (e.g., "30 days", "10 files")
            level: Logging level (e.g., "DEBUG", "INFO", "WARNING", "ERROR")
            format: Log message format string

        Example:
            LogManager.setup_logger("update_tick.log")
            LogManager.setup_logger("backtest.log", log_dir=BACKTEST_LOGS_DIR_PATH)
        """
        # Use default log directory if not specified
        if log_dir is None:
            log_dir = LOGS_DIR_PATH

        # Ensure log directory exists
        log_dir.mkdir(parents=True, exist_ok=True)

        # Create full log file path
        log_path = log_dir / log_file

        # Check if this log file has already been configured
        log_path_str = str(log_path)
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
            LogManager.setup_backtest_logger("momentum_strategy")
        """
        log_file = f"{strategy_name}.log"
        LogManager.setup_logger(
            log_file=log_file,
            log_dir=BACKTEST_LOGS_DIR_PATH,
            rotation=rotation,
            retention=retention,
            level=level,
        )

    @staticmethod
    def remove_default_handler() -> None:
        """
        Remove the default loguru handler (console output).
        Useful for testing or when you only want file logging.
        """
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
        """
        Get the loguru logger instance.

        Returns:
            The loguru logger instance

        Example:
            logger = LogManager.get_logger()
            logger.info("This is a log message")
        """
        return logger
