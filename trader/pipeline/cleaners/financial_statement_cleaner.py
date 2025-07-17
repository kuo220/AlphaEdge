import re
import pandas as pd
from pathlib import Path
from loguru import logger
from typing import List, Dict

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.utils.data_utils import DataUtils
from trader.pipeline.utils import FinancialStatementType, FileEncoding
from trader.config import FINANCIAL_STATEMENT_PATH, FINANCIAL_STATEMENT_META_DIR_PATH


class FinancialStatementCleaner(BaseDataCleaner):
    """Cleaner for quarterly financial Statement"""

    def __init__(self):
        super().__init__()

        # Raw column names for each report type (Load from .json)
        self.balance_sheet_cols: List[str] = []
        self.balance_sheet_cleaned_cols: List[str] = []
        self.comprehensive_income_cols: List[str] = []
        self.comprehensive_income_cleaned_cols: List[str] = []
        self.cash_flow_cols: List[str] = []
        self.cash_flow_cleaned_cols: List[str] = []
        self.equity_change_cols: List[str] = []
        self.equity_change_cleaned_cols: List[str] = []

        # Column mapping for each report type (Load from .json)
        self.balance_sheet_col_map: Dict[str, List[str]] = {}
        self.comprehensive_income_col_map: Dict[str, List[str]] = {}
        self.cash_flow_col_map: Dict[str, List[str]] = {}
        self.equity_change_col_map: Dict[str, List[str]] = {}

        # Reports Cleaned Columns Path
        self.balance_sheet_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.BALANCE_SHEET.lower()
            / f"{FinancialStatementType.BALANCE_SHEET.lower()}_cleaned_columns.json"
        )
        self.comprehensive_income_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.COMPREHENSIVE_INCOME.lower()
            / f"{FinancialStatementType.COMPREHENSIVE_INCOME.lower()}_cleaned_columns.json"
        )
        self.cash_flow_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.CASH_FLOW.lower()
            / f"{FinancialStatementType.CASH_FLOW.lower()}_cleaned_columns.json"
        )
        self.equity_change_cleaned_cols_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / FinancialStatementType.EQUITY_CHANGE.lower()
            / f"{FinancialStatementType.EQUITY_CHANGE.lower()}_cleaned_columns.json"
        )

        # Output directories for each report
        self.fs_dir: Path = FINANCIAL_STATEMENT_PATH
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

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Cleaner"""

        # Create Downloads Directory For Financial Reports
        self.fs_dir.mkdir(parents=True, exist_ok=True)
        self.balance_sheet_dir.mkdir(parents=True, exist_ok=True)
        self.comprehensive_income_dir.mkdir(parents=True, exist_ok=True)
        self.cash_flow_dir.mkdir(parents=True, exist_ok=True)
        self.equity_change_dir.mkdir(parents=True, exist_ok=True)

        # Load Report Column Names & Map
        self.load_all_column_names()
        self.load_column_maps()

    def clean_balance_sheet(
        self, df_list: List[pd.DataFrame], year: int, season: int
    ) -> pd.DataFrame:
        """Clean Balance Sheet (資產負債表)"""
        """
        資料區間（但是只有 102 年以後才可以爬）
        上市: 民國 78 (1989) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        # Step 1: 載入已清洗欄位，若未成功則執行清洗流程
        if not self.balance_sheet_cleaned_cols:
            self.load_cleaned_column_names(
                report_type=FinancialStatementType.BALANCE_SHEET
            )
            if not self.balance_sheet_cleaned_cols:
                self.clean_report_column_names(
                    raw_cols=self.balance_sheet_cols,
                    col_map=self.balance_sheet_col_map,
                    front_cols=["year", "season", "公司代號", "公司名稱"],
                    save_path=self.balance_sheet_cleaned_cols_path,
                )

        # Step 2: 清理 df_list 欄位名稱
        # 建立涵蓋所有 columns 的 df
        new_df: pd.DataFrame = pd.DataFrame(columns=self.balance_sheet_cleaned_cols)
        # 篩掉沒有 "公司名稱" 的 df
        required_cols: List[str] = ["公司名稱"]
        df_list: List[pd.DataFrame] = [
            df
            for df in df_list
            if DataUtils.check_required_columns(df=df, required_cols=required_cols)
        ]
        appended_df_list: List[pd.DataFrame] = []

        for df in df_list:
            # 清洗 df Column Names
            cleaned_cols = [
                self.map_column_name(
                    DataUtils.standardize_column_name(col), self.balance_sheet_col_map
                )
                for col in df.columns
            ]
            df.columns = cleaned_cols
            DataUtils.remove_cols_by_keywords(df, startswith=["Unnamed", "0"])

            # 對齊欄位並補上欄位
            aligned_df: pd.DataFrame = df.reindex(columns=new_df.columns)
            aligned_df["year"] = year
            aligned_df["season"] = season
            appended_df_list.append(aligned_df)

        new_df = (
            pd.concat(appended_df_list, ignore_index=True)
            .astype(str)
            .rename(columns={"公司代號": "股票代號"})
            .pipe(
                DataUtils.convert_col_to_numeric, exclude_cols=["股票代號", "公司名稱"]
            )
        )

        new_df.to_csv(
            self.balance_sheet_dir / f"balance_sheet_{year}Q{season}.csv",
            index=False,
            encoding=FileEncoding.UTF8.value,
        )

        return new_df

    def clean_comprehensive_income(
        self, df_list: List[pd.DataFrame], year: int, season: int
    ) -> pd.DataFrame:
        """Clean Statement of Comprehensive Income (綜合損益表)"""
        """
        資料區間（但是只有 102 年以後才可以爬）
        上市: 民國 77 (1988) 年 ~ present
        上櫃: 民國 82 (1993) 年 ~ present
        """

        # Step 1: 載入已清洗欄位，若未成功則執行清洗流程
        if not self.comprehensive_income_cleaned_cols:
            self.load_cleaned_column_names(
                report_type=FinancialStatementType.COMPREHENSIVE_INCOME
            )
            if not self.comprehensive_income_cleaned_cols:
                self.clean_report_column_names(
                    raw_cols=self.comprehensive_income_cols,
                    col_map=self.comprehensive_income_col_map,
                    front_cols=["year", "season", "公司代號", "公司名稱"],
                    save_path=self.comprehensive_income_cleaned_cols_path,
                )

        # Step 2: 清理 df_list 欄位名稱
        # 建立涵蓋所有 columns 的 df
        new_df: pd.DataFrame = pd.DataFrame(
            columns=self.comprehensive_income_cleaned_cols
        )
        # 篩掉沒有 "公司名稱" 的 df
        required_cols: List[str] = ["公司名稱"]
        df_list: List[pd.DataFrame] = [
            df
            for df in df_list
            if DataUtils.check_required_columns(df=df, required_cols=required_cols)
        ]
        appended_df_list: List[pd.DataFrame] = []

        for df in df_list:
            # 清洗 df Column Names
            cleaned_cols = [
                self.map_column_name(
                    DataUtils.standardize_column_name(col),
                    self.comprehensive_income_col_map,
                )
                for col in df.columns
            ]
            df.columns = cleaned_cols
            DataUtils.remove_cols_by_keywords(df, startswith=["0"])

            aligned_df: pd.DataFrame = df.reindex(columns=new_df.columns)
            aligned_df["year"] = year
            aligned_df["season"] = season
            appended_df_list.append(aligned_df)

        new_df = (
            pd.concat(appended_df_list, ignore_index=True)
            .astype(str)
            .rename(columns={"公司代號": "股票代號"})
            .pipe(
                DataUtils.convert_col_to_numeric, exclude_cols=["股票代號", "公司名稱"]
            )
        )

        new_df.to_csv(
            self.comprehensive_income_dir / f"comprehensive_income_{year}Q{season}.csv",
            index=False,
            encoding=FileEncoding.UTF8.value,
        )

        return new_df

    def clean_cash_flow(
        self, df_list: List[pd.DataFrame], year: int, season: int
    ) -> pd.DataFrame:
        """Clean Cash flow Statement (現金流量表)"""
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """

        # Step 1: 載入已清洗欄位，若未成功則執行清洗流程
        if not self.cash_flow_cleaned_cols:
            self.load_cleaned_column_names(report_type=FinancialStatementType.CASH_FLOW)
            if not self.cash_flow_cleaned_cols:
                self.clean_report_column_names(
                    raw_cols=self.cash_flow_cols,
                    col_map=self.cash_flow_col_map,
                    front_cols=["year", "season", "公司代號", "公司名稱"],
                    save_path=self.cash_flow_cleaned_cols_path,
                )

        # Step 2: 清理 df_list 欄位名稱
        # 建立涵蓋所有 columns 的 df
        new_df: pd.DataFrame = pd.DataFrame(columns=self.cash_flow_cleaned_cols)
        # 篩掉沒有 "公司名稱" 的 df
        required_cols: List[str] = ["公司名稱"]
        df_list: List[pd.DataFrame] = [
            df
            for df in df_list
            if DataUtils.check_required_columns(df=df, required_cols=required_cols)
        ]
        appended_df_list: List[pd.DataFrame] = []

        for df in df_list:
            # 清洗 df Column Names
            cleaned_cols = [
                self.map_column_name(
                    DataUtils.standardize_column_name(col), self.cash_flow_col_map
                )
                for col in df.columns
            ]
            df.columns = cleaned_cols
            DataUtils.remove_cols_by_keywords(df, startswith=["0"])

            aligned_df: pd.DataFrame = df.reindex(columns=new_df.columns)
            aligned_df["year"] = year
            aligned_df["season"] = season
            appended_df_list.append(aligned_df)

        new_df = (
            pd.concat(appended_df_list, ignore_index=True)
            .astype(str)
            .rename(columns={"公司代號": "股票代號"})
            .pipe(
                DataUtils.convert_col_to_numeric, exclude_cols=["股票代號", "公司名稱"]
            )
        )

        new_df.to_csv(
            self.cash_flow_dir / f"cash_flow_{year}Q{season}.csv",
            index=False,
            encoding=FileEncoding.UTF8.value,
        )

        return new_df

    def clean_equity_changes(self) -> pd.DataFrame:
        """Clean Statement of Changes in Equity (權益變動表)"""
        """
        資料區間
        上市: 民國 102 (2013) 年 ~ present
        上櫃: 民國 102 (2013) 年 ~ present
        """
        pass

    def clean_report_column_names(
        self,
        raw_cols: List[str],
        col_map: Dict[str, List[str]],
        front_cols: List[str],
        save_path: Path,
    ) -> List[str]:
        """
        - Description:
            清洗指定的 Report Column Names

        - Parameters:
            - raw_cols: List[str]
                原始欄位名稱清單
            - col_map: Dict[str, List[str]]
                欄位對應映射表 (舊名對應標準名)
            - front_cols: List[str]
                優先排序欄位 (例如 year, season 等)
            - save_path: Path
                儲存清洗後欄位的 JSON 路徑

        - Returns:
            - cleaned_cols: List[str]
                已清洗、排序、去重後的欄位名稱清單
        """

        # Step 1: 清洗欄位並做名稱對應
        cleaned_cols: List[str] = [
            self.map_column_name(DataUtils.standardize_column_name(word=col), col_map)
            for col in raw_cols
        ]

        # Step 2: 移除不必要欄位
        cleaned_cols = DataUtils.remove_items_by_keywords(
            cleaned_cols, startswith=["Unnamed", "0"]
        )

        # Step 3: 欄位排序
        cleaned_cols = self.reorder_columns(cleaned_cols, front_cols)

        # Step 4: 去除重複欄位（保留順序）
        cleaned_cols = list(dict.fromkeys(cleaned_cols))

        # Step 5: 儲存清洗結果
        DataUtils.save_json(data=cleaned_cols, file_path=save_path)
        logger.info(f"已儲存清洗後欄位名稱: {save_path.name}")

        return cleaned_cols

    def load_all_column_names(self) -> None:
        """載入 Report Column Names"""

        attr_map: Dict[FinancialStatementType, str] = {
            FinancialStatementType.BALANCE_SHEET: f"{FinancialStatementType.BALANCE_SHEET.lower()}_cols",
            FinancialStatementType.COMPREHENSIVE_INCOME: f"{FinancialStatementType.COMPREHENSIVE_INCOME.lower()}_cols",
            FinancialStatementType.CASH_FLOW: f"{FinancialStatementType.CASH_FLOW.lower()}_cols",
            FinancialStatementType.EQUITY_CHANGE: f"{FinancialStatementType.EQUITY_CHANGE.lower()}_cols",
        }

        for report_type, attr_name in attr_map.items():
            file_path: Path = (
                FINANCIAL_STATEMENT_META_DIR_PATH
                / report_type.lower()
                / f"{report_type.lower()}_all_columns.json"
            )

            if not file_path.exists():
                logger.warning(f"Metadata file not found: {file_path}")
                continue

            cols: List[str] = DataUtils.load_json(file_path=file_path)

            if hasattr(self, attr_name):
                setattr(self, attr_name, cols)

    def load_cleaned_column_names(
        self, report_type: FinancialStatementType
    ) -> List[str]:
        """根據報表類型載入已清洗過的 Column Names"""

        cleaned_cols: List[str] = []
        attr_name: str = f"{report_type.lower()}_cleaned_cols"
        file_path: Path = (
            FINANCIAL_STATEMENT_META_DIR_PATH
            / report_type.lower()
            / f"{report_type.lower()}_cleaned_columns.json"
        )

        if file_path.exists():
            cleaned_cols = DataUtils.load_json(file_path=file_path)
            if hasattr(self, attr_name):
                setattr(self, attr_name, cleaned_cols)

        return cleaned_cols

    def load_column_maps(self) -> None:
        """載入 Report Column Maps"""

        attr_map: Dict[FinancialStatementType, str] = {
            FinancialStatementType.BALANCE_SHEET: f"{FinancialStatementType.BALANCE_SHEET.lower()}_col_map",
            FinancialStatementType.COMPREHENSIVE_INCOME: f"{FinancialStatementType.COMPREHENSIVE_INCOME.lower()}_col_map",
            FinancialStatementType.CASH_FLOW: f"{FinancialStatementType.CASH_FLOW.lower()}_col_map",
            FinancialStatementType.EQUITY_CHANGE: f"{FinancialStatementType.EQUITY_CHANGE.lower()}_col_map",
        }

        for report_type, attr_name in attr_map.items():
            file_path: Path = (
                FINANCIAL_STATEMENT_META_DIR_PATH
                / report_type.lower()
                / f"{report_type.lower()}_column_map.json"
            )

            if not file_path.exists():
                logger.warning(f"Metadata file not found: {file_path}")
                continue

            col_map: Dict[str, List[str]] = DataUtils.load_json(file_path=file_path)

            if hasattr(self, attr_name):
                setattr(self, attr_name, col_map)

    def reorder_columns(
        self, all_columns: List[str], front_columns: List[str]
    ) -> List[str]:
        """將指定欄位移到最前面，其餘保持原順序"""

        tail_columns: List[str] = [
            col for col in all_columns if col not in front_columns
        ]
        return front_columns + tail_columns

    def map_column_name(self, col: str, column_map: Dict[str, List[str]]) -> str:
        """將欄位名稱對應至標準名稱，若無對應則回傳原名"""

        for std_col, variants in column_map.items():
            if col in variants:
                return std_col
        return col
