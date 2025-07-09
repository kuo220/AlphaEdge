import datetime
import pandas as pd
from io import StringIO
import requests
from pathlib import Path
from loguru import logger
from typing import List, Optional

from trader.pipeline.crawlers.base import BaseDataCrawler
from trader.pipeline.utils import URLManager
from trader.pipeline.utils.crawler_utils import CrawlerUtils
from trader.config import PRICE_DOWNLOADS_PATH