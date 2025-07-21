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

        # Downloads directory Path
        self.mrr_dir: Path = MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH

        # MMR Cleaned Columns Path
        self.monthly_revenue_report_cleaned_cols_path: Path = (
            MONTHLY_REVENUE_REPORT_META_DIR_PATH
            / f"{DataType.MRR.lower()}_cleaned_columns.json"
        )



    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Loader"""
        # Create the tick downloads directory
        self.mrr_dir.mkdir(parents=True, exist_ok=True)



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
