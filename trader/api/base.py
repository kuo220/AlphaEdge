from abc import ABC, abstractmethod

"""
Abstract base class for data access APIs.
Provides a common interface for querying data from the database.
"""


class BaseDataAPI(ABC):
    """ Base Class of Data API """

    def __init__(self):
        pass

    def setup(self):
        """ Set Up the Config of Cleaner """
        pass