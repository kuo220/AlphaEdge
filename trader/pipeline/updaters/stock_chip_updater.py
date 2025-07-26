import datetime
import random
import time
import requests
from loguru import logger
import pandas as pd
from io import StringIO
from typing import Optional

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils.url_manager import URLManager
from trader.utils import TimeUtils


"""
三大法人爬蟲資料時間表：
1. TWSE
    - TWSE: 2012/5/2 開始提供（這邊從 2014/12/1 開始爬）
    - TWSE 改制時間: 2014/12/1, 2017/12/18
2. TPEX
    - TPEX: 2007/4/20 開始提供 (這邊從 2014/12/1 開始爬)
    - TPEX 改制時間: 2018/1/15
"""


class StockChipUpdater(BaseDataUpdater):
    """ Stock Tick Updater """

    def __init__(self):
        super().__init__()


    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Updater"""
        pass


    def update(self) -> None:
        """Update the Database"""
        pass
