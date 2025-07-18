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
