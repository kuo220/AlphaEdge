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
from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.crawlers.stock_info_crawler import StockInfoCrawler
from trader.pipeline.utils.stock_tick_utils import StockTickUtils
from trader.config import (
    LOGS_DIR_PATH,
    TICK_DOWNLOADS_PATH,
    API_LIST,
)


class StockTickCleaner(BaseDataCleaner):
    """ Stock Tick Cleaner (Transform) """

    def __init__(self):
        super().__init__()


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Cleaner """
        pass