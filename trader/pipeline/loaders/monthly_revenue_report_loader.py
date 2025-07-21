import datetime
from io import StringIO
from loguru import logger
from pathlib import Path
from typing import List, Optional
import pandas as pd
import requests

from trader.pipeline.loaders.base import BaseDataLoader
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils import URLManager, DataType, MarketType, FileEncoding
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import (
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
)


class MonthlyRevenueReportLoader(BaseDataLoader):
    """TWSE & TPEX Monthly Revenue Report Loader"""

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

    def create_db(self, *args, **kwargs) -> None:
        """Create New Database"""
        pass

    def add_to_db(self, *args, **kwargs) -> None:
        """Add Data into Database"""
        pass
