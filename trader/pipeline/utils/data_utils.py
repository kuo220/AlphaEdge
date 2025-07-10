import datetime
from typing import List, Union
import pandas as pd
from dateutil.rrule import DAILY, MONTHLY, rrule


class DataUtils:
    """ Data Tools """

    @staticmethod
    def move_col(df: pd.DataFrame, col_name: str, ref_col_name: str) -> None:
        """ 移動 columns 位置：將 col_name 整個 column 移到 ref_col_name 後方 """

        col_data: pd.Series = df.pop(col_name)
        df.insert(df.columns.get_loc(ref_col_name) + 1, col_name, col_data)


    @staticmethod
    def remove_redundant_col(df: pd.DataFrame, col_name: str) -> pd.DataFrame:
        """ 刪除 DataFrame 中指定欄位後面的所有欄位 """

        if col_name in df.columns:
            last_col_loc: int = df.columns.get_loc(col_name)
            df = df.iloc[:, :last_col_loc + 1]
        return df


    @staticmethod
    def convert_col_to_numeric(df: pd.DataFrame, exclude_cols: List[str]) -> pd.DataFrame:
        """ 將 exclude_cols 以外的 columns 資料都轉為數字型態（int or float） """

        for col in df.columns:
            if col not in exclude_cols:
                df[col] = pd.to_numeric(df[col], errors='coerce')


    @staticmethod
    def convert_to_roc_year(year: Union[int, str]) -> str:
        """ 將西元年轉換成民國年 """

        try:
            year_int = int(year)
            if year_int < 1912:
                raise ValueError("民國元年從 1912 年開始，請輸入有效的西元年份")
            return str(year_int - 1911)
        except (ValueError, TypeError):
            raise ValueError(f"無效的年份輸入：{year}")


    @staticmethod
    def pad2(n: Union[int, str]) -> str:
        """ 將數字補足為兩位數字字串 """
        return str(n).zfill(2)


    @staticmethod
    def fill_nan(df: pd.DataFrame, value: int=0) -> pd.DataFrame:
        """ 檢查 DataFrame 是否有 NaN 值，若有則將所有 NaN 值填補為指定值 """

        if df.isnull().values.any():
            df.fillna(value, inplace=True)
        return df


    @staticmethod
    def generate_date_range(start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
        """ 產生從 start_date 到 end_date 的每日日期清單 """
        return [dt.date() for dt in rrule(DAILY, dtstart=start_date, until=end_date)]


    @staticmethod
    def generate_month_range(start_date: datetime.date, end_date: datetime.date) -> List[datetime.date]:
        """ 產生從 start_date 到 end_date 的每月清單（取每月的起始日） """
        return [dt.date() for dt in rrule(MONTHLY, dtstart=start_date, until=end_date)]


    @staticmethod
    def format_date(date: datetime.date, sep: str="") -> str:
        """ Format date as 'YYYY{sep}MM{sep}DD' """
        return date.strftime(f"%Y{sep}%m{sep}%d")