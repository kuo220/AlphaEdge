import datetime
import pandas as pd
import requests
from io import StringIO
import json
from pathlib import Path
from loguru import logger
from typing import List, Dict, Optional

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.crawlers.utils.payload import Payload
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils import (
    URLManager,
    MarketType,
    FinancialStatementType
)
from trader.config import (
    FINANCIAL_STATEMENT_PATH,
    DOWNLOADS_METADATA_DIR_PATH
)


class FinancialStatementCleaner(BaseDataCleaner):
    """ Cleaner for quarterly financial Statement """

    def __init__(self):
        super().__init__()

        # All Columns of Reports
        self.all_balance_sheet_cols: List[str] = []
        self.all_comprehensive_income_cols: List[str] = []
        self.all_cash_flow_cols: List[str] = []
        self.all_equity_changes_cols: List[str] = []

        # Financial Statement Directories Set Up
        self.fs_dir: Path = FINANCIAL_STATEMENT_PATH
        self.balance_sheet_dir: Path = self.fs_dir / "balance_sheet"
        self.comprehensive_income_dir: Path = self.fs_dir / "comprehensive_income"
        self.cash_flow_dir: Path = self.fs_dir / "cash_flow"
        self.equity_changes_dir: Path = self.fs_dir / "equity_changes"


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Cleaner """

        # Create Downloads Directory For Financial Reports
        self.fs_dir.mkdir(parents=True, exist_ok=True)
        self.balance_sheet_dir.mkdir(parents=True, exist_ok=True)
        self.comprehensive_income_dir.mkdir(parents=True, exist_ok=True)
        self.cash_flow_dir.mkdir(parents=True, exist_ok=True)
        self.equity_changes_dir.mkdir(parents=True, exist_ok=True)

        # Load Report Column Names
        self.load_column_names()


    def clean_balance_sheet(
        self,
        df_list: List[pd.DataFrame],
        date: datetime.date,
        season: int
    ) -> pd.DataFrame:
        """ Cleaner Balance Sheet (資產負債表) """
        """
        資料區間（但是只有 102 年以後才可以爬）
        上市: 民國 78 (1989) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        # Step 1: 清理欄位名稱
        for df in df_list:
            df.columns = (
                df.columns
                .map(str)
                .str.replace(r"\s+", "", regex=True)        # 刪除空白
                .str.replace("（", "(")                     # 全形左括號轉半形
                .str.replace("）", ")")                     # 全形右括號轉半形
                .str.replace("－", "")                      # 全形減號 → 刪除
            )

        df_list: List[pd.DataFrame] = [df for df in df_list if "公司名稱" in df.columns]


    def load_column_names(self) -> None:
        """ 載入 Report Column Names """

        attr_map: Dict[FinancialStatementType, str] = {
            FinancialStatementType.BALANCE_SHEET: "all_balance_sheet_cols",
            FinancialStatementType.COMPREHENSIVE_INCOME: "all_comprehensive_income_cols",
            FinancialStatementType.CASH_FLOW: "all_cash_flow_cols",
            FinancialStatementType.EQUITY_CHANGE: "all_equity_changes_cols",
        }

        for report_type, attr_name in attr_map.items():
            file_name = DOWNLOADS_METADATA_DIR_PATH / f"{report_type.value.lower()}_columns.json"

            with open(file_name, "r", encoding="big5") as f:
                cols = json.load(f)

            if not file_name.exists():
                logger.warning(f"Metadata file not found: {file_name}")
                continue

            setattr(self, attr_name, cols)