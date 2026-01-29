from abc import ABC, abstractmethod

"""Abstract base class for all data updaters that coordinate the full ETL process"""


class BaseDataUpdater(ABC):
    """Base Class of Data Updater"""

    def __init__(self):
        pass

    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""
        pass

    @abstractmethod
    def update(self, *args, **kwargs) -> None:
        """Update the Database"""
        pass
