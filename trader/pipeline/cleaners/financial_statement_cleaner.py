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
    FinancialStatementType,
    FileEncoding
)
from trader.config import (
    FINANCIAL_STATEMENT_PATH,
    DOWNLOADS_METADATA_DIR_PATH
)


class FinancialStatementCleaner(BaseDataCleaner):
    """ Cleaner for quarterly financial Statement """

    def __init__(self):
        super().__init__()

        # Raw column names for each report type
        self.balance_sheet_cols: List[str] = []
        self.comprehensive_income_cols: List[str] = []
        self.cash_flow_cols: List[str] = []
        self.equity_changes_cols: List[str] = []

        # Column mapping for each report type
        self.balance_sheet_column_map: Dict[str, List[str]] = {}
        self.comprehensive_income_map: Dict[str, List[str]] = {}
        self.cash_flow_map: Dict[str, List[str]] = {}
        self.equity_changes_map: Dict[str, List[str]] = {}

        # Output directories for each report
        self.fs_dir: Path = FINANCIAL_STATEMENT_PATH
        self.balance_sheet_dir: Path = self.fs_dir / "balance_sheet"
        self.comprehensive_income_dir: Path = self.fs_dir / "comprehensive_income"
        self.cash_flow_dir: Path = self.fs_dir / "cash_flow"
        self.equity_changes_dir: Path = self.fs_dir / "equity_changes"

        self.setup()


    def setup(self, *args, **kwargs) -> None:
        """ Set Up the Config of Cleaner """

        # Create Downloads Directory For Financial Reports
        self.fs_dir.mkdir(parents=True, exist_ok=True)
        self.balance_sheet_dir.mkdir(parents=True, exist_ok=True)
        self.comprehensive_income_dir.mkdir(parents=True, exist_ok=True)
        self.cash_flow_dir.mkdir(parents=True, exist_ok=True)
        self.equity_changes_dir.mkdir(parents=True, exist_ok=True)

        # Load Report Column Names & Map
        self.load_column_names()
        self.load_column_maps()


    def clean_balance_sheet(
        self,
        df_list: List[pd.DataFrame],
        year: int,
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
        self.balance_sheet_cols = [
            DataUtils.replace_column_name(
                self.clean_column_name(col),
                keywords,
                replacement
            )
            for col in self.balance_sheet_cols
        ]

        # 指定排序部分 Column Names
        front_cols: List[str] = ["年度", "季度", "公司代號", "公司名稱"]
        self.balance_sheet_cols = self.reorder_columns(self.balance_sheet_cols, front_cols)
        # 移除重複欄位，保留順序
        self.balance_sheet_cols = list(dict.fromkeys(self.balance_sheet_cols))

        # Step 2: 清理 df_list 欄位名稱
        # 建立涵蓋所有 columns 的 df
        new_df: pd.DataFrame = pd.DataFrame(columns=self.balance_sheet_cols)
        # 篩掉沒有 "公司名稱" 的 df
        df_list: List[pd.DataFrame] = [df for df in df_list if "公司名稱" in df.columns]

        # 清洗 Column Names
        cleaned_cols: List[str] = []
        cleaned_df_list: List[pd.DataFrame] = []
        for df in df_list:
            cleaned_cols = [
                DataUtils.replace_column_name(
                    self.clean_column_name(col),
                    keywords,
                    replacement
                )
                for col in df.columns
            ]
            df.columns = cleaned_cols
            cleaned_df_list.append(df)

        # Step 3: 將資料填入新建立的 new_df
        appended_df_list: List[pd.DataFrame] = []
        for df in cleaned_df_list:
            aligned_df: pd.DataFrame = df.reindex(columns=new_df.columns)
            aligned_df["年度"] = year
            aligned_df["季度"] = season
            appended_df_list.append(aligned_df)
        new_df = pd.concat(appended_df_list, ignore_index=True)

        # Step 4: 清洗特定 columns
        new_df = DataUtils.remove_columns_by_keywords(new_df, startswith=["Unname", "0"])

        new_df.to_csv(
            self.balance_sheet_dir / f"balance_sheet_{year}Q{season}.csv",
            index=False,
            encoding=FileEncoding.UTF8.value
        )

        return new_df


    def load_column_names(self) -> None:
        """ 載入 Report Column Names """

        attr_map: Dict[FinancialStatementType, str] = {
            FinancialStatementType.BALANCE_SHEET: "balance_sheet_cols",
            FinancialStatementType.COMPREHENSIVE_INCOME: "comprehensive_income_cols",
            FinancialStatementType.CASH_FLOW: "cash_flow_cols",
            FinancialStatementType.EQUITY_CHANGE: "equity_changes_cols",
        }

        for report_type, attr_name in attr_map.items():
            file_name = DOWNLOADS_METADATA_DIR_PATH / f"{report_type.value.lower()}_columns.json"

            if not file_name.exists():
                logger.warning(f"Metadata file not found: {file_name}")
                continue

            try:
                with open(file_name, "r", encoding=FileEncoding.UTF8.value) as f:
                    cols = json.load(f)

                if hasattr(self, attr_name):
                    setattr(self, attr_name, cols)
            except json.JSONDecodeError:
                logger.error(f"JSON 格式錯誤: {file_name}")


    def load_column_maps(self) -> None:
        """ 載入 Report Column Maps """

        attr_map: Dict[FinancialStatementType, str] = {
            FinancialStatementType.BALANCE_SHEET: "balance_sheet_map",
            FinancialStatementType.COMPREHENSIVE_INCOME: "comprehensive_income_map",
            FinancialStatementType.CASH_FLOW: "cash_flow_map",
            FinancialStatementType.EQUITY_CHANGE: "equity_changes_map",
        }

        for report_type, attr_name in attr_map.items():
            file_name = DOWNLOADS_METADATA_DIR_PATH / f"{report_type.value.lower()}_column_map.json"

            if not file_name.exists():
                logger.warning(f"Metadata file not found: {file_name}")
                continue

            try:
                with open(file_name, "r", encoding=FileEncoding.UTF8.value) as f:
                    col_map = json.load(f)

                if hasattr(self, attr_name):
                    setattr(self, attr_name, col_map)
            except json.JSONDecodeError:
                logger.error(f"JSON 格式錯誤: {file_name}")


    def clean_column_name(self, word: str) -> str:
        """ 清除空白與特殊符號（括號、全半形減號），標準化欄位名稱用 """

        word: str = str(word)
        word = re.sub(r"\s+", "", word)  # 清除所有空白（包含 tab, 換行, 全形空白）
        word = (
            word
            .replace("（", "(")                     # 全形左括號轉半形
            .replace("）", ")")                     # 全形右括號轉半形
            .replace("：", ":")                     # 全形冒號轉半形
        )

        # 移除所有減號與破折號（包含全形、半形、em dash、en dash、box drawing）
        dash_variants = ["－", "-", "—", "–", "─"]
        for dash in dash_variants:
            word = word.replace(dash, "")

        return word


    def reorder_columns(
        self,
        all_columns: List[str],
        front_columns: List[str]
    ) -> List[str]:
        """ 將指定欄位移到最前面，其餘保持原順序 """

        tail_columns = [col for col in all_columns if col not in front_columns]
        return front_columns + tail_columns

