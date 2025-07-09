from abc import ABC, abstractmethod

"""
Abstract base class for all data cleaners that transform raw data into a standardized format.
Subclasses should implement the `clean(df)` method.
"""


class BaseDataCleaner(ABC):
    """ Base Class of Data Cleaner """

    def __init__(self):
        pass


    @abstractmethod
    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Cleaner """
        pass