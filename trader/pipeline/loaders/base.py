from abc import ABC, abstractmethod

"""
Abstract base class for all data loaders that write processed data to a storage system.
Subclasses should implement the `load(df)` method.
"""


class BaseDataLoader(ABC):
    """Base Class of Data Loader"""

    def __init__(self):
        pass

    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""
        pass

    @abstractmethod
    def connect(self) -> None:
        """Connect to the Database"""
        pass

    @abstractmethod
    def disconnect(self) -> None:
        """Disconnect the Database"""
        pass

    @abstractmethod
    def create_db(self, *args, **kwargs) -> None:
        """Create New Database"""
        pass

    @abstractmethod
    def add_to_db(self, *args, **kwargs) -> None:
        """Add Data into Database"""
        pass
