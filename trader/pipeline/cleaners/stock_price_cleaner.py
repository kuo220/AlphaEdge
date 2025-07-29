import datetime
import pandas as pd
from pathlib import Path

from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.utils.data_utils import DataUtils
from trader.utils import TimeUtils
from trader.config import PRICE_DOWNLOADS_PATH


class StockPriceCleaner(BaseDataCleaner):
    """Stock Price Cleaner (Transform)"""

    def __init__(self):
        super().__init__()

        # TPEX Price Table Change Date
        self.tpex_table_change_date: datetime.date = datetime.date(2020, 4, 30)

        # Downloads directory Path
        self.price_dir: Path = PRICE_DOWNLOADS_PATH
        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Cleaner"""

        # Generate downloads directory
        self.price_dir.mkdir(parents=True, exist_ok=True)

    def clean_twse_price(
        self,
        df: pd.DataFrame,
        date: datetime.date,
    ) -> pd.DataFrame:
        """Clean TWSE Stock Price Data"""
        """
        TWSE 網站提供資料日期：
        1. 2004/2/11 ~ present
        """

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(0)

        df: pd.DataFrame = (
            df.drop(columns=["漲跌(+/-)"])
            .rename(columns={"證券代號": "stock_id"})
            .astype(str)
            .pipe(
                DataUtils.convert_col_to_numeric,
                exclude_cols=["date", "stock_id", "證券名稱"],
            )
        )
        df.insert(0, "date", date)
        DataUtils.move_col(df, "成交股數", "漲跌價差")
        DataUtils.move_col(df, "成交金額", "成交股數")
        DataUtils.move_col(df, "成交筆數", "成交金額")

        df.to_csv(
            self.price_dir / f"twse_{TimeUtils.format_date(date)}.csv",
            index=False,
        )

        return df

    def clean_tpex_price(
        self,
        df: pd.DataFrame,
        date: datetime.date,
    ) -> pd.DataFrame:
        """Clean TPEX Stock Price Data"""
        """
        1. 上櫃資料從 96/7/2 以後才提供
        2. 從 109/4/30 開始後 csv 檔的 column 不一樣
        """

        if isinstance(df.columns, pd.MultiIndex):
            df.columns = df.columns.droplevel(0)

        df: pd.DataFrame = df.drop(
            columns=["發行股數", "次日漲停價", "次日跌停價"]
        ).astype(str)
        df.insert(0, "date", date)

        if date >= self.tpex_table_change_date:
            df.columns = [
                "date",
                "stock_id",
                "證券名稱",
                "收盤價",
                "漲跌價差",
                "開盤價",
                "最高價",
                "最低價",
                "成交股數",
                "成交金額",
                "成交筆數",
                "最後揭示買價",
                "最後揭示買量",
                "最後揭示賣價",
                "最後揭示賣量",
            ]
        else:
            df.columns = [
                "date",
                "stock_id",
                "證券名稱",
                "收盤價",
                "漲跌價差",
                "開盤價",
                "最高價",
                "最低價",
                "成交股數",
                "成交金額",
                "成交筆數",
                "最後揭示買價",
                "最後揭示賣價",
            ]
        DataUtils.move_col(df, "收盤價", "最低價")
        DataUtils.move_col(df, "漲跌價差", "收盤價")
        df = DataUtils.remove_last_n_rows(df, n_rows = 2)
        df = DataUtils.convert_col_to_numeric(df, ["date", "stock_id", "證券名稱"])

        df.to_csv(
            self.price_dir / f"tpex_{TimeUtils.format_date(date)}.csv",
            index=False,
        )

        return df
