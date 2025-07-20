import datetime
import pandas as pd
from pathlib import Path

from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import PRICE_DOWNLOADS_PATH


class StockPriceLoader(BaseDataLoader):
    """Stock Price Loader"""

    def __init__(self):
        super().__init__()


    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""
        pass


    def connect(self) -> None:
        """Connect to the Database"""
        pass


    def disconnect(self) -> None:
        """Disconnect the Database"""
        pass


    def create_db(self) -> None:
        """Create New Database"""
        pass


    def add_to_db(self) -> None:
        """Add Data into Database"""
        pass
