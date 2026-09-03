import random
import sqlite3
import time
from pathlib import Path
from typing import List, Optional, Set, Tuple

import pandas as pd
from loguru import logger

from core.config import (
    BALANCE_SHEET_TABLE_NAME,
    CASH_FLOW_TABLE_NAME,
    COMPREHENSIVE_INCOME_TABLE_NAME,
    EQUITY_CHANGE_TABLE_NAME,
    FINANCIAL_STATEMENT_DOWNLOADS_PATH,
    STOCK_INFO_TABLE_NAME,
    TW_STOCK_DB_PATH,
)
from core.pipeline.shared.base_updater import BaseDataUpdater
from core.pipeline.tw.cleaners.financial_statement_cleaner import (
    FinancialStatementCleaner,
)
from core.pipeline.tw.crawlers.financial_statement_crawler import (
    FinancialStatementCrawler,
)
from core.pipeline.tw.loaders.financial_statement_loader import FinancialStatementLoader
from core.pipeline.utils import FinancialStatementType
from core.pipeline.utils.sqlite_utils import SQLiteUtils
from core.utils import TimeUtils
from core.utils.log_manager import LogManager

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

    BATCH_SLEEP_EVERY_N_FILES: int = 10
    BATCH_SLEEP_DURATION_SECONDS: int = 30
    BATCH_RANDOM_DELAY_MIN: int = 1
    BATCH_RANDOM_DELAY_MAX: int = 5
    LAST_SEASON: int = 4  # 第4季，用於季別進位判斷

    # 權益變動表專用（逐檔查詢，量級與其他三張報表差了三個數量級）
    EQUITY_CHANGE_LOAD_BATCH_SIZE: int = 100  # 每 100 檔入庫一次
    # 節流參數不與其他三張報表共用：那三張是「全市場一次查完」，整段回補也才幾十次
    # 請求，沒有放寬的必要；權益變動表一個年季就要兩千多次，節流直接決定回補要跑幾天。
    # 現行值為 2026-08-28 放寬後的設定（原為共用的 1~5 秒／每 10 檔睡 30 秒，約 6 秒/檔）：
    # 平均約 1.3 秒/檔，一個年季約 0.8 小時、56 個年季約 42 小時。
    # 放寬的依據是 2020Q1 全市場回補連續近 4 小時 unreachable = 0，代表原設定過於保守；
    # 但「放寬多少才會被擋」沒有實測過，若 log 尾端開始出現大量 unreachable 就調回來
    EQUITY_CHANGE_RANDOM_DELAY_MIN: float = 0.5
    EQUITY_CHANGE_RANDOM_DELAY_MAX: float = 1.5
    EQUITY_CHANGE_BATCH_SLEEP_EVERY_N_FILES: int = 50
    EQUITY_CHANGE_BATCH_SLEEP_DURATION_SECONDS: int = 15
    # 判斷「該年季是否已申報」用的試探標的：都是 2013 年前就上市的權值股，
    # 只要有任何一檔查得到，該年季就確定已申報（理由見 is_season_filed()）
    EQUITY_CHANGE_PROBE_STOCK_IDS: Tuple[str, ...] = ("2330", "2317", "1101")

    def __init__(self):
        super().__init__()

        # SQLite Connection
        self.conn: Optional[sqlite3.Connection] = None

        # ETL
        self.crawler: FinancialStatementCrawler = FinancialStatementCrawler()
        self.cleaner: FinancialStatementCleaner = FinancialStatementCleaner()
        self.loader: FinancialStatementLoader = FinancialStatementLoader()

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
            self.conn: sqlite3.Connection = sqlite3.connect(TW_STOCK_DB_PATH)

        # 設定 log 檔案儲存路徑
        LogManager.setup_logger("update_financial_statement.log")

    def update(
        self,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
    ) -> None:
        """Update the Database"""

        # Update Balance Sheet
        self.update_balance_sheet(start_year, end_year, start_season, end_season)

        # Update Comprehensive Income
        self.update_comprehensive_income(start_year, end_year, start_season, end_season)

        # Update Cash Flow
        self.update_cash_flow(start_year, end_year, start_season, end_season)

        # Update Equity Changes
        # 逐檔查詢，量級與前三張報表差三個數量級（一個年季約兩千次請求），
        # 故放在最後：即使這裡耗時或中斷，前三張報表已經入庫完成
        self.update_equity_changes(start_year, end_year, start_season, end_season)

    def update_balance_sheet(
        self,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
    ) -> None:
        """Update Balance Sheet"""

        logger.info("* Start Updating Balance Sheet Data...")

        # Step 1: Crawl
        # 取得要開始更新的年度、季度
        start_year: int
        start_season: int
        start_year, start_season = self.get_actual_update_start_year_season(
            table_name=BALANCE_SHEET_TABLE_NAME,
            default_year=start_year,
            default_season=start_season,
        )
        logger.info(f"Latest data date in database: {start_year}Q{start_season}")
        # Set Up Update Period
        # **不可用 years × seasons 的笛卡兒積**：起點 2024Q3、終點 2026Q4 時
        # `seasons` 只會是 [3, 4]，2025Q1／Q2 與 2026Q1／Q2 整整四季不會被爬，
        # 且不會有任何錯誤——它們只是從來沒出現在迴圈裡（健檢 F-054）
        year_seasons: List[Tuple[int, int]] = TimeUtils.generate_year_period_range(
            start_year, start_season, end_year, end_season, periods_per_year=4
        )
        file_cnt: int = 0

        for year, season in year_seasons:
            logger.info(f"* {year}Q{season}")
            df_list: Optional[List[pd.DataFrame]] = self.crawler.crawl_balance_sheet(
                year, season
            )

            # Step 2: Clean
            if df_list is None or not df_list:
                continue

            cleaned_df: pd.DataFrame = self.cleaner.clean_balance_sheet(
                df_list, year, season
            )

            if cleaned_df is None or cleaned_df.empty:
                logger.warning(
                    f"Cleaned balance sheet dataframe empty on {year}Q{season}"
                )
                continue

            file_cnt += 1
            if file_cnt == self.BATCH_SLEEP_EVERY_N_FILES:
                logger.info("Sleep 30 seconds...")
                file_cnt = 0
                time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
            else:
                delay: int = random.randint(
                    self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                )
                time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(
            dir_path=self.balance_sheet_dir,
            table_name=BALANCE_SHEET_TABLE_NAME,
            remove_files=False,
        )

        # 重新取得更新後的最新年度跟季度
        latest_year: Optional[int]
        latest_season: Optional[int]
        latest_year, latest_season = SQLiteUtils.get_max_secondary_value_by_primary(
            conn=self.conn,
            table_name=BALANCE_SHEET_TABLE_NAME,
            primary_col="year",
            secondary_col="season",
            default_primary_value=start_year,
            default_secondary_value=start_season,
        )
        logger.info(
            f"Balance sheet data updated. Latest available date: {latest_year}Q{latest_season}"
        )

    def update_comprehensive_income(
        self,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
    ) -> None:
        """Update Comprehensive Income"""

        logger.info("* Start Updating Comprehensive Income Data...")

        # Step 1: Crawl
        # 取得要開始更新的年度、季度
        start_year: int
        start_season: int
        start_year, start_season = self.get_actual_update_start_year_season(
            table_name=COMPREHENSIVE_INCOME_TABLE_NAME,
            default_year=start_year,
            default_season=start_season,
        )
        logger.info(f"Latest data date in database: {start_year}Q{start_season}")
        # Set Up Update Period
        # **不可用 years × seasons 的笛卡兒積**：起點 2024Q3、終點 2026Q4 時
        # `seasons` 只會是 [3, 4]，2025Q1／Q2 與 2026Q1／Q2 整整四季不會被爬，
        # 且不會有任何錯誤——它們只是從來沒出現在迴圈裡（健檢 F-054）
        year_seasons: List[Tuple[int, int]] = TimeUtils.generate_year_period_range(
            start_year, start_season, end_year, end_season, periods_per_year=4
        )
        file_cnt: int = 0

        for year, season in year_seasons:
            logger.info(f"* {year}Q{season}")
            df_list: Optional[List[pd.DataFrame]] = (
                self.crawler.crawl_comprehensive_income(year, season)
            )

            # Step 2: Clean
            if df_list is None or not df_list:
                continue

            cleaned_df: pd.DataFrame = self.cleaner.clean_comprehensive_income(
                df_list, year, season
            )

            if cleaned_df is None or cleaned_df.empty:
                logger.warning(
                    f"Cleaned comprehensive income dataframe empty on {year}Q{season}"
                )
                continue

            file_cnt += 1
            if file_cnt == self.BATCH_SLEEP_EVERY_N_FILES:
                logger.info("Sleep 30 seconds...")
                file_cnt = 0
                time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
            else:
                delay: int = random.randint(
                    self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                )
                time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(
            dir_path=self.comprehensive_income_dir,
            table_name=COMPREHENSIVE_INCOME_TABLE_NAME,
            remove_files=False,
        )

        # 重新取得更新後的最新年度跟季度
        latest_year: Optional[int]
        latest_season: Optional[int]
        latest_year, latest_season = SQLiteUtils.get_max_secondary_value_by_primary(
            conn=self.conn,
            table_name=COMPREHENSIVE_INCOME_TABLE_NAME,
            primary_col="year",
            secondary_col="season",
            default_primary_value=start_year,
            default_secondary_value=start_season,
        )
        logger.info(
            f"Comprehensive income data updated. Latest available date: {latest_year}Q{latest_season}"
        )

    def update_cash_flow(
        self,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
    ) -> None:
        """Update Cash Flow"""

        logger.info("* Start Updating Cash Flow Data...")

        # Step 1: Crawl
        # 取得要開始更新的年度、季度
        start_year: int
        start_season: int
        start_year, start_season = self.get_actual_update_start_year_season(
            table_name=CASH_FLOW_TABLE_NAME,
            default_year=start_year,
            default_season=start_season,
        )
        logger.info(f"Latest data date in database: {start_year}Q{start_season}")
        # Set Up Update Period
        # **不可用 years × seasons 的笛卡兒積**：起點 2024Q3、終點 2026Q4 時
        # `seasons` 只會是 [3, 4]，2025Q1／Q2 與 2026Q1／Q2 整整四季不會被爬，
        # 且不會有任何錯誤——它們只是從來沒出現在迴圈裡（健檢 F-054）
        year_seasons: List[Tuple[int, int]] = TimeUtils.generate_year_period_range(
            start_year, start_season, end_year, end_season, periods_per_year=4
        )
        file_cnt: int = 0

        for year, season in year_seasons:
            logger.info(f"* {year}Q{season}")
            df_list: Optional[List[pd.DataFrame]] = self.crawler.crawl_cash_flow(
                year, season
            )

            # Step 2: Clean
            if df_list is None or not df_list:
                continue

            cleaned_df: pd.DataFrame = self.cleaner.clean_cash_flow(
                df_list, year, season
            )

            if cleaned_df is None or cleaned_df.empty:
                logger.warning(f"Cleaned cash flow dataframe empty on {year}Q{season}")
                continue

            file_cnt += 1
            if file_cnt == self.BATCH_SLEEP_EVERY_N_FILES:
                logger.info("Sleep 30 seconds...")
                file_cnt = 0
                time.sleep(self.BATCH_SLEEP_DURATION_SECONDS)
            else:
                delay: int = random.randint(
                    self.BATCH_RANDOM_DELAY_MIN, self.BATCH_RANDOM_DELAY_MAX
                )
                time.sleep(delay)

        # Step 3: Load
        self.loader.add_to_db(
            dir_path=self.cash_flow_dir,
            table_name=CASH_FLOW_TABLE_NAME,
            remove_files=False,
        )

        # 重新取得更新後的最新年度跟季度
        latest_year: Optional[int]
        latest_season: Optional[int]
        latest_year, latest_season = SQLiteUtils.get_max_secondary_value_by_primary(
            conn=self.conn,
            table_name=CASH_FLOW_TABLE_NAME,
            primary_col="year",
            secondary_col="season",
            default_primary_value=start_year,
            default_secondary_value=start_season,
        )
        logger.info(
            f"Cash flow data updated. Latest available date: {latest_year}Q{latest_season}"
        )

    def update_equity_changes(
        self,
        start_year: int,
        end_year: int,
        start_season: int,
        end_season: int,
        stock_ids: Optional[List[str]] = None,
    ) -> None:
        """
        - Description:
            Update Equity Changes

            與其他三張報表不同，MOPS 的權益變動表端點是**逐檔查詢**，一個年季要打
            兩千多次請求。因此本方法不用 `get_actual_update_start_year_season()`
            決定起點——那是以「表內最新年季 +1」為準，一個年季爬到一半中斷時，
            該年季會被當成已完成而整季跳過，缺的公司永遠補不回來。
            改為逐年季查出「已入庫的 stock_id」，只補差集。
        - Parameters:
            - start_year / end_year / start_season / end_season: int
                更新區間
            - stock_ids: Optional[List[str]]
                要爬的股票清單；None 時取 `taiwan_stock_info` 的上市櫃股票
        """

        logger.info("* Start Updating Equity Changes Data...")

        target_stock_ids: List[str] = (
            stock_ids if stock_ids is not None else self.get_target_stock_ids()
        )

        if not target_stock_ids:
            logger.warning("No target stocks for equity changes, skipped")
            return

        # **不可用 years × seasons 的笛卡兒積**：起點 2024Q3、終點 2026Q4 時
        # `seasons` 只會是 [3, 4]，2025Q1／Q2 與 2026Q1／Q2 整整四季不會被爬，
        # 且不會有任何錯誤——它們只是從來沒出現在迴圈裡（健檢 F-054）
        year_seasons: List[Tuple[int, int]] = TimeUtils.generate_year_period_range(
            start_year, start_season, end_year, end_season, periods_per_year=4
        )

        unreachable_cnt: int = 0

        for year, season in year_seasons:
            # Step 1: 逐檔 resume——只補這個年季還沒入庫的公司
            crawled_stock_ids: Set[str] = self.get_crawled_stock_ids(year, season)
            pending_stock_ids: List[str] = [
                stock_id
                for stock_id in target_stock_ids
                if stock_id not in crawled_stock_ids
            ]

            if not pending_stock_ids:
                logger.info(f"* {year}Q{season} already complete, skipped")
                continue

            if not self.is_season_filed(year, season, crawled_stock_ids):
                logger.info(f"* {year}Q{season} not yet filed, skipped")
                continue

            logger.info(
                f"* {year}Q{season}: {len(pending_stock_ids)} stocks pending "
                f"({len(crawled_stock_ids)} already in database)"
            )
            unreachable_cnt += self.update_equity_changes_season(
                year=year, season=season, stock_ids=pending_stock_ids
            )

        if unreachable_cnt:
            # 站方過載造成的失敗不是「這檔沒資料」，下次重跑會自動補；但不講出來，
            # 就會變成「回補跑完了卻莫名少了幾百檔」
            logger.warning(
                f"Equity changes: {unreachable_cnt} requests unreachable after retries, "
                f"rerun to fill them"
            )

        # 重新取得更新後的最新年度跟季度
        latest_year: Optional[int]
        latest_season: Optional[int]
        latest_year, latest_season = SQLiteUtils.get_max_secondary_value_by_primary(
            conn=self.conn,
            table_name=EQUITY_CHANGE_TABLE_NAME,
            primary_col="year",
            secondary_col="season",
            default_primary_value=start_year,
            default_secondary_value=start_season,
        )
        logger.info(
            f"Equity changes data updated. Latest available date: {latest_year}Q{latest_season}"
        )

    def is_season_filed(
        self,
        year: int,
        season: int,
        crawled_stock_ids: Set[str],
    ) -> bool:
        """
        - Description:
            判斷該年季是否已申報，用來略過「還沒到申報期」的年季

            尚未申報的年季，每一檔都會是「查無資料」；不擋掉的話，每次日常更新都要
            為當季白打兩千次請求。

            **判斷依據是幾檔長期上市的權值股，不是「連續 N 檔查無資料」。**
            後者曾實際造成資料遺失：2026-08-22 的 2020Q1 回補跑到代號 6874 附近時，
            撞上一段「2020 年後才上市」的連續新股，被誤判成整季未申報而中止，
            **323 檔（含 9933 中鼎、9945 潤泰新等確定有資料的公司）從未被嘗試**。
            股票代號是排序過的，某個號段連續都是新股完全正常，拿它當全季的證據是錯的。
        - Parameters:
            - year / season: int
                要判斷的年季
            - crawled_stock_ids: Set[str]
                該年季已入庫的股票；非空即代表已申報，不必再打請求
        - Return:
            - bool
                是否已申報；暫時性失敗一律回 True（寧可多打請求，不可略過已申報的年季）
        """

        if crawled_stock_ids:
            return True

        for stock_id in self.EQUITY_CHANGE_PROBE_STOCK_IDS:
            df_list: Optional[List[pd.DataFrame]] = self.crawler.crawl_equity_changes(
                year, season, stock_id
            )

            # None 是站方過載，不是「沒有資料」，不能拿來證明整季未申報
            if df_list is None or df_list:
                return True

            time.sleep(
                random.uniform(
                    self.EQUITY_CHANGE_RANDOM_DELAY_MIN,
                    self.EQUITY_CHANGE_RANDOM_DELAY_MAX,
                )
            )

        return False

    def update_equity_changes_season(
        self,
        year: int,
        season: int,
        stock_ids: List[str],
    ) -> int:
        """逐檔爬取單一年季的權益變動表並分批入庫，回傳站方過載而失敗的次數"""

        cleaned_df_list: List[pd.DataFrame] = []
        unreachable_cnt: int = 0
        no_data_cnt: int = 0
        request_cnt: int = 0

        for stock_id in stock_ids:
            # Step 1: Crawl
            df_list: Optional[List[pd.DataFrame]] = self.crawler.crawl_equity_changes(
                year, season, stock_id
            )

            if df_list is None:
                unreachable_cnt += 1
            elif not df_list:
                # 該年季這檔沒有報表（多半是當時尚未上市）；本迴圈**不做任何早退**，
                # 見 update_equity_changes() 對「未申報年季」的處理
                no_data_cnt += 1
            else:
                # Step 2: Clean
                cleaned_df: pd.DataFrame = self.cleaner.clean_equity_changes(
                    df_list, year, season, stock_id
                )

                if cleaned_df is None or cleaned_df.empty:
                    logger.warning(
                        f"Cleaned equity changes dataframe empty on "
                        f"{stock_id} {year}Q{season}"
                    )
                else:
                    cleaned_df_list.append(cleaned_df)

            # Step 3: Load（分批入庫，中斷最多只損失最後一批）
            if len(cleaned_df_list) >= self.EQUITY_CHANGE_LOAD_BATCH_SIZE:
                self.load_equity_changes_batch(cleaned_df_list, year, season)
                cleaned_df_list = []

            request_cnt += 1
            if request_cnt % self.EQUITY_CHANGE_BATCH_SLEEP_EVERY_N_FILES == 0:
                logger.info(
                    f"Sleep {self.EQUITY_CHANGE_BATCH_SLEEP_DURATION_SECONDS} seconds..."
                )
                time.sleep(self.EQUITY_CHANGE_BATCH_SLEEP_DURATION_SECONDS)
            else:
                delay: float = random.uniform(
                    self.EQUITY_CHANGE_RANDOM_DELAY_MIN,
                    self.EQUITY_CHANGE_RANDOM_DELAY_MAX,
                )
                time.sleep(delay)

        # 收尾：把最後不滿一批的資料也寫進去
        if cleaned_df_list:
            self.load_equity_changes_batch(cleaned_df_list, year, season)

        logger.info(
            f"{year}Q{season} done: {request_cnt} requested, "
            f"{no_data_cnt} no data, {unreachable_cnt} unreachable"
        )

        return unreachable_cnt

    def load_equity_changes_batch(
        self,
        cleaned_df_list: List[pd.DataFrame],
        year: int,
        season: int,
    ) -> None:
        """把一批已清洗的權益變動表落地成 CSV 並入庫"""

        # 批次序號由 cleaner 依目錄現況決定，不在這裡累加——同一年季跑第二次時
        # 從 0 重數會蓋掉前一次的檔案（見 next_equity_changes_batch_index()）
        file_path: Optional[Path] = self.cleaner.save_equity_changes(
            df_list=cleaned_df_list,
            year=year,
            season=season,
        )

        if file_path is None:
            return

        self.loader.add_to_db(
            dir_path=self.equity_change_dir,
            table_name=EQUITY_CHANGE_TABLE_NAME,
            remove_files=False,
            only_files=[file_path],
        )

    def get_target_stock_ids(self) -> List[str]:
        """取得要逐檔爬取權益變動表的股票清單（上市櫃普通股，排除 ETF 與興櫃）"""

        query: str = f"""
        SELECT stock_id FROM {STOCK_INFO_TABLE_NAME}
        WHERE type IN ('twse', 'tpex')
          AND industry_category NOT LIKE '%ETF%'
          AND stock_id GLOB '[0-9][0-9][0-9][0-9]'
        ORDER BY stock_id
        """

        try:
            df: pd.DataFrame = pd.read_sql_query(query, self.conn)
        except Exception as e:
            logger.error(f"Failed to get target stocks for equity changes: {e}")
            return []

        return df["stock_id"].astype(str).tolist()

    def get_crawled_stock_ids(self, year: int, season: int) -> Set[str]:
        """取得指定年季已入庫的 stock_id，供逐檔爬取的中斷續跑使用"""

        if not SQLiteUtils.check_table_exist(
            conn=self.conn, table_name=EQUITY_CHANGE_TABLE_NAME
        ):
            return set()

        query: str = f"""
        SELECT DISTINCT stock_id FROM {EQUITY_CHANGE_TABLE_NAME}
        WHERE year = ? AND season = ?
        """

        try:
            df: pd.DataFrame = pd.read_sql_query(
                query, self.conn, params=(year, season)
            )
        except Exception as e:
            logger.error(f"Failed to get crawled stocks on {year}Q{season}: {e}")
            return set()

        return set(df["stock_id"].astype(str))

    def get_actual_update_start_year_season(
        self,
        table_name: str,
        default_year: int = 2025,
        default_season: int = 1,
    ) -> Tuple[int, int]:
        """回傳下一筆應更新的 (year, season)，若無資料則回傳預設值"""

        # Step 1: 先取得最新 year
        try:
            latest_year: Optional[int]
            latest_season: Optional[int]
            latest_year, latest_season = SQLiteUtils.get_max_secondary_value_by_primary(
                conn=self.conn,
                table_name=table_name,
                primary_col="year",
                secondary_col="season",
                default_primary_value=default_year,
                default_secondary_value=default_season,
            )
        except Exception as e:
            logger.error(f"Failed to get latest (year, season): {e}")
            return default_year, default_season

        # Step 2: 處理進位（第4季 → 第1季 + 年份進位）
        if latest_season == self.LAST_SEASON:
            return latest_year + 1, 1
        else:
            return latest_year, latest_season + 1
