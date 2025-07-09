from abc import ABC, abstractmethod

"""
Abstract base class for all data loaders that write processed data to a storage system.
Subclasses should implement the `load(df)` method.
"""


class BaseDataLoader(ABC):
    """ Base Class of Data Loader """

    def __init__(self):
        pass


    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Loader """
        pass