import time
import random
import pandas as pd
import requests
from io import StringIO
from pathlib import Path
from loguru import logger
from typing import List, Dict, Optional

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.crawlers.utils.payload import Payload
from trader.pipeline.utils import (
    URLManager,
    MarketType,
    FinancialStatementType,
)
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import (
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_META_DIR_PATH,
)


class FinancialStatementUpdater(BaseDataUpdater):
    """Financial Statement Updater"""

    def __init__(self):
        super().__init__()


    def setup(self) -> None:
        """Set Up the Config of Updater"""
        pass


    def update(self) -> None:
        """Update the Database"""
        pass