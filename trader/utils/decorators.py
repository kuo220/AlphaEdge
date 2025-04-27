import threading
from loguru import logger


def log_thread(func):
    """Decorator: log thread info when function starts."""
    
    def wrapper(*args, **kwargs):
        thread_id = threading.get_ident()
        thread_name = threading.current_thread().name
        logger.info(f"Thread started: id={thread_id}, name={thread_name}")
        return func(*args, **kwargs)
    return wrapper
