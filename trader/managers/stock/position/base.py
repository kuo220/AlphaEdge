from abc import ABC, abstractmethod

"""
Abstract base class for all position managers.
"""


class BasePositionManager(ABC):
    """Base Class of Position Manager"""

    def __init__(self):
        pass

    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Position Manager"""
        pass

    @abstractmethod
    def open_position(self, *args, **kwargs) -> None:
        """Open Position"""
        pass

    @abstractmethod
    def close_position(self, *args, **kwargs) -> None:
        """Close Position"""
        pass

    @abstractmethod
    def split_position(self, *args, **kwargs) -> None:
        """Split Position"""
        pass
