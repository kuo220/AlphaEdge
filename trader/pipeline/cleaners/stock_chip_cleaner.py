import os
import random
import sqlite3
import datetime
import time
from pathlib import Path
from typing import List, Dict, Optional, Any
from io import StringIO

import pandas as pd
import requests

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.utils.crawler_utils import CrawlerUtils, URLManager
from trader.config import (
    CHIP_DOWNLOADS_PATH,
    CHIP_DB_PATH,
)


class StockChipCleaner(BaseDataCleaner):
    """ Stock Chip Cleaner (Transform) """

    def __init__(self):
        super().__init__()


    def clean_twse_chip(self, df: pd.DataFrame) -> pd.DataFrame:
        """ Clean TWSE Stock Chip Data """

        