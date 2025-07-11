import datetime
import pandas as pd
import re
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
        # 清理欄位名稱
        keywords: List[str] = ["總計", "合計"]
        replacement: str = "總額"

        # Step 1: 處理 .json Column Names
        # 指定排序部分 Column Names
        self.all_balance_sheet_cols = [
            DataUtils.replace_column_name(
                self.clean_column_name(col),
                keywords,
                replacement
            )
            for col in self.all_balance_sheet_cols
        ]

        front_cols: List[str] = ["年度", "季度", "公司代號", "公司名稱"]
        self.all_balance_sheet_cols = self.reorder_columns(self.all_balance_sheet_cols, front_cols)



        # Step 2: 清理 df_list 欄位名稱
        # 篩掉沒有 "公司名稱" 的 df
        df_list: List[pd.DataFrame] = [df for df in df_list if "公司名稱" in df.columns]
        # 清洗 Column Names
        for df in df_list:
            cleaned_cols: List[str] = []
            for col in df.columns:
                new_col: str = self.clean_column_name(col)
                new_col = DataUtils.replace_column_name(new_col, keywords, replacement)
                cleaned_cols.append(new_col)
            df.columns = cleaned_cols



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


    def clean_column_name(self, word: str) -> str:
        """ 清除空白與特殊符號（括號、全形減號），標準化欄位名稱用 """

        word = re.sub(r"\s+", "", word)  # 清除所有空白（包含 tab, 換行, 全形空白）
        word = (
            word
            .replace("（", "(")                     # 全形左括號轉半形
            .replace("）", ")")                     # 全形右括號轉半形
            .replace("－", "")                      # 刪除全形減號
        )
        return word


    def reorder_columns(
        self,
        all_columns: List[str],
        front_columns: List[str]
    ) -> List[str]:
        """ 將指定欄位移到最前面，其餘保持原順序 """

        tail_columns = [col for col in all_columns if col not in front_columns]
        return front_columns + tail_columns

