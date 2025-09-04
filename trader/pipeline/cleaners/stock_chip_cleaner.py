import datetime
from pathlib import Path
from typing import List

import pandas as pd

from trader.config import CHIP_DOWNLOADS_PATH
from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils


class StockChipCleaner(BaseDataCleaner):
    """Stock Chip Cleaner (Transform)"""

    def __init__(self):
        super().__init__()

        # Chip DataFrame Cleaned Columns
        self.chip_cleaned_cols: List[str] = None

        # The date that TWSE chip data format was reformed
        self.twse_first_reform_date: datetime.date = datetime.date(2014, 12, 1)
        self.twse_second_reform_date: datetime.date = datetime.date(2017, 12, 18)

        # The date that TPEX chip data format was reformed
        self.tpex_first_reform_date: datetime.date = datetime.date(2014, 12, 1)
        self.tpex_second_reform_date: datetime.date = datetime.date(2018, 1, 15)

        # Downloads directory Path
        self.chip_dir: Path = CHIP_DOWNLOADS_PATH

        # Set Up
        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Cleaner"""

        # Set Up Chip DataFrame Cleaned Columns
        self.chip_cleaned_cols = [
            "date",
            "stock_id",
            "證券名稱",
            "外資買進股數",
            "外資賣出股數",
            "外資買賣超股數",
            "投信買進股數",
            "投信賣出股數",
            "投信買賣超股數",
            "自營商買進股數(自行買賣)",
            "自營商賣出股數(自行買賣)",
            "自營商買賣超股數(自行買賣)",
            "自營商買進股數(避險)",
            "自營商賣出股數(避險)",
            "自營商買賣超股數(避險)",
            "自營商買進股數",
            "自營商賣出股數",
            "自營商買賣超股數",
            "三大法人買賣超股數",
        ]

        # Generate downloads directory
        self.chip_dir.mkdir(parents=True, exist_ok=True)

    def clean_twse_chip(
        self,
        df: pd.DataFrame,
        date: datetime.date,
    ) -> pd.DataFrame:
        """Clean TWSE Stock Chip Data"""

        if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
            df.columns = df.columns.droplevel(0)

        # 先處理 raw df
        df.columns = [DataUtils.standardize_column_name(col) for col in df.columns]
        df.insert(0, "date", date)
        df = df.rename(columns={"證券代號": "stock_id"})
        # 合併自營商自行買賣與避險欄位
        df["自營商買進股數"] = df.get("自營商買進股數(自行買賣)", 0) + df.get(
            "自營商買進股數(避險)", 0
        )
        df["自營商賣出股數"] = df.get("自營商賣出股數(自行買賣)", 0) + df.get(
            "自營商賣出股數(避險)", 0
        )

        # 第二次格式改制前
        if date < self.twse_second_reform_date:
            aligned_df: pd.DataFrame = df.reindex(
                columns=self.chip_cleaned_cols, fill_value=0
            )

        # 第二次格式改制後
        elif date >= self.twse_second_reform_date:
            df["外資買進股數"] = df.get("外陸資買進股數(不含外資自營商)", 0) + df.get(
                "外資自營商買進股數", 0
            )
            df["外資賣出股數"] = df.get("外陸資賣出股數(不含外資自營商)", 0) + df.get(
                "外資自營商賣出股數", 0
            )
            df["外資買賣超股數"] = df.get(
                "外陸資買賣超股數(不含外資自營商)", 0
            ) + df.get("外資自營商買賣超股數", 0)
            aligned_df: pd.DataFrame = df.reindex(
                columns=self.chip_cleaned_cols, fill_value=0
            )

        aligned_df = DataUtils.convert_col_to_numeric(
            aligned_df, exclude_cols=["date", "stock_id", "證券名稱"]
        )
        aligned_df = DataUtils.fill_nan(aligned_df, 0)

        # 根據指定 columns 移除重複的 rows
        aligned_df = DataUtils.remove_duplicate_rows(
            df=aligned_df,
            subset=["date", "stock_id", "證券名稱"],
            keep="first",
        )

        # Save df to csv file
        aligned_df.to_csv(
            self.chip_dir / f"twse_{TimeUtils.format_date(date)}.csv",
            index=False,
        )

        return aligned_df

    def clean_tpex_chip(
        self,
        df: pd.DataFrame,
        date: datetime.date,
    ) -> pd.DataFrame:
        """Clean TPEX Stock Chip Data"""

        if isinstance(df.columns, pd.MultiIndex) and df.columns.nlevels > 1:
            df.columns = df.columns.droplevel(0)

        # Remove last row
        df = DataUtils.remove_last_n_rows(df, n_rows=1)

        # date < 第一次格式改制（2014/12/1）
        if date < self.tpex_first_reform_date:
            df.columns = [DataUtils.standardize_column_name(col) for col in df.columns]
            old_col_name: List[str] = list(df.columns)
            new_col_name: List[str] = [
                "stock_id",
                "證券名稱",
                "外資買進股數",
                "外資賣出股數",
                "外資買賣超股數",
                "投信買進股數",
                "投信賣出股數",
                "投信買賣超股數",
                "自營商買進股數",
                "自營商賣出股數",
                "自營商買賣超股數",
            ]
            rename_map = dict(zip(old_col_name, new_col_name))
            df = df.rename(columns=rename_map)
            df.insert(0, "date", date)
            df["三大法人買賣超股數"] = (
                df.get("外資買賣超股數", 0)
                + df.get("投信買賣超股數", 0)
                + df.get("自營商買賣超股數", 0)
            )

        # 第一次格式改制 <= date < 第二次格式改制（2018/1/15）
        elif self.tpex_first_reform_date <= date < self.tpex_second_reform_date:
            df.columns = [DataUtils.standardize_column_name(col) for col in df.columns]
            old_col_name: List[str] = list(df.columns)
            new_col_name: List[str] = [
                "stock_id",
                "證券名稱",
                "外資買進股數",
                "外資賣出股數",
                "外資買賣超股數",
                "投信買進股數",
                "投信賣出股數",
                "投信買賣超股數",
                "自營商買賣超股數",
                "自營商買進股數(自行買賣)",
                "自營商賣出股數(自行買賣)",
                "自營商買賣超股數(自行買賣)",
                "自營商買進股數(避險)",
                "自營商賣出股數(避險)",
                "自營商買賣超股數(避險)",
                "三大法人買賣超股數",
            ]
            rename_map = dict(zip(old_col_name, new_col_name))
            df = df.rename(columns=rename_map)
            df.insert(0, "date", date)

        # date >= 第二次格式改制（2018/1/15）
        elif date >= self.tpex_second_reform_date:
            # 因為 df.columns 是 MultiIndex(2層)，所以將其轉為1層
            df.columns = [
                f"{col1}{col2}" if col1 != col2 else col1 for col1, col2 in df.columns
            ]
            df.columns = [DataUtils.standardize_column_name(col) for col in df.columns]
            drop_cols = [
                "外資及陸資(不含外資自營商)買進股數",
                "外資及陸資(不含外資自營商)賣出股數",
                "外資及陸資(不含外資自營商)買賣超股數",
                "外資自營商買進股數",
                "外資自營商賣出股數",
                "外資自營商買賣超股數",
            ]
            df = df.drop(columns=drop_cols)
            df.insert(0, "date", date)

            # Rename df.columns
            old_col_name: List[str] = list(df.columns)
            new_col_name: List[str] = self.chip_cleaned_cols
            rename_map = dict(zip(old_col_name, new_col_name))
            df = df.rename(columns=rename_map)

        aligned_df: pd.DataFrame = df.reindex(
            columns=self.chip_cleaned_cols, fill_value=0
        )
        aligned_df = DataUtils.convert_col_to_numeric(
            aligned_df, exclude_cols=["date", "stock_id", "證券名稱"]
        )
        aligned_df = DataUtils.fill_nan(aligned_df, 0)

        # 根據指定 columns 移除重複的 rows
        aligned_df = DataUtils.remove_duplicate_rows(
            df=aligned_df,
            subset=["date", "stock_id", "證券名稱"],
            keep="first",
        )

        # Save df to csv file
        aligned_df.to_csv(
            self.chip_dir / f"tpex_{TimeUtils.format_date(date)}.csv",
            index=False,
        )

        return aligned_df
