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
        self.load_all_column_names()


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

        # Step 1: 載入已清洗欄位，若未成功則執行清洗流程
        if not self.monthly_revenue_report_cleaned_cols:
            self.load_cleaned_column_names()
            if not self.monthly_revenue_report_cleaned_cols:
                pass

        # Step 2: 清理 df_list 欄位名稱 & 建立涵蓋所有 columns 的 df
        new_df_list: List[pd.DataFrame] = []
        for df in df_list:
            if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
                df.columns = df.columns.droplevel(0)
                new_df_list.append(df)


    def clean_mrr_column_names(
        self,
        raw_cols: List[str],
        front_cols: List[str]
    ) -> List[str]:
        """
        - Description:
            清洗 MRR 的 Column Names

        - Parameters:
            - raw_cols: List[str]
                原始欄位名稱清單
            - front_cols: List[str]
                優先排序欄位 (例如 year, month 等)
            - save_path: Path
                儲存清洗後欄位的 JSON 路徑

        - Returns:
            - cleaned_cols: List[str]
                已清洗、排序、去重後的欄位名稱清單
        """

        # Step 1: 清洗欄位
        cleaned_cols: List[str] = [
            DataUtils.standardize_column_name(word=col)
            for col in raw_cols
        ]

        # Step 2: 移除不必要欄位
        cleaned_cols = DataUtils.remove_items_by_keywords(
            cleaned_cols, startswith=["因自102年1月起適用IFRSs申報月合併營收，故無101年12月合併營收之申報資料。", "備註"]
        )

        # Step 3: 欄位排序
        tail_columns: List[str] = [
            col for col in cleaned_cols if col not in front_cols
        ]
        cleaned_cols = front_cols + tail_columns

        # Step 4: 去除重複欄位（保留順序）
        cleaned_cols = list(dict.fromkeys(cleaned_cols))

        # Step 5: 儲存清洗結果
        DataUtils.save_json(data=cleaned_cols, file_path=self.monthly_revenue_report_cleaned_cols_path)
        logger.info(f"已儲存清洗後欄位名稱: {self.monthly_revenue_report_cleaned_cols_path.name}")



    def load_all_column_names(self) -> None:
        """載入 MMR Column Names"""

        file_path: Path = self.mrr_dir / f"{DataType.MRR.lower()}_all_columns.json"

        if not file_path.exists():
            logger.warning(f"Metadata file not found: {file_path}")
            return

        self.monthly_revenue_report_cols = DataUtils.load_json(file_path=file_path)


    def load_cleaned_column_names(self) -> None:
        """載入已清洗過的 MMR Column Names"""

        cleaned_cols: List[str] = []
        file_path: Path = self.mrr_dir / f"{DataType.MRR.lower()}_cleaned_columns.json"

        if not file_path.exists():
            logger.warning(f"Metadata file not found: {file_path}")
            return

        self.monthly_revenue_report_cleaned_cols = DataUtils.load_json(file_path=file_path)