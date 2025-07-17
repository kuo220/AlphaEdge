import threading
from loguru import logger
from typing import Callable, Any


def log_thread(func: Callable) -> Callable:
    """Decorator: log thread info when function starts."""

    def wrapper(*args: Any, **kwargs: Any) -> Any:
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        logger.info(f"Thread started: id={thread_id}, name={thread_name}")
        return func(*args, **kwargs)

    return wrapper
