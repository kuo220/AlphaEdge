import time
import random
import sqlite3
import pandas as pd
from pathlib import Path
from loguru import logger
from typing import List, Optional

from trader.pipeline.updaters.base import BaseDataUpdater
from trader.pipeline.crawlers.financial_statement_crawler import (
    FinancialStatementCrawler,
)
from trader.pipeline.cleaners.financial_statement_cleaner import (
    FinancialStatementCleaner,
)
from trader.pipeline.loaders.financial_statement_loader import FinancialStatementLoader
from trader.pipeline.utils import FinancialStatementType
from trader.pipeline.utils.sqlite_utils import SQLiteUtils
from trader.utils import TimeUtils
from trader.config import (
    DB_PATH,
    LOGS_DIR_PATH,
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    BALANCE_SHEET_TABLE_NAME,
    COMPREHENSIVE_INCOME_TABLE_NAME,
    CASH_FLOW_TABLE_NAME,
    EQUITY_CHANGE_TABLE_NAME,
)


"""
* Crawl Balance Sheet (資產負債表)
資料區間（但是只有 102 年以後才可以爬）
上市: 民國 78 (1989) 年 ~ present
上櫃: 民國 82 (1993) 年 ~ present

* Crawl Statement of Comprehensive Income (綜合損益表)
資料區間（但是只有 102 年以後才可以爬）
上市: 民國 77 (1988) 年 ~ present
上櫃: 民國 82 (1993) 年 ~ present

* Crawl Cash Flow Statement (現金流量表)
資料區間
上市: 民國 102 (2013) 年 ~ present
上櫃: 民國 102 (2013) 年 ~ present

* Crawl Statement of Changes in Equity (權益變動表)
資料區間
上市: 民國 102 (2013) 年 ~ present
上櫃: 民國 102 (2013) 年 ~ present
"""

"""
財報申報期限（依行業類型區分）：

1. 一般行業：
   - Q1：5月15日
   - Q2：8月14日
   - Q3：11月14日
   - 年報：3月31日

2. 金控業：
   - Q1：5月30日
   - Q2：8月31日
   - Q3：11月29日
   - 年報：3月31日

3. 銀行及票券業：
   - Q1：5月15日
   - Q2：8月31日
   - Q3：11月14日
   - 年報：3月31日

4. 保險業：
   - Q1：5月15日
   - Q2：8月31日
   - Q3：11月14日
   - 年報：3月31日

5. 證券業：
   - Q1：5月15日
   - Q2：8月31日
   - Q3：11月14日
   - 年報：3月31日
"""


class FinancialStatementUpdater(BaseDataUpdater):
    """Financial Statement Updater"""

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: sqlite3.Connection = None

        # ETL
        self.crawler: FinancialStatementCrawler = FinancialStatementCrawler()
        self.cleaner: FinancialStatementCleaner = FinancialStatementCleaner()
        self.loader: FinancialStatementLoader = FinancialStatementLoader()

        # Table latest year & season
        self.table_latest_year: Optional[int] = None
        self.table_latest_season: Optional[int] = None

        # Data directories for each report
        self.fs_dir: Path = FINANCIAL_STATEMENT_DOWNLOADS_PATH
        self.balance_sheet_dir: Path = (
            self.fs_dir / FinancialStatementType.BALANCE_SHEET.lower()
        )
        self.comprehensive_income_dir: Path = (
            self.fs_dir / FinancialStatementType.COMPREHENSIVE_INCOME.lower()
        )
        self.cash_flow_dir: Path = (
            self.fs_dir / FinancialStatementType.CASH_FLOW.lower()
        )
        self.equity_change_dir: Path = (
            self.fs_dir / FinancialStatementType.EQUITY_CHANGE.lower()
        )

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Updater"""

        # DB Connect
        if self.conn is None:
            self.conn = sqlite3.connect(DB_PATH)

        # 設定 log 檔案儲存路徑
        logger.add(f"{LOGS_DIR_PATH}/update_financial_statement.log")

    def update(
        self, start_year: int, end_year: int, start_season: int, end_season: int
    ) -> None:
        """Update the Database"""

        # Update Balance Sheet
        self.update_balance_sheet(start_year, end_year, start_season, end_season)

        # Update Comprehensive Income
        self.update_comprehensive_income(start_year, end_year, start_season, end_season)

        # Update Cash Flow
        self.update_cash_flow(start_year, end_year, start_season, end_season)

    def update_balance_sheet(
        self, start_year: int, end_year: int, start_season: int, end_season: int
    ) -> None:
        """Update Balance Sheet"""

        logger.info("* Start Updating Balance Sheet Data...")

        # Step 1: Crawl
        # Set Up Update Period
        # 取得最近更新的時間
        start_year: int = self.get_table_latest_year(
            table_name=BALANCE_SHEET_TABLE_NAME, default_year=start_year
        )
        start_season: int = self.get_table_latest_season(
            table_name=BALANCE_SHEET_TABLE_NAME, default_season=start_season
        )
        logger.info(f"Latest data date in database: {start_year}Q{start_season}")
        years: List[int] = TimeUtils.generate_season_range(start_year, end_year)
        seasons: List[int] = TimeUtils.generate_season_range(start_season, end_season)
        file_cnt: int = 0

        for year in years:
            for season in seasons:
                logger.info(f"* {year}Q{season}")
                df_list: Optional[List[pd.DataFrame]] = (
                    self.crawler.crawl_balance_sheet(year, season)
                )

                # Step 2: Clean
                if df_list is not None and len(df_list):
                    cleaned_df: pd.DataFrame = self.cleaner.clean_balance_sheet(
                        df_list, year, season
                    )

                    if cleaned_df is None or cleaned_df.empty:
                        logger.warning(
                            f"Cleaned balance sheet dataframe empty on {year}Q{season}."
                        )

                file_cnt += 1

                if file_cnt == 10:
                    logger.info("Sleep 30 seconds...")
                    file_cnt = 0
                    time.sleep(30)
                else:
                    delay = random.randint(1, 5)
                    time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(
            dir_path=self.balance_sheet_dir,
            table_name=BALANCE_SHEET_TABLE_NAME,
            remove_files=False,
        )

    def update_comprehensive_income(
        self, start_year: int, end_year: int, start_season: int, end_season: int
    ) -> None:
        """Update Comprehensive Income"""

        logger.info("* Start Updating Comprehensive Income Data...")

        # Step 1: Crawl
        # Set Up Update Period
        start_year: int = self.get_table_latest_year(
            table_name=COMPREHENSIVE_INCOME_TABLE_NAME, default_year=start_year
        )
        start_season: int = self.get_table_latest_season(
            table_name=COMPREHENSIVE_INCOME_TABLE_NAME, default_season=start_season
        )
        logger.info(f"Latest data date in database: {start_year}Q{start_season}")
        years: List[int] = TimeUtils.generate_season_range(start_year, end_year)
        seasons: List[int] = TimeUtils.generate_season_range(start_season, end_season)
        file_cnt: int = 0

        for year in years:
            for season in seasons:
                logger.info(f"* {year}Q{season}")
                df_list: Optional[List[pd.DataFrame]] = (
                    self.crawler.crawl_comprehensive_income(year, season)
                )

                # Step 2: Clean
                if df_list is not None and len(df_list):
                    cleaned_df: pd.DataFrame = self.cleaner.clean_comprehensive_income(
                        df_list, year, season
                    )

                    if cleaned_df is None or cleaned_df.empty:
                        logger.warning(
                            f"Cleaned comprehensive income dataframe empty on {year}Q{season}."
                        )

                file_cnt += 1

                if file_cnt == 10:
                    logger.info("Sleep 30 seconds...")
                    file_cnt = 0
                    time.sleep(30)
                else:
                    delay = random.randint(1, 5)
                    time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(
            dir_path=self.comprehensive_income_dir,
            table_name=COMPREHENSIVE_INCOME_TABLE_NAME,
            remove_files=False,
        )

    def update_cash_flow(
        self, start_year: int, end_year: int, start_season: int, end_season: int
    ) -> None:
        """Update Cash Flow"""

        logger.info("* Start Updating Cash Flow Data...")

        # Step 1: Crawl
        # Set Up Update Period
        start_year: int = self.get_table_latest_year(
            table_name=CASH_FLOW_TABLE_NAME, default_year=start_year
        )
        start_season: int = self.get_table_latest_season(
            table_name=CASH_FLOW_TABLE_NAME, default_season=start_season
        )
        logger.info(f"Latest data date in database: {start_year}Q{start_season}")
        years: List[int] = TimeUtils.generate_season_range(start_year, end_year)
        seasons: List[int] = TimeUtils.generate_season_range(start_season, end_season)
        file_cnt: int = 0

        for year in years:
            for season in seasons:
                logger.info(f"* {year}Q{season}")
                df_list: Optional[List[pd.DataFrame]] = self.crawler.crawl_cash_flow(
                    year, season
                )

                # Step 2: Clean
                if df_list is not None and len(df_list):
                    cleaned_df: pd.DataFrame = self.cleaner.clean_cash_flow(
                        df_list, year, season
                    )

                    if cleaned_df is None or cleaned_df.empty:
                        logger.warning(
                            f"Cleaned cash flow dataframe empty on {year}Q{season}."
                        )

                file_cnt += 1

                if file_cnt == 10:
                    logger.info("Sleep 30 seconds...")
                    file_cnt = 0
                    time.sleep(30)
                else:
                    delay = random.randint(1, 5)
                    time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(
            dir_path=self.cash_flow_dir,
            table_name=CASH_FLOW_TABLE_NAME,
            remove_files=False,
        )

    def update_equity_changes(
        self,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
        stock_id: str,
    ) -> None:
        """Update Equity Changes"""
        # TODO: 因為 Equity Changes 的 cleaner & loader 還未完成，所以這部分還無法使用

        logger.info("* Start Updating Equity Changes Data...")

        # Step 1: Crawl
        # Set Up Update Period
        start_year: int = self.get_table_latest_year(
            table_name=EQUITY_CHANGE_TABLE_NAME, default_year=start_year
        )
        start_season: int = self.get_table_latest_season(
            table_name=EQUITY_CHANGE_TABLE_NAME, default_season=start_season
        )
        logger.info(f"Latest data date in database: {start_year}Q{start_season}")
        years: List[int] = TimeUtils.generate_season_range(start_year, end_year)
        seasons: List[int] = TimeUtils.generate_season_range(start_season, end_season)
        file_cnt: int = 0

        for year in years:
            for season in seasons:
                logger.info(f"* {year}Q{season}")
                df_list: Optional[List[pd.DataFrame]] = (
                    self.crawler.crawl_equity_changes(year, season, stock_id)
                )

                # Step 2: Clean
                if df_list is not None and len(df_list):
                    cleaned_df: pd.DataFrame = self.cleaner.clean_equity_changes(
                        df_list, year, season
                    )

                    if cleaned_df is None or cleaned_df.empty:
                        logger.warning(
                            f"Cleaned equity changes dataframe empty on {year}Q{season}."
                        )

                file_cnt += 1

                if file_cnt == 10:
                    logger.info("Sleep 30 seconds...")
                    file_cnt = 0
                    time.sleep(30)
                else:
                    delay = random.randint(1, 5)
                    time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(
            dir_path=self.equity_change_dir,
            table_name=EQUITY_CHANGE_TABLE_NAME,
            remove_files=False,
        )

    def get_table_latest_year(self, table_name: str, default_year: int = 2025) -> int:
        """Update table latest year"""

        latest_year: Optional[int] = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=table_name, col_name="year"
        )
        self.table_latest_year = (
            int(latest_year) if latest_year is not None else default_year
        )
        return self.table_latest_year

    def get_table_latest_season(
        self, table_name: str, default_season: int = 2025
    ) -> int:
        """Update table latest year"""

        latest_season: Optional[int] = SQLiteUtils.get_table_latest_value(
            conn=self.conn, table_name=table_name, col_name="season"
        )
        self.table_latest_season = (
            int(latest_season) if latest_season is not None else default_season
        )
        return self.table_latest_season
