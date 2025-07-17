import datetime
from io import StringIO
from loguru import logger
from pathlib import Path
from typing import List, Optional
import pandas as pd
import requests

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils import URLManager, DataType, MarketType, FileEncoding
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import MONTHLY_REVENUE_REPORT_PATH, MONTHLY_REVENUE_REPORT_META_DIR_PATH


class MonthlyRevenueReportCleaner(BaseDataCleaner):
    """TWSE & TPEX Monthly Revenue Report Crawler"""

    def __init__(self):
        super().__init__()

        # Raw and cleaned column names for monthly revenue report
        self.monthly_revenue_report_cols: List[str] = []
        self.monthly_revenue_report_cleaned_cols: List[str] = []

        # MMR Cleaned Columns Path
        self.monthly_revenue_report_cleaned_cols_path: Path = (
            MONTHLY_REVENUE_REPORT_META_DIR_PATH
            / f"{DataType.MRR.lower}_cleaned_columns"
        )

        # Downloads Directory
        self.mrr_dir: Path = MONTHLY_REVENUE_REPORT_PATH

        self.setup()


    def setup(self) -> None:
        """Set Up the Config of Cleaner"""

        # Create the tick downloads directory
        self.mrr_dir.mkdir(parents=True, exist_ok=True)

        # Load MMR Column Names
        self.load_all_column_name()

    def clean_monthly_revenue(
        self,
        df_list: List[pd.DataFrame],
        date: datetime.date
    ) -> pd.DataFrame:
        """Clean TWSE Monthly Revenue Report"""
        """
        資料格式
        上市: 102（2013）年前資料無區分國內外（目前先從 102 年開始爬）
        """

        new_df_list: List[pd.DataFrame] = []
        for df in df_list:
            if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
                df.columns = df.columns.droplevel(0)
                new_df_list.append(df)




    def load_all_column_name(self) -> None:
        """載入 MMR Column Names"""

        file_path: Path = self.mrr_dir / "monthly_revenue_report_all_columns.json"

        if not file_path.exists():
            logger.warning(f"Metadata file not found: {file_path}")
            return

        self.monthly_revenue_report_cols = DataUtils.load_json(file_path=file_path)