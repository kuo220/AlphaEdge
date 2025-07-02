from abc import ABC, abstractmethod
from typing import List, Dict, Tuple, Optional, Any, Union

"""
Abstract base class for database managers.

Defines a standard interface for connect, disconnect, save, and get methods.
Intended to be subclassed by specific database managers (e.g., SQLite, DolphinDB).

Ensures consistent interaction across different storage backends.
"""


class BaseDatabaseManager(ABC):
    """ Base Class of Database Managers """

    def __init__(self):
        pass


    @abstractmethod
    def connect(self) -> None:
        """ Connect to the Database """
        pass


    @abstractmethod
    def disconnect(self) -> None:
        """ Disconnect the Database """
        pass


    @abstractmethod
    def create_db(self) -> None:
        """ Create New Database """
        pass


    @abstractmethod
    def add_to_db(self) -> None:
        """ Add Data into Database """
        pass