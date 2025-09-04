from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from trader.config import TICK_DOWNLOADS_PATH
from trader.pipeline.cleaners.base import BaseDataCleaner


class StockTickCleaner(BaseDataCleaner):
    """Stock Tick Cleaner (Transform)"""

    def __init__(self):
        super().__init__()

        # Downloads directory Path
        self.tick_dir: Path = TICK_DOWNLOADS_PATH
        self.setup()

    def setup(self) -> None:
        """Set Up the Config of Cleaner"""

        # Create the tick downloads directory
        self.tick_dir.mkdir(parents=True, exist_ok=True)

    def clean_stock_tick(
        self,
        df: pd.DataFrame,
        stock_id: str,
    ) -> Optional[pd.DataFrame]:
        """Clean Stock Tick Data"""

        try:
            df.ts = pd.to_datetime(df.ts)

            new_df: pd.DataFrame = self.format_tick_data(df, stock_id)
            new_df = self.format_time_to_microsec(new_df)

            # Save df to csv file
            new_df.to_csv(
                self.tick_dir / f"{stock_id}.csv",
                index=False,
            )
            logger.info(f"Saved {stock_id}.csv to {TICK_DOWNLOADS_PATH}")
            return new_df

        except Exception as e:
            logger.error(
                f"Error processing or saving tick data for stock {stock_id} | {e}"
            )
            return None

    def format_tick_data(
        self,
        df: pd.DataFrame,
        stock_id: str,
    ) -> pd.DataFrame:
        """統一 tick data 的格式"""

        df.rename(columns={"ts": "time"}, inplace=True)
        df["stock_id"] = stock_id
        new_columns_order: List[str] = [
            "stock_id",
            "time",
            "close",
            "volume",
            "bid_price",
            "bid_volume",
            "ask_price",
            "ask_volume",
            "tick_type",
        ]
        df = df[new_columns_order]

        return df

    def format_time_to_microsec(self, df: pd.DataFrame) -> pd.DataFrame:
        """將 tick dataframe 時間格式格式化至微秒（才能存進 dolphinDB）"""

        # 若 time 欄位沒有精確到微秒則格式化
        if not df["time"].astype(str).str.match(r".*\.\d{6}$").all():
            # 將 'time' 欄位轉換為 datetime 格式，並補足到微秒，同時加上年月日
            df["time"] = pd.to_datetime(df["time"], errors="coerce").dt.strftime(
                "%Y-%m-%d %H:%M:%S.%f"
            )

        return df
