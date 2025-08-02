import datetime
from io import StringIO
from loguru import logger
from pathlib import Path
from typing import List, Dict, Optional
import pandas as pd
import requests

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.crawlers.utils.request_utils import RequestUtils
from trader.pipeline.utils import URLManager, DataType, MarketType, FileEncoding
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import (
    MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH,
    MONTHLY_REVENUE_REPORT_META_DIR_PATH,
)


class MonthlyRevenueReportCleaner(BaseDataCleaner):
    """TWSE & TPEX Monthly Revenue Report Crawler"""

    def __init__(self):
        super().__init__()

        # Raw and cleaned column names for monthly revenue report
        self.monthly_revenue_report_cols: List[str] = []
        self.monthly_revenue_report_cleaned_cols: List[str] = []
        self.monthly_revenue_report_col_map: Dict[str, List[str]] = {}

        # MMR Cleaned Columns Path
        self.monthly_revenue_report_cleaned_cols_path: Path = (
            MONTHLY_REVENUE_REPORT_META_DIR_PATH
            / f"{DataType.MRR.lower()}_cleaned_columns.json"
        )
        self.monthly_revenue_report_col_map_path: Path = (
            MONTHLY_REVENUE_REPORT_META_DIR_PATH
            / f"{DataType.MRR.lower()}_column_map.json"
        )

        # Output Directory
        self.mrr_dir: Path = MONTHLY_REVENUE_REPORT_DOWNLOADS_PATH

        # Clean Set Up
        self.removed_cols: List[str] = [
            "因自102年1月起適用IFRSs申報月合併營收，故無101年12月合併營收之申報資料。",
            "備註",
        ]

        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Cleaner"""

        # Create the downloads directory
        self.mrr_dir.mkdir(parents=True, exist_ok=True)

        # Load MMR Column Names
        self.load_all_column_names()
        self.load_column_maps()

    def clean_monthly_revenue(
        self,
        df_list: List[pd.DataFrame],
        year: int,
        month: int,
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
                self.monthly_revenue_report_cleaned_cols = self.clean_mrr_column_names(
                    raw_cols=self.monthly_revenue_report_cols,
                    front_cols=["year", "month"],
                )

        # Step 2: 清理 df_list 欄位名稱
        # 建立涵蓋所有 columns 的 df
        new_df: pd.DataFrame = pd.DataFrame(
            columns=self.monthly_revenue_report_cleaned_cols
        )
        # 將 df 的 MultiIndex 降為一層
        new_df_list: List[pd.DataFrame] = []
        for df in df_list:
            if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
                df.columns = df.columns.droplevel(0)
                new_df_list.append(df)
        # 篩掉沒有 "公司名稱" 的 df
        required_cols: List[str] = ["公司名稱"]
        new_df_list = [
            df
            for df in new_df_list
            if DataUtils.check_required_columns(df=df, required_cols=required_cols)
        ]

        # 清洗 df Column Names
        appended_df_list: List[pd.DataFrame] = []
        for df in new_df_list:
            cleaned_cols: List[str] = [
                DataUtils.map_column_name(
                    DataUtils.standardize_column_name(col),
                    self.monthly_revenue_report_col_map,
                )
                for col in df.columns
            ]
            df.columns = cleaned_cols
            DataUtils.remove_cols_by_keywords(df, startswith=self.removed_cols)

            # 對齊欄位並補上欄位
            aligned_df: pd.DataFrame = df.reindex(columns=new_df.columns)
            aligned_df["year"] = year
            aligned_df["month"] = month
            appended_df_list.append(aligned_df)

        new_df = (
            pd.concat(appended_df_list, ignore_index=True)
            .astype(str)
            .loc[
                lambda df: ~df["stock_id"].str.contains("合計", na=False)
            ]  # 過濾掉那些包含「合計」的 row
            .pipe(
                DataUtils.convert_col_to_numeric, exclude_cols=["stock_id", "公司名稱"]
            )
        )

        # 修正 Big5 編碼無法表示「碁」字導致的亂碼（� 或 ��），補回正確字元
        new_df["公司名稱"] = new_df["公司名稱"].apply(self.fix_broken_char)

        # 根據指定 columns 移除重複的 rows
        df = df.drop_duplicates(
            subset=["year", "month", "stock_id", "公司名稱"],  # 根據這四個欄位判斷重複
            keep="first",  # 保留第一筆（預設值，也可以省略）
        ).reset_index(
            drop=True
        )  # 重排 index，避免 index 跳號

        new_df.to_csv(
            self.mrr_dir / f"{DataType.MRR.lower()}_{year}_{month}.csv",
            index=False,
            encoding=FileEncoding.UTF8.value,
        )

        return new_df

    def clean_mrr_column_names(
        self,
        raw_cols: List[str],
        front_cols: List[str],
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

        # Step 1: 欄位排序
        tail_columns: List[str] = [col for col in raw_cols if col not in front_cols]
        cleaned_cols = front_cols + tail_columns

        # Step 2: 移除不必要欄位
        cleaned_cols = DataUtils.remove_items_by_keywords(
            cleaned_cols, startswith=self.removed_cols
        )

        # Step 3: 清洗欄位
        cleaned_cols: List[str] = [
            DataUtils.map_column_name(
                DataUtils.standardize_column_name(word=col),
                self.monthly_revenue_report_col_map,
            )
            for col in cleaned_cols
        ]

        # Step 4: 去除重複欄位（保留順序）
        cleaned_cols = list(dict.fromkeys(cleaned_cols))

        # Step 5: 儲存清洗結果
        DataUtils.save_json(
            data=cleaned_cols, file_path=self.monthly_revenue_report_cleaned_cols_path
        )
        logger.info(
            f"已儲存清洗後欄位名稱: {self.monthly_revenue_report_cleaned_cols_path.name}"
        )

        return cleaned_cols

    def load_all_column_names(self) -> None:
        """載入 MMR Column Names"""

        file_path: Path = (
            MONTHLY_REVENUE_REPORT_META_DIR_PATH
            / f"{DataType.MRR.lower()}_all_columns.json"
        )

        if not file_path.exists():
            logger.warning(f"Metadata file not found: {file_path}")
            return

        self.monthly_revenue_report_cols = DataUtils.load_json(file_path=file_path)

    def load_cleaned_column_names(self) -> None:
        """載入已清洗過的 MMR Column Names"""

        if not self.monthly_revenue_report_cleaned_cols_path.exists():
            logger.warning(
                f"Metadata file not found: {self.monthly_revenue_report_cleaned_cols_path}"
            )
            return

        self.monthly_revenue_report_cleaned_cols = DataUtils.load_json(
            file_path=self.monthly_revenue_report_cleaned_cols_path
        )

    def load_column_maps(self) -> None:
        """載入 MRR Column Maps"""

        if not self.monthly_revenue_report_col_map_path.exists():
            logger.warning(
                f"Metadata file not found: {self.monthly_revenue_report_col_map_path}"
            )
            return

        self.monthly_revenue_report_col_map = DataUtils.load_json(
            self.monthly_revenue_report_col_map_path
        )

    def fix_broken_char(self, text: str) -> str:
        """將亂碼 � 或 �� 統一修正為 `碁`"""

        if isinstance(text, str):
            return text.replace("��", "碁").replace("�", "碁")
        return text
