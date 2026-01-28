from pathlib import Path
from typing import List, Optional

import pandas as pd
from loguru import logger

from trader.config import FINMIND_DOWNLOADS_PATH
from trader.pipeline.cleaners.base import BaseDataCleaner
from trader.pipeline.utils import FileEncoding, FinMindDataType


class FinMindCleaner(BaseDataCleaner):
    """FinMind Cleaner (Transform)

    由於 FinMind API 回傳的資料已經是結構化的，此 Cleaner 主要負責：
    1. 基本資料驗證（檢查空值、必要欄位等）
    2. 將清洗後的資料存入 CSV 檔案
    3. 返回清洗後的 DataFrame
    """

    def __init__(self):
        super().__init__()
        # Downloads directory Path
        self.finmind_dir: Path = FINMIND_DOWNLOADS_PATH
        self.setup()

    def setup(self, *args, **kwargs) -> None:
        """Set Up the Config of Cleaner"""
        # Generate downloads directory
        self.finmind_dir.mkdir(parents=True, exist_ok=True)

    def clean_stock_info(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        清洗台股總覽資料 (TaiwanStockInfo)

        參數:
            df: pd.DataFrame - 從 crawler 取得的原始資料

        回傳值:
            pd.DataFrame 或 None（如果資料為空或驗證失敗）
        """
        if df is None or df.empty:
            logger.warning("Stock info data is empty")
            return None

        # 基本驗證：檢查必要欄位
        required_columns: List[str] = ["stock_id", "stock_name"]
        missing_columns: List[str] = [
            col for col in required_columns if col not in df.columns
        ]
        if missing_columns:
            logger.error(
                f"Missing required columns in stock info data: {missing_columns}"
            )
            return None

        # 移除重複資料
        df = df.drop_duplicates(subset=["stock_id"], keep="first")

        # 存入 CSV 檔案到各自的資料夾
        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.STOCK_INFO.value.lower()
        )
        data_type_dir.mkdir(parents=True, exist_ok=True)
        csv_path: Path = data_type_dir / "taiwan_stock_info.csv"
        df.to_csv(csv_path, index=False, encoding=FileEncoding.UTF8_SIG.value)
        logger.info(f"Saved stock info data to {csv_path} ({len(df)} rows)")

        return df

    def clean_stock_info_with_warrant(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        清洗台股總覽(含權證)資料 (TaiwanStockInfoWithWarrant)

        參數:
            df: pd.DataFrame - 從 crawler 取得的原始資料

        回傳值:
            pd.DataFrame 或 None（如果資料為空或驗證失敗）
        """
        if df is None or df.empty:
            logger.warning("Stock info with warrant data is empty")
            return None

        # 基本驗證：檢查必要欄位
        required_columns: List[str] = ["stock_id", "stock_name"]
        missing_columns: List[str] = [
            col for col in required_columns if col not in df.columns
        ]
        if missing_columns:
            logger.error(
                f"Missing required columns in stock info data: {missing_columns}"
            )
            return None

        # 移除重複資料
        df = df.drop_duplicates(subset=["stock_id"], keep="first")

        # 存入 CSV 檔案到各自的資料夾
        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.STOCK_INFO_WITH_WARRANT.value.lower()
        )
        data_type_dir.mkdir(parents=True, exist_ok=True)
        csv_path: Path = data_type_dir / "taiwan_stock_info_with_warrant.csv"
        df.to_csv(csv_path, index=False, encoding=FileEncoding.UTF8_SIG.value)
        logger.info(
            f"Saved stock info with warrant data to {csv_path} ({len(df)} rows)"
        )

        return df

    def clean_broker_info(self, df: pd.DataFrame) -> Optional[pd.DataFrame]:
        """
        清洗證券商資訊表資料 (TaiwanSecuritiesTraderInfo)

        參數:
            df: pd.DataFrame - 從 crawler 取得的原始資料

        回傳值:
            pd.DataFrame 或 None（如果資料為空或驗證失敗）
        """
        if df is None or df.empty:
            logger.warning("Broker info data is empty")
            return None

        # 基本驗證：檢查必要欄位
        required_columns: List[str] = ["securities_trader_id", "securities_trader"]
        missing_columns: List[str] = [
            col for col in required_columns if col not in df.columns
        ]
        if missing_columns:
            logger.error(
                f"Missing required columns in broker info data: {missing_columns}"
            )
            return None

        # 移除重複資料
        df = df.drop_duplicates(subset=["securities_trader_id"], keep="first")

        # 存入 CSV 檔案到各自的資料夾
        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.BROKER_INFO.value.lower()
        )
        data_type_dir.mkdir(parents=True, exist_ok=True)
        csv_path: Path = data_type_dir / "taiwan_securities_trader_info.csv"
        df.to_csv(csv_path, index=False, encoding=FileEncoding.UTF8_SIG.value)
        logger.info(f"Saved broker info data to {csv_path} ({len(df)} rows)")

        return df

    def clean_broker_trading_daily_report(
        self, df: pd.DataFrame
    ) -> Optional[pd.DataFrame]:
        """
        清洗當日券商分點統計表資料 (TaiwanStockTradingDailyReportSecIdAgg)

        參數:
            df: pd.DataFrame - 從 crawler 取得的原始資料

        回傳值:
            pd.DataFrame 或 None（如果資料為空或驗證失敗）
        """
        if df is None or df.empty:
            logger.warning("Broker trading daily report data is empty")
            return None

        # 基本驗證：檢查必要欄位
        required_columns: List[str] = [
            "stock_id",
            "date",
            "securities_trader_id",
            "buy_volume",
            "sell_volume",
        ]
        missing_columns: List[str] = [
            col for col in required_columns if col not in df.columns
        ]
        if missing_columns:
            logger.error(
                f"Missing required columns in broker trading daily report data: {missing_columns}"
            )
            return None

        # 移除重複資料（以 stock_id, date, securities_trader_id 為唯一鍵）
        df = df.drop_duplicates(
            subset=["stock_id", "date", "securities_trader_id"], keep="first"
        )

        # 存入 CSV 檔案到各自的資料夾
        # 結構：broker_trading/{broker_id}/{stock_id}.csv
        data_type_dir: Path = (
            self.finmind_dir / FinMindDataType.BROKER_TRADING.value.lower()
        )
        data_type_dir.mkdir(parents=True, exist_ok=True)

        # 按照 securities_trader_id 和 stock_id 分組，為每個組合創建一個 CSV 檔案
        saved_files: List[str] = []
        for (securities_trader_id, stock_id), group_df in df.groupby(
            ["securities_trader_id", "stock_id"]
        ):
            # 創建 broker_id 資料夾
            broker_dir: Path = data_type_dir / str(securities_trader_id)
            broker_dir.mkdir(parents=True, exist_ok=True)

            # CSV 檔案路徑：{broker_id}/{stock_id}.csv
            csv_path: Path = broker_dir / f"{stock_id}.csv"

            # 如果檔案已存在，讀取現有資料並合併（使用追加模式避免覆蓋）
            if csv_path.exists():
                try:
                    existing_df: pd.DataFrame = pd.read_csv(
                        csv_path, encoding=FileEncoding.UTF8_SIG.value
                    )
                    # 合併資料
                    combined_df: pd.DataFrame = pd.concat(
                        [existing_df, group_df], ignore_index=True
                    )
                    # 再次去重（以 stock_id, date, securities_trader_id 為唯一鍵）
                    combined_df: pd.DataFrame = combined_df.drop_duplicates(
                        subset=["stock_id", "date", "securities_trader_id"],
                        keep="first",
                    )
                    group_df: pd.DataFrame = combined_df
                    logger.debug(
                        f"Merged existing data for broker_id={securities_trader_id}, "
                        f"stock_id={stock_id}. Total rows: {len(group_df)} "
                        f"(added {len(group_df) - len(existing_df)} new rows)"
                    )
                except Exception as e:
                    logger.warning(
                        f"Failed to read existing CSV file {csv_path}: {e}. "
                        f"Will overwrite file."
                    )

            # 寫入 CSV 檔案
            group_df.to_csv(csv_path, index=False, encoding=FileEncoding.UTF8_SIG.value)
            saved_files.append(f"{securities_trader_id}/{stock_id}.csv")
            logger.info(
                f"Saved broker trading daily report data to {csv_path} "
                f"(broker_id={securities_trader_id}, stock_id={stock_id}, {len(group_df)} rows)"
            )

        logger.info(f"Saved {len(saved_files)} broker trading daily report files")

        return df
