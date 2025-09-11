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