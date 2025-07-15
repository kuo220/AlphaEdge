import sys
import os
import shutil
import time
import datetime
import sqlite3
from io import StringIO
import shioaji as sj
from pathlib import Path
import requests
import pandas as pd
import numpy as np
from typing import List, Dict, Set, Optional
import json
from io import StringIO
from dotenv import load_dotenv
from tqdm import tqdm
from tqdm.notebook import tqdm
import zipfile
from dataclasses import dataclass, asdict

from trader.utils import ShioajiAccount, Units
from trader.api import (Data, Tick)
from trader.pipeline.crawlers.utils.payload import Payload
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.crawlers.stock_price_crawler import StockPriceCrawler
from trader.pipeline.crawlers.stock_chip_crawler import StockChipCrawler
from trader.pipeline.crawlers.stock_tick_crawler import StockTickCrawler
from trader.pipeline.crawlers.stock_info_crawler import StockInfoCrawler
from trader.pipeline.crawlers.financial_statement_crawler import FinancialStatementCrawler
from trader.pipeline.crawlers.monthly_revenue_report_crawler import MonthlyRevenueReportCrawler
from trader.pipeline.cleaners.stock_chip_cleaner import StockChipCleaner
from trader.pipeline.cleaners.stock_price_cleaner import StockPriceCleaner
from trader.pipeline.cleaners.stock_tick_cleaner import StockTickCleaner
from trader.pipeline.cleaners.financial_statement_cleaner import FinancialStatementCleaner
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils import (
    URLManager,
    MarketType,
    FinancialStatementType
)
from trader.pipeline import URLManager
from trader.config import (
    CRAWLER_DOWNLOADS_PATH,
    PRICE_DOWNLOADS_PATH,
    TICK_DOWNLOADS_PATH,
    FINANCIAL_STATEMENT_PATH,
    CERTS_FILE_PATH,
    CHIP_DB_PATH,
    CHIP_TABLE_NAME,
    TICK_METADATA_PATH,
    API_LIST
)


start_date = datetime.date(2013, 1, 1)
end_date = datetime.date(2025, 7, 1)
season = 1
code = '2330'


if __name__ == "__main__":
    fs_crawler: FinancialStatementCrawler = FinancialStatementCrawler()
    fs_cleaner: FinancialStatementCleaner = FinancialStatementCleaner()

    start_year: int = start_date.year
    end_year: int = end_date.year
    report_type = FinancialStatementType.COMPREHENSIVE_INCOME

    # for report_type in FinancialStatementType:
    #     if report_type == FinancialStatementType.EQUITY_CHANGE:
    #         continue

    cols: List[str] = fs_crawler.get_all_report_columns(
        start_year,
        end_year,
        report_type=report_type
    )

    print(cols)

    # for year in range(start_date.year, end_date.year):
    #     df = fs_crawler.crawl_balance_sheet(year, season)
    #     df = fs_cleaner.clean_balance_sheet(df, year, season)