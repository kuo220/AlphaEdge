import datetime
import os
import time
from concurrent.futures import Future, ThreadPoolExecutor, as_completed
from typing import List, Optional, Any
import pandas as pd
import shioaji as sj
from shioaji.data import Ticks
from loguru import logger
from tqdm import tqdm
from pathlib import Path

from trader.utils import ShioajiAccount, ShioajiAPI, log_thread
from trader.pipeline.updaters.stock_tick_updater import BaseDataUpdater
from trader.pipeline.crawlers.stock_info_crawler import StockInfoCrawler
from trader.pipeline.utils.stock_tick_utils import StockTickUtils
from trader.config import (
    LOGS_DIR_PATH,
    TICK_DOWNLOADS_PATH,
    API_LIST,
)


class StockTickUpdater(BaseDataUpdater):
    """Stock Tick Updater"""

    def __init__(self):
        pass

    def setup(self):
        """Set Up the Config of Updater"""
        pass

    def update(self):
        """Update the Database"""
        pass
